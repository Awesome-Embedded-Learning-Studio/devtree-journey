---
title: "booti 的第三个参数交给了谁,跳进内核之前树又被改了什么?"
volume: 3
chapter: 9
section: 1
order: 4
description: "booti 的第三个参数从命令行进了 cmd/booti.c,树的地址落成 images 的 ft_addr 与 ft_len,再由 set_working_fdt_addr 接进 working FDT,你用过的 fdt print 摸的就是它,跳内核之前 bootm 状态机把活分发到 boot_prep_linux,boot_relocate_fdt 搬运时添 padding,image_setup_libfdt 按调用次序改树,bootargs 写进 /chosen,实测内存改写 /memory,initrd 地址落进 chosen 节点,末了对上 control FDT 从头到尾没被碰过的判定"
status: draft
---

# booti 的第三个参数交给了谁,跳进内核之前树又被改了什么?

“U-Boot 自己也用设备树吗”那章收尾的时候,咱们把两棵树分清了:服务 U-Boot 自己的 control FDT,还有准备交给操作系统的 working FDT。归属分清了,新的疑问跟着就来了:内核真正拿到手的树,跟你编译机上编出来的 dtb 文件,还是同一份字节吗?咱们这一章从头到尾只追 working FDT,咱们把它从启动命令手里一路送到内核入口,交出去之前谁动了它、动了哪里、按什么约定交,咱们都拿源码对出来。

版本的事咱们交代一次,后面再引源码就不重复了:全卷锁定的版本是 U-Boot v2026.10 与 Linux v7.2.9。本章引用的每一处源码,我都从对应版本的官方仓库拉下来逐行核对过,文件路径随文都标了出来,你想自己核对的话,照着路径拉同样的版本就行。

导读的“谁会使用设备树”那篇把引导器的活分成了读取、修改、传递、消费四个环节,当时说好的是只认角色不追代码。现在咱们进了第三卷,修改这个环节的每一笔改动,咱们落到具体函数,传递这个环节的寄存器约定,咱们在 U-Boot 与内核两头的源码里对上。

## booti 的第三个参数,就是树的地址

咱们挑 booti 当主线。它引导的是 ARM Linux 的裸内核镜像 Image,板上最常见的启动命令就是它。bootz 引导的是 zImage,bootm 引导的是 uImage,两者收尾的时候也汇进了同一套 bootm 状态机,咱们认准 booti 往下走,别的命令就不逐个展开了。

命令的样子咱们直接看 U-Boot 手册里的示例:

```text
=> load mmc 0:1 $fdt_addr_r dtb-5.10.0-3-arm64
=> booti $kernel_addr_r $ramdisk_addr_r:$filesize $fdt_addr_r
```

咱们按位置认参数:头一个参数是内核镜像的地址,第二个参数是 initrd 的地址,第三个就是设备树产物在内存里的地址。不想传 initrd 的时候,手册里的第二种写法把第二个参数换成 '-'。咱们看 v2026.10 cmd/booti.c 的 do_booti,它把命令行参数收进了同一个结构体:

```c
	argc--; argv++;

	bootm_init(&bmi);
	if (argc)
		bmi.addr_img = argv[0];
	if (argc > 1)
		bmi.conf_ramdisk = argv[1];
	if (argc > 2)
		bmi.conf_fdt = argv[2];
```

booti 的帮助文本把第三个参数的用途也写得直白,咱们看原文:

```c
	"\tSince booting a Linux kernel requires a flat device-tree, a\n"
	"\tthird argument providing the address of the device-tree blob\n"
	"\tis required. To boot a kernel with a device-tree blob but\n"
	"\twithout an initrd image, use a '-' for the initrd argument.\n"
```

咱们回到 booti_start:内核镜像验完头部、挪到该在的位置之后,它把 ramdisk 与设备树的查找一并递了下去:

```c
	if (bootm_find_images(image_load_addr, bmi->conf_ramdisk, bmi->conf_fdt,
			      relocated_addr, image_size))
		return 1;
```

bootm_find_images 的家在 boot/bootm.c,咱们看它对设备树一段的处理:

```c
	if (CONFIG_IS_ENABLED(OF_LIBFDT)) {
		buf = map_sysmem(img_addr, 0);

		/* find flattened device tree */
		ret = boot_get_fdt(buf, conf_fdt, IH_ARCH_DEFAULT, &images,
				   &images.ft_addr, &images.ft_len);
```

boot_get_fdt 的实现在 boot/image-fdt.c,咱们让它认完地址、验完魔数,它打印的日志是这一行:

```c
		printf("   Booting using the fdt blob at %#08lx\n", fdt_addr);
```

