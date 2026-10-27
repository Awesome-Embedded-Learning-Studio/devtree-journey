---
title: "__symbols__ 是什么,又是给谁的?"
volume: 4
chapter: 14
section: 4
order: 144
description: "__symbols__ 的属性名是标签、值是完整路径,-@ 给所有带标签的节点强制发号,号的顺延落在检查与发号两个阶段的先后里,/omit-if-no-ref/ 被 -@ 翻盘,整套表是给 overlay 的路标,末了 edtc 的标签表加回填清单设计问出来,验收拿本章实验文件对拍 dtc v1.8.1"
status: draft
---

# 带 -@ 编译,标签名怎样回到产物里?

上一篇收尾的时候,咱们还欠着一个答案:带 `-@` 编译时多出来的 `__symbols__` 节点,它与 phandle 是什么关系?这一篇咱们就把它读透,末了再替咱们自己的编译器把设计问出来。实验咱们照旧在 /tmp/vol4ch14 里做。

## __symbols__:产物里另一套指路的系统

咱们带上 `-@` 再编一次 forms.dts,标签名便以另一副样子回到了产物里:

```shell
dtc -@ -I dts -O dtb -o forms-sym.dtb forms.dts
dtc -I dtb -O dts forms-sym.dtb
```

```dts
/dts-v1/;

/ {
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	clk1: clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x04>;
		#clock-cells = <0x00>;
		phandle = <0x01>;
	};

	intc: interrupt-controller@3000 {
		compatible = "demo,intc";
		reg = <0x3000 0x10>;
		interrupt-controller;
		#interrupt-cells = <0x01>;
		phandle = <0x02>;
	};

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <0x01>;
		interrupt-parent = <0x02>;
		interrupts = <0x05>;
		firmware = "/clock@100";
		mixed = "pair:", "/clock@100";
	};

	__symbols__ {
		clk1 = "/clock@100";
		intc = "/interrupt-controller@3000";
	};
};
```

多出来的 `__symbols__` 节点咱们分几层读。它的每个属性对应的是一个标签:属性名是标签的名字,值是节点的完整路径,没有标签的 taker@2000 就不在表里。反编译的树里标签也回来了,clk1 与 intc 又挂回了节点的前面,那是 dtc 的反编译器照着 `__symbols__` 把标签描了回去。还有一处容易被看漏的地方:两个被引节点本来就有 phandle,咱们在这里看不出新增,可咱们在 idle.dts 上试过,一个谁都没引用的标签,带 `-@` 编译后也拿到了 phandle 1,还进了符号表。`-@` 干的事于是多了一件:给所有带标签的节点强制发号,有没有引用都拦不住了。手册对 `-@` 的说明有一段原话,咱们直译过来就是:“在根节点生成一个 __symbols__ 节点。这个节点为每个标签包含一个属性,属性名是标签名,值是带标签节点的路径。”

咱们把路径的完整性放到嵌套的树上看,soc-board-style.dts 把设备挂在了 soc 子节点下:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	soc: soc@0 {
		compatible = "demo,soc";
		reg = <0x0 0x1000>;
		#address-cells = <1>;
		#size-cells = <1>;

		uart0: serial@1000 {
			compatible = "demo,uart";
			reg = <0x1000 0x100>;
			clocks = <&uartclk>;
		};

		uartclk: clock@800 {
			compatible = "demo,clock";
			reg = <0x800 0x4>;
			#clock-cells = <0>;
		};
	};
};
```

```shell
dtc -@ -I dts -O dtb -o soc-sym.dtb soc-board-style.dts
dtc -I dtb -O dts soc-sym.dtb | sed -n '/__symbols__/,$p'
```

```output
	__symbols__ {
		soc = "/soc@0";
		uart0 = "/soc@0/serial@1000";
		uartclk = "/soc@0/clock@800";
	};
};
```

三个值全是从根出发的完整路径。咱们再反过来看:一份没有任何标签的源文件带上 `-@`,产物里会是什么样?咱们在 nolabel.dts 上试过,反编译的全文如下,连 `__symbols__` 的影子都没有,可见有了标签才有表:

```shell
dtc -@ -I dts -O dtb -o nolabel-sym.dtb nolabel.dts
dtc -I dtb -O dts nolabel-sym.dtb
```

```dts
/dts-v1/;

