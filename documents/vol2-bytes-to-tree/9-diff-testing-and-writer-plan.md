---
title: "怎样跟参考实现对拍,writer 的设计与验收怎么立?"
volume: 2
chapter: 7
section: 3
order: 73
description: "对拍的纪律是咱们的工具每走一步,参考实现也跑同一份输入,输出拿来一比。裁判背后是 libfdt,Linux 内核里还有一份 CONFIG_LIBFDT 管着的副本,四个坏输入被拒在 read_dtb 门口,dtc 的退出码同样给 1。对拍之外,本篇还替 edtc 立起 DTB writer 的设计与三层验收,rt.py 留作将来 reader 的活体规格说明,第二卷就此收工"
status: draft
---

# 裁判怎么请,writer 动工前的设计怎么立?

语义等价的活例子在前一篇到手了,验收线的道理有了实物撑着。本篇咱们把眼光从实验本身挪开:咱们写下的工具,每一步都是跟谁比的?坏输入进了链路,又在哪儿被拒?裁判自己的出身,咱们也查一查,查完再替 edtc 把 DTB writer 的设计与验收立起来,第二卷的收工也放在本篇。

## 对拍:每一步都请 dtc 当裁判

往返跑通了,咱们把背后的工作纪律说明白,它的名字叫对拍:咱们的工具每走一步,都把同一份输入也让参考实现跑了一遍,比一比两边的输出。本章咱们已经拍过三组:写完之后比反编译的文本,再比两边的字节数,坏输入则比拒收的行为。往后咱们给 edtc 每加一个能力,对拍的范围就跟着扩一圈。

咱们请的参考实现其实不止 dtc 一个可执行文件。dtc 的官方仓库里带着一个 `libfdt` 子目录,那是一份独立的 C 库,它挂的许可是 BSD-2-Clause,读写 DTB 的函数都在里面。它还带着一套顺序写的接口,咱们这章用到的名字有 `fdt_create`、`fdt_begin_node`、`fdt_property`、`fdt_finish`,它的套路是从空文件起步,一个记号接一个记号地往里放,咱们 `write_dtb` 干的就是同一种活的 python 版。dtc 自带的 `fdtget`、`fdtput`、`fdtoverlay` 这些工具,也都建在 libfdt 的上面。

libfdt 其实还有一重身份,咱们得单独交代:Linux 内核的源码树里,也带着一份实际在用的副本。2026-10-18 咱们在主线源码里核对过,它的实现在 `scripts/dtc/libfdt/`,而内核 `lib/` 目录下的八个同名 `.c` 文件每个只有两行,它们拿 `#include` 把实现挂进了内核的构建,`lib/fdt_rw.c` 的全部内容就是:

```c
#include <linux/libfdt_env.h>
#include "../scripts/dtc/libfdt/fdt_rw.c"
```

编不编由 `CONFIG_LIBFDT` 说了算,咱们核对到的 `lib/Makefile` 原文如下:

```make
libfdt_files = fdt.o fdt_ro.o fdt_wip.o fdt_rw.o fdt_sw.o fdt_strerror.o \
	       fdt_empty_tree.o fdt_addresses.o
$(foreach file, $(libfdt_files), \
	$(eval CFLAGS_$(file) = -I $(srctree)/scripts/dtc/libfdt))
lib-$(CONFIG_LIBFDT) += $(libfdt_files)
```

arm64 与 riscv 的早期启动(pi)构建、arm 的压缩内核构建,头文件查找路径里挂的都是 `scripts/dtc/libfdt`。咱们在自己电脑上请来的裁判,它的同门却在每一台 Linux 设备的启动最早期干着解析 DTB 的活。

再补一句 dtc 自身的读入检查:dtc 读 DTB 时自带一份 magic 与偏移的核验,报错在它自己的 `flattree.c` 里,咱们实验里马上就能见到它的 `FATAL ERROR`。

## 坏输入过 writer 链路:拒在门口

“如何安全遍历所有节点”那章的坏输入素材咱们复用,还是截断文件的老办法,再补两个手工改坏的:

