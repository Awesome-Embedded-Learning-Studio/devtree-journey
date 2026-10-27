---
title: "引用为什么能写在标签前面?"
volume: 4
chapter: 14
section: 1
order: 141
description: "标签只活在源码里不进 DTB,属性值里的引用解析时只登记、全树成形后才回填,所以前向能过;顶层扩展引用解析的当下就要拿到节点,写前面就报语法错。basic.dts 与 fwd-ext、bwd-ext 在 dtc v1.8.1 上实测,机制回 dtc-parser.y 与 checks.c 核对"
status: draft
---

# 引用排在定义前面,编译器是怎么接住的?

“怎样读懂一小部分 DTS”那章立下了第一版文法,标签与 `&` 引用的活当时整个划到了下一章。咱们现在就来接这批活,从第一卷看过的现象重新问起。

## 名字留在源码里,数住进产物里

你在第一卷已经把现象看过两回了。“怎样描述和组织设备”那章里咱们写下过 `clocks = <&clk24>`,反编译回来它变成了 `clocks = <0x01>`,被引用的节点身上还多了一个咱们没写过的 `phandle = <0x01>`。那章的结尾咱们留了两个问题:编号是谁分的,重号怎么避免?这一章就来把它们回答掉,办法还是咱们的老一套:动手做实验,再回 dtc 的源码里核对。

咱们把源码层与字节层的分界说清。标签是写给读源码的人看的名字,它挂在节点的前头,别处的引用靠它指路。DTB 里却没有标签的位置,规范 v0.4 的 §6.2 有一句原话,咱们直译过来就是:“标签只用于设备树源格式,不编码进 DTB 二进制”。所以编译器要干的活,是把源码里所有靠名字表达的连接,换成产物里靠数字和路径表达的连接。咱们这一章盯着它换的过程,看看名字在哪一步被记了下来,号在哪一步发了下去,字节在哪一步被改写成了真值。

“构建系统实际上做了什么”那章里咱们还认过另一张脸:带 `-@` 编译的时候,产物里会多出一个名为 `__symbols__` 的节点,标签名又回来了。它与 phandle 是什么关系?咱们也放到本章的后半段讲清。

咱们照旧在 /tmp 里开工,目录的名字叫 /tmp/vol4ch14:

```shell
mkdir -p /tmp/vol4ch14
cd /tmp/vol4ch14
```

咱们用的版本是 dtc v1.8.1,与全仓锁定的一致,验证的日子是 2026-10-18。本章贴出的每条命令与输出都在我的电脑上真实跑过,你要是换别的版本来复现,报错的措辞可能有出入。

## 引用写在标签前面,编译照样过

头一个实验咱们就直奔前向引用,DTS 里最有味道的现象就是它。basic.dts 里的 taker@2000 要用两个时钟,它的 clocks 属性引用了 clk1 与 clk2,而定义它们的两个节点排在源码的后面:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <&clk1>, <&clk2>;
	};

	clk1: clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x4>;
		#clock-cells = <0>;
	};

	clk2: clock@104 {
		compatible = "demo,clock";
		reg = <0x104 0x4>;
		#clock-cells = <0>;
	};
};
```

```shell
dtc -I dts -O dtb -o basic.dtb basic.dts
dtc -I dtb -O dts basic.dtb
```

```dts
/dts-v1/;

/ {
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <0x01 0x02>;
	};

	clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x04>;
		#clock-cells = <0x00>;
		phandle = <0x01>;
	};

	clock@104 {
		compatible = "demo,clock";
		reg = <0x104 0x04>;
		#clock-cells = <0x00>;
		phandle = <0x02>;
	};
};
```

引用写在节点的前面,定义排在文件的后面,编译却安安静静地过了,咱们连一条告警都没见到。反编译的树里你能读到两处变化:taker@2000 的 clocks 变成了 `<0x01 0x02>`,两个名字都没了影子。clock@100 与 clock@104 的身上各多了一个 `phandle = <0x01>` 和一个 `phandle = <0x02>`,它们是 dtc 添上去的,咱们没有写过。

前向引用为什么能过?咱们到 dtc 的源码里看它的安排。读入源码的阶段,语法器按 dtc-parser.y 的文法规则处理数组元素,遇到 `&clk1` 的时候它并不找节点,而是在属性值里追加一个 32 位全 1 的占位数,再把引用的名字与位置记成一条 REF_PHANDLE 记号。整棵树读完了才轮到第二遍,检查器把树重新走了一遍,把每条记号都兑现成了真值。干这个活的函数叫 fixup_phandle_references,它的家在 checks.c,它按记号找到被引的节点,给被引的节点要一个 phandle,再用真实的数把占位数覆盖掉。前向引用能过的道理就在这儿:找节点的活被推迟到了全树成形之后,clk1 定义在文件的后面也不碍事,第二遍开始的时候它早就在树上了。

所以咱们在源码里写的每个引用都带着两类信息:名字是一类,想要的字节形态是另一类。这两样信息在 DTB 里都找不到落脚的地方,产物里只剩下被改写后的 4 个字节。咱们讲引用回填的时候,说的就是把这个兑现的动作做完整。

## 扩展节点的引用,为什么不能写在前面

属性值里的引用能前向,顶层的 `&标签 { }` 扩展写法却不行。咱们拿一对文件做对比,差别立刻就出来了。咱们的 fwd-ext.dts 把扩展写在了最前面,标签的定义藏在后面的根节点里:

```dts
/dts-v1/;

