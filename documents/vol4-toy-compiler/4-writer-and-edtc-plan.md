---
title: "树模型怎么写回第一个 DTB,edtc 的前端怎么接手?"
volume: 4
chapter: 13
section: 4
order: 134
description: "八十来行的 toywrite.py 把树模型拼成 DTB:四种 token,pad4 补齐,字符串表去重,版本 17,跑出来的 576 字节跟 dtc v1.8.1 逐字节一致,反编译与 xxd 的头部逐个对上号,末了定下 edtc 的 C++26 前端打算,词法语法两边手写,位置两头都记,交棒给标签与引用"
status: draft
---

# 咱们自己编的 DTB 怎么对上字节,edtc 又怎么接手?

树在咱们手里了,坏输入咱们也拦得住,这一篇把流水线的后半条接上:写一个精简的 writer,把树模型编成咱们自己的 DTB。编完了还不算完,咱们拿 dtc 当裁判对拍,语义等价是咱们的硬标准,字节的一致算意外之喜。

## 精简 writer 接上,第一个 DTB 出炉

树模型到手了,咱们接下来的活是把它写回 DTB。“怎样证明读写没有改变内容”那章的往返实验是咱们这里的底本:那一章的 writer 服务的是读回核对,保证编出去的 DTB 再读回来还是同一棵树。咱们写个精简版:输入就是刚才的树模型,输出的排布照“这个 DTB 文件如何布局”那章认过的老底,把头部、保留区、结构块、字符串块四个区块一一拼了起来。剩下的活交给第二个文件 toywrite.py,全部的行数也就八十来行:

```python
#!/usr/bin/env python3
"""toywrite.py —— 把树模型写成 DTB,精简版的 DTB writer"""

import struct
import sys

from toyparse import DTSError, Parser, lex

FDT_BEGIN_NODE = 1
FDT_END_NODE = 2
FDT_PROP = 3
FDT_END = 9
HEADER = ">10I"  # 十个 32 位大端整数


def pad4(blob):
    while len(blob) % 4:
        blob.append(0)


def build(root):
    strings = bytearray()
    string_off = {}

    def stroff(name):
        if name not in string_off:
            string_off[name] = len(strings)
            strings.extend(name.encode() + b"\x00")
        return string_off[name]

    body = bytearray()  # 结构块

    def emit(node):
        pad4(body)
        body.extend(struct.pack(">I", FDT_BEGIN_NODE))
        body.extend((node.name if node.name != "/" else "").encode() + b"\x00")
        for name, data in node.props:
            pad4(body)
            body.extend(struct.pack(">III", FDT_PROP, len(data), stroff(name)))
            body.extend(data)
        for child in node.children:
            emit(child)
        pad4(body)
        body.extend(struct.pack(">I", FDT_END_NODE))

    emit(root)
    pad4(body)
    body.extend(struct.pack(">I", FDT_END))

    off_rsv = 40                      # 头 40 字节,后面紧跟内存保留区
    off_struct = off_rsv + 16         # 保留区只有一条全零的结束记录
    off_strings = off_struct + len(body)
    total = off_strings + len(strings)
    header = struct.pack(
        HEADER,
        0xD00DFEED,      # magic
        total,           # totalsize
        off_struct,      # off_dt_struct
        off_strings,     # off_dt_strings
        off_rsv,         # off_mem_rsvmap
        17,              # version
        16,              # last_comp_version
        0,               # boot_cpuid_phys
        len(strings),    # size_dt_strings
        len(body),       # size_dt_struct
    )
    return header + b"\x00" * 16 + body + strings


def main():
    src_path, out_path = sys.argv[1], sys.argv[2]
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    try:
        root = Parser(lex(src)).parse_file()
    except DTSError as exc:
        print(f"{src_path}: {exc}", file=sys.stderr)
        raise SystemExit(1)
    blob = build(root)
    with open(out_path, "wb") as fh:
        fh.write(blob)
    print(f"{out_path}: {len(blob)} bytes")


if __name__ == "__main__":
    main()
```

结构块里咱们只用了四种 token,数字就是结构块 token 的值,“如何安全遍历所有节点”那章的 token 表里对得上号:

| token | 值 | 作用 |
| ---- | ---- | ---- |
| `FDT_BEGIN_NODE` | 1 | 开一个节点,后面跟名字 |
| `FDT_PROP` | 3 | 写一条属性,跟长度、字符串表偏移、数据 |
| `FDT_END_NODE` | 2 | 关一个节点 |
| `FDT_END` | 9 | 整棵树收尾 |

