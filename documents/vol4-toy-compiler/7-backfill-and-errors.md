---
title: "同一个引用回填出什么字节,写错的树怎么拦?"
volume: 4
chapter: 14
section: 3
order: 143
description: "数组里的引用回填成 4 字节的 phandle 数,数组外的引用回填成完整路径字符串,差异在解析阶段就记成了 REF_PHANDLE 与 REF_PATH 两种记号,dts 进 dts 出让活树把引用写回名字形态,重复标签被 duplicate_label 拦下,悬空引用按位置报三种错,报错原文与退出码全是实测"
status: draft
---

# 同一个引用,回填成什么,写错了怎么拦?

“phandle 的号是谁分的,按什么顺序分”那篇把发号的规则摸清了,号的事算是交了底。上一篇收尾的时候咱们留了一层悬念:同样是引用,clocks 里的回填成了数,firmware 里的回填成了字符串,差别由什么定?咱们这一篇把几种位置一次摆全,实验咱们照旧在 /tmp/vol4ch14 里做。

## 同一个引用,写进不同的属性,回填出不同的字节

引用回填成什么,取决于它所在的位置。dtc 自家的 dts-format.txt 说法很干脆:数组里的引用展开成节点的 phandle,数组外的引用展开成节点的完整路径。咱们用 forms.dts 把几种位置一次摆全:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	clk1: clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x4>;
		#clock-cells = <0>;
	};

	intc: interrupt-controller@3000 {
		compatible = "demo,intc";
		reg = <0x3000 0x10>;
		interrupt-controller;
		#interrupt-cells = <1>;
	};

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <&clk1>;
		interrupt-parent = <&intc>;
		interrupts = <5>;
		firmware = &clk1;
		mixed = "pair:", &clk1;
	};
};
```

```shell
dtc -I dts -O dtb -o forms.dtb forms.dts
dtc -I dtb -O dts forms.dtb
```

```dts
/dts-v1/;

/ {
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x04>;
		#clock-cells = <0x00>;
		phandle = <0x01>;
	};

	interrupt-controller@3000 {
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
};
```

咱们逐个属性对照。clocks 与 interrupt-parent 的引用待在尖括号里,回填成了 4 字节的数,这是消费软件拿去连线用的形态。firmware 的引用没有尖括号,回填成了字符串 `"/clock@100"`,字节内容是路径外加结尾的零字节。mixed 则把字符串与引用拼在了一起,回填后的两段字符串首尾相接。源码里凭什么区分?读入阶段的记号类型就不同:数组里的引用记的是 REF_PHANDLE,数组外的引用记的是 REF_PATH,第二遍里各有各的兑现函数,前者写的是数,后者插的是路径字符串,兑现后者的函数叫 fixup_path_references,住在咱们已经熟悉的 checks.c 里。

回填前后的对照咱们不用肉眼去找,一条 diff 就能看清楚了。dtc 支持 dts 进 dts 出的走法,让它把自己回填后的树重新打印成源码:

```shell
dtc -I dts -O dts -o forms-resolved.dts forms.dts
diff -u forms.dts forms-resolved.dts
```

```output
--- forms.dts	2026-10-18 14:57:17.303086938 +0800
+++ forms-resolved.dts	2026-10-18 14:57:22.351146545 +0800
@@ -1,20 +1,22 @@
 /dts-v1/;

 / {
-	#address-cells = <1>;
-	#size-cells = <1>;
+	#address-cells = <0x01>;
+	#size-cells = <0x01>;

 	clk1: clock@100 {
 		compatible = "demo,clock";
-		reg = <0x100 0x4>;
-		#clock-cells = <0>;
+		reg = <0x100 0x04>;
+		#clock-cells = <0x00>;
+		phandle = <0x01>;
 	};

 	intc: interrupt-controller@3000 {
 		compatible = "demo,intc";
 		reg = <0x3000 0x10>;
 		interrupt-controller;
-		#interrupt-cells = <1>;
+		#interrupt-cells = <0x01>;
+		phandle = <0x02>;
 	};

 	taker@2000 {
@@ -22,8 +24,8 @@
 		reg = <0x2000 0x10>;
 		clocks = <&clk1>;
 		interrupt-parent = <&intc>;
-		interrupts = <5>;
-		firmware = &clk1;
-		mixed = "pair:", &clk1;
+		interrupts = <0x05>;
+		firmware = "/clock@100";
+		mixed = "pair:", "/clock@100";
 	};
 };
```

diff 里数字补零一类的变化咱们略过,值得看的是三处:两个被引的节点各多了一行 phandle,firmware 与 mixed 里的引用换成了路径字符串。diff 里还有一处没变的,它反而最要紧。clocks 与 interrupt-parent 在回填后的源码里,仍然是原来的 `<&clk1>` 与 `<&intc>`。dts 出 dts 走的是内存里的活树,树的身上还挂着标签与记号,打印源码的时候它把引用又写回了名字的形态。咱们在 DTB 的反编译里看到的才是字节层的真相,活树打印出来的源码里名字还活着。咱们把两条路各看一眼,你就同时见到了回填前的登记与回填后的字节。

咱们还能直接拿路径当引用。pathref.dts 的时钟没有标签,taker 的引用写成了 `<&{/clock@100}>`:

```shell
dtc -I dts -O dtb -o pathref.dtb pathref.dts
dtc -I dtb -O dts pathref.dtb
```

```dts
/dts-v1/;

