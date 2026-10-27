---
title: "cpp 和 dtc 怎么接力,头文件去哪里找?"
volume: 1
chapter: 3
section: 1
order: 31
description: "带 #include 和 #define 的源码走一遍 cpp 加 dtc 的接力,宏展开、行标记和反编译对拍都看得见,尖括号只查 -I 给的路径,引号连当前目录一起查,拿掉 -I 听 cpp 报错,dtc 自带的 /include/ 不认宏,带宏的源码非过 cpp 不可"
status: draft
---

# cpp 和 dtc 怎么接力,头文件去哪里找?

## 前两章你敲的命令,内核构建也在敲

“改一行 DTS,产物发生了什么”那章里你亲手跑过 dtc,把一份小源码编成了 DTB,又把它反编译了回来。“怎样描述和组织设备”那章咱们认过了 dtsi 的分层写法,标签和引用你也混了个脸熟。可你回头想想,前两章的每一条编译命令,都是你自己一个字母一个字母敲出来的。

真项目里没人这么干。一份内核源码里躺着几百块板子的 dts,一次完整构建要把它们的 DTB 全部编出来,让人挨个手敲是不现实的。替你敲的是构建系统:内核那边叫 kbuild(内核的构建系统,咱们下文细说),U-Boot 那边沿用同一套 make 驱动的路子。你往它们的构建过程里看一眼,下场的工具会让你眼熟:cpp 干的是文本层面的归拢,dtc 干的是从文本到二进制的编译,Makefile 在旁边替咱们调度。

本章的活儿也就清楚了。咱们在 /tmp 里亲手把流水线搭一遍:用带 #include 和 #define 的源码走一遍 cpp 加 dtc 的接力,弄清头文件的查找路径,见一见真实的告警,再看 -@ 往产物里多塞了什么。最后咱们回到内核和 U-Boot,看看同一对工具在真实构建里是怎么被串起来的。

## 备料:三个小文件,搭出要预处理的现场

咱们把 cpp 的身份交代清楚:它指的是 C 预处理器(preprocessor,编译前的文本加工阶段就叫预处理),GCC 工具家族里专管井号指令的工具,跟 C++ 是没有关系的。它认 #include(把别的文件原样搬进来)和 #define(定一条替换用的宏,宏名出现的地方一律换成给定的内容),其余的语法一概不看。仓库里的 edtc 工程将来自己写前端时也得面对它,不过那是后面卷的事了。

咱们照旧在 /tmp 开工,目录的名字就叫 /tmp/lab-build,里面还给 include/ 留了子目录:

```shell
mkdir -p /tmp/lab-build/include
cd /tmp/lab-build
```

三个文件是这么分工的,咱们从宏头看起。include/acme-regs.h 的全文:

```c
#define ACME_UART_BASE  0x1000
#define ACME_UART_SZ     0x100
#define ACME_LED_BASE    0x8
#define STATUS_OKAY      "okay"
```

内核里干这活的目录叫 include/dt-bindings/,放的全是给 dts 共享的常量,咱们实验里的 include/ 模仿的就是它。宏的值有数字也有字符串,替换的时候原样搬过去。

接着是描述 SoC 那层的 soc.dtsi,寄存器地址咱们全交给宏:

```dtsi
/ {
	compatible = "acme,soc1000";
	#address-cells = <1>;
	#size-cells = <1>;

	uart0: serial@1000 {
		compatible = "acme,uart";
		reg = <ACME_UART_BASE ACME_UART_SZ>;
	};
};
```

咱们再看板级的入口 board.dts,它的位置跟宏头不同:宏头住进了子目录,它待的位置是最外层。

```dts
/dts-v1/;

#include <acme-regs.h>
#include "soc.dtsi"

/ {
	model = "ACME Lab Board";

	led0: led@8 {
		compatible = "acme,led";
		reg = <ACME_LED_BASE 0x4>;
		status = STATUS_OKAY;
	};
};
```

两个 #include 的括号形状不一样,差别的后果马上就能看到,咱们到下一节细说。board.dts 自己也有一个标签和几个用宏写的属性,等会儿正好拿来看 -@ 的效果。

## cpp 归拢文本,dtc 编译成二进制

咱们让接力开跑,第一步在你电脑上敲这个:

```shell
cpp -nostdinc -I include -undef -D__DTS__ -x assembler-with-cpp board.dts -o board.pp.dts
```

咱们把几个参数的意思说清:`-nostdinc` 的意思是不去系统目录找头文件,`-I include` 的意思是额外补一条查找路径,`-undef` 的意思是把 C 环境预置的宏收掉,`-D__DTS__` 的意思是补一个空宏当身份标记,`-x assembler-with-cpp` 的意思是按汇编的宽松章法读输入。dts 又不是照 C 的语法写的,要的恰恰是这样的宽松。内核构建给 cpp 传的也是同一串意思,咱们在主线脚本里核对到过。

