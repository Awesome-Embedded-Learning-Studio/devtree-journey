---
title: "Linux 何时读取 DTB?"
volume: 3
chapter: 10
section: 1
order: 6
description: "控制权跳进内核入口之后,树的首地址躺进 __fdt_pointer 与 __atags_pointer 两个全局变量,进了 start_kernel 读树的活全交给 setup_arch,arm64 拿 early_fixmap_init 立好的固定映射区把 DTB 的物理地址映射进去,fixmap_remap_fdt 查过 header 的魔数与总长,early scan 随后在平坦的树上取走 chosen 的 bootargs 与 rng-seed、memory 的内存区间,内存进了 memblock,arm32 另起一个入口,of_flat_dt_match_machine 拿根上的 compatible 挑 machine_desc,之后汇进与 arm64 一字不差的扫描,没有 DTB 时 setup_machine_tags 接 ATAGS 兜底,别的架构咱们只认核对过的,内核读树读了两遍的答案也提前亮出来"
status: draft
---

# 内核醒来的哪一步,读到了设备树?

## 从寄存器到全局变量,树的地址一直有人保管

上一章的结尾处,控制权刚跳进了内核入口:U-Boot 改好的 working FDT 躺在内存里,它的首地址被装进了寄存器,ARM32 装进的是 r2,ARM64 装进的是 x0。树的内容还一眼都没有被读过,咱们这一章就跟着内核走,看它从拿到地址到读出内容分了几步,又在什么时刻动了嘴。

arm64 的入口汇编你在上一章见过开头的 `mov x21, x0`,它后面的去向写在 `arch/arm64/kernel/head.S` 的 `__primary_switched` 里。咱们把关键的两行抄过来,省略号是咱们省的:

```asm
	str_l	x21, __fdt_pointer, x5		// Save FDT pointer
	...
	bl	start_kernel
```

x21 里的地址被存进了全局变量 `__fdt_pointer`,紧接着控制权就进了 C 世界的大门 `start_kernel`。arm32 那边是同一个故事的 r2 版,登记的动作落在 `arch/arm/kernel/head-common.S` 的 `__mmap_switched_data` 里,咱们把相关的一行抄来:

```asm
	.long	__atags_pointer			@ r2
```

r2 的值被登进了 `__atags_pointer`。变量名里的 atags 是历史留下的,咱们交代一下它的来历:老式的 ATAGS 传参也走 r2,这个名字就沿用了下来,DTB 与 ATAGS 共用的是同一个保管人。

进了 C 世界,大门就是 `init/main.c` 的 `start_kernel`,咱们抄它开头的几行主干:

```c
	boot_cpu_init();
	page_address_init();
	pr_notice("%s", linux_banner);
	setup_arch(&command_line);
```

打印完内核的横幅,架构相关的活就被整个交给了 `setup_arch`。读树的调用全在 `setup_arch` 里,而这个函数每个体系结构各写各的,所以从这儿开始,路按架构分岔了。咱们把 ARM64 与 ARM32 两条分开走,别的架构咱们放到后面单独交代。

全卷锁定的版本是 U-Boot v2026.10 与 Linux v7.2.9,本章咱们只看 Linux 侧,引到的源码都从 kernel.org 的 v7.2.9 标签拉下来核对过,每段引文都带着它的文件路径。答案咱们也可以提前亮出来:内核读树读了两遍,头一遍只挑启动急用的几样,第二遍才把整棵树立了起来,咱们一步步看。

两条路咱们从 ARM64 走起,它的 `setup_arch` 怎么把地址映射进去,头一遍读又读走了什么。

## ARM64 的路:把地址映射进去,再扫头一遍

咱们进 `arch/arm64/kernel/setup.c` 看 `setup_arch` 的开头,读树的调用就出现在这里:

```c
	early_fixmap_init();
	early_ioremap_init();

	setup_machine_fdt(__fdt_pointer);
```

