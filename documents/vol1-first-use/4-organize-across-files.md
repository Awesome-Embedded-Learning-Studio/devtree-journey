---
title: "一堆文件怎么分工才算管得住?"
volume: 1
chapter: 2
section: 3
order: 23
description: "公共描述放进 .dtsi,/include/ 把它拼进板子的 .dts,同路径节点走合并,标签在源码里写名字、进了产物换成 phandle 编号,不合身的部分用重写、/delete-property/ 和 /delete-node/ 三种手段改"
status: draft
---

# 公共的描述怎么共享,不合身的部分怎么改?

前两篇咱们把描述的事办妥了:节点有名有姓,属性的值按写法各就各位,`reg` 的切法也有了声明。剩下的疑问全在文件这一头:真实板子的描述常常分在好几个文件里,公共的部分怎么共享,跨节点的连线怎么表达,不合身的部分怎么改。组织的事,这一篇咱们一次办完,用的还是老办法:认一种写法就编译一回,再到产物里看它变成了什么。动手的位置照旧,你在自己电脑上建一个工作目录:

```shell
mkdir -p /tmp/dt-ch2
cd /tmp/dt-ch2
```

本仓验证的工具是 dtc v1.8.1,咱们跑命令的日子是 2026-10-18。

## 公共描述放 .dtsi,/include/ 拼进来

咱们想一想真实的分工:芯片厂商把 SoC 里的外设写成一份描述,板卡厂商拿同一颗芯片做出不同的板子,公共的部分犯不着重写。设备树把这层分工做成了文件:公共的片段放进 .dtsi 文件,板子的 .dts 把它引进来,再补上这块板独有的东西。“DTS、DTB、dtc 都是什么”那篇里咱们跟 .dtsi 混过脸熟,现在来真的。

咱们编一份芯片级的 soc.dtsi:

```dts
/ {
	compatible = "demo,soc";
	#address-cells = <1>;
	#size-cells = <1>;

	uart@1000 {
		compatible = "demo,uart";
		reg = <0x1000 0x100>;
		status = "okay";
	};

	i2c@2000 {
		compatible = "demo,i2c";
		reg = <0x2000 0x80>;
		status = "okay";
	};

	dsp@3000 {
		compatible = "demo,dsp";
		reg = <0x3000 0x400>;
		status = "disabled";
	};
};
```

板子的 board-include.dts 用 `/include/` 把它引进来,咱们再给 uart 补上时钟频率、添一个 leds 节点:

```dts
/dts-v1/;

/include/ "soc.dtsi"

/ {
	uart@1000 {
		clock-frequency = <115200>;
	};

	leds {
		compatible = "demo,leds";
	};
};
```

咱们编译再反编译:

```shell
dtc -I dts -O dtb -o board-include.dtb board-include.dts
dtc -I dtb -O dts board-include.dtb
```

咱们把回来的树整棵读一遍:

```dts
/dts-v1/;

/ {
	compatible = "demo,soc";
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	uart@1000 {
		compatible = "demo,uart";
		reg = <0x1000 0x100>;
		status = "okay";
		clock-frequency = <0x1c200>;
	};

	i2c@2000 {
		compatible = "demo,i2c";
		reg = <0x2000 0x80>;
		status = "okay";
	};

	dsp@3000 {
		compatible = "demo,dsp";
		reg = <0x3000 0x400>;
		status = "disabled";
	};

	leds {
		compatible = "demo,leds";
	};
};
```

产物里只剩一棵完整的树,文件边界消失了。`uart@1000` 在两个文件里各出现了一回,合并的结果是:dtsi 里的老属性全在,.dts 新加的 clock-frequency 也进来了。同路径的节点走的是合并,老属性全都留了下来,新属性也加了进来。合并之外还有一个产物观察:十进制的 115200 进产物再回来变成了 0x1c200,你在那章见过的老现象,咱们在这里再确认一回。

