---
title: "没有板子怎么亲眼看见改动,交接又按什么约定?"
volume: 3
chapter: 9
section: 2
order: 5
description: "拿 dtc 与 fdtoverlay 在文件层面重演 U-Boot 的改动:底树把 memory 写成 256MB 的估计值,两个 overlay 依次补进 bootargs 与 initrd 地址、把 reg 改成 512MB,反编译的 diff 再把每处改动对回 fdt_chosen、fdt_initrd 与 fdt_fixup_memory_banks 的活,交接那一刻按架构分两条线两头核对,ARM32 的 r2 与机器号的老约定,ARM64 的 x0 调用约定,booting 文档的对齐与大小要求跟 boot_relocate_fdt 的 0x1000 对齐咬合,末了看 preserve_boot_args 把 x0 保管起来"
status: draft
---

# 没有板子怎么亲眼看见改动,交接又按什么约定?

上一篇把修改逐笔对到了函数,可咱们看到的终究是源码里的调用与清单。树被改之前的字节、改完之后的字节,你想亲眼比一比的话,手头没有正在启动的板子也不碍事。本篇咱们请 fdtoverlay 出场,把同类改动在文件的层面上重演一遍。

实验的身份咱们说在前面:U-Boot 的修改发生在内存里,接口是 libfdt 的 fdt_setprop 一类调用,直接在 DTB 的字节流上改。咱们手头没有正在启动的板子,就拿 fdtoverlay 在文件的层面上重演同类改动,应用前后咱们各反编译一次,diff 会把改动摆给咱们看。咱们做的算一次模拟,模拟的对象是产物在内存里被改写的动作,并不是 U-Boot 真实的调用路径。overlay 自身的语法与机制是第五卷“怎样在不同阶段叠加修改”那章的主题,咱们用完就回正题。

咱们的工作目录是 /tmp/vol3ch9/lab,用的工具是本机的 dtc 与 fdtoverlay,两者的版本都是 1.8.1。底树里咱们故意让 memory 节点写上 256MB 的保守值,bootargs 的位置则空着,模拟的是编译时只能写估计值的状态:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;
	model = "vol3,ch9-demo";
	compatible = "vol3,ch9-demo";

	memory@40000000 {
		device_type = "memory";
		reg = <0x40000000 0x10000000>;
	};

	chosen {
		stdout-path = "serial@42000000";
	};

	serial@42000000 {
		compatible = "vol3,uart";
		reg = <0x42000000 0x100>;
		status = "okay";
	};
};
```

咱们把改动写进两个 overlay,一个改的是 /chosen,另一个改的是 memory:

```dts
/dts-v1/;
/plugin/;

/ {
	fragment@0 {
		target-path = "/chosen";
		__overlay__ {
			bootargs = "console=ttyS0,115200 root=/dev/mmcblk0p2 rw";
			linux,initrd-start = <0x48000000>;
			linux,initrd-end = <0x48040000>;
		};
	};
};
```

```dts
/dts-v1/;
/plugin/;