头一步干完了,咱们看看 cpp 交出来的中间文件:

```shell
cat board.pp.dts
```

```output
# 0 "board.dts"
# 0 "<built-in>"
# 0 "<command-line>"
# 1 "board.dts"
/dts-v1/;

# 1 "include/acme-regs.h" 1
# 4 "board.dts" 2
# 1 "soc.dtsi" 1
/ {
	compatible = "acme,soc1000";
	#address-cells = <1>;
	#size-cells = <1>;

	uart0: serial@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
	};
};
# 5 "board.dts" 2

/ {
	model = "ACME Lab Board";

	led0: led@8 {
		compatible = "acme,led";
		reg = <0x8 0x4>;
		status = "okay";
	};
};
```

值得停下的是这几处。宏全没了:reg 里的 0x1000、0x100、0x8 和 `status` 的 `"okay"`,都是展开后的样子,acme-regs.h 在原地只留了一行笔记,四个 #define 全被消费掉了,文件里没剩下能输出的内容。soc.dtsi 的全文嵌了进来,你的源文件和被包含的文件,到了 cpp 手里已经是一整份纯文本。还有那些 `# 数字 "文件名"` 形式的行,它们的名字叫行标记(line marker),是 cpp 的笔记,dtc 是认得它们的。开头几行 `<built-in>`、`<command-line>` 说的是 cpp 自己的事,咱们不用理。最妙的是 `#address-cells` 开头也是井号,却原样放行了:它不是 cpp 认识的指令,汇编模式下 cpp 对认不出的井号行网开一面。缺了这样的网开一面,dts 根本过不了 cpp 这一关。

咱们接着把中间文件交给 dtc:

```shell
dtc -I dts -O dtb -o board.dtb board.pp.dts
ls -l board.dtb
```

```output
.rw-r--r-- 359 charliechen 18 Oct 13:34 board.dtb
```

本机实测的版本跟全仓锁定的一致:dtc v1.8.1,cpp 用的是 GCC 16.2.1,咱们验证的日子是 2026-10-18。`ls -l` 的格式随系统不同,你认大小就够了,我的机器上是 359 字节。

咱们反编译回来验一眼:

```shell
dtc -I dtb -O dts board.dtb
```

```dts
/dts-v1/;

/ {
	compatible = "acme,soc1000";
	#address-cells = <0x01>;
	#size-cells = <0x01>;
	model = "ACME Lab Board";

	serial@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
	};

	led@8 {
		compatible = "acme,led";
		reg = <0x08 0x04>;
		status = "okay";
	};
};
```

soc.dtsi 和 board.dts 各写了一个根节点,合起来却成了一棵树。同名节点的合并,你在“怎样描述和组织设备”那章里靠 dtsi 已经用过了,现在你知道了,把两份文本拼在一起的是 cpp。你还会看到标签没影了:uart0 和 led0 都不在,产物里本来就是不留标签的,这跟你前两章见到的一致。

行标记的用处,咱们故意惹一个错看看。把 soc.dtsi 里的 ACME_UART_BASE 改成哪儿都没定义的 TYPO_CONST,咱们再把两步重新跑一遍:

```output
Lexical error: soc.dtsi:8.10-20 Unexpected 'TYPO_CONST'
FATAL ERROR: Syntax error parsing input tree
```

dtc 读的明明是合并后的 board.pp.dts,报错却直指 soc.dtsi 的第 8 行,行标记就是干这个的。顺带你也见到了宏没展开时的报错长相:dtc 到了这儿两眼一抹黑,它没法知道你写的原本是个宏名,只报了个 Unexpected。你要是图清爽给 cpp 加上 -P 抹掉行标记,咱们实测过,同一个错就报在 board.pp.dts 的第 8 行了,指回原始文件的好处全没了。

接力咱们完整走了一遍,编译和反编译都对上了。board.dts 里两个 #include 的括号形状不一样,查找路径的规则还没说开,咱们接下来就把它问明白。

## 头文件去哪里找:cpp 的 -I 与 dtc 自带的 include

上一节的编译之所以能成,靠的是 `-I include` 把查找路径配对了。咱们把 -I 拿掉再跑一次,听听 cpp 的抱怨:

```shell
cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp board.dts -o /dev/null
```

```output
board.dts:3:23: error: no include path in which to search for acme-regs.h
    3 | #include <acme-regs.h>
      |                       ^
```

