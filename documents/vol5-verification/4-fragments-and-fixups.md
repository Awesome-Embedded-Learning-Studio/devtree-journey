---
title: "板子定了型还想改树,引用的答案为什么推迟?"
volume: 5
chapter: 17
section: 1
order: 171
description: "配置分家的板子给出另一条路:基础树只写共有部分,配件描述打包成 overlay,源文件多一行 /plugin/,每个 fragment 挑中目标节点往身上叠增量,基础带 -@ 编译,标签收进 __symbols__ 对照表。传感器 overlay 编译出一串缺上下文的 reg_format 告警,反编译现出 fragment@0、__overlay__ 与 __fixups__ 的原形,引用欠成清单,缝合推迟到应用那一刻,标签还能跨 overlay 接力,sensor0 的欠条留给实验"
status: draft
---

# 增量怎么打包,引用的答案为什么等到应用那一刻?

“编译成功就代表写对了吗”那章里咱们拿 schema 把写错的树拦在了门外,写树这件事算是有了把关的工序。可还有一类改动的方向不一样:毛病不出在写错的树上,出在配置分家的板子上。核心板定下了型,I2C 总线引出了插座,插温度传感器的订单是一种,什么都不插的裸板又是一种,过两个月配件就又要换代了。你要为每种配置维护一份完整的大树吗?配件的种类一多,基础里就得塞进一堆当下用不上的描述,咱们还得拿 `status = "disabled"` 把它们压住,你每改动一处基础,手头的几十份拷贝就得跟着重改。

设备树给了另一条路:基础树只写所有板子共有的部分,配件的描述单独打包成 overlay(设备树插件,叠到基础树上的增量描述),等到了合适的时机再把 overlay 缝到基础树上。缝的时机不止一个,咱们开发它的电脑上能缝、板子的引导阶段能缝,内核跑起来之后咱们照样有办法缝。这一章咱们把三个位置都走到,每个位置的环境与适用范围分别记清,电脑上的部分咱们真跑,板子上的两处按官方文档讲,未实测的地方明写出来。

这一章的题目是“怎样在不同阶段叠加修改?”,咱们分成几篇来走。本篇讲增量的打包与引用的欠条:overlay 的源文件长什么样,fragment 里装的是什么,基础树的编译为什么要带上 `-@`。

## 增量怎么打包:fragment 里只装要叠的内容

overlay 的源文件长得跟普通的 DTS 几乎一样,咱们能看出来的差别有两处。开头多了一行 `/plugin/;`,它声明的是插件的身份,允许文件里引用基础树的标签而当时不给答案。“标签和引用怎样变成二进制”那章咱们认过引用变 phandle 的底子,这里轮到它跨文件干活了。另一处的差别在内容本身:overlay 不重写基础,只写要叠上去的增量,每个 fragment 的意思是“挑中一个目标节点,往它身上叠一段内容”。

咱们照旧动手。工作目录咱们开在 /tmp/vol5ch17,免得中间的产物混进仓库。本机的工具是 dtc v1.8.1,dtc 和 fdtoverlay 两位都住在 /usr/sbin 的目录里,咱们跑命令的日子是 2026-10-18。基础树咱们写一块最小核心板,I2C 控制器挂上了 i2c0 的标签,串口挂上了 uart0 的标签,别的从简:

```dts
/dts-v1/;

/ {
	compatible = "acme,soc2000";
	model = "ACME Core Board";
	#address-cells = <1>;
	#size-cells = <1>;

	i2c0: i2c@800 {
		compatible = "acme,i2c";
		reg = <0x800 0x20>;
		#address-cells = <1>;
		#size-cells = <0>;
		status = "okay";
	};

	uart0: serial@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
		clock-frequency = <115200>;
		status = "okay";
	};
};
```

编译基础的时候咱们带上 `-@`。不带它的话标签名不进产物,带上了,dtc 才会把标签收进产物里的 `__symbols__` 节点,留成了一张对照表,备着缝合的时候用:

```shell
cd /tmp/vol5ch17
dtc -@ -I dts -O dtb -o base.dtb base.dts
```

命令静默地完成了,咱们连一条告警都没见到。咱们反编译回来看,就能看到 `-@` 多放进产物的两样东西:

```shell
dtc -I dtb -O dts base.dtb
```

