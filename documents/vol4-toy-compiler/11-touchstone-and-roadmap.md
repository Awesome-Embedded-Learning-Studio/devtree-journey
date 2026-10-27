---
title: "拿 imx51-babbage 当试金石,扩展路线怎么排,第四卷怎么收工?"
volume: 4
chapter: 15
section: 3
order: 153
description: "v3.7 的 dts 配上 -i 查找路径才编得通,include 链一环一环补齐,七条警告咱们逐条读,数出 87 个节点 9.8K 的产物,v7.2.9 交给 cpp,行标记与表达式现身中间文件,150 个节点 22K,两版的差距汇成一张表对上支持矩阵,正本规格的里程碑照需求排队,第四卷收工,下一卷拿 schema 验描述"
status: draft
---

# 两棵真树各编一回,扩展的路线怎么排?

支持矩阵立起来了,拒绝的路数也定了,剩下的验证得拿真树跑一回。工作目录用的还是本章开头建好的 /tmp/vol4ch15,咱们接着在里面干活。

## v3.7 起步:链上的每一环都得在路径上

光读文件是量不出差距的,咱们真的编一回。咱们从 v3.7 那版起步,两份摘录从本仓的缓存拷进工作目录:

```shell
cp /home/charliechen/devtree-journey/.claude/materials/kernel-excerpts/imx51-babbage.dts.v3.7 imx51-babbage.dts
cp /home/charliechen/devtree-journey/.claude/materials/kernel-excerpts/imx51.dtsi.v3.7 dts/imx51.dtsi
```

仓库之外的读者,从内核源码树的 `arch/arm/boot/dts/` 里按 v3.7 的 tag 取同名的文件,内容是一样的。咱们图省事直接拿 dts 喂给 dtc:

```shell
dtc -I dts -O dtb -o babbage.dtb imx51-babbage.dts
```

```output
FATAL ERROR: Couldn't open "imx51.dtsi": No such file or directory
```

dts 与 dtsi 分家在不同的目录里,include 的文件也就找不到了。咱们给 dtc 配上自家的查找路径 `-i`:

```shell
dtc -i dts -I dts -O dtb -o babbage.dtb imx51-babbage.dts
```

```output
FATAL ERROR: Couldn't open "skeleton.dtsi": No such file or directory
```

报错换了对象:imx51.dtsi 找到了,它自己 include 的 skeleton.dtsi 还没着落。include 是链式的,链上的每一环都得在路径上。咱们从内核源码树把 v3.7 的 skeleton.dtsi 取来放进 dts/ 目录,它的全文总共 13 行,咱们全文看一眼:

```shell
curl -fsSL -o dts/skeleton.dtsi \
  'https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/plain/arch/arm/boot/dts/skeleton.dtsi?h=v3.7'
```

```dtsi
/*
 * Skeleton device tree; the bare minimum needed to boot; just include and
 * add a compatible value.  The bootloader will typically populate the memory
 * node.
 */

/ {
	#address-cells = <1>;
	#size-cells = <1>;
	chosen { };
	aliases { };
	memory { device_type = "memory"; reg = <0 0>; };
};
```

咱们再编一回,include 的链全通了:

```shell
dtc -i dts -I dts -O dtb -o babbage.dtb imx51-babbage.dts 2>warn.txt; echo "exit=$?"
ls -l babbage.dtb
```

```output
exit=0
.rw-r--r-- 9.8k charliechen 18 Oct 14:53 babbage.dtb
```

编译过了,警告留在了 warn.txt 里,九行的输出装着七条警告,咱们原文贴出来:

```output
dts/skeleton.dtsi:12.9-50: Warning (unit_address_vs_reg): /memory: node has a reg or ranges property, but no unit name
  also defined at imx51-babbage.dts:20.9-22.4
imx51-babbage.dts:219.24-225.7: Warning (unit_address_format): /soc/aips@80000000/i2c@83fc4000/codec@0a: unit name should not have leading 0s
imx51-babbage.dts:219.24-225.7: Warning (i2c_bus_reg): /soc/aips@80000000/i2c@83fc4000/codec@0a: I2C bus unit address format error, expected "a"
dts/imx51.dtsi:100.20-107.7: Warning (spi_bus_bridge): /soc/aips@70000000/spba@70000000/ecspi@70010000: node name for SPI buses should be 'spi'
  also defined at imx51-babbage.dts:50.20-172.7
babbage.dtb: Warning (spi_bus_reg): Failed prerequisite 'spi_bus_bridge'
dts/imx51.dtsi:33.9-56.4: Warning (avoid_unnecessary_addr_size): /clocks: unnecessary #address-cells/#size-cells without "ranges", "dma-ranges" or child "reg" or "ranges" property
imx51-babbage.dts:57.22-152.8: Warning (avoid_unnecessary_addr_size): /soc/aips@70000000/spba@70000000/ecspi@70010000/mc13892@0: unnecessary #address-cells/#size-cells without "ranges", "dma-ranges" or child "reg" or "ranges" property
```