对齐的活儿咱们交给 `pad4`:名字与数据的长度都补到 4 的倍数,缺的拿零垫。字符串块的活是给属性名去重,表里的同一个名字只保留一份,谁后到谁用现成的偏移。头部的十个数全是 32 位大端,版本号写的是 17,最早兼容的版本写 16,内存保留区只有一条全零的结束记录。

咱们把它跑起来,裁判的活儿也一并交给 dtc:

```shell
python3 toywrite.py demo.dts demo.dtb
dtc -I dts -O dtb -o ref.dtb demo.dts
wc -c demo.dtb ref.dtb
cmp demo.dtb ref.dtb && echo "cmp: identical"
md5sum demo.dtb ref.dtb
```

```output
demo.dtb: 576 bytes
 576 demo.dtb
 576 ref.dtb
1152 total
cmp: identical
1cde077bdd67ce9faad7bf095a7c0627  demo.dtb
1cde077bdd67ce9faad7bf095a7c0627  ref.dtb
```

## 拿上游 dtc 对拍:语义等价,字节也一致

上面输出里的 cmp 一声没吭,md5 的值也一模一样,576 字节两边对上了,咱们自己的 DTB writer 编出了跟 dtc v1.8.1 逐字节相同的产物。反编译的路咱们再走一遍,树和值的对错全看它:

```shell
dtc -I dtb -O dts demo.dtb
```

```dts
/dts-v1/;

/ {
	compatible = "acme,demo-board", "acme,demo-soc";
	model = "Acme Demo Board";
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	uart@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
		clock-frequency = <0x1c200>;
		status = "okay";
	};

	otp@50 {
		compatible = "acme,otp";
		reg = <0x50 0x08>;
		serial-number = [de ad be ef 5a a5];
	};

	keys {
		compatible = "acme,gpio-keys";
		autorepeat;
		poll-interval = <0x14>;
		key-codes = <0x1c 0x1d 0x35 0x65736300>;
	};
};
```

树和值全回来了,`key-codes` 的印法跟咱们打印器的一模一样,上下游对同一份字节做出了同样的解读。咱们再把头部的 40 个字节对一遍号,xxd 的前四行就是头部:

```shell
xxd -l 64 demo.dtb
```

```output
00000000: d00d feed 0000 0240 0000 0038 0000 01c8  .......@...8....
00000010: 0000 0028 0000 0011 0000 0010 0000 0000  ...(............
00000020: 0000 0078 0000 0190 0000 0000 0000 0000  ...x............
00000030: 0000 0000 0000 0000 0000 0001 0000 0000  ................
```

| 头部的字段 | 字节 | 换算过来 |
| ---- | ---- | ---- |
| magic | `d00d feed` | DTB 的身份号 |
| totalsize | `0000 0240` | 576,与 wc -c 一致 |
| off_dt_struct | `0000 0038` | 56,头部 40 加保留区 16 |
| off_dt_strings | `0000 01c8` | 456 |
| off_mem_rsvmap | `0000 0028` | 40,紧跟头部 |
| version | `0000 0011` | 17 |
| last_comp_version | `0000 0010` | 16 |
| boot_cpuid_phys | `0000 0000` | 0 |
| size_dt_strings | `0000 0078` | 120 |
| size_dt_struct | `0000 0190` | 400 |

0x38 那个 `0000 0001` 就是根节点的 BEGIN_NODE,后面跟的空名补零到 4 字节,结构块从它起算的长度正好是 400 字节。字节对上了,咱们得把话说全:它说明咱们一路做下的几个选择,跟 dtc v1.8.1 恰好对上了,节点和属性都按源码的顺序写,名字与数据的长度都补到 4 的倍数,字符串表里的属性名只落一份,版本与兼容版本的取值也一样,保留区都只放一条全零的记录。换了输入就没有这样的保证了:咱们的子集连重复属性名的行为都没定义,更怪的输入碰上了,咱们就得把对拍重跑一遍。硬的标准是语义等价,反编译出的树跟上游的一致就算过,字节的一致算意外之喜。“怎样证明读写没有改变内容”那章的对拍套路,咱们在这里又用了一遍,将来的 edtc 每添一种新的语法,咱们都照这个办法再对拍一遍。

流水线到这一步就全通了,咱们喂进去的是源码,拿到手的是 DTB,还跟上游对上了字节。剩下的活是替 edtc 打算:Python 的预演里哪些做法值得搬进 C++26 的工程,下面咱们来交底。

## edtc 的 C++26 前端打算怎么落

