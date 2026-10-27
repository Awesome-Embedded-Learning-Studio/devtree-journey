---
title: "一个设备怎么写才算写得清楚?"
volume: 1
chapter: 2
section: 1
order: 21
description: "节点名字和单元地址怎么搭配,@ 与 reg 该在不在各挨什么警告,属性值的五种写法进了产物一律摊平成字节,反编译印出来的形式是猜的,咱们再拿 xxd 认大端和字符串结尾的零"
status: draft
---

# 一个设备怎么写,才算写得清楚?

“改一行 DTS,产物发生了什么”那章里咱们只守着一个串口节点,你改一个属性、编译、反编译,这个循环已经走熟了。真实板子的东西可不止一个串口:UART、I2C、SPI、GPIO,还有时钟、内存这样的成员,几百个节点的家当挤在了一棵树里,而且描述还常常分在了好几个文件里。设备多了起来,两个问题也就冒了出来:一个东西怎么写才算写得清楚?一堆文件怎么分工才算管得住?这一章咱们把两件事分开办:本篇和下一篇办描述,组织的事单独一篇办。描述的头一件事就在本篇:节点怎么起名,属性的值有哪几副面孔。套路还是那一章的老办法:认一种写法就编译一回,再到产物里看它变成了什么。动手的位置照旧,你在自己电脑上建一个工作目录:

```shell
mkdir -p /tmp/dt-ch2
cd /tmp/dt-ch2
```

本仓验证的工具是 dtc v1.8.1,咱们跑命令的日子是 2026-10-18。

## 节点几十个,名字怎么起才不乱

设备树里节点的名字分成两截:@ 前面的部分叫节点的名字(node-name),@ 后面的部分是单元地址(unit-address)。两截各有各的要求,咱们挨个看。

咱们给节点起名,要按设备的通用大类来,uart、i2c、gpio 这样的名字就是推荐写法。名字的长度在 1 到 31 个字符之间,能用的字符只有数字、大小写字母,以及 `, . _ + -` 几个额外的符号,开头的字符还得是字母。同层节点的名字不能重复,也不能跟同层的属性名混在一起。单元地址跟着 `reg` 走:节点的 `reg` 头一个地址是什么,@ 后面写的就是它,没有 `reg` 的节点,@ 就干脆省了。

咱们写一份 namecases.dts,把三种起名的路数一次试齐:

```dts
/dts-v1/;

/ {
	chosen {
		bootargs = "console=ttyS0";
	};

	leds {
		compatible = "demo,leds";
	};

	flash@0 {
		compatible = "demo,flash";
	};
};
```

咱们来编译它:

```shell
dtc -I dts -O dtb -o namecases.dtb namecases.dts
```

咱们拿到的输出只有一行警告:

```output
namecases.dts:12.10-14.4: Warning (unit_address_vs_reg): /flash@0: node has a unit name, but no reg or ranges property
```

`chosen` 和 `leds` 的身上没有 `reg`,@ 自然也就省了,咱们这么写不光合法,还正是规范要求的写法。`flash@0` 带了 @ 却拿不出 `reg`,dtc 就警告了。咱们把搭配反过来也试了一把,新文件的名字是 reg-no-unit.dts,内容是一个带 `reg` 的节点起名时不带 @:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	uart {
		compatible = "demo,uart";
		reg = <0x1000 0x100>;
	};
};
```

咱们编译它:

```shell
dtc -I dts -O dtb -o reg-no-unit.dtb reg-no-unit.dts
```

咱们拿到的警告换了个说法:

```output
reg-no-unit.dts:7.7-10.4: Warning (unit_address_vs_reg): /uart: node has a reg or ranges property, but no unit name
```

名字里的符号越界又是什么待遇?咱们把感叹号塞进节点的名字,存成了 badchar.dts:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	uart!0 {
		reg = <0x1000 0x100>;
	};
};
```

这回咱们连编译都过不去:

```shell
dtc -I dts -O dtb -o badchar.dtb badchar.dts
```

```output
Error: badchar.dts:7.6-7 syntax error
FATAL ERROR: Unable to parse input tree
```

