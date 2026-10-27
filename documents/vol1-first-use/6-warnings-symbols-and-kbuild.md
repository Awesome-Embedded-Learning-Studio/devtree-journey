---
title: "dtc 的告警和 __symbols__ 是给谁的,真实构建里谁在替咱们敲?"
volume: 1
chapter: 3
section: 2
order: 32
description: "unit_address_vs_reg 查有无不查数值对不对,退出码 0 产物照出,带 -@ 编出的 __symbols__ 对照表和 phandle 是给 overlay 备下的记号,内核的 kbuild 中央规则与 U-Boot 的 OF_CONTROL、DEFAULT_DEVICE_TREE、dts/upstream/ 把同一对工具串进真实构建"
status: draft
---

# dtc 的告警和 __symbols__ 是给谁的,真实构建里谁在替咱们敲?

树编出来了,dtc 却还有话要跟咱们讲。源码里藏着毛病的时候,它会把告警摆到你眼前。带上 -@ 编的时候,多出来的还有一张 __symbols__ 表。两张脸咱们挨个认一认,看完你就知道告警该不该怕,表又是备给谁的。

## 告警长什么样,咱们要不要怕

告警这块咱们备两个会出状况的源文件。头一个出状况的源文件叫 warn-noreg.dts,节点的名字里挂着 @1000,reg 属性倒是没写:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	serial@1000 {
		compatible = "acme,uart";
	};
};
```

```shell
dtc -I dts -O dtb -o warn-noreg.dtb warn-noreg.dts
```

```output
warn-noreg.dts:7.14-9.4: Warning (unit_address_vs_reg): /serial@1000: node has a unit name, but no reg or ranges property
```

咱们把告警读顺:warn-noreg.dts 是文件名,7.14-9.4 说的是第 7 行第 14 列到第 9 行第 4 列,unit_address_vs_reg 是检查的名字,后面那句人话是它给出的描述。名字说的是 @1000,身上却连 reg 或 ranges 的影子都没有,地址没了着落,dtc 提醒你一下。提醒是要提醒的,命令的退出码是 0,warn-noreg.dtb 也照常写出来了,咱们用 `ls -l` 看得见它。

第二个源文件咱们叫它 warn-mismatch.dts,名字挂的还是 @1000,reg 给的却是 0x9000:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	serial@1000 {
		compatible = "acme,uart";
		reg = <0x9000 0x100>;
	};
};
```

```shell
dtc -I dts -O dtb -o warn-mismatch.dtb warn-mismatch.dts
```

这一遍干干净净地编过去了,退出码也稳稳地是 0,咱们连一条告警都没见到。咱们翻过 dtc 1.8.1 的源码,这个检查问的就两个问题:单元地址写了没有,reg 或 ranges 挂了没有。至于名字里的 1000 和 reg 里的 0x9000 对不对得上,这个层面的一致性它不管,管它的是第五卷才登场的 schema 校验。

那告警该不该怕?咱们的心态可以放平:告警是 dtc 白送的检查单,提示的多是写法层面的毛病,改掉就完了。真正要当心的是“带病产物”:告警是拦不住编译的,DTB 还是照常出来的,你要是无视它,毛病就跟着产物进了启动链路。dtc 给每个检查都配了开关,咱们实测加 `-Wno_unit_address_vs_reg` 之后告警就消失了。关是能关的,但内核和 U-Boot 给 dtc 传了自家的一串参数,被默认关掉的检查在里头都有安排,具体等版本锁定后咱们再核对,现在咱们不去学他们关告警的手法。

## 带 -@ 编出来的产物,里面多了 __symbols__

咱们还是拿 board.pp.dts 当原料,编一个带 `-@` 的版本:

```shell
dtc -@ -I dts -O dtb -o board-sym.dtb board.pp.dts
ls -l board.dtb board-sym.dtb
```

```output
.rw-r--r-- 359 charliechen 18 Oct 13:34 board.dtb
.rw-r--r-- 478 charliechen 18 Oct 13:35 board-sym.dtb
```

咱们把 359 和 478 放在一起,多出来的 119 字节装了什么?咱们反编译看看:

```shell
dtc -I dtb -O dts board-sym.dtb
```

