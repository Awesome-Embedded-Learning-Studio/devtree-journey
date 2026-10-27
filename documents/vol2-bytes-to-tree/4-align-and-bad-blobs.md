---
title: "补零补在哪几条缝里,坏产物能立起哪些防线?"
volume: 2
chapter: 5
section: 2
order: 52
description: "名字与值是变长数据,读完要向上取整到 4 的倍数,而 len 自己不许取整,字符串块没有对齐要求,按偏移取名字还图到了共享的便宜。规则备齐之后咱们亲手造截断、len 越界、nameoff 越界、配对缺口、生面孔记号五个坏产物,换来 dtc 的五句真报错,没防线的 walk.py 报假话退出码还是 0,防线清单一并列出来"
status: draft
---

# 读指针怎么走得准,坏产物能立起哪些防线?

上一篇的收尾咱们提过,walk.py 里有两处算式咱们照着写了、还没细看:一句管的是对齐,另一句管的是取名字。这一篇咱们把两处算式的规则看清楚,一处是补零的缝,另一处是字符串块里名字的住址,规则都备齐了,咱们再拿坏产物试一试,给遍历器把该立的防线列出来。

## 对齐到 4 字节,补零补在哪几条缝里

对齐的规则一句话能说完:每个记号都得落在从产物开头数 4 字节对齐的偏移上,不够的地方就拿 0x00 补。咱们真正要补零的地方只有两处,一段跟在节点的名字后面,另一段跟在属性值的后面,都是变长数据的尾巴。咱们把 mini.dtb 里的实例排一排,你就知道补零有多常客:

| 数据                   | 字节数 | 补零 | 数据起点 |
| ---------------------- | ------ | ---- | -------- |
| 根节点的名字(空串加结尾符) | 1      | 3    | 0x3c     |
| `serial@1000\0` 名字   | 12     | 0    | 0x7c     |
| `edts,a_demo\0` 值     | 12     | 0    | 0x4c     |
| `acme,uart\0` 值       | 10     | 2    | 0x94     |
| `okay\0` 值            | 5      | 3    | 0xd0     |

表里最容易犯的错,是把 `len` 当成了对齐后的长度。`len` 报的是纯字节长度,status 的 5 就是 5,`okay\0` 连结尾符一起都算了进去。指针怎么走是另一件事:读指针从属性记号的开头起,走完 4 加 4 加 len 的路程,再向上取整到 4 的倍数,walk.py 里那句 `(pos + 12 + ln + 3) & ~3` 干的就是这件事。你要是把 len 自己取了整,后面的每个记号都会错位,而错出的偏移还全是 4 的倍数,对齐的检查反而报不出错来。

结构块与字符串块在对齐上的待遇不同。结构块的起点要 4 字节对齐,块里的记号因此天然对齐,mini.dtb 的 0x38 正好满足。字符串块就自由了,规范明说它没有对齐的要求,出现在产物里的哪个偏移都行。块里的名字一个挨着一个,分隔的活只靠一个 `\0`,补零也一并省了。你回头看 0xe4 那段转储就会发现,`reg\0` 只占了 4 个字节,后面紧跟的就是 `clock-frequency`,中间一个多余的 00 都没有。

## 属性名住在字符串块,报个偏移就能取

字符串块的转储咱们这回完整看一遍:

```shell
xxd -s 0xe4 -l 0x41 mini.dtb
```

```output
000000e4: 636f 6d70 6174 6962 6c65 0023 6164 6472  compatible.#addr
000000f4: 6573 732d 6365 6c6c 7300 2373 697a 652d  ess-cells.#size-
00000104: 6365 6c6c7300 7265 6700 636c 6f63 6b2d  cells.reg.clock-
00000114: 6672 6571 7565 6e63 7900 7374 6174 7573  frequency.status
00000124: 00                                       .
```

咱们把 `\0` 当分隔符划开,六个名字的住址就都出来了:

| 属性名            | 偏移   | 长度     |
| ----------------- | ------ | -------- |
| `compatible`      | +0x00  | 11 字节  |
| `#address-cells`  | +0x0b  | 15 字节  |
| `#size-cells`     | +0x1a  | 12 字节  |
| `reg`             | +0x26  | 4 字节   |
| `clock-frequency` | +0x2a  | 16 字节  |
| `status`          | +0x3a  | 7 字节   |

六个名字连同结尾符的总长是 65 个字节,恰好是文件头里 size_dt_strings 的 0x41,而块尾 0x125 也是产物的最后一个字节,富余一点都没有了。咱们把属性名集中搬去字符串块,图的是共享。mini.dtb 里 compatible 属性出现了两次,根节点用了一次,serial@1000 又用了一次,你在手工解码那里已经看到,两条 `FDT_PROP` 的 nameoff 都是 0,指的是同一份 `compatible\0`。名字只存了一份,每条 `FDT_PROP` 只背 4 个字节的偏移,树越大重复的名字越多,省下来的就越可观。真实板子的产物动辄几百个属性,compatible 和 status 这样的名字到处都是,而共享让字符串块不至于跟着属性数翻倍。