`__fdt_pointer` 里存的是物理地址,可常规的页表这时候还没铺好,而 `paging_init` 还远远排在后面,内核手头可用的只有 `early_fixmap_init` 刚立好的固定映射区。所以读树的头一步是映射,`setup_machine_fdt` 把物理地址交给了 `fixmap_remap_fdt`,这个函数的实现住在 `arch/arm64/mm/fixmap.c`,咱们看主干:

```c
void *__init fixmap_remap_fdt(phys_addr_t dt_phys, int *size, pgprot_t prot)
{
	const u64 dt_virt_base = __fix_to_virt(FIX_FDT);
	...
	if (!dt_phys || dt_phys % MIN_FDT_ALIGN)
		return NULL;

	dt_phys_base = round_down(dt_phys, PAGE_SIZE);
	offset = dt_phys % PAGE_SIZE;
	dt_virt = (void *)dt_virt_base + offset;

	/* map the first chunk so we can read the size from the header */
	create_mapping_noalloc(dt_phys_base, dt_virt_base, PAGE_SIZE, prot);

	if (fdt_magic(dt_virt) != FDT_MAGIC)
		return NULL;

	*size = fdt_totalsize(dt_virt);
	if (*size > MAX_FDT_SIZE)
		return NULL;
	...
}
```

它映射了头一页,读 header 里的魔数与总长,把两样都查了一遍,对不上的话就空手而归。“字节怎样成为可查询的树”那章讲过 header 里的魔数与总长,内核在这儿当了它们的第一个读者。上一章 booting 文档提过的 8 字节对齐与 2MB 上限,执行检查的也是它,`MIN_FDT_ALIGN` 管的是对齐,`MAX_FDT_SIZE` 管的是大小,`setup_machine_fdt` 的报错文案还把两条要求原样复述了一遍:

```c
		pr_crit("\n"
			"Error: invalid device tree blob: PA=%pa, VA=%px, size=%d bytes\n"
			"The dtb must be 8-byte aligned and must not exceed 2 MB in size.\n"
			"\nPlease check your bootloader.\n",
```

映射立稳了之后,`setup_machine_fdt` 的下一件事才是真正的读取,调的是 `early_init_dt_scan(dt_virt, dt_phys)`。内核读树的头一遍就从它开始,咱们进下一节看它读了什么。

## 头一遍读什么:early scan 在平坦的树上取走三样

咱们进 `drivers/of/fdt.c` 看 `early_init_dt_scan`,它的个头小得可怜:

```c
bool __init early_init_dt_scan(void *dt_virt, phys_addr_t dt_phys)
{
	bool status;

	status = early_init_dt_verify(dt_virt, dt_phys);
	if (!status)
		return false;

	early_init_dt_scan_nodes();
	return true;
}
```

`early_init_dt_verify` 干的是检查与登记,咱们看它的主干:

```c
	/* check device tree validity */
	if (fdt_check_header(dt_virt))
		return false;

	/* Setup flat device-tree pointer */
	initial_boot_params = dt_virt;
	initial_boot_params_pa = dt_phys;
	of_fdt_crc32 = crc32_be(~0, initial_boot_params,
				fdt_totalsize(initial_boot_params));

	/* Initialize {size,address}-cells info */
	early_init_dt_scan_root();
```

`initial_boot_params` 从此指在了平坦的 DTB 上,咱们留意它:头一遍扫描的期间谁要读树,都得从它的手里下手。物理地址也同时登记进了 `initial_boot_params_pa`,crc32 顺带算了一份校验和存底,`early_init_dt_scan_root` 读的是根上的 `#address-cells` 与 `#size-cells`,存进了 `dt_root_addr_cells` 与 `dt_root_size_cells`,留给等会的内存扫描去用。

咱们要的清单摆在 `early_init_dt_scan_nodes` 里,三样信息各领到了一个调用,清单末尾另有一条 kexec 交接用的检查,咱们这卷用不上它,认个脸也就够了:

```c
void __init early_init_dt_scan_nodes(void)
{
	int rc;

	/* Retrieve various information from the /chosen node */
	rc = early_init_dt_scan_chosen(boot_command_line);
	if (rc)
		pr_warn("No chosen node found, continuing without\n");

	/* Setup memory, calling early_init_dt_add_memory_arch */
	early_init_dt_scan_memory();

	/* Handle linux,usable-memory-range property */
	early_init_dt_check_for_usable_mem_range();

	/* Handle kexec handover */
	early_init_dt_check_kho();
}
```

咱们从 chosen 看起,上一章 U-Boot 的 `fdt_chosen` 往 `/chosen` 里写了 bootargs,读它的人就在这儿:

```c
	/* Retrieve command line */
	p = of_get_flat_dt_prop(node, "bootargs", &l);
	if (p != NULL && l > 0)
		strscpy(cmdline, p, min(l, COMMAND_LINE_SIZE));
```

命令行被抄进了 `boot_command_line`,arm64 的 `setup_arch` 里随后就有 `parse_early_param` 消费它,启动参数的来路你到这儿就通了。chosen 里还有个值得看的细节:rng-seed 读一遍就被抹掉了:

```c
	rng_seed = of_get_flat_dt_prop(node, "rng-seed", &l);
	if (rng_seed && l > 0) {
		add_bootloader_randomness(rng_seed, l);

		/* try to clear seed so it won't be found. */
		fdt_nop_property(initial_boot_params, node, "rng-seed");
```

种子喂给了内核的随机数池,原地又被 `fdt_nop_property` 改成了 nop 节点,读过的痕迹当场抹掉,后面的读者再看不到它。

memory 的一支是重头,咱们看 `early_init_dt_scan_memory` 的主干:

```c
int __init early_init_dt_scan_memory(void)
{
	int node, found_memory = 0;
	const void *fdt = initial_boot_params;

	fdt_for_each_subnode(node, fdt, 0) {
		const char *type = fdt_stringlist_get(fdt, node,
						      "device_type", 0, NULL);
		...
		/* We are scanning "memory" nodes only */
		if (type == NULL || strcmp(type, "memory") != 0)
			continue;
		...
		reg = of_flat_dt_get_addr_size_prop(node, "linux,usable-memory", &l);
		if (reg == NULL)
			reg = of_flat_dt_get_addr_size_prop(node, "reg", &l);
		...
		for (i = 0; i < l; i++) {
			u64 base, size;

			of_flat_dt_read_addr_size(reg, i, &base, &size);
			...
			early_init_dt_add_memory_arch(base, size);
			...
		}
	}
	return found_memory;
}
```

咱们看它的挑法:只认根的孩子里 `device_type` 为 memory 的节点,取 reg 或 `linux,usable-memory` 的值,折算的活在 v7.2.9 里交给了 `of_flat_dt_read_addr_size`,它按根上两个 cells 的个数,把一串 32 位的 cell 折成 64 位的基址与大小,一对一对地往下送。接收方 `early_init_dt_add_memory_arch` 的末行是:

```c
	memblock_add(base, size);
```

memblock 是内核早期的内存管家,而页表分配器还没接班,启动初期的内存登记与分配全从它手里过。内存进了 memblock,内核才算知道了自己有多少地盘,后面的 `paging_init` 也才有东西可铺。你回头看 arm64 的 `setup_arch`,内存初始化与页表初始化正排在这场扫描的后面,顺序不是白排的。

咱们还得点出这遍读的形态:树从头到尾都是平坦的,`fdt_for_each_subnode` 直接在 DTB 的结构块上走,正是你在“字节怎样成为可查询的树”那章认过的平坦游走。这样的走法开销小、拿得快,不过查询就谈不上了,启动等的就是这几样,够用了。

ARM64 的路到这儿就走完了。ARM32 的入口另起一处,汇进的却是同一场扫描,咱们接着走。