树的位置从此有了正经的住处,咱们跟着记两个名字:images 的 ft_addr 记地址,ft_len 记的是长度。紧接着 bootm_find_images 还做了一件跟上一章直接相关的事:

```c
		if (IS_ENABLED(CONFIG_CMD_FDT))
			set_working_fdt_addr(map_to_sysmem(images.ft_addr));
```

set_working_fdt_addr 的家在 cmd/fdt.c,咱们看它的动作:全局变量 working_fdt 被指了过去,地址还写进了环境变量 fdtaddr:

```c
/*
 * The working_fdt points to our working flattened device tree.
 */
struct fdt_header *working_fdt;
...
void set_working_fdt_addr(ulong addr)
{
	printf("Working FDT set to %lx\n", addr);
	set_working_fdt_addr_quiet(addr);
}
```

上一章你用过的 fdt print、fdt set 这些命令,摸的就是这个 working_fdt。booti 替你把 fdt addr 的活干完了,后面的修改也全都落在它的身上。

地址进了门,身份也定了,可章节开头的疑问还悬着:内核拿到手的树,跟编出来的文件还是同一份字节吗?咱们要回答它,就得看树跳进内核之前被改了什么,改动的次序与每一笔的去处,咱们跟着 bootm 状态机逐笔对出来。

## 跳进内核之前,这棵树被改了什么?

参数收齐了,do_booti 把后续的活打包成一组状态交给 bootm_run_states 分发,咱们关心的修改藏在 BOOTM_STATE_OS_PREP 里:

```c
	states = BOOTM_STATE_MEASURE | BOOTM_STATE_OS_PREP |
		BOOTM_STATE_OS_FAKE_GO | BOOTM_STATE_OS_GO;
	if (IS_ENABLED(CONFIG_SYS_BOOT_RAMDISK_HIGH))
		states |= BOOTM_STATE_RAMDISK;

	ret = bootm_run_states(&bmi, states);
```

bootm_run_states 按镜像的 OS 类型查表,咱们查到的引导函数是 do_bootm_linux,arch/arm/lib/bootm.c 里接应 PREP 状态的代码长这样:

```c
	if (flag & BOOTM_STATE_OS_PREP) {
		boot_prep_linux(images);
		return 0;
	}
```

boot_prep_linux 认的是 FDT 与 ATAGS 两条路,咱们眼下关心的是有树的路:

```c
	if (CONFIG_IS_ENABLED(OF_LIBFDT) && IS_ENABLED(CONFIG_LMB) && images->ft_len) {
		debug("using: FDT\n");
		if (image_setup_linux(images)) {
			panic("FDT creation failed!");
		}
	}
```

咱们再往下走就到了 image_setup_linux。它的家在 boot/image-board.c,咱们把它串起的线摘出来:

```c
	if (CONFIG_IS_ENABLED(OF_LIBFDT))
		boot_fdt_add_mem_rsv_regions(*of_flat_tree);
	...
	if (CONFIG_IS_ENABLED(OF_LIBFDT)) {
		ret = boot_relocate_fdt(of_flat_tree, &of_size);
		if (ret)
			return ret;
	}

	if (CONFIG_IS_ENABLED(OF_LIBFDT) && of_size) {
		ret = image_setup_libfdt(images, *of_flat_tree, true);
		if (ret)
			return ret;
	}
```

搬运的活儿咱们交给同在 boot/image-fdt.c 的 boot_relocate_fdt,它给树额外添了 padding:

```c
	/* position on a 4K boundary before the alloc_current */
	/* Pad the FDT by a specified amount */
	of_len = *of_size + CONFIG_SYS_FDT_PAD;
```

咱们看它为什么添 padding,理由其实很实在:后面的修改要往树里写属性,而属性一多,树就有被撑大的可能,所以得提前留出生长空间,免得写到邻居的地盘上。boot_relocate_fdt 分配新位置的时候按的是 0x1000 对齐,你想让树留在原地不搬,把环境变量 fdt_high 设成 0xffffffff 就可以了,同函数里有对应的分支,不过 v2026.10 在这个分支里还打了一条警告,说树停在原地不一定落在 8 字节的边界上,这样起不来的风险不小,非必要咱们别这么设。你在串口日志里见过的 Loading Device Tree to ...,它的出处就在这个函数里。

真正的修改集中在 image_setup_libfdt,咱们按调用次序走:

```c
	if (fdt_root(blob) < 0) {
		printf("ERROR: root node setup failed\n");
		goto err;
	}
	if (fdt_chosen(blob) < 0) {
		printf("ERROR: /chosen node create failed\n");
		goto err;
	}
	if (arch_fixup_fdt(blob) < 0) {
		printf("ERROR: arch-specific fdt fixup failed\n");
		goto err;
	}
```

