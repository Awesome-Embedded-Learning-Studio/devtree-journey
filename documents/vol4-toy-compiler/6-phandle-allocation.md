---
title: "phandle 的号是谁分的,按什么顺序分?"
volume: 4
chapter: 14
section: 2
order: 142
description: "分配由引用触发,号跟着回填顺序走,一个节点挂两个标签也只发一个号,手写的号被计数器避开,重复号与 0 被 explicit_phandles 拦下,引用自己与借别人的号各见分晓,/omit-if-no-ref/ 让没人引用的节点整个退场,规律回 livetree.c 的 get_node_phandle 核对"
status: draft
---

# phandle 的号,是怎么发下来的?

“引用为什么能写在标签前面”那篇收尾的时候,第一卷留下的两个问题还在手上:编号是谁分的,重号怎么避免。答案都在 phandle 的分配器里,咱们这一篇把它摸清。咱们照旧在 /tmp/vol4ch14 里开工,用的版本还是 dtc v1.8.1。

## phandle 的号是谁分的,按什么顺序分

规则性的问题咱们用实验一条条归纳,拿不准的地方回源码核对。头一个问题:号按什么顺序分?order.dts 里的两个时钟都带着标签,taker@2000 引用后定义的 clk2,taker@3000 引用的是定义靠前的 clk1:

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

	clk2: clock@104 {
		compatible = "demo,clock";
		reg = <0x104 0x4>;
		#clock-cells = <0>;
	};

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <&clk2>;
	};

	taker@3000 {
		compatible = "demo,taker";
		reg = <0x3000 0x10>;
		clocks = <&clk1>;
	};
};
```

```shell
dtc -I dts -O dtb -o order.dtb order.dts
dtc -I dtb -O dts order.dtb
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
		phandle = <0x02>;
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

	taker@3000 {
		compatible = "demo,taker";
		reg = <0x3000 0x10>;
		clocks = <0x02>;
	};
};
```

要是号跟着标签的定义顺序走,拿到 1 的本该是 clk1。实验给的不是:clk2 拿了 1,clk1 拿了 2。咱们再想想上一篇读到的源码,答案就顺了:号是在第二遍回填的时候发的,检查器沿着树依次地走,taker@2000 排在了 taker@3000 的前面,它的 clocks 里的引用就头一个兑现,clk2 便成了第一个拿到号的节点。咱们观察到的行为是,号跟着引用被回填的顺序走,不跟标签在源码里的定义顺序。dtc 的手册没有记载它,咱们是靠实验加源码归纳的,源码里 get_node_phandle 的实现住在 livetree.c,咱们下面就去读它。

第二个问题咱们看节点与标签的数量:一个节点挂两个标签,会分到两个号吗?twolabel.dts 给同一个时钟挂了 fast 与 fclk 两个名字,引用咱们各写了一次:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	fast: fclk: clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x4>;
		#clock-cells = <0>;
	};

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clock-names = "bus", "core";
		clocks = <&fast>, <&fclk>;
	};
};
```

```shell
dtc -I dts -O dtb -o twolabel.dtb twolabel.dts
dtc -I dtb -O dts twolabel.dtb
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
		clock-names = "bus", "core";
		clocks = <0x01 0x01>;
	};
};
```

clocks 里的两个位置,咱们看到填的都是 1。phandle 认的是节点,标签只是节点的别名,不管别名挂了几个,发出去的号都只有一个。

第三个问题:没被任何引用用过的标签,它的节点会拿到号吗?idle.dts 里只有一个带标签的时钟,咱们谁都不去引用它:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	idleclk: clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x4>;
		#clock-cells = <0>;
	};
};
```

```shell
dtc -I dts -O dtb -o idle.dtb idle.dts
dtc -I dtb -O dts idle.dtb
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
	};
};
```

咱们看到产物里连 phandle 的影子都没有。分配是被引用触发的:没人引用的节点就不编号,树上连一个多余的属性都不留。你要是写了一个可能被引用也可能不被引用的节点,DTS 还备了 `/omit-if-no-ref/` 指令,咱们在本篇末尾看它。

第四个问题咱们看手写的号:源码里手写的 phandle,自动分配会让着它吗?explicit.dts 给 clk1 手写了 0x21,给 clk3 手写了 0x1,clk2 与 clk4 留给了自动分配:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	clk1: clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x4>;
		#clock-cells = <0>;
		phandle = <0x21>;
	};

	clk2: clock@104 {
		compatible = "demo,clock";
		reg = <0x104 0x4>;
		#clock-cells = <0>;
	};

	clk3: clock@108 {
		compatible = "demo,clock";
		reg = <0x108 0x4>;
		#clock-cells = <0>;
		phandle = <0x1>;
	};

	clk4: clock@10c {
		compatible = "demo,clock";
		reg = <0x10c 0x4>;
		#clock-cells = <0>;
	};

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <&clk1>, <&clk2>, <&clk3>, <&clk4>;
	};
};
```

```shell
dtc -I dts -O dtb -o explicit.dtb explicit.dts
dtc -I dtb -O dts explicit.dtb
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
		phandle = <0x21>;
	};

	clock@104 {
		compatible = "demo,clock";
		reg = <0x104 0x04>;
		#clock-cells = <0x00>;
		phandle = <0x02>;
	};

	clock@108 {
		compatible = "demo,clock";
		reg = <0x108 0x04>;
		#clock-cells = <0x00>;
		phandle = <0x01>;
	};

	clock@10c {
		compatible = "demo,clock";
		reg = <0x10c 0x04>;
		#clock-cells = <0x00>;
		phandle = <0x03>;
	};

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <0x21 0x02 0x01 0x03>;
	};
};
```

