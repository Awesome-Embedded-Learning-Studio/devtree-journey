---
title: "同一道对表题差在哪,亲手编一棵 control FDT 是什么样子?"
volume: 3
chapter: 8
section: 3
order: 3
description: "Linux v7.2.9 的 platform_match 经 of_driver_match_device 到 of_match_node 拿 of_match_table 对表,与 U-Boot 的 udevice_id 逐项对照出分工、组织、遍数三处差别,两边处境的不同是根子,再拿 cpp 与 dtc 手工复刻 U-Boot 为 ROCK Pi 4 组装 control FDT 的那段构建,空文件顶替 config.h 折掉 binman 布局,fdtget 向产物提问,对照组 upstream.dtb 缺的正是增补,整章的线索也就收拢了"
status: draft
---

# 同一道对表题差在哪,亲手编一棵 control FDT 是什么样子?

“树里的节点,怎么变成干活的设备”那篇走完了 U-Boot 这边的对表与 probe,答法咱们攥下了一份。Linux 那边的源码也拉在本机,它的对表路径,咱们在本篇里走一遍,两边的差别,咱们接着数清楚。

版本还是开篇锁定的 U-Boot v2026.10 与 Linux v7.2.9,本篇引的函数与行号,你在同样的地址都核对得上。

“谁会使用设备树”那篇里咱们说过,U-Boot 的消费路子跟 Linux 是同一个,现在两边的源码都摆在桌上,咱们把两份答案放在一起看。

Linux v7.2.9 这边咱们看对表的地方:设备树展平完了之后,创建平台设备的活交给 `of_platform_populate`,它的家在 drivers/of/platform.c:443,咱们跟着它从根节点一路往下看,匹配发生在 platform 总线的 `platform_match` 里:

```c
/* drivers/base/platform.c:1368,有删节 */
static int platform_match(struct device *dev, const struct device_driver *drv)
{
	...
	/* Attempt an OF style match first */
	if (of_driver_match_device(dev, drv))
		return 1;
	...
}
```

```c
/* include/linux/of_device.h:20 */
static inline int of_driver_match_device(struct device *dev,
					 const struct device_driver *drv)
{
	return of_match_device(drv->of_match_table, dev) != NULL;
}
```

```c
/* drivers/of/device.c:25 */
const struct of_device_id *of_match_device(const struct of_device_id *matches,
					   const struct device *dev)
{
	...
	return of_match_node(matches, dev->of_node);
}
```

咱们把同一道对表的题摆在两边看,结构体连名字都各起各的。Linux 的驱动包在 `struct platform_driver` 里,匹配表挂在它内嵌的 `struct device_driver` 的 `of_match_table` 字段上,表的类型是 `struct of_device_id`,U-Boot 的 `struct driver` 自己带 `of_match` 字段,表类型换成了 `struct udevice_id`。对表的顺序两边一致,都按节点 compatible 列表的书写顺序,它从最具体的字符串问起。

差别倒是实打实的,咱们数三处看得见的。头一处差别在分工上:U-Boot 把读属性单独拆成了 `of_to_plat` 一步,probe 管的只是让硬件动起来,Linux 的驱动在 probe 里自己读属性,没有对应的独立阶段。第二处差别在组织上:在驱动的上面还有 uclass 这一层,同一类的设备共用一套接口,Linux 对应的角色由总线类型和各子系统担任,platform 总线就是其中的一张。第三处差别在遍数上:U-Boot 的绑定要来两遍,头一遍带着启动阶段标记的过滤,Linux 的枚举只有一遍,启动阶段标记的那套概念,在 Linux 那边没有对应的东西。这些差别都源于两边的处境:U-Boot 的处境是内存又小又紧、横幅要赶早,Linux 却是从从容容的,一次就把家底盘完了。