后面的调用还有一串,咱们摘要紧的几笔:

```c
	/* Update ethernet nodes */
	fdt_fixup_ethernet(blob);
	...
		fdt_ret = ft_board_setup(blob, gd->bd);
	...
	if (fdt_initrd(blob, *initrd_start, *initrd_end))
		goto err;
	...
	ret = fdt_shrink_to_minimum(blob, 0);
```

清单按次序给咱们列出来:

- fdt_root 把环境变量 serial# 写进根节点的 serial-number。
- fdt_chosen 建立 /chosen 并写入 bootargs,细节咱们马上展开。
- arch_fixup_fdt 按实测内存修正 /memory,ARM 上还捎带 PSCI 一类修正。
- fdt_fixup_ethernet 把 MAC 地址写进网卡节点。
- ft_board_setup 是板级钩子,板卡代码想补什么就在这里补。
- fdt_initrd 把 initrd 的起止地址写进 /chosen。
- fdt_shrink_to_minimum 把改完的树收缩回紧凑的大小。

bootargs 是咱们最关心的一笔。fdt_chosen 的实现在 boot/fdt_support.c,开场找的就是 /chosen,没有的话就现场建一个:

```c
	/* find or create "/chosen" node. */
	nodeoffset = fdt_find_or_add_subnode(fdt, 0, "chosen");
	if (nodeoffset < 0)
		return nodeoffset;
```

bootargs 的来源藏在同一个函数里,咱们看这几行:

```c
	str = board_fdt_chosen_bootargs(fdt_get_property(fdt, nodeoffset,
							 "bootargs", NULL));

	if (str) {
		err = fdt_setprop(fdt, nodeoffset, "bootargs", str,
				  strlen(str) + 1);
```

board_fdt_chosen_bootargs 的默认实现就一行,咱们看原文:

```c
__weak const char *board_fdt_chosen_bootargs(const struct fdt_property *fdt_ba)
{
	return env_get("bootargs");
}
```

所以你在 U-Boot 命令行里改环境变量 bootargs,内核命令行跟着就变了,写入的动作就发生在这里。板子想用自己的逻辑拼命令行,把这个 weak 函数覆写掉就可以了,v2026.10 还给它添了一个参数,把 /chosen 里已有的 bootargs 属性递了进来,覆写的逻辑里想参考旧值,材料也是现成的。fdt_chosen 收尾的时候还会写入 `u-boot,version` 属性,配置开到位的时候连 rng-seed 也会注入,咱们不展开。

咱们再看内存的修正,ARM 上走的是 arch/arm/lib/bootm-fdt.c 里的 arch_fixup_fdt:

```c
	int bank;
	u64 start[CONFIG_NR_DRAM_BANKS];
	u64 size[CONFIG_NR_DRAM_BANKS];

	for (bank = 0; bank < CONFIG_NR_DRAM_BANKS; bank++) {
		start[bank] = gd->dram[bank].start;
		size[bank] = gd->dram[bank].size;
	}
	...
	ret = fdt_fixup_memory_banks(blob, start, size, CONFIG_NR_DRAM_BANKS);
```

咱们追一追数据的来源:gd->dram 数组记录的是实测的内存布局,实测到 512MB 的板子,记录里写的就是 512MB。改产物的活儿归 fdt_fixup_memory_banks,它拿的就是实测值:

```c
	/* find or create "/memory" node. */
	nodeoffset = fdt_find_or_add_subnode(blob, 0, "memory");
	...
	err = fdt_setprop(blob, nodeoffset, "device_type", "memory",
			sizeof("memory"));
	...
	len = fdt_pack_reg(blob, tmp, start, size, banks);

	err = fdt_setprop(blob, nodeoffset, "reg", tmp, len);
```

你编源码的时候 memory 节点写的可能是估计值,内核认的是修正后的实测值。导读里那句话咱们还记得吧,“内存的真实大小要等启动时才量得出来”,落到代码里的就是这里。用了 initrd 的话,咱们还会见到 fdt_initrd,它往 /chosen 写进的就是 `linux,initrd-start` 与 `linux,initrd-end` 两个属性:

```c
	nodeoffset = fdt_find_or_add_subnode(fdt, 0, "chosen");
	...
	err = fdt_setprop_uxx(fdt, nodeoffset, "linux,initrd-start",
			      (uint64_t)initrd_start, is_u64);
	...
	err = fdt_setprop_uxx(fdt, nodeoffset, "linux,initrd-end",
			      (uint64_t)initrd_end, is_u64);
```