/ {
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x04>;
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

被引用的节点连标签都没有,号照样发了。咱们由此看出,分配的触发者是引用这个动作,标签只是让引用写起来方便的语法糖。

字节层的真相到这里看全了:数组里的引用回填成了 4 字节的数,数组外的引用回填成了路径字符串,连没有标签的节点也能拿路径引用到。机制顺了,下面咱们专看写错的树,重复的标签与悬空的引用,看 dtc 拿什么把它们拦下。

## 写错了会怎样:重复标签与悬空引用

报错也是机制的一部分,咱们把两类经典的错都真跑一遍。dup-label.dts 给两个不同的节点挂了同一个标签 clk1:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	clk1: clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x4>;
	};

	clk1: clock@104 {
		compatible = "demo,clock";
		reg = <0x104 0x4>;
	};

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <&clk1>;
	};
};
```

```shell
dtc -I dts -O dtb -o dup-label.dtb dup-label.dts
```

```output
dup-label.dts:12.18-15.4: ERROR (duplicate_label): /clock@104: Duplicate label 'clk1' on /clock@104 and /clock@100
ERROR: Input tree has errors, aborting (use -f to force output)
```

duplicate_label 检查把它拦了下来,报错里两个节点的路径写得清清楚楚,咱们量到的退出码是 2,产物也不见了。还有个有意思的现象,重复的标签挂在同一个节点身上并不算错。咱们在 twolabel.dts 里挂的 fast 与 fclk 是两个不同的名字,而同一个名字在同一节点上重复出现的时候,dtc 也把它当作同一个标签了。

悬空引用的报错按位置分三种,咱们一种一种看。报错的第一种形态出在数组里,dangling-cell.dts 引用了哪儿都不存在的 ghost:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <&ghost>;
	};
};
```

```shell
dtc -I dts -O dtb -o dangling-cell.dtb dangling-cell.dts
```

```output
dangling-cell.dts:7.13-11.4: ERROR (phandle_references): /taker@2000: Reference to non-existent node or label "ghost"

ERROR: Input tree has errors, aborting (use -f to force output)
```

报错的第二种形态出在数组外,咱们让 dangling-path.dts 写的是 `firmware = &ghost`,报错的检查名换成了 path_references,其余的措辞一字不差:

```output
dangling-path.dts:7.13-11.4: ERROR (path_references): /taker@2000: Reference to non-existent node or label "ghost"

ERROR: Input tree has errors, aborting (use -f to force output)
```

第三种报错咱们用扩展引用来触发,dangling-ext.dts 写了 `&ghost { }`:

```output
Error: dangling-ext.dts:13.1-7 Label or path ghost not found
FATAL ERROR: Syntax error parsing input tree
```

三种报错的阶段与退出码都不同,咱们把它们排开看。数组内外的两种都在第二遍被检查器拦下,报错里带着检查的名字,退出码交了 2。扩展引用的形态则在读入阶段就死了,退出码交了 1,措辞走的是语法错的路子,跟 fwd-ext.dts 的报错同一个样子。你排查一份编不过的 dts 时,看到 FATAL ERROR 配 Syntax error 的组合,问题多半出在结构或者扩展引用的顺序上。看到的是 ERROR 配检查名的组合,问题多半藏在属性值的引用里。

三类报错排开了,排查的线索也就齐了:咱们看到 FATAL 配语法错的时候,就去查结构与扩展引用的顺序,看到 ERROR 配检查名的时候,就去查属性值里的引用。本章第一篇开头咱们还留过一个问话:带 `-@` 时多出来的 `__symbols__` 节点,它与 phandle 是什么关系?咱们下一篇就交答案。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. `clocks = <&clk1>` 与 `firmware = &clk1` 回填出来的字节有什么不同?决定差异的信息在哪个阶段就记下了?
2. dtc 走 dts 进 dts 出的路线时,clocks 里的引用被打回了什么形态?它与 DTB 反编译里看到的为什么不一致?
3. 被引用的节点连标签都没有,phandle 的号还发吗?分配的触发者到底是什么?
4. 两个不同的节点挂同一个标签,dtc 报什么错?重复的标签挂在同一个节点身上,算错吗?
5. 悬空引用的三种报错分别在哪个阶段被拦下?退出码各是多少?

<details>
<summary>参考答案(想好再展开)</summary>

1. 尖括号里的引用回填成 4 字节的 phandle 数,尖括号外的引用回填成完整路径字符串加结尾零字节。差异由解析阶段记下的记号类型决定,REF_PHANDLE 与 REF_PATH 各有对应的兑现函数。
2. 打回了名字的形态,仍然是原来的 `<&clk1>`。dts 出 dts 走的是内存里的活树,树的身上还挂着标签与记号,DTB 的反编译里看到的才是字节层的真相。
3. 号照样发。分配的触发者是引用这个动作,标签只是让引用写起来方便的语法糖。
4. duplicate_label 检查把它拦下,报错里两个节点的路径写得清清楚楚,退出码是 2,产物也不见了。同一个节点身上同名重复不算错,dtc 把它当作同一个标签了。
5. 数组内外的两种都在第二遍被检查器拦下,报错里带着检查的名字,退出码交了 2。扩展引用的形态在读入阶段就死了,退出码交了 1,措辞走的是语法错的路子。

</details>

## 延伸阅读

本篇的回填形态规则与错误检查,出处给你备在这里:

- [dtc: dts-format.txt](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/tree/Documentation/dts-format.txt):dtc 自己写的 DTS 格式说明,数组内引用展开成 phandle、数组外引用展开成路径的规则在这里。
- [dtc: checks.c](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/tree/checks.c):fixup_phandle_references 与 fixup_path_references 住在这里,duplicate_label 与 explicit_phandles 等检查也都在。
