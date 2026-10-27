---
title: "设备没工作从哪一层查起,产物旧了坏了怎么验?"
volume: 5
chapter: 18
section: 1
order: 181
description: "设备失灵的排查地图:描述写对、产物编对、产物传对、格式要完好、枚举要成功,五层的关口逐条写清,案例照取证的便宜程度排次序,实验全在本机跑,工具是 dtc v1.8.1 与独立 venv 里版本 2026.9 的 dt-validate。构建产物层重演改了 clock-frequency 没重编的事故,时间戳与反编译两样证据读出产物比源码旧,补上编译后 0x1c200 换成 0x2580。格式层的两种损伤:截断的 cut.dtb 报 EOF before reading 293 bytes of DT blob,坏魔数的 badmagic.dtb 报 incorrect magic number,交出去的产物拿反编译自己验读一遍"
status: draft
---

# 设备没工作从哪一层查起,旧产物与坏产物怎么验?

板子上的设备没了动静,串口不出字了,网卡也不见了,咱们手里的现象五花八门,链路上的问法却只有一个:从描述到驱动,哪一层断了?这一章是第五卷的收尾,也是全课程的毕业章,咱们把前四卷攒下的本事全部押上,一层一个案例地走,每个案例咱们都端上现象、证据链与修复前后对照。

## 排查地图:一块设备要活,链上五层都得通

链上的五层要是断了任何一层,设备就活不成了,咱们把每一层的关口写清楚。

- 描述要写对:源码里的写法得合 binding 的约定,compatible 一个字母都错不得。
- 产物要编对:源码的每次改动都得真的编进 DTB。
- 产物要传对:交到内核手里的,确实是描述这块板的那棵树。
- 格式要完好:产物字节完整,读它的一方解析得动。
- 枚举要成功:节点要变成设备,compatible 要对上驱动的匹配表。

这五层你不是头一回见。“谁会使用设备树”那篇里咱们认过读取、修改、传递、消费四站:写对与编对发生在咱们开发它的电脑上,传对的事交给了传递,格式完好与枚举成功都归了消费,而引导器读产物的时刻,其实也在考格式那一关。“设备树长什么样,谁跟它打交道”那篇里咱们认过硬件、设备树、binding 与驱动的四方分工,咱们排查的五层,查的其实就是四方里谁交上来的货不对样。

案例的排列咱们不照链条的次序,照的是取证的便宜程度:反编译一条命令就能出证据的层排在前面,要动内核运行状态才看得见毛病的层排在后面。你在真实的排错现场也照这个次序排,咱们把便宜的证据拿全,再去花贵的功夫。

实验咱们全在本机跑,跑的日期是 2026-10-18,工作目录用的是 /tmp/vol5ch18,输入来自仓库里的 [mini.dts](../../edtc/example/00_bootstrap/mini.dts)。咱们的工具是 dtc v1.8.1 和 QEMU 11.1.2,版本 2026.9 的 dt-validate 咱们装在了独立 venv 里。案例里贴的输出全部原样来自当天的运行,推演的部分咱们单独标注。

地图铺好了,咱们这就进头一层的现场,把一个改了源码却没重编的事故重演一遍。

## 构建产物层:源码改了,编出来还是旧的

头一个案例是排错现场出镜率最高的毛病:你改了源码,设备的表现却纹丝不动,咱们头一件要查的就是产物,改动真的编进去了吗?咱们在实验目录里把事故重演一遍,漏掉的正是重编那一步:

```shell
mkdir -p /tmp/vol5ch18
cd /tmp/vol5ch18
cp /home/charliechen/devtree-journey/edtc/example/00_bootstrap/mini.dts board.dts
dtc -I dts -O dtb -o board.dtb board.dts
sleep 1  # 拉开一秒的间隔,时间戳的先后好看清
sed -i 's/clock-frequency = <115200>;/clock-frequency = <9600>;/' board.dts
```

现象咱们看两样东西:时间戳与反编译。

```shell
stat -c "%y  %s  %n" board.dts board.dtb
dtc -I dtb -O dts board.dtb | grep clock-frequency
```

```output
2026-10-18 14:56:43.217729620 +0800  345  board.dts
2026-10-18 14:56:42.214752793 +0800  293  board.dtb
		clock-frequency = <0x1c200>;
```

证据链咱们这么读:stat 报出 board.dts 的改动时间比 board.dtb 晚一秒,产物是在改动之前编的。反编译进一步给咱们作证,产物里的值还是 0x1c200,咱们把它换算回来,得到的正是 115200,而源码里写的已经是 9600。你交出去的是一份旧产物,所以设备照着旧描述办事,表现当然一点没变。

修复就是把缺的那次编译补上,补完咱们把同两样证据再收一遍:

```shell
dtc -I dts -O dtb -o board.dtb board.dts
stat -c "%y  %s  %n" board.dts board.dtb
```

```output
2026-10-18 14:56:43.217729620 +0800  345  board.dts
2026-10-18 14:56:43.223338329 +0800  293  board.dtb
```

```shell
dtc -I dtb -O dts board.dtb | grep clock-frequency
echo $((0x1c200)) $((0x2580))
```

```output
		clock-frequency = <0x2580>;
115200 9600
```

修复前后对照就摆在咱们的眼前:产物的时间戳翻到了源码之后,反编译里的值从 0x1c200 换成了 0x2580,咱们把两个十六进制数换算回来,得到的正是 115200 与 9600。真实项目里的构建系统替你跑编译,事故就藏在构建脚本编的是另一个文件、或缓存没失效的现场,套路跟咱们的演示一模一样。

这一层的验法一句话:咱们核对的永远是产物,反编译看的是 DTB,源码自己说了不算。

产物编对了只是过了头一关,咱们接着看产物缺了尾巴的现场,读它的 dtc 当场就拒收。