/ {
	fragment@1 {
		target-path = "/memory@40000000";
		__overlay__ {
			reg = <0x40000000 0x20000000>;
		};
	};
};
```

咱们把两个 overlay 依次应用,就像 U-Boot 在内存里依次执行的那两笔修改:

```shell
cd /tmp/vol3ch9/lab
dtc -I dts -O dtb -o base.dtb base.dts
dtc -@ -I dts -O dtb -o fixup-chosen.dtbo fixup-chosen.dts
dtc -@ -I dts -O dtb -o fixup-mem.dtbo fixup-mem.dts -Wno-reg_format -Wno-unit_address_vs_reg -Wno-avoid_default_addr_size
/usr/sbin/fdtoverlay -i base.dtb -o step1.dtb fixup-chosen.dtbo
/usr/sbin/fdtoverlay -i step1.dtb -o merged.dtb fixup-mem.dtbo
wc -c base.dtb step1.dtb merged.dtb
```

```output
435 base.dtb
568 step1.dtb
568 merged.dtb
```

三面 -Wno 旗子咱们交代一下:overlay 单独编译的时候,dtc 的检查器看不到底树的 #address-cells,按默认值猜了个 2,reg 的字节数就被判成了错,压掉的是误报。产物对不对的问题,咱们以应用之后的 diff 为准。

字节数的读数里也有信息:头一回应用完了之后,产物从 435 涨到了 568,bootargs 与 initrd 的属性进来了。第二回改的是 reg,新旧值都是一对 32 位的数,长度倒是没有变,字节数也就停在了 568。这样的现象咱们在第一卷就见过,当时的章名是“改一行 DTS,产物发生了什么”,改的是值而不动大小,前提是新旧值的字宽相同。

咱们做反编译与对照:

```shell
dtc -I dtb -O dts base.dtb > base.decompiled.dts
dtc -I dtb -O dts merged.dtb > merged.decompiled.dts
diff base.decompiled.dts merged.decompiled.dts
```

```output
11c11
< 		reg = <0x40000000 0x10000000>;
---
> 		reg = <0x40000000 0x20000000>;
14a15,17
> 		linux,initrd-end = <0x48040000>;
> 		linux,initrd-start = <0x48000000>;
> 		bootargs = "console=ttyS0,115200 root=/dev/mmcblk0p2 rw";
```

diff 报出的不同只有两处,咱们逐个对。memory 的 reg 从 0x10000000 变成 0x20000000,256MB 的估计值被改写成 512MB,对应源码里 fdt_fixup_memory_banks 干的活。chosen 里多出了三个属性,bootargs 对应 fdt_chosen 写的那一笔,两个 `linux,initrd-*` 属性对应的是 fdt_initrd 的活。diff 里没有 stdout-path 的事,可见改动确实只落在了目标属性上。

咱们顺带记一个小观察:属性在节点里的前后次序不带语义,fdtoverlay 落笔的次序跟源文件里的书写次序不一致,内核将来的取值只认属性名,咱们读 diff 也只认名字和值。

字节数的读数、diff 的对照、属性次序的小观察,模拟实验的活到这里收工。树已经在内存里改成了成品,可它还留在 U-Boot 的手里,按什么约定交到内核的门口,咱们接着对。

传递的约定按架构分两条线,咱们两头核对:U-Boot 这头是怎么放的,内核那头又是怎么收的。

## ARM32:r2 装着树的地址

咱们看 U-Boot 侧的代码,位置在 arch/arm/lib/bootm.c 的 boot_jump_linux:

```c
	unsigned long machid = gd->bd->bi_arch_number;
	...
	void (*kernel_entry)(int zero, int arch, uint params);
	unsigned long r2;
	...
	if (CONFIG_IS_ENABLED(OF_LIBFDT) && images->ft_len)
		r2 = (unsigned long)images->ft_addr;
	else
		r2 = gd->bd->bi_boot_params;
	...
		kernel_entry(0, machid, r2);
```

咱们数一数参数:函数指针 kernel_entry 收的是三个参数,r2 装的就是树的地址。分支的另一半是老接口:没编进 FDT 支持的时候,r2 装的是 ATAGS 参数块的地址,走的是设备树普及之前的传参老路。r0 的值固定成 0,r1 装的是机器号,那是更老的板级识别约定,内核的文档里至今还写着它。

咱们再看内核那头,arch/arm/kernel/head.S 开头的注释直接认领:

```c
 * This is normally called from the decompressor code.  The requirements
 * are: MMU = off, D-cache = off, I-cache = dont care, r0 = 0,
 * r1 = machine nr, r2 = atags or dtb pointer.
```

内核文档 Documentation/arch/arm/booting.rst 的口径跟注释一致,咱们摘关键的几行:

```text
  - r0 = 0,
  - r1 = machine type number discovered in (3) above.
  - r2 = physical address of tagged list in system RAM, or
    physical address of device tree block (dtb) in system RAM