## 改的始终是 working FDT

清单走完了,咱们停下来对一对上一章的判断。修改链条里传进传出的 blob,源头就是 images 的 ft_addr,指的就是 working FDT。control FDT 住在哪?include/asm-generic/global_data.h 里 gd->fdt_blob 的注释写得明白:

```c
	/**
	 * @fdt_blob: U-Boot's own device tree, NULL if none
	 */
	const void *fdt_blob;
```

注释说的是 U-Boot 自己的树。两条指针里的一条服务自己,另一条是准备外送的,fixup 的每一笔都落在后者上,control FDT 的字节从头到尾没被碰过半点。“U-Boot 自己也用设备树吗”那章里你见过的判断,现在在源码里有了着落。

咱们再补一个汇合点。image_setup_libfdt 的开头有个钩子:

```c
	if (IS_ENABLED(CONFIG_OF_ENV_SETUP)) {
		const char *fdt_fixup;

		fdt_fixup = env_get("fdt_fixup");
		if (fdt_fixup) {
			set_working_fdt_addr(map_to_sysmem(blob));
			ret = run_command_list(fdt_fixup, -1, 0);
```

开了 CONFIG_OF_ENV_SETUP 的板子上,环境变量 fdt_fixup 里存的命令会在跳内核之前跑一遍。set_working_fdt_addr 把工作树指到了当前这棵上,你在命令行里手敲的 fdt 命令与自动 fixup,就这样汇合在了同一棵树上。

所以咱们交给 Linux 的树,不是编译机上那个文件的原样字节,跟 control FDT 倒是不相干的,它是 working FDT 经历搬运与一串 fixup 之后的成品。

清单与判定到这里都齐了,可源码走读给的毕竟是函数与打印,树在改动前后的真实模样,咱们还一眼都没有见过。手头没有正在启动的板子,咱们照样有办法看上一回,下一篇的活儿交给 fdtoverlay,让它在文件的层面上把同类改动重演一遍。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. booti 命令的第三个参数是什么?只想传内核与设备树、不想传 initrd 的时候,命令行怎么写?
2. boot_get_fdt 认完了树之后,树的位置与长度记在 images 的哪两个成员里?你在命令行里用 fdt print 摸的又是哪棵树?
3. U-Boot 环境变量 bootargs 里的内容,经由哪个函数写进产物的哪个属性?/chosen 节点原本不存在的话会怎样?
4. ARM 上 /memory 节点的 reg 按什么数据修正?负责的函数链叫什么?
5. 对 working FDT 的 fixup 会不会改动 control FDT?两边的指针分别是什么?

<details>
<summary>参考答案(想好再展开)</summary>

1. 第三个参数是设备树产物在内存里的地址。不传 initrd 的时候,第二个参数写 '-' 占位,例如 `booti $kernel_addr_r - $fdt_addr_r`。
2. 位置记在 ft_addr,长度记在 ft_len。fdt print 摸的是 working FDT,set_working_fdt_addr 把全局变量 working_fdt 指了过去,地址还写进了环境变量 fdtaddr。
3. fdt_chosen 调 board_fdt_chosen_bootargs,默认实现返回环境变量 bootargs,再由 fdt_setprop 写进 /chosen 节点的 bootargs 属性。/chosen 不存在的话,fdt_find_or_add_subnode 会现场建一个。
4. 按 gd->dram 数组里记录的实测内存布局修正。链条是 image_setup_libfdt 调 arch_fixup_fdt(arch/arm/lib/bootm-fdt.c),后者调 fdt_fixup_memory_banks 改写 /memory 的 reg。
5. 不会。working FDT 的指针是 images->ft_addr(命令行侧对应 cmd/fdt.c 的 working_fdt),control FDT 的指针是 gd->fdt_blob,fixup 只落在前者上。

</details>

## 延伸阅读

咱们核对过的源码与文档,入口都给你备好了:

- [U-Boot fdt 命令手册](https://docs.u-boot.org/en/latest/usage/cmd/fdt.html):命令行侧查看与修改 working FDT 的正式说明,fdt addr、fdt print、fdt set 的用法在这里。
- [U-Boot v2026.10 的 boot/image-fdt.c](https://github.com/u-boot/u-boot/blob/v2026.10/boot/image-fdt.c):boot_get_fdt 与 image_setup_libfdt 的实现所在,点进去就能对着看了。
- [U-Boot: Devicetree Control](https://docs.u-boot.org/en/latest/develop/devicetree/control.html):control FDT 一侧的机制说明,上一章的主场。