还有一个容易误会的地方,咱们把它单独试一遍:@ 后面的地址跟 `reg` 的数值对不上,dtc 会不会管?咱们故意写岔一份 badname.dts,让节点挂上 `serial@2000` 的名字,`reg` 的起始地址却给了 0x1000:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	serial@2000 {
		compatible = "demo,uart";
		reg = <0x1000 0x100>;
	};
};
```

咱们编译它,再反编译回来看它的结果:

```shell
dtc -I dts -O dtb -o badname.dtb badname.dts; echo "exit=$?"
dtc -I dtb -O dts badname.dtb | grep serial
```

咱们拿到的输出如下:

```output
exit=0
	serial@2000 {
```

编译居然一声不吭地通过了,退出码也给了 0,`serial@2000` 也原样待在反编译的输出里。咱们把观察说准:dtc 检查的是 @ 与 `reg` 该不该搭配,至于单元地址的数值跟 `reg` 对不对得上,它默认是不查的。规范要求单元地址必须与 `reg` 的第一个地址保持一致,这个一致性得靠写的人自己守,或者交给更严格的检查工具。名字进了产物就是字符串的一部分,写岔了也照样跟着住进去。

## 属性的值有哪几副面孔

名字起好了,咱们往节点里放信息。属性就是咱们写了一路的“名字 = 值”,值的写法常见的有五种:字符串、字符串列表、cells、字节串,还有混着写的。咱们把五种一次全写进一份 props.dts:

```dts
/dts-v1/;

/ {
	compatible = "demo,props";
	model = "Demo Props Board";

	a-string = "hello";
	a-string-list = "alpha", "beta", "gamma";
	one-cell = <0x1000>;
	cell-list = <0x11 0x22 0x33>;
	bytes-three = [01 02 3a];
	bytes-four = [01 02 3a 4f];
	mixed = "text", <0x10 0x20>, [aa bb];
};
```

咱们编译再反编译:

```shell
dtc -I dts -O dtb -o props.dtb props.dts
dtc -I dtb -O dts props.dtb
```

咱们拿回来的树是这个样子的:

```dts
/dts-v1/;

/ {
	compatible = "demo,props";
	model = "Demo Props Board";
	a-string = "hello";
	a-string-list = "alpha", "beta", "gamma";
	one-cell = <0x1000>;
	cell-list = <0x11 0x22 0x33>;
	bytes-three = [01 02 3a];
	bytes-four = <0x1023a4f>;
	mixed = [74 65 78 74 00 00 00 00 10 00 00 00 20 aa bb];
};
```

咱们逐行对照。字符串、字符串列表、cell 列表、三个字节的字节串都原样回来了,`bytes-four` 却变了脸,四个字节回来被印成了尖括号里的 `<0x1023a4f>`。`mixed` 的变化更彻底,回来干脆成了一长串字节。咱们想解释它,就得把下面这件事立住了:产物里存的只有字节,尖括号、方括号都是源码层的写法,进了 DTB 一律摊平成字节。印出来的形式是 dtc 猜的:像文本又以零收尾的值按字符串印,长度恰好被 4 整除的按 cell 印,剩下的按字节串印。`bytes-four` 的长度恰好被 4 整除,正好落进按 cell 印的猜测里。`mixed` 的情况更直接:里头混着印不出来的字节,长度又不是 4 的倍数,dtc 只好把它按字节串印了出来。所以反编译回来的形式能帮咱们查值,不能当源码写法的凭据。

咱们拿 xxd 直接把产物打开:

```shell
xxd props.dtb
```

我从输出里挑了几行贴给你:

```output
00000080: 0000 0011 6865 6c6c 6f00 0000 0000 0003  ....hello.......
00000090: 0000 0011 0000 001a 616c 7068 6100 6265  ........alpha.be
000000a0: 7461 0067 616d 6d61 0000 0000 0000 0003  ta.gamma........
000000b0: 0000 0004 0000 0028 0000 1000 0000 0003  .......(........
000000c0: 0000 000c 0000 0031 0000 0011 0000 0022  .......1......."
00000100: 7465 7874 0000 0000 1000 0000 20aa bb00  text........ ...
```

有四个细节值得咱们停下来认。`a-string` 的 hello 变成了 `68 65 6c 6c 6f` 再跟一个 `00`,字符串带着结尾的零进产物,机器拿这个零切字符串的边界。字符串列表的样子就是三个字符串各自带零连着排,你能在输出里认出 alpha、beta、gamma 三个词。`one-cell` 的 0x1000 排成了 `00 00 10 00`,高位字节排在了前面,cell 的大端约定在字节里也守着。`mixed` 的各段字节依次连排,text 的尾巴零、两个 cell 的八个字节、末尾的 aa bb,全都肩并肩地躺在一起。

写法也不是咱们随手挑的。binding 会告诉咱们某个属性该用哪种写法,咱们照着写,读树的人和读树的软件就对得上。常见的搭配是 compatible 用字符串,地址和长度用的是 cells,MAC 地址这类天生按字节的东西用字节串。

值的五种写法到这儿就认齐了。可咱们写了一路的 `reg` 还压着一层疑问:尖括号里那串数,哪几个算地址?哪几个算长度?切法的声明写在哪儿、缺了会怎样,咱们下一篇把它办清楚。

## 本节自检

文章读完了,你拿下面的小问题验一验自己。

1. `flash@0` 没写 `reg`,dtc 抱怨了什么?反过来,节点写了 `reg` 却不带 @,dtc 又是什么态度?
2. 节点的名字里能用哪些字符?开头的字符有什么要求?同层的两个节点能重名吗?
3. 反编译看到 `bytes-four = <0x1023a4f>`,能据此断定源码里写的是尖括号吗?
4. hello 这样的字符串进了产物,字节是什么样子?结尾跟上的那个零是干什么的?

<details>
<summary>参考答案(想好再展开)</summary>

1. 前者挨了警告,说它有单元地址却缺 `reg` 或 `ranges`。后者同样挨警告,说它有 `reg` 却没有单元名。@ 与 `reg` 要么都在,要么都不在。
2. 能用的字符是数字、大小写字母,外加 `, . _ + -` 几个符号,长度得在 1 到 31 个字符之间,开头的字符还得是字母。同层节点的名字不能重复,也不能跟同层的属性名混在一起。
3. 不能。产物里只有字节,反编译打印的形式是 dtc 按字节长度猜的,长度被 4 整除就印成 cell,源码当时可能写的是字节串。
4. hello 变成 `68 65 6c 6c 6f`,后面再跟一个 `00`。字符串带着结尾的零进产物,机器拿这个零切字符串的边界。

</details>

## 延伸阅读

本篇的条款出处与工具文档,给你备好了:

- [Devicetree Specification 官方页](https://www.devicetree.org/specifications/):节点的起名条款在 §2.2.1,本仓缓存的是 v0.4 版本。
- [dtc 手册(上游仓库)](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/tree/Documentation/manual.txt):dtc 的命令行选项与各类告警的官方说明。

咱们引用的条款来自规范 v0.4(本仓缓存副本),正文里的命令与输出全部在本机真实运行过,验证环境的版本是 dtc v1.8.1,验证的日子是 2026-10-18。
