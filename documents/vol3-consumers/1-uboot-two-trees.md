---
title: "U-Boot 的两棵树怎么分清,control FDT 又从哪儿来?"
volume: 3
chapter: 8
section: 1
order: 1
description: "U-Boot 的源码里两棵树各有官名与指针:control FDT 服务它自己,住在 gd->fdt_blob,working FDT 是 fdt 命令搭手、准备交给操作系统的那棵,导读里写进 chosen 的改动也各自归位,fdtdec_setup 再在启动头几步给 gd->fdt_blob 定来源,bloblist、OF_SEPARATE 一类选项按次序挑,编 dtb 的活是内核同源的 dts 加按顺序查找的 -u-boot.dtsi 增补,ROCK Pi 4 的文件链与 uart2 节点的增补原文也摆上桌"
status: draft
---

# U-Boot 的两棵树怎么分清,control FDT 又从哪儿来?

导读收尾的那篇留过一句话:“这两棵树在第三卷的前两章会分清,咱们到时候追踪同一个节点在两处的不同命运”。承诺到兑现的日子了。今天咱们把两棵树的身份、名字和来路分清,咱们再挑一个真实的串口节点,追着它走完 U-Boot 自家那棵树的消费全程。交给 Linux 的那一棵,它的命运咱们留到下一章去追,下一章的题目是“传给 Linux 的 DTB 是哪一份”。

咱们从这一章进入源码走读的地界。全卷锁定的版本是 U-Boot v2026.10 与 Linux v7.2.9,本章引用的每一处函数与调用链,都是我在两份源码里亲眼核对过的,源码拉在本机的 /tmp/vol3ch8 目录下,咱们不在仓库里存任何拷贝。你照着同样的地址拉下来,看到的行号跟咱们引用的对得上。

整章的故事从名字讲起。两棵树的身份、名字与来路是本篇的活,串口节点的消费全程、跟 Linux 的对照、动手编一棵标本树,咱们分成几篇接着讲。

## 名字分清:control FDT 与 working FDT

两棵树的名字不是咱们随口起的,U-Boot 的源码和文档里它们就是这么叫的。咱们请两处原话出场。

咱们头一处要请的原话住在 ofnode 接口的头文件里,那是 Driver Model 读树的门面,它对默认那棵树的注释写得直白:

```c
/* include/dm/ofnode.h:347 */
/**
 * oftree_default() - Returns the default device tree (U-Boot's control FDT)
 * ...
 */
```

服务 U-Boot 自身配置的那一棵,它的官名就是 control FDT,咱们把它译作控制用 FDT。它的正文身份是一个指针,住在 U-Boot 的全局数据结构里,它的注释也写得一样不含糊:

```c
/* include/asm-generic/global_data.h:50 */
	/**
	 * @fdt_blob: U-Boot's own device tree, NULL if none
	 */
	const void *fdt_blob;
```

咱们在代码里说的 `gd->fdt_blob`,说的就是它。gd 是 U-Boot 的全局数据结构,global data 的缩写就是它,各个模块在启动的全程都在读写它,哪个串口当前在用、树躺在内存的哪里,它都记了下来。

另一处原话来自 `fdt` 命令的实现。导读里咱们在命令行里摸过的那套 `fdt` 命令,它操作的那棵树在源码里有自己独立的指针:

```c
/* cmd/fdt.c:35 */
/*
 * The working_fdt points to our working flattened device tree.
 */
struct fdt_header *working_fdt;
```

这一棵的官名是 working FDT,咱们把它理解成工作台上那棵:咱们用 `fdt addr` 把它指到一块内存,之后的 `fdt ls`、`fdt set` 都对它下手。源码里还有个会打印动静的函数,`fdt addr` 走到了最后就会调它,打印的内容是 `Working FDT set to ...`,名字跟变量两边对上了。

导读里讲过的那几桩修改,写进 `chosen` 的 `bootargs` 与按实测修正的 `memory`,全都落在了 working FDT 上。那篇里强调过的事你现在能说准了:改移交出去的树,改的并不是 U-Boot 自己的家底,它的家底在 control FDT 里,两边各有各的指针。两棵树的来源常常是同一份描述,重叠的内容也不少,不过“谁在读、谁在改”的分工,从名字上就分开了。

名字分清了,两棵树各有各的指针、各有各的读者。control FDT 的来路还悬着:它的地址是谁定的,dtb 又是从哪些源文件编出来的,这些问题的答案,咱们往下翻。

地址是谁定的,树的内容又是从哪些源文件编出来的,咱们顺着 U-Boot 的启动流程与构建流水线各走一遍。版本还是前文锁定的 U-Boot v2026.10,咱们引的每一处行号,你在同样的地址都核对得上。