## ARM32 的路:入口另起,汇进同一个扫描

arm32 的 `setup_arch` 住在 `arch/arm/kernel/setup.c`,咱们抄开头一段:

```c
	const struct machine_desc *mdesc = NULL;
	void *atags_vaddr = NULL;

	if (__atags_pointer)
		atags_vaddr = FDT_VIRT_BASE(__atags_pointer);

	setup_processor();
	if (atags_vaddr) {
		mdesc = setup_machine_fdt(atags_vaddr);
		if (mdesc)
			memblock_reserve(__atags_pointer,
					 fdt_totalsize(atags_vaddr));
	}
	if (!mdesc)
		mdesc = setup_machine_tags(atags_vaddr, __machine_arch_type);
```

`FDT_VIRT_BASE` 把物理地址折进早期固定映射的窗口,宏的定义在 `arch/arm/include/asm/memory.h` 里,思路与 arm64 的 fixmap 一致。`setup_machine_fdt` 收到的是换算好的虚拟地址,它的 arm32 版本住在 `arch/arm/kernel/devtree.c`,咱们看:

```c
const struct machine_desc * __init setup_machine_fdt(void *dt_virt)
{
	const struct machine_desc *mdesc, *mdesc_best = NULL;
	...
	if (!dt_virt || !early_init_dt_verify(dt_virt, __pa(dt_virt)))
		return NULL;

	mdesc = of_flat_dt_match_machine(mdesc_best, arch_get_next_mach);
	...
	early_init_dt_scan_nodes();
```

verify 走的是同一个,可中间多了一道 arm32 自家的活,`of_flat_dt_match_machine` 拿根上的 compatible 去机器描述表里挑 `machine_desc`,32 位世界里的板级机制还剩这一口气。挑完了之后 `early_init_dt_scan_nodes` 照旧,chosen 与 memory 的扫描和 arm64 一字不差。而要是根本没有 DTB,兜底的 `setup_machine_tags` 还能接老式的 ATAGS 传参,咱们在上一章的 booti 世界里没走它,这里咱们认个脸就够了。

## 别的架构另有入口,咱们只认核对过的

到这儿咱们把课程的要求立起来:本章写的是 ARM64 与 ARM32 两条具体的路,课程的正本专门提醒过,不把某一条架构路径说成内核的通例。RISC-V、PowerPC、LoongArch 各有自己的 `setup_arch`,读树的时机与函数咱们没有逐个核对,咱们就不替它们写流程。内核共用的只有 `drivers/of/` 里的那一层,入口的走法由各架构自己负责,你读别的资料时留个心眼,把单一架构的路径讲成“内核都这样”的说法,多半是讲过头了。

两条架构的路到这儿都走完了,树这时候还躺在 `initial_boot_params` 的手里。把它立起来的活是第二遍读,下一篇咱们接着看。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. ARM64 与 ARM32 各用哪个寄存器接收树的首地址?地址又被存进了哪个全局变量,存的动作分别写在哪个文件?
2. 变量名 `__atags_pointer` 里的 atags 是怎么来的?DTB 与 ATAGS 的保管人是什么关系?
3. 进了 C 世界之后,读树的调用全在哪个函数里?为什么从它开始,路就按架构分岔了?
4. `fixmap_remap_fdt` 映射了头一页之后,从 header 里查了哪两样?对齐与大小的两条要求,由哪两个宏管着?
5. 内核头一遍读树的时候,树是什么形态的?这一遍取走了哪三样信息,清单写在哪个函数里?
6. rng-seed 被读走之后,下场是什么?
7. memory 节点的 reg 是怎样一步步进到内核早期内存管理里的?把经手的函数按顺序列出来。
8. memblock 在启动初期管的是什么?内存进了它,后面的什么活才有东西可铺?
9. arm32 的 `setup_machine_fdt` 收到的是物理地址还是虚拟地址?换算的宏叫什么,定义住在哪里?
10. verify 与 `early_init_dt_scan_nodes` 之间,arm32 多干了哪道自家的活?挑中的是什么?
11. 要是根本没有 DTB,arm32 谁来兜底?它接的是什么传参?
12. RISC-V、PowerPC、LoongArch 的读树流程,咱们为什么不写?