```shell
head -c 30 mini.dtb > bad-short.dtb
head -c 120 mini.dtb > bad-mid.dtb
python3 -c "
b = bytearray(open('mini.dtb','rb').read()); b[3] ^= 0xff; open('bad-magic.dtb','wb').write(b)
b = bytearray(open('mini.dtb','rb').read()); b[8:12] = (0x7fffffff).to_bytes(4,'big'); open('bad-offset.dtb','wb').write(b)
"
for f in bad-short bad-mid bad-magic bad-offset; do
  python3 rt.py round-trip $f.dtb /dev/null
  echo "退出码 $?"
done
```

```output
拒收 bad-short.dtb: 文件只有 30 字节,装不下 40 字节的文件头
退出码 1
拒收 bad-mid.dtb: 文件头声称共 293 字节,文件却只有 120 字节
退出码 1
拒收 bad-magic.dtb: 魔数是 0xd00dfe12,我认的却是 d00dfeed
退出码 1
拒收 bad-offset.dtb: 结构块的偏移加长度越过了文件尾
退出码 1
```

四个坏输入全被拒在 `read_dtb` 的门口,它们连 `write_dtb` 的门都没摸到。咱们特意看拒收的位置:writer 吃的只是树模型,树模型只能从 reader 的门进来,所以 reader 的核验就是 writer 的防线,坏字节也就没了被摊成“合法的”坏产物的机会。

咱们再请裁判对同样的输入表个态:

```shell
for f in bad-short bad-mid bad-magic bad-offset; do
  dtc -I dtb -O dts -o /dev/null $f.dtb
  echo "$f 的退出码 $?"
done
```

```output
FATAL ERROR: EOF before reading 293 bytes of DT blob
bad-short 的退出码 1
FATAL ERROR: EOF before reading 293 bytes of DT blob
bad-mid 的退出码 1
FATAL ERROR: Blob has incorrect magic number
bad-magic 的退出码 1
FATAL ERROR: DT structure offset exceeds total size
bad-offset 的退出码 1
```

四位裁判全都判了拒绝,退出码给的都是 1,跟咱们拒收的方向对上了。报错的说法不同,判的方向一致,对拍看的就是方向。

门口守住了,裁判的口径也对上了。链路本身的事到这里齐了,剩下的活是替 edtc 打算将来:它的 DTB writer 怎么落、验收分几层,接下来咱们就把设计立起来,第二卷的收工也在本篇。

## edtc 的 DTB writer 打算怎么落

咱们把话说在前面:今天的 edtc 还停在输入与环境的阶段,文件读入、字节序这些底座有了,DTB 的解析还没动工,DTB writer 的实现自然也还没开始。本节立的是设计与验收,没实现的部分咱们标明在案。

设计上咱们打算让 DTB writer 吃两样东西,吃进来的有树模型,还有内存保留区的条目表。接口走整树一次成的路,吃进树模型、交出完整的字节,理由是 edtc 的树模型在内存里已经立好了,不像 libfdt 的顺序写接口那样要为流式写入预留缓冲。排布的选择就抄本章验证过的最省事那套:字符串表按头一回遇见的顺序追加,名字相同的条目直接复用,名字与值的补零到 4 字节,区块之间的空隙一概不留。

验收咱们分三层来定。咱们的硬验收是语义等价:咱们准备一份语料,里面是若干 dtc 产出的 DTB,覆盖空属性、奇长值、保留区、深嵌套这些边角的情况,语料里的每一份都得跑一遍往返,反编译的文本必须与参照全同,坏输入必须一个不剩地拒收。第二层是字节一致的清单:哪些语料做到了逐字节一致,咱们逐条记下,它量的是咱们的排布与 dtc 排布的巧合程度,等 dtc 换了版本,清单就成了咱们的报警器。排在第三层的是性能与体积,咱们把它放在最后,理由是性能的目标不该反过来挤压排布的自由。

等 edtc 的 DTB reader 动了工,咱们就拿这一章的 `rt.py` 当它的活体规格说明,验收的三层照搬即可。