## 格式层:产物被截断,dtc 当场拒读

产物编对了,还要完整地送到读它的一方手里。产物在拷贝或烧写时缺了尾巴,就轮到格式层的事故登场,咱们从完好的产物上截一段出来当现场:

```shell
dtc -I dts -O dtb -o good.dtb mini.dts
head -c 200 good.dtb > cut.dtb
wc -c good.dtb cut.dtb
```

```output
293 good.dtb
200 cut.dtb
493 total
```

200 字节的 cut.dtb 就是截断的产物,咱们请 dtc 读它:

```shell
dtc -I dtb -O dts cut.dtb
```

```output
FATAL ERROR: EOF before reading 293 bytes of DT blob
```

报错原文咱们一句一句看:dtc 认得它的头部,头部里的 totalsize 写着整棵树 293 字节,它照头部说的数去读文件,文件读到末尾还差了 93 字节,于是报了 EOF。截断伤的是长度,头部倒是还在,身份倒是还认得出。咱们再看身份被毁掉的版本,把开头的魔数换成四个不相干的字节:

```shell
printf '\xde\xad\xbe\xef' > badmagic.dtb
head -c 289 good.dtb >> badmagic.dtb
dtc -I dtb -O dts badmagic.dtb
```

```output
FATAL ERROR: Blob has incorrect magic number
```

badmagic.dtb 的长度与好产物一样,坏的是开头的魔数,dtc 连头部都进不去了,报的是 incorrect magic number。两种报错把两类损伤分开了:读到 EOF 的是长度问题,卡在 magic 的是身份问题。读产物的引导器同样会验头部,“谁会使用设备树”那篇里咱们认过,它认了头部才知道产物多大,所以这两类损伤在真实现场也过不了检查。

修复没什么巧的,把完整的产物重新交过去,交之前咱们自己验读一遍:

```shell
dtc -I dtb -O dts good.dtb | head -5
```

```output
/dts-v1/;

/ {
	compatible = "edts,a_demo";
	#address-cells = <0x01>;
```

修复前后对照就是 cut.dtb 与 good.dtb 的待遇之差:一个被 FATAL ERROR 拒在了门外,一个倒是反编译得清清楚楚。“从字节到自己的树”那卷里咱们会逐个认区块与头部字段,这里咱们只用上了 totalsize 与魔数两个字段。

这一层的验法一句话:咱们每次易手都拿 `dtc -I dtb -O dts` 验读,读得动的产物才准进下一双手。

格式完好说完了,咱们还没考过描述本身合不合约定,下一篇咱们就故意把 compatible 打错一个字母,看编译器一声不吭的现场。

## 本节自检

文章读完了,你拿九个小问题验一验自己,想好了再展开参考答案。

1. 一块设备要活,链上的五层都得通,它们是哪五层?
2. 五层的讲解次序咱们不照链条排,照的是什么?你自己在排错现场为什么也照这个次序?
3. 写对与编对发生在哪里?传对、格式完好与枚举成功各归了谁?
4. 源码改了、产物没重编,反编译里看到的值是哪个?验这一层用的命令是什么?
5. 真实项目里的构建系统替你跑编译,同样的事故藏在哪两种现场?
6. 这一层的验法,咱们核对的永远是什么?
7. 截断的产物与坏魔数的产物,dtc 的报错原文各是什么?两类损伤差在哪里?
8. 把产物交出去之前,咱们自己验读用的命令是什么?
9. 这一层咱们只动用了头部里的哪两个字段?

<details>
<summary>参考答案(想好再展开)</summary>

1. 描述要写对、产物要编对、产物要传对、格式要完好、枚举要成功。各层的关口一句话:描述的写法得合 binding 的约定,源码的改动得真的编进 DTB,交到内核手里的得是描述这块板的那棵树,读它的一方得解析得动完整的产物,节点得变成设备,compatible 得对上驱动的匹配表。
2. 照取证的便宜程度排,反编译一条命令就能出证据的层排在前面,要动内核运行状态才看得见毛病的层排在后面。你在真实的排错现场也照这个次序排,便宜的证据拿全了,再去花贵的功夫。
3. 写对与编对发生在咱们开发它的电脑上,传对的事交给了传递,格式完好与枚举成功都归了消费,而引导器读产物的时刻,其实也在考格式那一关。
4. 反编译里还是旧值 0x1c200,换算回来是 115200。命令用 `dtc -I dtb -O dts board.dtb | grep clock-frequency`,时间戳用 `stat` 对照,产物比源码旧就是没重编。
5. 藏在构建脚本编的是另一个文件、或缓存没失效的现场,套路跟咱们演示的一模一样。
6. 核对的永远是产物,反编译看的是 DTB,源码自己说了不算。
7. 截断的报 `FATAL ERROR: EOF before reading 293 bytes of DT blob`,坏魔数的报 `FATAL ERROR: Blob has incorrect magic number`。截断伤的是长度,头部还认得出,坏魔数伤的是身份,连头部都进不去。
8. 用 `dtc -I dtb -O dts good.dtb | head -5`,读得出开头的五行,产物才算完整。
9. 只用上了 totalsize 与魔数,区块与头部字段的逐个认读,归“从字节到自己的树”那卷。

</details>

## 延伸阅读

咱们用到的机制与工具,正式的出处都在官方文档里:

- [dtc 手册(官方仓库)](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/tree/Documentation/manual.txt):`-I dtb` 读产物的行为与命令行选项的正本,格式层验法的出处。

- [Devicetree Specification v0.4](https://github.com/devicetree-org/devicetree-specification/releases/tag/v0.4):头部字段与区块布局的定义正本,totalsize 与魔数都定义在它的第 5 章,本仓缓存了全文副本。