咱们挑三处读。报错的位置会跨文件:有的警告指 skeleton.dtsi 的第 12 行,imx51.dtsi 与板级的 dts 也各挨了几条,include 的回溯在报错里是通的,将来咱们玩具的报错也照这个标准验。also defined at 的两行缀在警告后面,它告诉你同一个节点在两个文件里各定义过一回,合并的现场被检查器原样拍了下来,和咱们读源码时看到的同名节点正好对上。2011 年的写法按今天的检查标准还挨了几条提醒,codec@0a 的地址里不该有打头的零,这些警告咱们改不改,产物照样出来了。

咱们再数数产物:

```shell
dtc -I dtb -O dts babbage.dtb | grep -c '{'
dtc -I dtb -O dts babbage.dtb | wc -l
```

```output
87
588
```

咱们数出来的节点连根在内有 87 个,反编译出来的行数是 588,产物的个头是 9.8K。教学例子编出来的产物不过几百字节,真实板卡的树一上手就是十 KB 的量级,DTB reader 当年读的小样片,搁在咱们眼前的真树里就成了整片的街区。

## v7.2.9 的树,全靠 cpp 喂大

轮到 v7.2.9 了。咱们照内核源码树的相对位置摆文件,nxp/imx/ 里放进板级的 dts、imx51.dtsi 和 imx51-pinfunc.h,dt-bindings/ 下放它要的头文件,uapi/ 下再补齐 event-codes 的真身。板级文件直接喂 dtc 会怎么样?

```shell
dtc -I dts -O dtb -o direct.dtb nxp/imx/imx51-babbage.dts
```

```output
Error: nxp/imx/imx51-babbage.dts:7.1-9 syntax error
FATAL ERROR: Unable to parse input tree
```

报错的位置落在第 7 行,正是 `#include` 所在的那一行。dtc 不认井号的指令,咱们把它交给 cpp。查找路径没配好的时候,cpp 的抱怨分两种。板级文件孤零零一个文件的时候,报的是找不到 dtsi:

```shell
cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp imx51-babbage.dts -o /dev/null
```

```output
imx51-babbage.dts:7:10: fatal error: imx51.dtsi: No such file or directory
    7 | #include "imx51.dtsi"
      |          ^~~~~~~~~~~~
compilation terminated.
```

dtsi 备齐了而 `-I` 没配的时候,咱们看到的现象是:引号形式的 imx51.dtsi 能就地找到,尖括号形式的 dt-bindings 头就没了着落:

```shell
cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp nxp/imx/imx51-babbage.dts -o /dev/null
```

```output
In file included from nxp/imx/imx51-babbage.dts:7:
nxp/imx/imx51.dtsi:7:42: error: no include path in which to search for dt-bindings/clock/imx5-clock.h
    7 | #include <dt-bindings/clock/imx5-clock.h>
      |                                          ^
nxp/imx/imx51.dtsi:8:35: error: no include path in which to search for dt-bindings/gpio/gpio.h
    8 | #include <dt-bindings/gpio/gpio.h>
      |                                   ^
nxp/imx/imx51.dtsi:9:37: error: no include path in which to search for dt-bindings/input/input.h
    9 | #include <dt-bindings/input/input.h>
      |                                     ^
nxp/imx/imx51.dtsi:10:50: error: no include path in which to search for dt-bindings/interrupt-controller/irq.h
   10 | #include <dt-bindings/interrupt-controller/irq.h>
      |                                                  ^
```

两种查找的差别,你在“构建系统实际上做了什么”那章里已经见过它的章法,这里在真实的树上又验了一回。咱们把路径配上,预处理就跑通了:

```shell
cpp -nostdinc -I . -I nxp/imx -undef -D__DTS__ -x assembler-with-cpp \
  nxp/imx/imx51-babbage.dts -o babbage.pp.dts
wc -l babbage.pp.dts
```

```output
1394 babbage.pp.dts
```

咱们拿到的中间文件行数到了 1394,比板级的源文件厚了将近一倍。开头的几行长这个样子:

```output
# 0 "nxp/imx/imx51-babbage.dts"
# 0 "<built-in>"
# 0 "<command-line>"
# 1 "nxp/imx/imx51-babbage.dts"
/dts-v1/;
# 1 "nxp/imx/imx51.dtsi" 1
# 1 "nxp/imx/imx51-pinfunc.h" 1
# 7 "nxp/imx/imx51.dtsi" 2
# 1 "./dt-bindings/clock/imx5-clock.h" 1
```