## 地址的敲定:启动头几步里的一次 setup

control FDT 在内存里的地址是谁定的?咱们从启动流程的头几步追。U-Boot 的启动代码把一份按次序排好的初始化调用清单挨个执行,`fdtdec_setup` 就排在清单里很靠前的位置:

```c
/* common/board_f.c:917 起,initcall_run_f() 的开头,有删节 */
static void initcall_run_f(void)
{
	/*
	 * Please do not add logic to this function (variables, if (), etc.).
	 * For simplicity it should remain an ordered list of function calls.
	 */
	INITCALL(setup_mon_len);
	INITCALL(initf_malloc);
#if CONFIG_IS_ENABLED(OF_CONTROL)
	INITCALL(fdtdec_setup);
#endif
	...
	INITCALL(initf_dm);
	...
	INITCALL(init_baud_rate);	/* initialze baudrate settings */
	INITCALL(serial_init);		/* serial communications setup */
	INITCALL(console_init_f);	/* stage 1 init of console */
	INITCALL(display_options);	/* say that we are here */
```

清单里的两个名字,咱们要各追一遍。`fdtdec_setup` 排在很靠前的位置,它负责把 control FDT 的地址定下来。`display_options` 排在咱们节选的末尾,它管打 U-Boot 的横幅,横幅的出口是串口,所以顺序也只能这样。从 setup 到横幅的路上,隔着的是 Driver Model 和串口初始化,咱们按执行顺序走过去。

`fdtdec_setup` 的本体住在 lib/fdtdec.c 里,它按一套固定的次序把 `gd->fdt_blob` 指向来源,咱们看删节后的主干:

```c
/* lib/fdtdec.c:1821 起,有删节 */
int fdtdec_setup(void)
{
	int ret = -ENOENT;

	if (CONFIG_IS_ENABLED(BLOBLIST) && (xpl_phase() > PHASE_TPL)) {
		...
			gd->fdt_blob = bloblist_find(BLOBLISTT_CONTROL_FDT, 0);
		...
	}

	/* Otherwise, the devicetree is typically appended to U-Boot */
	if (ret) {
		if (IS_ENABLED(CONFIG_OF_SEPARATE)) {
			gd->fdt_blob = fdt_find_separate();
			gd->fdt_src = FDTSRC_SEPARATE;
		} else { /* embed dtb in ELF file for testing / development */
			fdtdec_setup_embed();
		}
	}

	/* Allow the board to override the fdt address. */
	if (IS_ENABLED(CONFIG_OF_BOARD)) {
		...
	}

	/* Allow the early environment to override the fdt address */
	...
		addr = env_get_hex("fdtcontroladdr", 0);
	...
	ret = fdtdec_prepare_fdt(gd->fdt_blob);
	...
}
```

咱们数一数它的来源,常见的有这么几种:

- 前一级阶段通过 bloblist(阶段之间传东西用的列表)把树递过来
- dtb 直接接在 U-Boot 二进制的后面,这是 OF_SEPARATE,最常见的常规做法
- dtb 编进 ELF 文件里,只图调试方便,这是 OF_EMBED
- 板级代码在现场指认地址,这是 OF_BOARD
- 环境变量 `fdtcontroladdr` 在最后压轴覆盖

这些来源在 include/fdtdec.h 里立成了一张枚举表,咱们去看 `FDTSRC_SEPARATE` 的注释,它写明的正是常规做法。函数末尾的 `fdtdec_prepare_fdt` 做的是核对头部一类的体检,树本身的内容从头到尾没有变过。

## 树是谁编的:同源的 dts 与 U-Boot 的增补

那 dtb 在构建的时候又是从哪儿编出来的?流水线你在“构建系统实际上做了什么”那章里已经认过了,归拢文本的活归 cpp,编二进制的活归 dtc。v2026.10 的 U-Boot 把与内核共享的板级 dts 放在 dts/upstream/src/ 下,内容跟内核是同源的。U-Boot 自己的增补写在另一处,构建会按文档写明的顺序自动找一份 `-u-boot.dtsi` 追加进树里:

```text
/* doc/develop/devicetree/control.rst,Adding tweaks for U-Boot 一节 */
   <orig_filename>-u-boot.dtsi
   <CONFIG_SYS_SOC>-u-boot.dtsi
   <CONFIG_SYS_CPU>-u-boot.dtsi
   <CONFIG_SYS_VENDOR>-u-boot.dtsi
   u-boot.dtsi
```

查找的顺序从板名往泛里走,命中了一份就收手,命中的文件里还可以再 `#include` 别的,于是能搭出共享的层级。咱们本章的标本板是 Radxa ROCK Pi 4,它的 defconfig 里写着 `CONFIG_DEFAULT_DEVICE_TREE="rockchip/rk3399-rock-pi-4a"`,咱们把它的文件链摆出来:

- `dts/upstream/src/arm64/rockchip/rk3399-rock-pi-4a.dts` 是板级入口,内容与内核同源
- 它包含 `rk3399-rock-pi-4.dtsi`,`chosen` 的 `stdout-path` 就写在这里,再往下是 SoC 级的 `rk3399.dtsi`,串口一类的 SoC 外设又拆在它包含的 `rk3399-base.dtsi` 里
- `arch/arm/dts/rk3399-rock-pi-4a-u-boot.dtsi` 按上面的顺序头一个命中,它层层包含到 `rk3399-u-boot.dtsi`

`rk3399-base.dtsi` 里的串口节点与 `rk3399-u-boot.dtsi` 里的增补,是咱们下文追踪的主角,咱们把原文摆上桌:

```dts
/* dts/upstream/src/arm64/rockchip/rk3399-base.dtsi:818,有删节 */
	uart2: serial@ff1a0000 {
		compatible = "rockchip,rk3399-uart", "snps,dw-apb-uart";
		reg = <0x0 0xff1a0000 0x0 0x100>;
		reg-shift = <2>;
		reg-io-width = <4>;
		status = "disabled";
	};
```

```dts
/* arch/arm/dts/rk3399-u-boot.dtsi:148 */
&uart2 {
	bootph-all;
	clock-frequency = <24000000>;
};
```

咱们看的是同一个节点:内核同源的文件给了它两个 compatible 字符串,板级的 dtsi 又把它的 `status` 改成 `okay`,U-Boot 的增补再补上 `bootph-all` 和 `clock-frequency`。`bootph-all` 是设备树规范定下的启动阶段标记,标记的意思是任何阶段都可能用到这个节点。这些增补进的是同一棵 control FDT,U-Boot 与内核的“同源不同用”,具体的样子就落在这里。

control FDT 的地址与内容到这里都有了着落,地址的敲定归 `fdtdec_setup`,内容的来路是内核同源的 dts 加 `-u-boot.dtsi` 增补。咱们摆上桌的 uart2 节点还没人消费,树进了 Driver Model 之后的日子,咱们到下一篇里接着追。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. control FDT 与 working FDT 各自服务谁?它们在源码里分别住在哪个变量上?
2. 导读里写进 `chosen` 的 `bootargs` 与按实测修正的 `memory`,落在哪一棵树上?为什么这些改动动不到 U-Boot 的家底?
3. `fdtdec_setup` 给 `gd->fdt_blob` 定来源时,最常见的 OF_SEPARATE 是什么做法?环境变量 `fdtcontroladdr` 在挑选的次序里排在什么位置?
4. 咱们标本板的 control FDT 由哪些文件拼成?`-u-boot.dtsi` 的查找顺序从哪儿往哪儿走?

<details>
<summary>参考答案(想好再展开)</summary>

1. control FDT 服务 U-Boot 自身的配置与驱动,住在 `gd->fdt_blob`。working FDT 是 `fdt` 命令操作、准备交给操作系统的那棵,住在 cmd/fdt.c 的 `working_fdt` 变量上。
2. 都落在 working FDT 上。U-Boot 的家底在 control FDT 里,两边各有各的指针,改移交出去的树,动不到它自己的家底。
3. OF_SEPARATE 把编好的 dtb 接在 U-Boot 二进制之后,运行时由 `fdt_find_separate` 找到,这是最常见的常规做法。`fdtcontroladdr` 排在最后压轴,它能覆盖前面的来源。
4. 板级入口是 `dts/upstream/src/arm64/rockchip/rk3399-rock-pi-4a.dts`,它包含 `rk3399-rock-pi-4.dtsi`,再往下是 SoC 级的 `rk3399.dtsi`,串口一类的 SoC 外设拆在它包含的 `rk3399-base.dtsi` 里。增补按顺序头一个命中的是 `arch/arm/dts/rk3399-rock-pi-4a-u-boot.dtsi`,它层层包含到 `rk3399-u-boot.dtsi`。查找顺序从板名往泛里走,命中了一份就收手。

</details>

## 延伸阅读

本篇的机制叙述与源码引用,咱们在官方文档里都找到了正本:

- [U-Boot: fdt 命令](https://docs.u-boot.org/en/latest/usage/cmd/fdt.html):working FDT 的命令行入口,`fdt addr` 与打印的那句 `Working FDT set to` 都能在这里查到。
- [U-Boot: Devicetree Control](https://docs.u-boot.org/en/latest/develop/devicetree/control.html):control FDT 的构建、OF_SEPARATE 等来源选项、`-u-boot.dtsi` 的查找顺序,本篇多处引用的官方底本。