咱们把四个号摆在一起读。手写的 0x21 与 0x1 原样保留,引用处回填的也是手写值。自动分配的两个号是 2 和 3:clk2 分号的时候,计数器站在 1 的位置,发现 1 已经被 clk3 占了,便跳到了 2。轮到 clk4 的时候,2 也被占了,于是拿了 3。0x21 在远处没有被碰到吗?它会被跳过的前提是计数器走到了那儿,咱们的树上节点少,计数器压根没有走到过 0x21 的地盘,也就谈不上避让它了。咱们把规律归纳成一句:计数器从 1 起步,而且只往前走,而每次分配前它都沿着全树扫一遍,跳过已被占用的号,拿到了空号才发。

这句规律不是咱们猜的,livetree.c 里的 get_node_phandle 就是这么写的。函数里有一个从 1 起步的静态计数器,每次调用的时候它会沿着树查当前这个号是不是有了主人,有主人的号就加一继续查,查到了空号才登记,随后还给节点补上了 phandle 属性。静态计数器的意思是,一次编译里发过的号不会重来,重复也就不会出现了。咱们核对的副本在本仓的 reference/dtc 下,版本 1.8.1 与你机器上跑的 dtc 一致。

手写 phandle 的边界情况咱们也收进实验里。两个节点手写同一个号的话,dtc 的 explicit_phandles 检查会拦住它,dup-phandle.dts 里的两个时钟都写了 0x3:

```shell
dtc -I dts -O dtb -o dup-phandle.dtb dup-phandle.dts
```

```output
dup-phandle.dts:13.18-17.4: ERROR (explicit_phandles): /clock@104: duplicated phandle 0x3 (seen before at /clock@100)
ERROR: Input tree has errors, aborting (use -f to force output)
```

咱们再试 0 这个保留值:zero-phandle.dts 手写了 `phandle = <0x0>`,报错的出处还是 explicit_phandles:

```output
zero-phandle.dts:10.3-19: ERROR (explicit_phandles): /clock@100:phandle: bad value (0x0) in phandle property
ERROR: Input tree has errors, aborting (use -f to force output)
```

这两类错的退出码都是 2,产物也不见了。咱们接着看一种有趣的写法:让节点引用自己的标签,把 `phandle = <&clk1>` 写在 clk1 自己的身上。咱们拿 selfref.dts 试了它,编译顺利地过了,产物里这个节点拿到了 phandle 1。源码里对它的注释写得很直白:引用自己的意思就是请 dtc 给它发号,和有没有别的引用是无关的。反过来咱们再看借号的写法,borrow-phandle.dts 在 clk2 里写了 `phandle = <&clk1>`,把别人的号安在自己头上,dtc 的回应是:

```output
borrow-phandle.dts:12.18-16.4: ERROR (explicit_phandles): /clock@104: phandle is a reference to another node
ERROR: Input tree has errors, aborting (use -f to force output)
```

最后咱们看 `/omit-if-no-ref/`。它写在节点定义的前面,它的意思是:没人引用的节点就别进产物。omit.dts 给 idleclk 挂上了它,usedclk 则正常地被引用着:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	/omit-if-no-ref/ idleclk: clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x4>;
		#clock-cells = <0>;
	};

	usedclk: clock@104 {
		compatible = "demo,clock";
		reg = <0x104 0x4>;
		#clock-cells = <0>;
	};

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <&usedclk>;
	};
};
```

```shell
dtc -I dts -O dtb -o omit.dtb omit.dts
dtc -I dtb -O dts omit.dtb
```

```dts
/dts-v1/;

/ {
	#address-cells = <0x01>;
	#size-cells = <0x01>;

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

clock@100 整个不见了。引用在源码层的信息再一次显出了力量:一个节点进不进产物,取决于有没有引用落在它的身上。不过带 `-@` 编译的时候它会回来,咱们到讲符号表的那篇再看这个回合。

号的事到这里就齐了:分配是被引用触发的,计数器是从 1 起步的,发号的时候只往前走、避开已占的号,没人引用的节点连一个属性都不多占。可是引用回填出来的字节,凭什么 clocks 里是数、firmware 里是路径?咱们下一篇看位置怎样决定字节。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. dtc 按什么顺序给节点发 phandle?一个节点挂两个标签,会分到两个号吗?
2. 源码手写 `phandle = <0x21>` 与 `phandle = <0x1>`,另外两个被引用的节点自动分配,它们各拿到什么号,为什么?
3. 两个节点手写同一个 phandle,与手写 `phandle = <0x0>`,dtc 各报什么错?退出的码是多少?

<details>
<summary>参考答案(想好再展开)</summary>

1. 号按引用被回填的顺序发放,不按标签的定义顺序。两个标签指向的是同一个节点,所以号也只有一个,两处引用回填成了同一个数。
2. 手写的 0x21 与 0x1 原样保留。自动分配的节点拿到 2 和 3:计数器从 1 起步,发现 1 被手写占用就跳到 2,再次分配的时候 2 也被占用,于是发 3。0x21 没有被跳过,因为计数器压根没走到那儿。
3. 同一个号报 duplicated phandle,0 报 bad value (0x0) in phandle property,出处都是 explicit_phandles 检查,退出码交了 2,产物也不见了。

</details>

## 延伸阅读

本篇的发号规则与边界实验,出处给你备在这里:

- [Devicetree Specification: §2.3.3 phandle](https://devicetree-specification.readthedocs.io/en/latest/chapter2-devicetree-basics.html):标准属性的正式定义,还有“多数 dts 不手写 phandle,DTC 编译时自动插入”的注记。
- [dtc: livetree.c](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/tree/livetree.c):get_node_phandle 的家,从 1 起步的计数器与跳号逻辑就在函数体里。