行标记记下了每个片段来自哪个文件,宏全都摊开了。咱们抽两处看展开后的样子,GPIO 的极性宏变成了数字,带参的 MATRIX_KEY 变成了带位运算的表达式:

```output
 cs-gpios = <&gpio4 24 0>,
     <&gpio4 25 1>;
 status = "okay";
```

```output
 linux,keymap = <
  ((((0) & 0xFF) << 24) | (((0) & 0xFF) << 16) | ((103) & 0xFFFF))
  ((((0) & 0xFF) << 24) | (((1) & 0xFF) << 16) | ((108) & 0xFFFF))
```

咱们把预处理的产物交给 dtc:

```shell
dtc -I dts -O dtb -o babbage-v729.dtb babbage.pp.dts; echo "exit=$?"
dtc -I dtb -O dts babbage-v729.dtb | grep -c '{'
ls -l babbage-v729.dtb
```

```output
exit=0
150
.rw-r--r-- 22k charliechen 18 Oct 19:53 babbage-v729.dtb
```

咱们一条警告都没等到,产物的个头到 22K,节点连根在内到了 150 个。十五年过去了,同一块板的树胖了七成,而且 2026 年的这棵树全靠 cpp 喂大了,dtc 连嚼碎的活都没沾。

## 两棵树编完,底气与短板各在一头

两棵树都编过了,咱们把量出来的差距汇成下面的一张表:

| 写法 | 标本里的用量 | 咱们的子集 |
| ---- | ------------ | ---------- |
| /dts-v1/ 头 | 两版各一处 | M4,已定文法 |
| 嵌套节点 | v3.7 成品 87 个,v7.2.9 成品 150 个 | M4,已定文法 |
| 字符串与字符串列表 | 满树都是 | M4,已定文法 |
| 32 位非负 cells | 满树都是 | M4,已定文法 |
| 空属性 | v3.7 三文件 34 处,v7.2.9 的 dts 27 处 | M4,已定文法 |
| 注释 | 常用 | M4,已定文法 |
| 标签与 & 引用 | v3.7 共 70 处,v7.2.9 共 308 处 | M5 排期 |
| /include/ | v3.7 两条链式指令 | M6 排期 |
| 节点合并 | v3.7 同名节点 15 个 | M6 排期 |
| 井号指令与宏 | v7.2.9 五个头文件,MX51_PAD 宏 131 处 | 预处理接入 |
| 表达式 | v7.2.9 预处理产物里 16 行 | 不支持,拒绝或排期 |
| 顶格 &label 块 | v7.2.9 共 19 处 | M6 靠后 |
| /delete-* 指令 | 两版都没用上 | M6 排期 |
| /bits/ 与 /incbin/ | 两版都没用上 | 不支持,拒绝 |

咱们把表竖着读一遍,咱们的底气与短板各在一头。属性值的写法十五年没变过样,两版树里用的全是 M4 子集内的那几种,字符串、字符串列表、cells、空属性全都用上了,字节串倒是一次都没出场。可是 include、合并、宏、顶格 & 块这些组织的手段,全落在 M5 与 M6 的地界里,而组织恰恰是真实树的主干。咱们的玩具离真实有多远?咱们单看语法离得不远,单看组织还差着一整段的路,所以扩展路线得照着组织排。

排队的次序怎么定,正本规格里已经写好了,下面咱们把里程碑读清楚,第四卷的收工也一起交代。

## 设计讨论:扩展路线照着正本排

正本规格把这段路写成了里程碑,从 M4 的最小前端,到 M5 的标签与引用,再到 M6 的按需扩展。前两章的文法与机制咱们都过了一遍,这一章补的就是 M6 的图纸。排队的次序照需求走,不照语法的难易走:

1. M5 收尾。标签、引用、phandle 分配的实现按“标签和引用怎样变成二进制”那章的设计落地,悬空引用与重复标签按拒绝原则拦,材料就是本章 rej-undef 与 rej-dupe-label 这类夹具。
2. M6 的头一项,/include/。词法层搬文件,验收夹具就用实验里那条三层的 include 链,外加 dtsi 不在路径上的报错样张。
3. M6 的第二项,节点合并。树模型上的同路径合并,验收拿 v3.7 的 15 个同名节点对拍 dtc 的产物,字段一致才算过。
4. M6 的第三项,删除指令。跟着合并落地,删不存在的行为按拒绝原则的第三条定,夹具锁死。
5. 预处理接入。输入的约定定为 cpp 的输出加行标记,报错位置与 dtc 对拍,含表达式的输入按矩阵的行处理,拒绝要带出路。
6. 顶格 &label 块排在 M6 末段,它要靠 M5 的标签到路径解析打底,验收拿 v7.2.9 的 19 个块。