&clk1 {
	status = "okay";
};

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	clk1: clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x4>;
	};
};
```

```shell
dtc -I dts -O dtb -o fwd-ext.dtb fwd-ext.dts
```

```output
Error: fwd-ext.dts:3.7-5.3 Label or path clk1 not found
FATAL ERROR: Syntax error parsing input tree
```

咱们把顺序反过来就没事了。bwd-ext.dts 把根节点放在了前面,扩展跟在了后面:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	clk1: clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x4>;
	};
};

&clk1 {
	status = "okay";
};
```

```shell
dtc -I dts -O dtb -o bwd-ext.dtb bwd-ext.dts
dtc -I dtb -O dts bwd-ext.dtb
```

```dts
/dts-v1/;

/ {
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x04>;
		status = "okay";
	};
};
```

报错的位置说明了两类引用的待遇差别。`&clk1 { }` 走的是 dtc-parser.y 里另一条文法规则,读到这里的时候它必须当场拿到节点,拿不到的时候,它就报出 Label or path not found 的错误,连 FATAL 的措辞都换成了语法错的样子。属性值里的引用却走的是另一条路:解析时只做登记,兑现延后到全文读完的那一刻。你写内核风格的板级 dts 时,`&uart0 { status = "okay"; }` 总是排在 include 的后面,现在你知道了,这样的排法是有硬原因的。

bwd-ext 的反编译里还有一个细节,咱们单说它:clock@100 的身上没有 phandle。扩展引用干的只是把属性合并进目标节点,它不住在属性值的行列里:不需要编号,dtc 也就不给它分配了。分配只发生在引用要被回填成数的时刻,下一篇咱们就把分配的规则摸清。

这一篇咱们把两类引用的待遇分清了。属性值里的引用在解析阶段只做登记,兑现的活被推迟到了全树成形之后,所以前向的写法能安静地过。顶层的扩展引用却要在解析的当下拿到节点,于是内核风格的 dts 才总把 `&uart0 { }` 排在 include 的后面。第一卷留下的两个问题,编号是谁分的、重号怎么避免,咱们下一篇就动手回答。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. 属性值里的引用与顶层的扩展引用,dtc 分别在哪个阶段解析?前向引用对哪一种成立?
2. basic.dts 编译后反编译回来,taker@2000 的 clocks 变成了什么?两个 clock 节点的身上多了哪个咱们没写过的属性?
3. 扩展引用 `&clk1 { }` 写在根节点的前面,dtc 报什么错?报错的措辞走的是哪条路子?

<details>
<summary>参考答案(想好再展开)</summary>

1. 属性值里的引用在解析阶段只做登记,回填发生在整棵树成形后的检查阶段,所以前向引用成立。顶层扩展引用在解析的当下就要找到节点,前向的写法会报 `Label or path not found` 并按语法错退出。
2. clocks 变成了 `<0x01 0x02>`,两个名字都没了影子。clock@100 与 clock@104 的身上各多了一个 `phandle = <0x01>` 和一个 `phandle = <0x02>`,它们是 dtc 添上去的。
3. 报错是 `Error: fwd-ext.dts:3.7-5.3 Label or path clk1 not found` 与 `FATAL ERROR: Syntax error parsing input tree`,措辞走的是语法错的路子,连 FATAL 的样子都换了。

</details>

## 延伸阅读

本篇的机制叙述都能在规范与 dtc 自家的文档里对上,出处给你备在这里:

- [Devicetree Specification: 第 6 章源语言](https://devicetree-specification.readthedocs.io/en/latest/chapter6-source-language.html):标签只活在源格式、不进 DTB 的原话在 §6.2,本仓缓存的 v0.4 副本在 .claude/materials/devicetree-specification-v0.4.md。
- [dtc: dtc-parser.y](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/tree/dtc-parser.y):文法正本,数组内引用的占位数与记号、顶层扩展引用的当场解析,都在文法规则里。

咱们把正文引用的源码行为按本仓 reference/dtc 下的 1.8.1 副本核对过,实验全部在我的电脑上真实跑过,验证的日子是 2026-10-18,跑实验的版本是 dtc v1.8.1。