```dts
/dts-v1/;

/ {
	compatible = "acme,soc1000";
	#address-cells = <0x01>;
	#size-cells = <0x01>;
	model = "ACME Lab Board";

	uart0: serial@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
		phandle = <0x01>;
	};

	led0: led@8 {
		compatible = "acme,led";
		reg = <0x08 0x04>;
		status = "okay";
		phandle = <0x02>;
	};

	__symbols__ {
		uart0 = "/serial@1000";
		led0 = "/led@8";
	};
};
```

对比前面编 board.dtb 时的反编译,你会看到三处不同。根下面多了一个 __symbols__ 节点,属性的内容是一张对照表:标签名做的是属性名,节点的完整路径做值,表里记了两行,uart0 和 led0 各自指向自己的节点。标签也跟着回来了:不带 -@ 的产物里没有标签,反编译自然就描不出来了,带 -@ 的产物把对照表存进了树里,dtc 反编译时照着它把标签写了回去。两个带标签的节点还多了 phandle 属性,不带 -@ 的产物里可没有它们,这是 dtc 顺手补上的编号,为的是让节点可以被别处引用。

__symbols__ 是给谁用的?给 overlay(设备树插件,运行时叠到基础树上的增量描述)。overlay 引用基础树里的节点时,靠的就是 __symbols__ 的对照表。完整的 overlay 机制是第五卷的主题,咱们在这里只认脸:以后咱们再见到 __symbols__,你就知道这棵树编的时候带了 -@,备好了被叠加的记号。

实验里手敲的两步,你摸得够熟了。真实项目里同一件事由谁代劳?命令又是从谁手里发出来的?咱们接下来就看内核和 U-Boot 的构建怎么安排同一对工具。

## 内核和 U-Boot 的构建里,谁在替咱们敲

kbuild 这个名字咱们在开头提过,这里咱们把它补齐:它是内核的构建系统,核心就是一组 Makefile(描述每个产物从哪些原料、按什么步骤生成的构建脚本)加上辅助脚本,U-Boot 的构建照着同一套 make 的路子组织。CONFIG 选项是两边用的配置开关,它们的名字一律以 CONFIG_ 开头,你在配置阶段把它们选好,后面的构建照单办事。

内核这边的说法,咱们能跟官方文档对上的有这么几条:

- kbuild 文档说,把 .dts 编成 .dtb 用的是一条中央规则,架构目录不需要自己写规则,构建时还能通过 DTC_FLAGS 传参数。
- 哪块板子的树要编,取决于配置阶段选中的 CONFIG 选项,咱们实验里手敲的 dtc 命令,在内核那边由中央规则替你敲。
- 常量头的挂法:内核源码树的 include/dt-bindings/ 供所有 dts 共享,咱们核对主线构建脚本时见到它挂在 cpp 的查找路径上。
- dtbs_check 是官方文档记录的校验目标,拿 dt-validate 对着 schema 查树,比 dtc 的告警更高一层,咱们到第五卷再展开。

咱们在主线构建脚本里核对到的接力,跟实验里的两步是同一个样子:cpp 带着同一串意思的参数把 .dts 归拢成中间文件,dtc 再把它编成了 .dtb,include/dt-bindings/ 目录也捎带着挂进了查找路径。你在本机实验里摸到的,跟内核那边干的是同一件事。

U-Boot 的官方文档把这摊事讲得最直白,咱们引用几条:

- 设备树的编译由 dtc 完成,这个 dtc 由 U-Boot 构建自带,你不用自己装。
- 设备树的支持由 OF_CONTROL 这个开关决定,你不打开它,U-Boot 那边就当设备树不存在了。
- DEFAULT_DEVICE_TREE 指定默认要编的树,你 make 的时候还能拿 DEVICE_TREE= 临时换一棵,也能用 EXT_DTB= 直接塞一份编好的 DTB。
- 树源的首选是 dts/upstream/ 里跟内核共享的子树,板子自己的增补写在 `arch/<arch>/dts/` 下的 `*-u-boot.dtsi` 文件里,构建会自动找到它们,再追加进你的树。
- 产物怎么进镜像的事同样由 CONFIG 决定,比如 OF_SEPARATE 的做法,树单独编成了 u-boot.dtb,和 u-boot-nodtb.bin 并排成了两个文件。