## 第二卷收工:树在咱们手里了

咱们回头看,“从字节到自己的树”这卷把一条链走完整了:布局那章认了四个区块,遍历那章守着记号协议安全地走了全树,立树那章把字节立成了可查询的树模型,本章又把树写回了 DTB,还给它配了能自证清白的验收。进去的是一份 DTB,出来的也是一份 DTB,凭什么说内容没变?咱们的答案已经攒齐:验收认的是语义等价,裁判请的是 dtc,字节一致算成附赠的福利。

产的这边咱们摸过了,读的这边咱们也自己写过一遍了。接下来的一卷“U-Boot 与 Linux 如何消费设备树”看的是消费侧:固件在启动时把 DTB 放到了哪里,内核从哪个寄存器手里接过了它,再展开成内核里的设备又是哪些路。你在本卷敲过的每一条核对命令,到了那边的卷里都会换成一句新的问话:“人家的代码是怎么把这件事做对的”。

## 本节自检

这一篇读完了,你拿七个小问题验一验自己,想好了再展开参考答案。

1. libfdt 的顺序写接口,咱们这章用到的名字有哪几个?咱们 `write_dtb` 干的活和它是什么关系?
2. 坏输入在 writer 链路的哪一步被拒?为什么说 reader 的核验就是 writer 的防线?
3. 咱们和 dtc 对四个坏输入的报错说法一样吗?对拍看的是什么?
4. Linux 内核里的 libfdt 副本住在哪里?编不编进内核由谁说了算?
5. edtc 的 DTB writer 打算吃哪两样东西?接口为什么走整树一次成的路,而不像 libfdt 那样顺序写?
6. 验收的三层怎么分?哪一层是硬验收,字节一致的清单又拿来干什么?
7. 等 edtc 的 DTB reader 动了工,rt.py 在里面充当什么?

<details>
<summary>参考答案(想好再展开)</summary>

1. `fdt_create`、`fdt_begin_node`、`fdt_property`、`fdt_finish`。它的套路是从空文件起步,一个记号接一个记号地往里放,咱们 `write_dtb` 干的就是同一种活的 python 版。
2. 拒在 `read_dtb` 的核验处。writer 只吃树模型,树模型只能从 reader 进来,坏字节被挡在门外,就没有机会被摊成一份格式合法的坏产物。
3. 报错的说法不同,判的方向一致。四位裁判全都判了拒绝,退出码给的都是 1,跟咱们拒收的方向对上了,对拍看的就是方向。
4. 实现住在 `scripts/dtc/libfdt/`,`lib/` 下八个同名文件拿两行 include 把它挂进构建,由 `CONFIG_LIBFDT` 决定编不编。
5. 吃进来的有树模型,还有内存保留区的条目表。edtc 的树模型在内存里已经立好了,不像 libfdt 的顺序写接口那样要为流式写入预留缓冲,所以接口走整树一次成的路。
6. 硬验收是语义等价:语料里每一份 dtc 产出的 DTB 都得跑一遍往返,反编译的文本与参照全同,坏输入必须一个不剩地拒收。第二层是字节一致的清单,量的是咱们的排布与 dtc 排布的巧合程度,dtc 换了版本,清单就成了报警器。第三层是性能与体积,放在最后,性能的目标不该反过来挤压排布的自由。
7. 咱们拿 `rt.py` 当它的活体规格说明,验收的三层照搬即可。

</details>

## 延伸阅读

咱们用到的机制与出处,正式的文档都在这里:

- [dtc 官方仓库](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/):咱们对拍的裁判,`libfdt/` 子目录是读写 DTB 的独立 C 库,顺序写的接口声明在 `libfdt/libfdt.h` 里。
- [Linux 内核里的 libfdt 副本](https://github.com/torvalds/linux/tree/master/scripts/dtc/libfdt):内核实际在用的那一份,`lib/Makefile` 的 `CONFIG_LIBFDT` 把它编进内核的 lib,本篇引用的两行 include 也在这条链上。