`/include/` 是 dtc 自己认识的指令,规范第 6 章把它列为 DTS 的编译器指令,被引的文件按惯例用 .dtsi 结尾,还能一层套一层地引。咱们的两个文件放在同一目录,dtc 就近找到了它。那内核源码里常见的 `#include` 呢?咱们单独拿 dtc 试一把,hash-include.dts 的内容只有两行:

```dts
/dts-v1/;

#include "soc.dtsi"
```

咱们来看 dtc 的反应:

```shell
dtc -I dts -O dtb -o hash-include.dtb hash-include.dts
```

```output
Error: hash-include.dts:3.1-9 syntax error
FATAL ERROR: Unable to parse input tree
```

咱们看到 dtc 根本不认识 `#include`,它是 C 预处理器 cpp 的指令,得由 cpp 处理完了再交给 dtc。内核构建里就是这么接力的,引文件的是谁、路径去哪儿找,咱们到下一章里看个究竟。

## 标签和引用:源码里写名字,产物里是数字

树里常有跨节点的连线:uart 用哪个时钟、中断发给哪个控制器,这样的关系咱们用引用来表达。咱们谁都不想每次抄一长串路径,DTS 就备了标签(label)的写法:在节点的前面挂个名字加冒号,别处写 `&名字` 就指了回来。咱们写一份 label.dts,给时钟节点挂好 clk24 的标签,让 uart 的 clocks 引用它:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	clk24: clock-controller {
		compatible = "demo,fixed-clock";
		clock-frequency = <24000000>;
		#clock-cells = <0>;
	};

	uart@1000 {
		compatible = "demo,uart";
		reg = <0x1000 0x100>;
		clocks = <&clk24>;
	};
};
```

咱们编译再反编译:

```shell
dtc -I dts -O dtb -o label.dtb label.dts
dtc -I dtb -O dts label.dtb
```

回来的树里,咱们能看见两处变化:

```dts
/dts-v1/;

/ {
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	clock-controller {
		compatible = "demo,fixed-clock";
		clock-frequency = <0x16e3600>;
		#clock-cells = <0x00>;
		phandle = <0x01>;
	};

	uart@1000 {
		compatible = "demo,uart";
		reg = <0x1000 0x100>;
		clocks = <0x01>;
	};
};
```

被引用的 clock-controller 多了一个 `phandle = <0x01>`,咱们没写它,这是 dtc 自动编上去的,规范在 phandle 的说明里也交代了这一点。引用的位置呢,`clocks = <&clk24>` 回来变成了 `clocks = <0x01>`,名字没了,只剩下了编号。消费软件拿两边的编号一对,连线就接上了。标签名字自己去了哪儿?咱们用 strings 把产物里的字符串捞一遍:

```shell
strings label.dtb | grep clk24
strings label.dtb | grep clock-controller
```

头一条什么都没捞到,第二条给了 `clock-controller`。规范的说法很直白,咱们照它翻译:标签只活在源码的格式里,不编码进 DTB 的产物。名字是给人用的,编号是给机器用的,编译这一步就是换岗的关口。咱们也有必要把话说全:dtc 还有个 `-@` 选项会把标签名收进产物里的 `__symbols__` 节点,那是给运行时覆盖准备的机制,咱们到下一章里再遇到它。编号是谁分的、重号怎么避免,这些细节咱们留到第四卷,那一章的名字就叫“标签和引用怎样变成二进制”。

## 公共部分不合身怎么办:覆盖和删除

soc.dtsi 拼好了公共部分,可它不可能跟每块板都严丝合缝:有的板没焊 DSP,有的板要改串口的配置。dtsi 里的东西怎么改?咱们一次看全三种手段:同路径的节点里重写同名属性,新的值就把老的覆盖了,多余的属性用 `/delete-property/` 删,整个设备不要了用 `/delete-node/` 拔掉。板子的 board-alt.dts 引的还是同一份 soc.dtsi:

```dts
/dts-v1/;

/include/ "soc.dtsi"