<details>
<summary>参考答案(想好再展开)</summary>

1. ARM64 用 x0,`arch/arm64/kernel/head.S` 的 `__primary_switched` 把 x21 存进了 `__fdt_pointer`。ARM32 用 r2,`arch/arm/kernel/head-common.S` 的 `__mmap_switched_data` 把它登记成了 `__atags_pointer`。
2. 老式的 ATAGS 传参也走 r2,这个名字就沿用了下来,DTB 与 ATAGS 共用的是同一个保管人。
3. 全在 `setup_arch` 里。这个函数每个体系结构各写各的,ARM64 与 ARM32 两条分开走,别的架构咱们放到后面单独交代。
4. 查的是 header 里的魔数与总长,对不上的话就空手而归。`MIN_FDT_ALIGN` 管的是对齐,`MAX_FDT_SIZE` 管的是大小。
5. 树还是平坦的 DTB,`initial_boot_params` 指着它,一个节点结构都没建。取走的三样是 chosen 里的命令行与 rng-seed、memory 节点里的内存区间、`linux,usable-memory-range` 属性,清单在 `early_init_dt_scan_nodes` 里,清单末尾另有一条 kexec 交接的检查。
6. 种子喂给了内核的随机数池,原地又被 `fdt_nop_property` 改成了 nop 节点,后面的读者再看不到它。
7. `early_init_dt_scan_memory` 找 `device_type` 为 memory 的节点,把 reg 交给 `of_flat_dt_read_addr_size` 按根上的 cells 折出 base 与 size,再交给 `early_init_dt_add_memory_arch`,它的末行调 `memblock_add`,内存区间从此进了 memblock。
8. memblock 是内核早期的内存管家,页表分配器还没接班,启动初期的内存登记与分配全从它手里过。内存进了 memblock,后面的 `paging_init` 才有东西可铺。
9. 收到的是换算好的虚拟地址。`FDT_VIRT_BASE` 把物理地址折进早期固定映射的窗口,宏的定义在 `arch/arm/include/asm/memory.h`,思路与 arm64 的 fixmap 一致。
10. `of_flat_dt_match_machine` 拿根上的 compatible 去机器描述表里挑 `machine_desc`,32 位世界里的板级机制还剩这一口气。
11. `setup_machine_tags` 接老式的 ATAGS 传参,咱们在上一章的 booti 世界里没走它。
12. 它们各有自己的 `setup_arch`,读树的时机与函数咱们没有逐个核对,咱们就不替它们写流程。内核共用的只有 `drivers/of/` 里的那一层,入口的走法由各架构自己负责。

</details>

## 延伸阅读

咱们核对过的文档,入口都给你备好了:

- [Linux: Linux and the Devicetree](https://docs.kernel.org/devicetree/usage-model.html):内核官方的使用模型文档,内核在什么阶段读树、哪些代码消费树,官方的说法在这里。
- [Linux: Booting ARM Linux](https://docs.kernel.org/arch/arm/booting.html) 与 [Booting AArch64 Linux](https://docs.kernel.org/arch/arm64/booting.html):r2 与 x0 约定的正本,上一章引用过,本篇寄存器故事的源头。
- [Linux v7.2.9 的 drivers/of/fdt.c](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/of/fdt.c?h=v7.2.9):early scan 的正本,这一篇头一遍读的引文都出自这里。
- [Linux v7.2.9 的 arch/arm64/kernel/setup.c](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/arch/arm64/kernel/setup.c?h=v7.2.9) 与 [arch/arm/kernel/setup.c](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/arch/arm/kernel/setup.c?h=v7.2.9):两条架构路径的 setup_arch 正本,点进去就能对着看。