```dts
/dts-v1/;

/ {
	compatible = "acme,soc2000";
	model = "ACME Core Board";
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	i2c0: i2c@800 {
		compatible = "acme,i2c";
		reg = <0x800 0x20>;
		#address-cells = <0x01>;
		#size-cells = <0x00>;
		status = "okay";
		phandle = <0x01>;
	};

	uart0: serial@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
		clock-frequency = <0x1c200>;
		status = "okay";
		phandle = <0x02>;
	};

	__symbols__ {
		i2c0 = "/i2c@800";
		uart0 = "/serial@1000";
	};
};
```

“构建系统实际上做了什么”那章里你见过 `__symbols__` 的面孔:标签名做的是属性名,节点的完整路径做值,dtc 替咱们把全树的标签编成了一张对照表。那一章咱们只认了脸,它到底给谁用、怎么用,今天咱们把链条走通。

对照表备好了,fragment 装什么也认了,可表里的名字留给谁用?overlay 编译出来的欠条长什么样?咱们接着往下看。

## 引用欠下,缝合推迟到应用那一刻

基础备好了,咱们给插传感器的板子写 overlay。`sensor@48` 挂上温度传感器的描述,叠的位置是 i2c0 名下,源文件咱们存成 sensor-overlay.dtso:

```dts
/dts-v1/;
/plugin/;

&i2c0 {
	sensor@48 {
		compatible = "acme,temp-sensor";
		reg = <0x48>;
		status = "okay";
	};
};
```

“怎样描述和组织设备”那章你用过 `&i2c0 { ... }` 的写法,普通的树里它指同文件或被包含文件里的标签。进了插件,它的意思变成了“去基础树里找 i2c0,把花括号里的内容叠上去”。咱们编译它的时候同样带上 `-@`:

```shell
dtc -@ -I dts -O dtb -o sensor-overlay.dtbo sensor-overlay.dtso
```

```output
sensor-overlay.dtso:7.3-16: Warning (reg_format): /fragment@0/__overlay__/sensor@48:reg: property has invalid length (4 bytes) (#address-cells == 2, #size-cells == 1)
sensor-overlay.dtbo: Warning (pci_device_reg): Failed prerequisite 'reg_format'
sensor-overlay.dtbo: Warning (pci_device_bus_num): Failed prerequisite 'reg_format'
sensor-overlay.dtbo: Warning (simple_bus_reg): Failed prerequisite 'reg_format'
sensor-overlay.dtbo: Warning (i2c_bus_reg): Failed prerequisite 'reg_format'
sensor-overlay.dtbo: Warning (spi_bus_reg): Failed prerequisite 'reg_format'
sensor-overlay.dtso:5.12-9.4: Warning (avoid_default_addr_size): /fragment@0/__overlay__/sensor@48: Relying on default #address-cells value
sensor-overlay.dtso:5.12-9.4: Warning (avoid_default_addr_size): /fragment@0/__overlay__/sensor@48: Relying on default #size-cells value
sensor-overlay.dtbo: Warning (avoid_unnecessary_addr_size): Failed prerequisite 'avoid_default_addr_size'
sensor-overlay.dtbo: Warning (unique_unit_address): Failed prerequisite 'avoid_default_addr_size'
```

产物照常出来了,告警倒是来了一串。它们有同一个来源:dtc 检查的是 sensor-overlay.dtso 自己这棵树,sensor@48 在编译时其实见不到 i2c0,dtc 只能按规范默认的 cells 去掐算 reg 的长度,长度对不上就报了告警。叠上去之后的真正父节点是 i2c0,它写明了 `#address-cells = <1>`,一个 cell 的 reg 正合适。所以这一串告警咱们读的时候心态放平:它出自“检查缺上下文”的场景,真假咱们等缝合之后再判,咱们马上就拿反编译来验。

咱们把 overlay 产物反过来看,fragment 的结构在编译之后现了原形:

```shell
dtc -I dtb -O dts sensor-overlay.dtbo
```

```dts
/dts-v1/;
/plugin/;

/ {

	fragment@0 {
		target = <&i2c0>;

		__overlay__ {

			sensor@48 {
				compatible = "acme,temp-sensor";
				reg = <0x48>;
				status = "okay";
			};
		};
	};

	__fixups__ {
		i2c0 = "/fragment@0:target:0";
	};
};
```