/ {
	uart@1000 {
		clock-frequency = <115200>;
	};

	i2c@2000 {
		status = "disabled";
		/delete-property/ compatible;
	};

	/delete-node/ dsp@3000;
};
```

咱们编译再反编译:

```shell
dtc -I dts -O dtb -o board-alt.dtb board-alt.dts
dtc -I dtb -O dts board-alt.dtb
```

反编译回来的树,把三种手段的结果全摆给咱们看了:

```dts
/dts-v1/;

/ {
	compatible = "demo,soc";
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	uart@1000 {
		compatible = "demo,uart";
		reg = <0x1000 0x100>;
		status = "okay";
		clock-frequency = <0x1c200>;
	};

	i2c@2000 {
		reg = <0x2000 0x80>;
		status = "disabled";
	};
};
```

咱们挨个核对。`uart@1000` 走的还是合并的路数,老属性又添了新属性。`i2c@2000` 的 status 从 okay 重写成了 disabled,同名属性后写的赢,compatible 被 `/delete-property/` 删掉了,节点里剩下的只有 reg 和 status。`dsp@3000` 整个从树上消失了,产物里连它的字节都不占。

拼写上有个容易吃亏的地方,咱们头一回把删属性写成 `/delete-prop/`,dtc 的回应是:

```output
Error: board-alt.dts:12.3-4 syntax error
FATAL ERROR: Unable to parse input tree
```

规范附录的语法表里写的是全称 `/delete-property/`,本机的 dtc v1.8.1 也只认全称,咱们照规范写就不会被绊住。

你还记得 `i2c` 的处理只是标了 disabled 吧,节点和它的 `reg` 都还在产物里。禁用和删除是两回事:disabled 的意思是“设备在,但别用它”,描述保留了下来,消费软件读了 status 就会绕开它,删除的意思则是“当它不存在”,连它的字节都不留。咱们该用哪个,看的还是板上的事实:设备真有但暂时不用,咱们标 disabled,压根没焊的设备,咱们就删掉。

这一章咱们把描述和组织都办妥了:节点有名有姓,属性的值按写法各就各位,公共部分分文件、连线用标签、不合身的部分改掉。可你合上文件想一想,真项目里几十个 .dts 和 .dtsi 散在源码树的各处,cpp 和 dtc 怎么接力,include 的搜索路径是什么,dtc 还有哪些选项没跟咱们打过照面?这些活都归下一章,它的名字就叫“构建系统实际上做了什么”,咱们下一章见。

## 本节自检

文章读完了,你拿下面的小问题验一验自己。

1. 同一个节点在 dtsi 和 dts 里各写了一回,进了产物是什么样子?
2. `#include` 直接交给 dtc,下场是什么?这条指令本来归谁管?
3. 标签 `clk24` 编译后还找得到吗?`clocks = <&clk24>` 在产物里变成了什么?
4. `status = "disabled"` 和 `/delete-node/` 都能让设备不被驱动,差别在哪?

<details>
<summary>参考答案(想好再展开)</summary>

1. 同路径的节点走的是合并:dtsi 里的老属性全在,.dts 新加的属性也进来了,产物里只剩一棵完整的树,文件边界消失了。
2. dtc 报了语法错误,编译都过不去。`#include` 是 C 预处理器 cpp 的指令,得由 cpp 处理完了再交给 dtc,内核构建里就是这么接力的。
3. 找不到了,标签只活在源码里。引用变成了数字,被引节点多了 `phandle` 属性,引用处的值与它相同。
4. disabled 的节点还在产物里,描述保留着,消费软件读了 status 绕开它。删除则让节点从产物里彻底消失,字节都不占。

</details>

## 延伸阅读

本篇的条款出处与工具文档,给你备好了:

- [Devicetree Specification 官方页](https://www.devicetree.org/specifications/):/include/、标签和删除语法在第 6 章,本仓缓存的是 v0.4 版本。
- [dtc 的 DTS 格式说明](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/tree/Documentation/dts-format.txt):dtc 仓库自己写的 DTS 语法说明,标签与 phandle 引用的写法在这里。

咱们引用的条款来自规范 v0.4(本仓缓存副本),正文里的命令与输出全部在本机真实运行过,验证环境的版本是 dtc v1.8.1,验证的日子是 2026-10-18。