/ {
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	serial@1000 {
		compatible = "demo,uart";
		reg = <0x1000 0x100>;
	};
};
```

`-@` 与引用回填的配合还有个顺序细节值得专门看。sym-order.dts 里的 zzz 排在树的前面,引用它的人一个都没有,咱们让排在后面的 aaa 被 taker 引用:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	zzz: clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x4>;
		#clock-cells = <0>;
	};

	aaa: clock@104 {
		compatible = "demo,clock";
		reg = <0x104 0x4>;
		#clock-cells = <0>;
	};

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <&aaa>;
	};
};
```

```shell
dtc -I dts -O dtb -o sym-order.dtb sym-order.dts
dtc -I dtb -O dts sym-order.dtb
dtc -@ -I dts -O dtb -o sym-order-sym.dtb sym-order.dts
dtc -I dtb -O dts sym-order-sym.dtb
```

咱们看不带 `-@` 的产物:

```dts
/dts-v1/;

/ {
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x04>;
		#clock-cells = <0x00>;
	};

	clock@104 {
		compatible = "demo,clock";
		reg = <0x104 0x04>;
		#clock-cells = <0x00>;
		phandle = <0x01>;
	};

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <0x01>;
	};
};
```

咱们再看带上 `-@` 的产物:

```dts
/dts-v1/;

/ {
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	zzz: clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x04>;
		#clock-cells = <0x00>;
		phandle = <0x02>;
	};

	aaa: clock@104 {
		compatible = "demo,clock";
		reg = <0x104 0x04>;
		#clock-cells = <0x00>;
		phandle = <0x01>;
	};

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <0x01>;
	};

	__symbols__ {
		zzz = "/clock@100";
		aaa = "/clock@104";
	};
};
```

咱们把两次的号摆在一起看:不带 `-@` 的时候,只有被引用的 aaa 拿到了 1,zzz 连号的影子都没有。带上 `-@` 后 aaa 的号还是 1,zzz 拿了 2。号为什么这么分?回填的时机在检查阶段,`-@` 的强制发号发生在检查之后,aaa 的号是回填的时候发的,轮到 zzz 的时候,1 已经被占用了,它便顺延到了 2。一次编译里两个阶段的前后顺序,就这样留在了号的大小上。这一段是咱们从实验加 dtc.c 的调用顺序里归纳的,dtc.c 里 process_checks 排在了 generate_label_tree 的前面,行为与源码对上了。

`-@` 还改变了 `/omit-if-no-ref/` 的结局。咱们让 omit.dts 带上 `-@` 再编一次,idleclk 回到了产物里,符号表也收下了它:

```shell
dtc -@ -I dts -O dtb -o omit-sym.dtb omit.dts
dtc -I dtb -O dts omit-sym.dtb | grep -A4 "__symbols__"
```

```output
	__symbols__ {
		idleclk = "/clock@100";
		usedclk = "/clock@104";
	};
```

道理与上一段是同一个:符号表的目标是给所有标签留路标,被引用与否就不再决定节点的去留。你在内核的 dts 里见到 `/omit-if-no-ref/` 的时候,它服务的是不带 `-@` 的普通编译,带 `-@` 的那套产物另有用途。

那么 `__symbols__` 到底是给谁的?给运行时的 overlay(设备树插件,叠到基础树上的增量描述)。overlay 引用基础树里的节点的时候,它的 dts 里没有基础树的标签,靠的就是基础树符号表里的路径。“构建系统实际上做了什么”那章咱们说过它是给运行时覆盖准备的路标,现在你能把它的内容逐字段讲出来了。它和 phandle 是并存的两套东西:phandle 是字节层给消费软件的连线编号,`__symbols__` 是字符串层给后续工具的路径表。前者的号由编译器分配,后者的表只是忠实地抄录标签。完整的 overlay 机制属于第五卷“怎样在不同阶段叠加修改”那章的主场,符号表咱们认到这里就够了。

## edtc 打算怎么做:一张标签表,两遍走

轮到咱们自己的编译器了。“怎样读懂一小部分 DTS”那章里咱们用 python 搓过子集文法的解析器,树咱们已经读得出来,但那棵树上还没有标签与引用的容身之处。本章的实验正好替 edtc 把设计问出来了,咱们把打算记在这里,落地的代码一行还没有:当前 edtc 的 src 里只有文件读取与字节序的底子,连解析器的影子都没有。

思路直接沿用 dtc 的两遍结构,动手之前咱们把它的合理性想了一遍。单遍为什么不行?前向引用是咱们的硬需求,内核风格的 dts 里 include 的文件与板级补丁层层叠叠,引用与定义出现的前后全靠巧合。单遍的做法要么禁止前向引用,要么在遇到引用的时候反复回扫,咱们两头都不想要。登记加延迟兑现的结构对错误的诊断也友好:标签表齐了之后,悬空引用能一次全部地报出来,而不用报一个停一个。