咱们把三个部件对上号。`fragment@0` 就是那个装增量的容器,源文件里 `&i2c0 { ... }` 的糖衣被脱掉,露出了 target 指目标、`__overlay__` 装增量的直白结构。`__fixups__` 就是欠引用的清单:它说 i2c0 的引用还没拿到答案,答案该填进 fragment@0 的 target 属性第 0 个 cell,给答案的差事归基础。编译 overlay 的时候基础根本不在场,i2c0 对应哪个 phandle 的事,dtc 当然既不知道、也不需要知道。

咱们把缝合推迟到应用那一刻,这正是符号表存在的理由。基础的 `__symbols__` 说 i2c0 住在 `/i2c@800`,基础自己的结构块说 `/i2c@800` 的 phandle 是 1,应用器把两张表对上了,再把 1 回填进 target 的位置,fragment 的增量从此有了挂靠。核对型号的活不劳编译期操心,查表和回填都发生在应用的现场。

符号的链还能接着往下传。咱们给 overlay 自己的节点挂上标签,后面的第二份 overlay 就能引用它了。咱们再做一份小的给传感器补轮询间隔,要写的两份源文件长这样:

```dts
/dts-v1/;
/plugin/;

&i2c0 {
	sensor0: sensor@48 {
		compatible = "acme,temp-sensor";
		reg = <0x48>;
		status = "okay";
	};
};
```

```dts
/dts-v1/;
/plugin/;

&sensor0 {
	poll-interval = <100>;
};
```

头一份咱们存成 sensor-labeled-overlay.dtso,它在 sensor-overlay.dtso 的基础上只多了 sensor0 一个标签,编译报的告警跟前面那一串是同一批,行号列号挪了位置,咱们不重贴。第二份咱们存成 chain-overlay.dtso,它编译的时候一声不吭,因为它的增量只有一个属性,告警的由头一点没有。它反编译出来的 `__fixups__` 里欠的是 sensor0,而基础里没有这个名字:

```dts
	__fixups__ {
		sensor0 = "/fragment@0:target:0";
	};
```

应用器怎么还清 sensor0 的欠条,咱们到实验里看。

## 本节自检

文章读完了,你拿五个小问题验一验自己,想好了再展开参考答案。

1. 基础树编译的时候,`-@` 带与不带,产物差在哪里?
2. overlay 的源文件跟普通的 DTS 差在哪两处?
3. fragment 的意思是什么?overlay 为什么不用重写基础?
4. overlay 的增量装在哪个节点里?目标节点的引用记在哪张表里?它为什么不能在编译 overlay 的时候就把答案定下来?
5. 编译 sensor-overlay.dtso 的那一串 reg_format 告警是怎么来的?叠上去之后为什么就没事了?

<details>
<summary>参考答案(想好再展开)</summary>

1. 不带它的话标签名不进产物,带上了,dtc 才会把标签收进产物里的 `__symbols__` 节点,留成了一张对照表,备着缝合的时候用。
2. 开头多了一行 `/plugin/;`,它声明的是插件的身份,允许文件里引用基础树的标签而当时不给答案。另一处的差别在内容本身,overlay 不重写基础,只写要叠上去的增量。
3. 每个 fragment 的意思是“挑中一个目标节点,往它身上叠一段内容”。overlay 只写要叠上去的增量,基础树不用重写。
4. 增量装在 `fragment@0` 的 `__overlay__` 里,目标引用记在 `__fixups__`,值是 `/fragment@0:target:0`。编译 overlay 时基础不在场,i2c0 对应哪个 phandle 编译器不知道,答案只能等应用时查基础的 `__symbols__` 回填。
5. dtc 检查的是 overlay 自己那棵树,sensor@48 编译时不知道父节点是谁,reg 只能按默认 cells 掐算长度,对不上就告警。叠上去之后父节点是 i2c0,它写明了 `#address-cells = <1>`,reg 的长度正合适。

</details>

## 延伸阅读

- [dtc 仓库的 overlay 中间格式说明](https://github.com/dgibson/dtc/blob/master/Documentation/dt-object-internal.txt):fragment、`__fixups__`、`__local_fixups__` 的正式定义,想抠格式细节到这里读。