工具还是咱们认得的那一对,两步的安排也没变,变了的只是谁来敲、编哪些树、产物往哪儿放,这些安排都写在了构建规则里,由 CONFIG 和 Makefile 说了算。

## 逐行走读?版本锁定之前不写

讲到这儿你也许想问:两边的构建脚本,咱们为什么不直接翻开走读?本课程有条底线:涉及源码的逐行走读,咱们都要等版本锁定之后,在正本源码上核对过了才写进章节。今天的主线天天在动,咱们现在抄进书里的规则行,过几个月可能就挪了窝。所以本章给到机制和官方出处为止,内核与 U-Boot 构建规则的逐行走读,等版本定了,在后面的卷里对着源码做。你在本机实验里摸到的两步,跟那边干的是同一件事,这一点咱们已经在主线上核对过了。

## 第一卷收工,下一卷钻进字节里

第一卷到这里就齐了。你会把 DTS 编译成 DTB、反编译回来检查,也会用节点和属性把描述组织起来了,也知道了构建系统在那头替你做着同样的事,还多认了告警和 __symbols__ 两张脸。接下来的一卷叫“从字节到自己的树”,它要钻进产物的内部:DTB 的每个字节住着什么,header、结构块、字符串块怎么布局,咱们还要亲手写一个读 DTB 的 reader,仓库里的 edtc 工程就从那边起步。你在这一卷敲过的命令,到了那边都会变成“我写的程序也要经得起同样的检查”。

## 本节自检

文章读完了,你拿下面的小问题验一验自己。

1. unit_address_vs_reg 检查的是什么、不检查什么?告警会不会拦住编译?
2. 带 -@ 编出来的 DTB 比不带的多出什么?它是给谁用的?
3. 加 `-Wno_unit_address_vs_reg` 能让告警消失,咱们为什么不学着内核关告警?
4. 内核和 U-Boot 的构建里,编哪块板子的树由什么说了算?
5. U-Boot 那边想临时换一棵树编,make 的时候怎么写?
6. 两边的构建脚本,咱们为什么不直接翻开走读?

<details>
<summary>参考答案(想好再展开)</summary>

1. 它检查的是有无:名字里带没带单元地址,节点带没带 reg 或 ranges,数值对不对得上不管。告警不拦编译,退出码是 0,DTB 照常生成。
2. 多出一个 __symbols__ 节点,记录标签名到节点路径的对照,带标签的节点还补上了 phandle。它是给 overlay 用的,overlay 靠这张表引用基础树里的节点。
3. 内核和 U-Boot 给 dtc 传的自家参数里,被默认关掉的检查都有安排,要等版本锁定后咱们再核对。告警拦不住编译,你要是无视它,毛病就跟着产物进了启动链路,所以咱们不学他们关告警的手法。
4. 由配置阶段选中的 CONFIG 选项说了算,U-Boot 那边对应的开关叫 DEFAULT_DEVICE_TREE,make 时还能用 DEVICE_TREE= 临时换树。
5. make 的时候用 DEVICE_TREE= 临时换一棵,也能用 EXT_DTB= 直接塞一份编好的 DTB,默认要编的树由 DEFAULT_DEVICE_TREE 指定。
6. 本课程有条底线:涉及源码的逐行走读,要等版本锁定之后,在正本源码上核对过了才写进章节。今天的主线天天在动,现在抄进书里的规则行,过几个月可能就挪了窝。

</details>

## 延伸阅读

两边官方文档的出处,咱们原样给你列在这里:

- [Linux: Kbuild makefiles](https://docs.kernel.org/kbuild/makefiles.html):内核构建文档,dtc 一节讲了 .dts 到 .dtb 的中央规则和 DTC_FLAGS。
- [Linux: Writing devicetree bindings schemas](https://docs.kernel.org/devicetree/bindings/writing-schema.html):dtbs_check 与 DT_SCHEMA_FILES 的用法,比 dtc 告警更高一层的校验入口。
- [U-Boot: Devicetree Control](https://docs.u-boot.org/en/latest/develop/devicetree/control.html):U-Boot 官方讲它的树怎么编、CONFIG 怎么选,本篇引用的 U-Boot 说法多数出于这里。

构建规则的逐行走读,等版本锁定了,咱们在后面的卷里对着源码做。