对咱们的遍历器来说,这里多了一条要小心的索引:nameoff 只是个偏移,它自己是不带长度的,咱们取名字的办法是从偏移处往后找 `\0`。偏移指到了块外,或者指了进来却一直到块尾都找不着 `\0`,两种情况咱们都会当成坏产物,后面的实验拿真货来试。

对齐的缝和名字的住址都对上了,walk.py 里的两句算式到这一步全有了着落。不过着落归着落,咱们这个遍历器还一点防线都没有,产物要是坏了呢?walk.py 会报错吗,还是会一声不吭地算下去?

## 造五个坏产物,看参考实现怎么拒绝

规则讲完了,咱们换个玩法,亲手把产物弄坏了拿去喂 dtc,看看它拒绝时的原话。参考实现的报错是有分量的证词,它拒绝的输入,咱们的遍历器一样不能放行。

咱们从最简单的坏开始:拿 `head -c` 把产物拦腰一裁。

```shell
head -c 200 mini.dtb > trunc200.dtb
dtc -I dtb -O dts trunc200.dtb
```

```output
FATAL ERROR: EOF before reading 293 bytes of DT blob
```

dtc 开工的头一步是按文件头的 totalsize 把整个产物读进内存,文件头要的是 293,而磁盘上只剩 200 个字节,dtc 就把整个产物拒绝了,连结构块的门都没摸到。剩下的四个坏产物,咱们拿 Python 在好产物上各动四个字节:

```python
import struct

def patch(out, offset, value):
    data = bytearray(open('mini.dtb', 'rb').read())
    struct.pack_into('>I', data, offset, value)
    open(out, 'wb').write(data)

patch('bad-prop-len.dtb', 0x44, 0x00000100)  # 第一个 PROP 的 len,指向产物外
patch('bad-nameoff.dtb', 0x48, 0x00001000)   # 同一个 PROP 的 nameoff,指出字符串块外
patch('bad-depth.dtb',   0xdc, 0x00000004)   # 根节点的 END_NODE 换成 NOP,配对缺一口
patch('bad-opcode.dtb',  0x40, 0x00000007)   # 头一个 PROP 换成谁都不认的 0x7
```

接下来咱们把四个文件挨个喂给 dtc:

```shell
dtc -I dtb -O dts bad-prop-len.dtb
dtc -I dtb -O dts bad-nameoff.dtb
dtc -I dtb -O dts bad-depth.dtb
dtc -I dtb -O dts bad-opcode.dtb
```

```output
FATAL ERROR: Premature end of data parsing flat device tree
FATAL ERROR: String offset 4096 overruns string table
FATAL ERROR: Premature FDT_END in device tree blob
FATAL ERROR: Invalid opcode word 00000007 in device tree blob
```

四句话各有各的出处,咱们在 edtc/reference/dtc 的 flattree.c 里逐条核对过:

- len 越界拦在 flat_read_chunk,那里把“当前指针加长度”与缓冲区的末端比大小,超了就拒绝。
- nameoff 越界拦在 flat_read_stringtable,它从偏移处往后找 `\0`,指针出了字符串块的范围,或者找到块尾也没见到 `\0`,都报同一句。
- 配对缺口的报错来自 unflatten_tree,根节点还没关门就见到了 `FDT_END`,深度没归零,门里的人不该见到送客的话。
- 不认识的记号落在同一个函数的 default 分支,值原样报了出来,一点没含糊。

有意思的是 bad-depth.dtb 顺带验证了 NOP 的待遇。咱们把根节点的 `FDT_END_NODE` 改成了 NOP,dtc 读到它一声不吭地跳过,直到读出 `FDT_END` 的时候才发现深度对不上。规范的要求是任何程序都得忽略它,而 dtc 的表现跟要求一致。

那咱们自己那个没防线的 walk.py 呢?你也拿坏产物喂喂它:

```shell
python3 walk.py bad-prop-len.dtb
```

```output
/  compatible = 256 字节
遍历结束,栈深度 1,读指针停在 0x14c,结构块末端 0xe4
```

它倒是没有报错,而退出码还是 0。面对 0x100 的 len 它照单全收,报出了“compatible 长 256 字节”的假话,读指针冲到了 0x14c,比结构块的末端还远,栈里还挂着没关的门。截断的产物喂进去更狼狈,指针一口气冲到了 0x10e,而那个偏移已经出了文件尾,Python 报出来的是一句没头没脑的 `ValueError: subsection not found`。咱们这个没防线的遍历器有两种死相,要么悄悄地算错,要么不明不白地崩掉,而哪种都比 dtc 那四句话差得远。

## 咱们的遍历器开工前,防线清单一并列出来

edtc 的 DTB reader 目前还没动工,工程还停在输入与环境的那一层,所以下面是设计,而不是代码回顾。清单里的每一条,你都能在上面五个坏产物里找到对应的证词:

- 长度对总数:把文件头里的 totalsize 与实际读到的字节数相比,不够就整个拒绝,别进结构块,trunc200.dtb 的证词在这里。
- 出界判在动手前:每读一个记号、一段名字、一个 `len`、一段值,咱们都把“当前位置加本次长度”与结构块末端比一遍,再与产物末端比一遍,超了就带着偏移报错,bad-prop-len.dtb 的证词在这里。
- 对齐算出来,不猜出来:读指针只在 4 字节边界上取记号,名字与值读完向上取整前进,读到不在边界上的记号开头,产物本身就有假,这一条没有坏产物证词,它拦的是更刁钻的错位。
- 配对有始有终:`FDT_BEGIN_NODE` 与 `FDT_END_NODE` 必须配平,`FDT_END` 只许在深度归零时到场,整块只许有一个,遍历收工时栈必须是空的,bad-depth.dtb 的证词在这里。
- 生面孔一律拒绝:五种记号之外的值就是坏产物,报出偏移和值,不猜含义也不跳过,bad-opcode.dtb 的证词在这里。
- 字符串索引两头都查:nameoff 要落在字符串块的范围内,从那里到块尾之间必须找得到 `\0`,两头任一头失守都拒绝,bad-nameoff.dtb 的证词在这里。
- NOP 无罪放行:它不带数据,出现在哪条缝里都合法,咱们跳过就行,连计数都不必。

咱们在清单之外还留了半条,它的作用是提醒:规范要求属性排在子节点前面,而 dtc 对乱序只告警。咱们到时可以选严格拒绝,也可以学 dtc 宽容地告警,这个取舍咱们留到 DTB reader 动工时再定,现在咱们只要知道有这个岔路。

## 交棒:下一章,字节怎样成为可查询的树

咱们走到这里,你手里的遍历器能把结构块读成一串带路径的节点和属性了,但是属性值还是生字节。`compatible` 的值你不知道该按字符串读,`reg` 的值你不知道该按几个 cell 切,而字节要变成“能查的树”,中间还差着一层解释的活。接棒的正是下一章“字节怎样成为可查询的树”:咱们把遍历的产出装进树模型,原始属性与已知属性的解读分开对待,phandle 的索引也立起来。edtc 的 DTB reader 与树模型也就从那一章起步。

## 本节自检

文章读完了,你拿六个小问题验一验自己,想好了再展开参考答案。

1. status 的 len 是 5,从记号开头到下一个记号,读指针前进了多少?`acme,uart` 的 len 是 10 呢?
2. compatible 属性出现了两次,字符串块里存了几份?两条 `FDT_PROP` 靠什么指到它?
3. 字符串块自己有对齐的要求吗?块里的名字靠什么分隔,补零省到哪去了?
4. 五个坏产物各自让 dtc 报了什么?每一句背后是哪条防线在拦?
5. 没防线的 walk.py 吃下 len 越界的产物时干了什么?它退出码是多少,这说明什么?
6. 防线清单里哪一条没有坏产物的证词?它拦的是什么样的错?

<details>
<summary>参考答案(想好再展开)</summary>

1. status 前进 4 + 4 + 4 + 5 = 17 个字节,再向上取整到 4 的倍数是 20。`acme,uart` 前进 4 + 4 + 4 + 10 = 22,取整到 24,补了 2 个零。
2. 存一份,11 个字节住在字符串块开头。两条 `FDT_PROP` 的 nameoff 都是 0,同一个偏移指着同一份名字,共享就是这么省字节的。
3. 没有,规范明说字符串块没有对齐的要求,出现在产物里的哪个偏移都行。名字一个挨着一个,分隔只靠一个 `\0`,补零也一并省了,`reg\0` 后面紧跟的就是 `clock-frequency`。
4. 截断报 `EOF before reading 293 bytes of DT blob`,拦在按 totalsize 读入那一步。len 越界报 `Premature end of data parsing flat device tree`,拦在逐段读数据的边界检查。nameoff 越界报 `String offset 4096 overruns string table`,拦在字符串块索引。配对缺口报 `Premature FDT_END in device tree blob`,拦在深度检查。生面孔记号报 `Invalid opcode word 00000007`,拦在记号分发。
5. 它报出了“compatible 长 256 字节”的假话,读指针冲过结构块末端,栈里还剩一层没关的门,退出码是 0。没有防线时最坏的失败是悄悄算错还自称成功。
6. 对齐那一条。五个坏产物没给它当证词,它拦的是更刁钻的错位:记号的开头落在了不对齐的偏移上,那样的产物本身就有假。

</details>

## 延伸阅读

咱们本篇的实验与五句报错的出处都在这里:

- [dtc 手册(官方仓库)](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/tree/Documentation/manual.txt):`-I dtb` 的行为与命令行选项的正式说明。
- [dtc 源码(官方仓库)](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/):五句报错的老家在 flattree.c,本仓 edtc/reference/ 留有 1.8.1 的源码拷贝,git 不跟踪,磁盘上能翻到。内核与 U-Boot 运行时常用的 libfdt 也住在同一仓库,第三卷再细看它。