咱们把话说在前面:仓库里的 edtc 是 C++26 工程,它现在的进度停在打地基的一段。文件读取的实现在 `edtc/src/base/file_reader.cpp`,字节序的辅助在 `include/edtc/base/endian.hpp`,全部家当也就这两样了,DTS 的前端和 DTB reader 的代码都还没动工。所以本章的 Python 是设计加手搓的预演,不是 edtc 的代码转写,咱们不假装那些 C++ 已经存在。

落法咱们照搬本章的分法:DTS 的前端拆成词法与语法两层,吃进的是源码,交出的是树模型,编字节的活交给 DTB writer。模块的划分你在前几卷见过:读字节进来的叫 DTB reader,认 DTS 源码的叫 DTS 前端,存字的叫树模型,写 DTB 出去的叫 DTB writer。链路的后半条已经盖好了,第四卷咱们来补前半条,等 DTS 的前端接上,自己的源码就能一路编到 DTB。

dtc 自己的前端是生成出来的:词法的部分由 flex 从 `dtc-lexer.l` 生成,语法的部分由 bison 从 `dtc-parser.y` 生成,原始的两份文件仓库里也有,位置在仓库的 `edtc/reference/dtc/` 之下,那是 dtc v1.8.1 的完整源码副本。咱们打算在 edtc 里两边都手写。词法器的手写版不难,模式栈的做法直接翻译过去就行。语法器咱们手写递归下降,图的好处很实际:报错的位置区间想记多细记多细,错误恢复的策略想怎么定就怎么定,构建的流程不用再拉生成工具。错误恢复咱们打算这么走:报错之后跳到最近的分号或右花括号再接着解析,咱们让一份源码跑完一遍,报出的错就不止一个。bison 的缺省恢复咱们调不了那么细,这是放弃它的主要原因。

位置的记法也要升级。咱们在玩具里只给记号记了起点,C++ 的版本打算两头都记,树节点再带整个节点覆盖的区间,这样告警的样式就能向 dtc 看齐,报出从几行几列到几行几列的区间,读的人一眼锁定范围。这套记法在咱们的 Python 里已经有它的雏形,升级的成本不高。

## 收工,交棒

从文法的清单到词法器、语法器、树模型,再接上精简的 writer,链路咱们算是通了,DTB 从咱们手里编了出来,还跟上游对上了字节。可子集的边界也明摆着:uart 挂时钟的引用,咱们眼下写不出来,被引的节点也拿不到自动分配的 phandle。标签的收纳、符号表的建立、引用的回填,咱们把这些活儿全留给下一章,下一章的名字就叫“标签和引用怎样变成二进制?”。include、宏、overlay 这些更外圈的写法,咱们把它们留给“如何逐步接近实际输入”那章的篇幅,摊子会在那里一点一点地收起来。往真实输入靠拢的路还长,咱们慢慢走。

## 本节自检

这一篇读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. 咱们的 writer 编出的字节跟 dtc 完全一致,靠的是哪几个共同的选择?换个输入还敢保证吗?
2. toywrite.py 里的对齐是谁在管?名字与数据的长度补到多少?
3. 字符串块里同一个属性名存几份?
4. dtc 的前端由 flex 和 bison 生成,edtc 为什么打算两边都手写?
5. 咱们的玩具只给记号记了什么?C++ 版打算多记什么?

<details>
<summary>参考答案(想好再展开)</summary>

1. 节点和属性按源码顺序写,名字和数据补齐到 4 字节,属性名在字符串表里只存一份,版本 17 加最早兼容 16,保留区一条全零记录。换个输入不敢保证,语义等价才是硬标准,字节一致只是这一次的巧合。
2. pad4 在管。名字与数据的长度都补到 4 的倍数,缺的拿零垫。
3. 只保留一份,谁后到谁用现成的偏移。
4. 为了报错和构建:手写的位置区间想记多细记多细,错误恢复能跳到最近的分号或右花括号接着报,构建也不用拉生成工具。代价是文法变长后代码量比生成器大,子集的规模下这个代价值得付。
5. 玩具里只给记号记了起点。C++ 的版本打算两头都记,树节点再带整个节点覆盖的区间,告警的样式就能向 dtc 看齐,报出从几行几列到几行几列的区间。

</details>

## 延伸阅读

本篇说到的 flex 与 bison,一手材料的出处也给你备好了:

- 仓库里的 dtc 源码副本:`edtc/reference/dtc/dtc-lexer.l` 管词法定义,`edtc/reference/dtc/dtc-parser.y` 管语法定义。上游 dtc v1.8.1 的原始文件,本仓缓存了副本,git 不跟踪,你在本地克隆里直接翻。flex 与 bison 的写法长什么样,这两份就是一手材料。