差别数完了,咱们回过头再看,U-Boot 的两遍绑定、单立的 `of_to_plat`,都长在它内存又小又紧的处境上,Linux 的从容也长在它的处境上。源码的走读到这里告了一段落,咱们换个手法,干的活是亲手编一棵 control FDT 当标本。

源码走读的摊子收了,按卷里的分工,实验的分量刻意放轻。咱们不编译 U-Boot,只把它构建 control FDT 的那一段手工复刻出来,咱们拿 dtc 验个明白:内核同源的树,加上 U-Boot 的增补,编出来的到底是什么样子。工具还是咱们熟悉的 cpp、dtc、fdtget,版本与全仓锁定的一致。咱们的工作目录放在 /tmp/vol3ch8/lab 下,咱们开工。

## 动手:亲手编一棵 control FDT 当标本

上游源在拉下来的 U-Boot 树里,增补链咱们按 control.rst 写明的顺序手工拼,入口文件咱们各写了一个:

```dts
/* control-rockpi4a.dts:复刻构建为 rock-pi-4a 组装的源 */
#include "rk3399-rock-pi-4a.dts"
#include "rk3399-rock-pi-4a-u-boot.dtsi"
```

```dts
/* upstream-rockpi4a.dts:对照组,只编内核同源的部分 */
#include "rk3399-rock-pi-4a.dts"
```

有一处诚实的交代:`rockchip-u-boot.dtsi` 链的深处有 `#include <config.h>`,真构建里头文件是板级配置生成的,咱们没跑构建,就用一个空文件顶了位置。效果是 `CONFIG_SPL` 一类的开关全部当作了未定义,binman(打包镜像的工具)的布局节点整段折掉,剩下的正是硬件描述与 U-Boot 增补,恰是咱们要看的东西。接着咱们跑预处理和编译:

```shell
mkdir -p /tmp/vol3ch8/lab/stub-include
cd /tmp/vol3ch8/lab
: > stub-include/config.h
UB=/tmp/vol3ch8/u-boot
cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
  -I "$UB/dts/upstream/src/arm64/rockchip" -I "$UB/dts/upstream/include" \
  -I "$UB/arch/arm/dts" -I stub-include \
  control-rockpi4a.dts -o control.pp.dts
dtc -I dts -O dtb -o control.dtb control.pp.dts 2> dtc-warnings.txt
wc -c control.dtb
```

```output
70235 control.dtb
```

编译的退出码是 0,告警倒是攒了一小把,里面就有你认识的 `unit_address_vs_reg`,它们来自内核同源的 dts,“构建系统实际上做了什么”那章里你已经见过这类告警,咱们不在这章展开。咱们反编译回来,`chosen` 和咱们追了一路的串口节点是这样的:

```dts
/* dtc -I dtb -O dts control.dtb 的节选 */
	chosen {
		stdout-path = "serial2:1500000n8";
		u-boot,spl-boot-order = "same-as-spl", "/mmc@fe330000", "/mmc@fe320000";
	};

	serial@ff1a0000 {
		compatible = "rockchip,rk3399-uart", "snps,dw-apb-uart";
		reg = <0x00 0xff1a0000 0x00 0x100>;
		reg-shift = <0x02>;
		reg-io-width = <0x04>;
		status = "okay";
		bootph-all;
		clock-frequency = <0x16e3600>;
	};
```

`u-boot,spl-boot-order` 是 U-Boot 自己加的配置,它向 SPL 交代了从哪块存储启动,`chosen` 里咱们导读认过的 `stdout-path` 原样在场。串口节点把整条故事收拢了:两个 compatible、板级 dtsi 打开的 `status`、增补的 `bootph-all`,咱们把 `0x16e3600` 换算过来,得到的正是 24000000。咱们用 fdtget 还能直接向产物提问:

```shell
fdtget control.dtb /serial@ff1a0000 clock-frequency
fdtget control.dtb /chosen stdout-path
```

```output
24000000
serial2:1500000n8
```

对照组咱们也编了出来,咱们比一比两棵的差异:

```shell
dtc -I dts -O dtb -o upstream.dtb upstream.pp.dts 2> /dev/null
wc -c upstream.dtb control.dtb
fdtget upstream.dtb /serial@ff1a0000 clock-frequency
```

```output
62824 upstream.dtb
70235 control.dtb
Error at 'clock-frequency': FDT_ERR_NOTFOUND
```

内核同源的产物里根本没有这个属性,fdtget 如实报了没找到。两个产物相差的 7411 字节里,装着启动阶段标记、启动顺序、内存初始化参数这些 U-Boot 的增补。同一块板子的同一棵树,两家各自消费的部分,你在字节层面摸到了实感。产物格式本身咱们不另外讲,“从字节到自己的树”那卷已经把 header 和结构块走完了,今天编出来的 control.dtb 跟那卷拆过的 DTB 是同一种文件。

实验收了工,咱们把整章的线索归拢一遍。今天咱们追完了一条线:control FDT 是 U-Boot 服务它自己的那棵树,它的住处是 `gd->fdt_blob`,来源的敲定在 `fdtdec_setup` 手里,内容由内核同源的 dts 加 `-u-boot.dtsi` 增补编成。消费它的是 Driver Model,绑定的一步拿 compatible 对表,probe 顺着 `chosen` 的 `stdout-path` 找到串口,`of_to_plat` 读走了属性,横幅由此上了屏。另一棵的身份是 working FDT,`fdt` 命令的手就搭在它上面,它跟 `gd->fdt_blob` 是两个不同的指针,树的职责也分成了两份。

同一个节点的另一段命运,就在 bootm 的启动路上等着咱们,源码里连线索都备好了:处理启动镜像的 boot/image-fdt.c 里有个 `boot_relocate_fdt`,交接树进内存之后的安置就是它的活,收尾时会调用 `set_working_fdt_addr` 把树接进 working FDT 的通道。它的来路是哪块存储、路上会被谁改过、最后按什么约定交到内核的手里,这些问题的答案,咱们到下一章展开,下一章的题目是“传给 Linux 的 DTB 是哪一份”。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. Linux v7.2.9 里 platform 总线匹配设备的 OF 路径经过了哪些函数?两边的匹配表各叫什么名字,表挂在哪个结构体字段上?
2. 真构建里 `rockchip-u-boot.dtsi` 链深处的 `#include <config.h>`,咱们拿什么顶了位置?顶替带来的是什么效果?
3. 对照组 upstream.dtb 里查 `clock-frequency`,fdtget 报了什么?为什么报它?
4. control.dtb 与 upstream.dtb 相差的 7411 字节里,装着的是哪些东西?

<details>
<summary>参考答案(想好再展开)</summary>

1. 路径是 `platform_match` 调 `of_driver_match_device`,再到 `of_match_device` 与 `of_match_node`,拿设备的 `of_node` 对驱动的 `of_match_table`。Linux 的表叫 `struct of_device_id`,挂在 `struct device_driver` 的 `of_match_table` 字段,U-Boot 的表叫 `struct udevice_id`,挂在 `struct driver` 的 `of_match` 字段。
2. 拿一个空文件顶了位置。效果是 `CONFIG_SPL` 一类的开关全部当作了未定义,binman 的布局节点整段折掉,剩下的正是硬件描述与 U-Boot 增补。
3. 报的是 `FDT_ERR_NOTFOUND`。内核同源的树里没有这个属性,它是 `rk3399-u-boot.dtsi` 写进 control FDT 的,fdtget 如实报了没找到。
4. 装着启动阶段标记、启动顺序、内存初始化参数这些 U-Boot 的增补。

</details>

## 延伸阅读

本篇的机制叙述与源码引用,咱们在官方文档里都找到了正本:

- [Linux: Devicetree Usage Model](https://docs.kernel.org/devicetree/usage-model.html):内核消费设备树的使用模型,与本篇对照的那一侧的权威叙述。