每一项落地的时候,支持矩阵的对应行会点亮,正常测试、拒绝测试、对拍记录的三样材料一起交,课程的实验同步更新。代码现状咱们再说一遍:edtc 在仓库里的进度停在 M0 附近,DTS 前端本身就在 M4 的排期里,上面的次序是给它的路线图,不是已经能跑的功能。真跑的验证,等实现进了仓库,咱们在这些章节的实验里一轮一轮补上。

## 第四卷收工,玩具的骨架立起来了

咱们这一卷从读 DTB 的字节起步一路走到今天,玩具编译器该有的四副骨架都过了设计关:DTB reader 的活是把产物读成树,DTS 前端的活是把源码解成带位置的树,树模型在中间当唯一的事实,DTB writer 的活是把树编回二进制,验的活由对拍与测试夹具扛着。读、解、编、验这四件事的接口在正本规格里定了型,代码的进度按里程碑往前赶,矩阵和拒绝测试就是赶路的刻度。

树的门外还有一层天地。编译成功只说明语法过了自家的文法,树里的设备合不合 binding 的约束,咱们一路都没验过。下一卷的卷名叫“工程验证与排错”,开门的头一件事就是拿 schema 去验描述。“编译成功就代表写对了吗?”那章是下一卷的开场,它要干的事就是拿 YAML 写的 schema 去验描述,dt-validate 的用法、好输入与坏输入的对照都会讲到。真实板卡的那 150 个节点合不合 binding,恰好是下一卷现成的考题。咱们把图纸收好,下一卷里咱们再见。

## 本节自检

文章读完了,你拿下面的小问题验一验自己。

1. v3.7 的 imx51-babbage.dts 直接喂 dtc,报了什么?include 链上缺环的时候,报错里的文件名怎么变?
2. v7.2.9 的板级文件直接喂 dtc,报了什么?报错的位置落在哪一行?
3. cpp 找不到路径的抱怨分两种,各是什么样子?
4. 两版的产物各是多少个节点、多大个头?
5. M6 的头一项为什么是 `/include/`?验收夹具用什么?
6. 顶格 &label 块为什么排在 M6 末段?
7. 第四卷的四副骨架各干什么活?验证的活由谁扛?
8. 下一卷开场的头一件事是什么?

<details>
<summary>参考答案(想好再展开)</summary>

1. 报 FATAL ERROR: Couldn't open “imx51.dtsi”。链上缺的是哪一环,报错就指谁的名:配好 -i 之后 imx51.dtsi 找到了,报错的对象换成了 skeleton.dtsi。
2. 报 Error 加 syntax error,还有 FATAL ERROR: Unable to parse input tree。位置落在第 7 行,正是 #include 所在的那一行,dtc 不认井号的指令。
3. 板级文件孤零零一个的时候,报的是找不到 dtsi。dtsi 备齐而 -I 没配的时候,引号形式的 imx51.dtsi 能就地找到,尖括号形式的 dt-bindings 头就没了着落。
4. v3.7 编出的 babbage.dtb 是 9.8K,节点连根在内 87 个,反编译出来 588 行。v7.2.9 预处理后再编,产物 22K,节点 150 个,咱们一条警告都没等到。
5. 它的活最薄,词法层搬文件就行。验收夹具用实验里那条三层的 include 链,外加 dtsi 不在路径上的报错样张。
6. 它要靠 M5 的标签到路径解析打底,验收拿 v7.2.9 的 19 个块。
7. DTB reader 把产物读成树,DTS 前端把源码解成带位置的树,树模型在中间当唯一的事实,DTB writer 把树编回二进制。验证的活由对拍与测试夹具扛着。
8. 拿 YAML 写的 schema 去验描述。dt-validate 的用法、好输入与坏输入的对照都会讲到,真实板卡的那 150 个节点恰好是现成的考题。

</details>

## 延伸阅读

实验用到的工具文档与标本源头,给你备在这里:

- [dtc 手册(上游仓库)](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/tree/Documentation/manual.txt):-i 查找路径与各类检查项的官方说明。
- [imx51-babbage.dts v3.7](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/arch/arm/boot/dts/imx51-babbage.dts?h=v3.7) 与 [imx51-babbage.dts v7.2.9](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/arch/arm/boot/dts/nxp/imx/imx51-babbage.dts?h=v7.2.9):本章两份标本的源头,实验里补取的 skeleton.dtsi、imx51.dtsi 与 dt-bindings 头文件也在同样的 tag 下。v7.2.9 是 stable 仓库的点版本,链接也就指向了 stable 树。

正文里的命令与输出都是咱们在本机真实跑出来的,工具版本是 dtc v1.8.1 与 GCC 16.2.1 的 cpp,验证的日子是 2026-10-18。两版标本的摘录缓存在本仓的 .claude/materials/kernel-excerpts/,实验里补取的源文件许可证是 GPL-2.0,出处咱们以内核源码树为准。