落到 edtc 的部件上,咱们打算这么分。解析阶段咱们维护一张标签表,键是标签的名字,值是节点的指针,遇到 `fast: fclk: clock@100` 的写法就把两个名字都指到同一个节点上,同一节点上的同名重复登记直接合并,轮到不同节点抢同名的时候,标签表把冲突原样记了下来,报错的事留给检查阶段统一去发,这样报错的位置信息最全。属性值里的引用在解析阶段不解析,咱们按位置把它们记进一张待回填清单,清单的每一条带着三类信息:引用的名字,值里的字节偏移,还有引用的类型,数组里的记成 phandle 型,数组外的记成 path 型。顶层的扩展引用不走清单的路子,它在解析的当下就要拿到节点,找不到的时候就立刻报错,报错的措辞向 dtc 的 `Label or path not found` 看齐,对拍的时候一眼就能认出来。树成形之后咱们跑第二遍,把待回填的清单沿着树走一遍:phandle 型的找标签表要节点,path 型的查路径,该写数的写数,该插字符串的插字符串。发号的分配器咱们单独做成一个部件,里面放一个从 1 起步的计数器和一个已占用号的集合,手写的 phandle 在检查阶段就登记进集合,自动分配的时候跳过集合里的号,这样 explicit.dts 里观察到的跳号行为自然复现。符号表的生成挂在 `-@` 一类的开关后面,开关打开之后咱们遍历活树,把标签的名字与完整路径写进 `__symbols__` 节点。

计划与现状的差距咱们如实交底,标签表、回填清单、分配器、符号表四个部件的代码一行都还没有。它们的验收方式倒是已经能定下来了,本章的每一份实验文件都是现成的测试用例,basic 到 forms 走的是正常路径,dup 系列与 dangling 系列走的是错误路径,产物的字节与报错的原文都拿 dtc v1.8.1 对拍。

## 收工,下一章逼近真实的输入

这一章咱们把“名字换数”的全过程走完了:引用在解析阶段被记成带类型的记号,第二遍照着记号完成了回填,phandle 的号由从 1 起步的计数器按回填顺序发放,并避开已占的号。重复标签与悬空引用各有各的报错时机,`-@` 则把标签名连同路径抄进了 `__symbols__`,给 overlay 留下了路标。你在源码里写的每一个 & 符号,到了产物里都能指出它变成的那几个字节。

可是咱们的玩具编译器离真实的 dts 还差得远。在真实的世界里,一份板级 dts 的开头往往是成串的 #include 与 #define,属性里还可能出现 `/incbin/` 的身影,多层文件叠出了最终的树。“如何逐步接近实际输入?”就是下一章的名字,咱们按需求把 include 与节点合并这些能力一个个加进 edtc,支持矩阵与拒绝测试也同步地建起来。咱们下一章见。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. `-@` 生成的 `__symbols__` 里,属性名与值各是什么?它与 phandle 是一套东西吗?
2. sym-order.dts 不带 `-@` 与带 `-@` 各编一次,zzz 的号为什么从无到有,又为什么是 2?
3. `/omit-if-no-ref/` 在不带 `-@` 与带 `-@` 的编译下,行为有什么差别?
4. edtc 打算用什么结构处理标签与引用?单遍的做法为什么被咱们否了?

<details>
<summary>参考答案(想好再展开)</summary>

1. 属性名是标签名,值是标签节点的完整路径。它与 phandle 是两套并存的东西,一个给后续工具按名字找路径,一个给消费软件按编号连线,互不替代。
2. 不带 `-@` 的时候没人引用 zzz,分配不会发生,连号的影子都没有。带 `-@` 后强制发号发生在检查阶段之后,aaa 的号是回填的时候发的,轮到 zzz 的时候 1 已被占用,它便顺延到了 2。
3. 不带 `-@` 的时候,没被引用的节点整个从产物里消失。带 `-@` 的时候节点会回来,因为符号表要给所有标签留路径,节点去留不再由引用决定。
4. 登记加延迟兑现的两遍结构:解析阶段维护标签表与待回填清单,第二遍沿着树兑现。单遍要么禁止前向引用,要么在遇到引用的时候反复回扫,咱们两头都不想要,标签表齐了之后悬空引用还能一次全部地报出来。

</details>

## 延伸阅读

本篇的符号表与 edtc 设计,出处给你备在这里:

- [dtc: manual.txt](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/tree/Documentation/manual.txt):dtc 手册,`-@` 条目的正式说法在这里。