报错落在尖括号的头上。规则咱们直接总结:尖括号形式只查 -I 给出的路径,咱们又开着 -nostdinc,系统默认路径也被收走了,于是哪儿都找不到了。引号形式会把当前文件所在的目录也算进查找范围,soc.dtsi 就是这么被找到的,咱们从头到尾没为它配过路径。内核的真实场景里 -I 指向的是源码树专门的目录,include/dt-bindings/ 的入口就挂在这样一类路径上,所以板级的 dts 能随手写 `#include <dt-bindings/...>`,这个挂法我写这篇时在主线构建脚本里核对过。咱们的小实验用一个 include/ 目录,演的就是同一回事。

除了 cpp 的路线,dtc 自己也带了一套搬文件的写法。咱们把不带宏的 soc-plain.dtsi 放进 dtsi/ 子目录,内容跟 soc.dtsi 的一样,只是宏换成了数字:

```dtsi
/ {
	compatible = "acme,soc1000";
	#address-cells = <1>;
	#size-cells = <1>;

	uart0: serial@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
	};
};
```

咱们再写一个压根不经过 cpp 的 native.dts,用 dtc 自带的 /include/ 指令把文件搬进来:

```dts
/dts-v1/;

/include/ "soc-plain.dtsi"

/ {
	model = "ACME Lab Board (no cpp)";
};
```

```shell
mkdir -p dtsi
dtc -i dtsi -I dts -O dtb -o native.dtb native.dts
```

编过了,咱们拿反编译验货,产物跟 cpp 路线的一致,serial@1000 稳稳地待在树上。dtc 的 `-i` 就是它自家 include 的查找路径,跟 cpp 的 -I 长得像,管的东西不一样。

那差别在哪?`/include/` 会干的活只有搬文件,宏它是不认的。咱们把 cpp 路线的 board.dts 直接喂给 dtc 会怎么样?

```shell
dtc -I dts -O dtb -o fail.dtb board.dts
```

```output
Error: board.dts:3.1-9 syntax error
FATAL ERROR: Unable to parse input tree
```

报错的定位落在第 3 行,正是 #include 所在的那一行。dtc 没有 cpp 那套处理井号指令的本事,一句 syntax error 就拍上来了。所以真实的内核和 U-Boot 都把 include 与宏的活交给 cpp,dtc 只管从纯文本到二进制的编译。咱们核对两边主线构建脚本的时候,看到的是同一副接力:cpp 干完文本的活,dtc 接着干二进制的活。

工具的分工到这儿就齐了。不过 dtc 干活的时候还会跟你打两种招呼:一种是屏幕上的告警,另一种是它往产物里多写的东西。下一篇咱们把两张脸都认下来。

## 本节自检

文章读完了,你拿下面的小问题验一验自己。

1. cpp 和 dtc 在流水线里各干什么?
2. 行标记是 cpp 留给谁看的?你要是给 cpp 加上 -P,同一个错会报在哪个文件的第几行?
3. 宏的展开是谁干的?展开完之后,acme-regs.h 在中间文件里留下了什么?
4. 要是漏了 cpp 这一步,dtc 会报出什么样的错?
5. `#include <x.h>` 和 `#include "y.dtsi"` 在查找上有什么差别?`-I` 影响的是谁?
6. dtc 自带的 /include/ 指令,比 cpp 的 #include 少了什么本事?

<details>
<summary>参考答案(想好再展开)</summary>

1. cpp 负责文本层面的归拢:搬进被包含的文件、展开宏、留下行标记。dtc 负责从纯文本到二进制的编译。
2. 行标记是留给 dtc 的笔记,dtc 认得它们,报错才能指回原始文件。给 cpp 加上 -P 抹掉行标记之后,同一个错就报在 board.pp.dts 的第 8 行了。
3. 宏是 cpp 展开的。acme-regs.h 在原地只留了一行笔记,四个 #define 全被消费掉了。
4. dtc 会在 #include 所在的行报 syntax error,咱们实验里的报错是 board.dts:3.1-9。
5. 尖括号形式只查 -I 给出的路径,配上 -nostdinc 之后系统默认路径也没了。引号形式会把当前文件所在的目录算进查找范围。`-I` 是 cpp 的选项,影响的是 cpp。
6. /include/ 指令只会搬文件,宏它是不认的,所以带宏的源码没法绕开 cpp。

</details>

## 延伸阅读

这一篇的查找规则在 cpp 官方手册里都有正本,链接给你备在这里:

- [GCC: The C Preprocessor](https://gcc.gnu.org/onlinedocs/cpp/):cpp 官方手册,两种 include 写法的查找规则、-I 与 -nostdinc 的语义都在这里。