```

## ARM64:x0 装着树的地址

ARM64 上 U-Boot 的写法换了个面,咱们看 boot_jump_linux 的函数指针,它把树的地址放在头一个参数:

```c
#ifdef CONFIG_ARM64
static void boot_jump_linux(struct bootm_headers *images, int flag)
{
	void (*kernel_entry)(void *fdt_addr, void *res0, void *res1,
			void *res2);
	kernel_entry = (void (*)(void *fdt_addr, void *res0, void *res1,
				void *res2))images->ep;
```

咱们接着看真正的起跳,它多半要经过异常级别的切换。下面引的是同函数里 AArch64 常走的分支,递出的头一个参数还是它:

```c
		else
			armv8_switch_to_el2((u64)images->ft_addr, 0, 0, 0,
					    images->ep,
					    ES_TO_AARCH64);
```

咱们再请出一处注释,它住在 arch/arm/include/asm/macro.h 的汇编宏注释里,写的是大白话:

```c
 * For loading 32-bit OS, x1 is machine nr and x2 is ftaddr.
 * For loading 64-bit OS, x0 is physical address to the FDT blob.
 * They will be passed to the guest.
```

咱们在 asm/system.h 的函数声明里也能读到同一件事,只是那里换成了逐个参数的写法,64 位 OS 时 args 装的就是 fdt 地址。

C 函数的头一个参数在 AArch64 的调用约定里走 x0,起跳代码递出的正是 working FDT 的地址,你看,落点正好是内核认领的那个寄存器。内核那头的认领写在 arch/arm64/kernel/head.S 的注释里:

```c
 * The requirements are:
 *   MMU = off, D-cache = off, I-cache = on or off,
 *   x0 = physical address to the FDT blob.
```

咱们再看 arm64 的 booting 文档,寄存器表摘出来是这样的:

```text
- Primary CPU general-purpose register settings:

    - x0 = physical address of device tree blob (dtb) in system RAM.
    - x1 = 0 (reserved for future use)
    - x2 = 0 (reserved for future use)
    - x3 = 0 (reserved for future use)
```

同一份文档还提了对齐与大小的要求:dtb 必须落在 8 字节的边界上,大小也有不能超过 2MB 的上限。分配新位置的时候 boot_relocate_fdt 按 0x1000 对齐,8 字节的要求顺带就满足了,你看两头的设计是咬合的。

咱们把两边的信息汇成一张表:

| 架构 | 装树地址的寄存器 | U-Boot 侧出处 | Linux 侧出处 |
|---|---|---|---|
| ARM32 | r2 | arch/arm/lib/bootm.c 的 boot_jump_linux | arch/arm/kernel/head.S 注释与 booting 文档 |
| ARM64 | x0 | arch/arm/lib/bootm.c 与 asm/macro.h 注释 | arch/arm64/kernel/head.S 注释与 booting 文档 |

到这里交接就完成了:working FDT 在内存里改好了,r2 或 x0 里放着它的地址,控制权也跳向了内核入口。可树进内核之后的事,咱们还一步都没追。入口的汇编把寄存器收好保管,arm64 的 preserve_boot_args 头一行就是 `mov x21, x0`,注释写的是 x21=FDT,解析的活留给了后面的代码:

```c
SYM_CODE_START_LOCAL(preserve_boot_args)
	mov	x21, x0				// x21=FDT

	adr_l	x0, boot_args			// record the contents of
	stp	x21, x1, [x0]			// x0 .. x3 at kernel entry
```

内核什么时候真正去读树、读成什么样的结构,这些问题咱们留给下一章的“Linux 何时读取 DTB?”。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. 为什么说咱们做的算一次模拟?它模拟的是哪个动作,又不是哪条路径?
2. overlay 单独编译的时候,三面 -Wno 旗子压掉的是什么?产物对不对又以什么为准?
3. merged.dtb 对 base.dtb 的 diff 报出了哪两处不同?它们分别对应 U-Boot 源码里的哪些活?
4. ARM32 与 ARM64 各用哪个寄存器接收 DTB 地址?U-Boot 侧与内核侧你各能在哪个文件里核对到?
5. arm64 的 booting 文档对 dtb 的对齐与大小提了什么要求?boot_relocate_fdt 分配新位置的时候为什么顺带满足了对齐的要求?

<details>
<summary>参考答案(想好再展开)</summary>

1. U-Boot 的修改发生在内存里,接口是 libfdt 的 fdt_setprop 一类调用,咱们手头没有正在启动的板子,就拿 fdtoverlay 在文件的层面上重演。模拟的是产物在内存里被改写的动作,并不是 U-Boot 真实的调用路径。
2. dtc 的检查器看不到底树的 #address-cells,按默认值猜了个 2,reg 的字节数就被判成了错,压掉的是误报。产物对不对,以应用之后的 diff 为准。
3. memory 的 reg 从 0x10000000 变成 0x20000000,对应 fdt_fixup_memory_banks 干的活。chosen 里多出 bootargs 与两个 `linux,initrd-*` 属性,分别对应 fdt_chosen 与 fdt_initrd 的活。
4. ARM32 用 r2,ARM64 用 x0。U-Boot 侧都在 arch/arm/lib/bootm.c 的 boot_jump_linux,内核侧在 arch/arm/kernel/head.S 与 arch/arm64/kernel/head.S 的入口注释,外加两份 booting 文档。
5. dtb 必须落在 8 字节的边界上,大小不能超过 2MB。boot_relocate_fdt 分配新位置的时候按 0x1000 对齐,8 字节的要求顺带就满足了,两头的设计是咬合的。

</details>

## 延伸阅读

咱们核对过的源码与文档,入口都给你备好了:

- [Linux 内核文档,32 位 ARM 的启动约定](https://docs.kernel.org/arch/arm/booting.html):r0、r1、r2 口径的正本,本章的内核侧出处之一。
- [Linux 内核文档,ARM64 的启动约定](https://docs.kernel.org/arch/arm64/booting.html):x0 口径与 dtb 对齐、大小要求的正本。
- [Linux v7.2.9 的 arch/arm64/kernel/head.S](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/arch/arm64/kernel/head.S?h=v7.2.9):preserve_boot_args 所在的文件,点进去就能对着看了。
