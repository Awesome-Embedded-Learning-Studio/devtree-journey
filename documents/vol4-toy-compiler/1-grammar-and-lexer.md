---
title: "全量文法圈哪一块,词法器怎么切出记号?"
volume: 4
chapter: 13
section: 1
order: 131
description: "第四卷开卷坐上编译器的位置:全量 DTS 文法块头太大,咱们把认的范围写成一页产生式清单,五种值的写法进了树模型全摊平成字节,词法语法分两层,demo.dts 备齐,词法器一个循环切出带行列的记号,括号栈记着待在哪种括号里"
status: draft
---

# 轮到咱们自己造:一小段 DTS 怎么切成记号?

前三卷你一直站在工具的另一头。“改一行 DTS,产物发生了什么”那章里你只改过一个数,产物就跟着换了字节。“从字节到自己的树”那卷里咱们把 DTB 的字节一段段读开,养出了自己的树模型和能写回的 writer。“U-Boot 与 Linux 如何消费设备树”那卷里咱们陪走了全程。到第四卷咱们就换工位:坐上编译器的位置,咱们自己把一段 DTS 读成树,再编出第一个属于自己的 DTB。

这一章的活是一条流水线:咱们圈出一小块文法,给文法配上小巧的词法器与语法器,把源码解成内存里的树模型,再写精简的 writer 编出 DTB,验证的活儿交给本机的 dtc,咱们拿它对拍。

咱们把工具与日子交代清楚:手搓的部分用 python3 写,裁判的活儿交给 dtc v1.8.1,实验跑在 2026-10-18 这天的本机,动手的目录开在 /tmp/vol4ch13。你跟着做的话,照着建一个同样的目录就能复现全部输出。

## 全量文法太大,咱们圈一块自留地

咱们得圈地,原因其实很实在:全量 DTS 文法的块头很大。咱们把单子念一念你就明白了:`/include/` 指令、C 预处理器的宏、标签与引用、删除指令、括号表达式、`/bits/` 位宽写法、overlay,全量的文法哪个都得认。咱们的玩具一次吃不下这么多,干脆把要认的范围写成一页清单,清单外的写法一律拒收。拒收其实也算一种诚实:报错的时候不装懂,轮到真出事才露馅的编译器反而误事。

清单咱们用产生式的样子写,这些符号的读法很省事:X 写的就是 X 自己,方括号裹着的表示可有可无,竖线表示的是二选一,大括号里的表示重复零次以上。子集文法的定义就下面这几行:

```text
文件     := "/dts-v1/" ";" 根节点
根节点   := "/" 节点体
节点     := 名字 ["@" 单元地址] 节点体
节点体   := "{" {属性 | 节点} "}" ";"
属性     := 名字 ";" | 名字 "=" 值 ";"
值       := 片段 {"," 片段}
片段     := 字符串 | "<" 数字 {数字} ">" | "[" 字节 {字节} "]"
注释     := "//" 到行尾 | "/*" 跨行到 "*/"
```

值的五种写法你在“怎样描述和组织设备”那章已经认全了,咱们的子集把五种全都收进来,外加一种不带值的写法。各写法进了树模型变成什么,咱们列表对一遍:

| 值的写法 | 例子 | 进了树模型的字节 |
| ---- | ---- | ---- |
| 字符串 | `"acme,uart"` | 文本的字节,结尾多补一个 0 |
| 字符串列表 | `"acme,a", "acme,b"` | 两段文本各带 0 连着排 |
| cells | `<0x1000 0x100>` | 每个数字摊成 4 个字节,大端 |
| 字节串 | `[de ad be ef]` | 两位十六进制原样落字节 |
| 混合 | `<0x1>, "x"` | 各段的字节依次连排 |

“进了树模型的字节”那一栏值得你多看一眼:五种写法进了树模型就全部摊平成了字节,原来的写法没了踪影,留下的只有字节。不带值的写法就是布尔属性,名字后面连 `=` 都省了,树模型里给它存的是一段长度为零的空字节。

节点起名的规则沿用“怎样描述和组织设备”那章的条款:名字的长度在 1 到 31 个字符之间,开头的字符得是字母,可用的字符是数字与大小写字母,外加的符号有 `, . _ + -` 几样,同层的名字不能重复。`@` 后面住的是单元地址,按惯例跟 `reg` 的第一个地址保持一致。至于 `@` 与 `reg` 的搭配检查(有 `@` 没 `reg` 就告警的那类),咱们本章不做,那是 dtc 的语义检查层,咱们本章只管把字符读成树,搭配对不对留给读回之后的核对环节。

清单外的写法,去处也定好了。标签与 `&` 引用牵扯 phandle 的分配与回填,咱们把它们整个划到下一章,下一章的名字就叫“标签和引用怎样变成二进制?”。`/include/`、宏、表达式、`/bits/`、overlay、删除指令这些更外圈的写法,咱们把归宿定在“如何逐步接近实际输入”那章的进度里,摊子会在那里一点一点地收起来。眼下咱们的编译器见了它们就报错,报错里也会把话说清楚了,明说这是子集外的写法。

地的边界画好了,读源码的活也就能够开工了。不过代码还一行没写,咱们得把一件事情想清楚:读 DTS 的活为什么要分成词法与语法两层?实验的材料也得备上,本篇接下来就把这两件事一起办了。

## 词法管切字符,语法管挂树,位置得跟着走

两层怎么分工?词法(lexer)的活是把字符流切成记号,语法(parser)的活是把记号挂成树。记号是一小段有了身份的字符:咱们拿到 `uart@1000 {` 这样的开头,词法器切出的记号依次是名字 uart、符号 `@`、数字 1000、符号 `{`,每个记号都随身带着自己的行号和列号。

语法层咱们用递归下降的手法,名字倒是唬人,道理其实很家常:咱们给每条文法规则配一个函数,函数会看一眼当前的记号,下一步调用谁由记号说了算,子结构的活干完就返回,树一层层地挂出来。全程只有普普通通的函数调用,你跟着咱们的 Python 读一遍就能看穿它。

源码位置为什么得从头带着走?因为错误信息少了位置就没法定位,修输入的人只好拿肉眼一行行扫。dtc 的做法你在“改一行 DTS,产物发生了什么”那章见过了:告警里带着起止的行列,`namecases.dts:12.10-14.4: Warning (unit_address_vs_reg) ...` 就是它的样子,起止的行列全都摆在明面上。咱们的玩具定同样的标准:记号一出生就带上了行号列号,报错一律站在出错记号的头上说话。

## 咱们的实验素材:把子集写全的 demo.dts

动手的目录开好了,咱们接着把材料备上:

```shell
mkdir -p /tmp/vol4ch13
cd /tmp/vol4ch13
```

你把下面的内容原样存成 demo.dts 就行,五种值的写法、布尔属性、带单元地址的节点、不带地址的节点,全在它身上凑齐了:

```dts
/dts-v1/;

/ {
	compatible = "acme,demo-board", "acme,demo-soc";
	model = "Acme Demo Board";
	#address-cells = <1>;
	#size-cells = <1>;

	uart@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
		clock-frequency = <115200>;
		status = "okay";
	};

	otp@50 {
		compatible = "acme,otp";
		reg = <0x50 0x8>;
		serial-number = [de ad be ef 5a a5];
	};

	keys {
		compatible = "acme,gpio-keys";
		autorepeat;
		poll-interval = <20>;
		key-codes = <0x1c 0x1d 0x35>, "esc";
	};
};
```

分工想清楚了,材料也备齐了,接下来咱们就动笔写词法器,看它怎么把 demo.dts 的字符流切成一个个带位置的记号。

## 词法器:字符流进,带位置的记号出

咱们把词法器、语法器和打印器写在同一个 toyparse.py 里,全部加起来三百来行的样子。上半段管的是词法,咱们连文件头一起贴在下面,你照着敲的时候,文件的名字就叫 toyparse.py:

```python
#!/usr/bin/env python3
"""toyparse.py —— 子集 DTS 的词法加语法,把源码解成树模型再打印出来"""

import sys
from collections import namedtuple

Token = namedtuple("Token", "kind value line col raw", defaults=(None,))


class DTSError(Exception):
    """带源码位置的报错,line 是行号,col 是列号,都从 1 起数"""

    def __init__(self, line, col, msg):
        super().__init__(f"{line}:{col}: {msg}")


# ---------- 词法:把字符流切成记号 ----------

NAME_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789,._+*#?-"
)
PUNCT = "{}<>[]=;,@/"


def lex(src):
    toks = []
    i, line, col = 0, 1, 1
    stack = []  # 记着咱们待在 <> 还是 [] 里,元素是 "<" 或 "["

    def err(msg):
        raise DTSError(line, col, msg)

    while i < len(src):
        ch = src[i]
        if ch == "\n":
            i += 1
            line += 1
            col = 1
            continue
        if ch in " \t\r":
            i += 1
            col += 1
            continue
        if src.startswith("//", i):
            while i < len(src) and src[i] != "\n":
                i += 1
                col += 1
            continue
        if src.startswith("/*", i):
            i += 2
            col += 2
            while i < len(src) and not src.startswith("*/", i):
                if src[i] == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
                i += 1
            i += 2
            col += 2
            continue
        if src.startswith("/dts-v1/", i):
            toks.append(Token("dir", "/dts-v1/", line, col))
            i += 8
            col += 8
            continue
        if ch == '"':
            start_col = col
            i += 1
            col += 1
            out = []
            while i < len(src) and src[i] != '"':
                if src[i] == "\n":
                    err("字符串没写完就换行了")
                if src[i] == "\\" and i + 1 < len(src):
                    out.append(src[i + 1])
                    i += 2
                    col += 2
                else:
                    out.append(src[i])
                    i += 1
                    col += 1
            if i >= len(src):
                raise DTSError(line, start_col, "字符串没写完,文件就到头了")
            i += 1
            col += 1
            toks.append(Token("str", "".join(out), line, start_col))
            continue
        if ch in PUNCT:
            if stack and stack[-1] == "<" and ch in ";,{[":
                err(f"尖括号还没闭上,却读到了 {ch!r}")
            if stack and stack[-1] == "[" and ch in ";,{<":
                err(f"方括号还没闭上,却读到了 {ch!r}")
            if ch in "<[":
                stack.append(ch)
            elif ch in ">]":
                opener = {">": "<", "]": "["}[ch]
                if not stack or stack[-1] != opener:
                    err(f"多出来一个 {ch!r}")
                stack.pop()
            toks.append(Token("punct", ch, line, col))
            i += 1
            col += 1
            continue
        # 剩下的都按“词”读:名字、数字、字节
        start = i
        while i < len(src) and src[i] in NAME_CHARS:
            i += 1
            col += 1
        word = src[start:i]
        if not word:
            err(f"不认识的字符 {ch!r}")
        if stack and stack[-1] == "[":
            if len(word) == 2 and all(c in "0123456789abcdefABCDEF" for c in word):
                toks.append(Token("byte", int(word, 16), line, col - 2))
            else:
                err(f"方括号里该是两位十六进制字节,却读到了 {word!r}")
        elif word[0].isdigit():
            try:
                toks.append(Token("num", int(word, 0), line, col - len(word), word))
            except ValueError:
                err(f"数字的写法不认得:{word!r}")
        elif stack and stack[-1] == "<":
            err(f"尖括号里只认数字,却读到了 {word!r}")
        else:
            toks.append(Token("name", word, line, col - len(word)))
    return toks
```

词法器的主干是一个 while 循环,每转一圈咱们就收获一个记号。空白与注释的字符直接跳过去,不产生任何的记号,行号列号在跳的时候照样推进。字符串、数字、名字和各类符号各有各的认法,咱们挑两个值钱的细节说。

头一个细节是那个名叫 stack 的栈。`<>` 里住的该是数字,`[]` 里住的该是两位十六进制,可字符层面上 `1c` 这样的词跟名字长得一模一样,词法器得清楚地记得自己待在哪种括号里,不然就分不清了。栈就是它的记性:咱们读到 `<` 或 `[` 就压一层,读到收尾的 `>` 或 `]` 就弹一层,待在 `<>` 里读到别的名字,报错写的就是“尖括号里只认数字”。真实世界里的标签与引用就住在尖括号里,咱们的子集把它们划出去了,咱们让词法器见了就明说。

另一个细节是行列的推进。列号一个字符一个字符地加,行号只在换行的地方加一,跨行的注释里循环也把行号带着走,咱们一路这么记着,每个记号拿到的行列就都是它在源文件里的真实住址。报错的底气全从这里来。

词法器把记号切好了,记号身上的行号列号也都齐了,可它们还躺在一串线性的列表里,树的影子都还没有。下一篇咱们写语法器,看递归下降怎么把记号一层层地挂成树,挂完了再拿 demo.dts 试跑一遍。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. 咱们的子集拒收了哪些写法?拒收为什么也算一种诚实?
2. 五种值的写法进了树模型,各自变成什么?不带值的写法又存了什么?
3. 节点起名的条款有哪几条?`@` 与 `reg` 的搭配检查为什么本章不做?
4. 词法器交出的记号长什么样?拿 `uart@1000 {` 这样的开头说一说。
5. 递归下降的名字唬人,道理是什么?
6. 源码位置为什么得从头带着走?
7. 词法器在尖括号里读到 uart 这样的词,它会怎么报?行号列号是谁记下的?
8. 词法器靠什么记得自己待在尖括号还是方括号里?

<details>
<summary>参考答案(想好再展开)</summary>

1. `/include/` 指令、C 预处理器的宏、标签与引用、删除指令、括号表达式、`/bits/` 位宽写法、overlay,清单外的写法一律拒收。报错的时候不装懂,轮到真出事才露馅的编译器反而误事。
2. 五种写法全部摊平成了字节,原来的写法没了踪影:字符串与字符串列表带 0 排字节,cells 每个数字摊成 4 个字节大端排,字节串两位十六进制原样落字节,混合值各段的字节依次连排。不带值的写法是布尔属性,树模型里存的是一段长度为零的空字节。
3. 名字的长度在 1 到 31 个字符之间,开头的字符得是字母,可用的字符是数字与大小写字母,外加 `, . _ + -` 几样,同层的名字不能重复。搭配检查是 dtc 的语义检查层,咱们本章只管把字符读成树,搭配对不对留给读回之后的核对环节。
4. 词法器切出的记号依次是名字 uart、符号 `@`、数字 1000、符号 `{`,每个记号都随身带着自己的行号和列号。
5. 道理其实很家常:咱们给每条文法规则配一个函数,函数会看一眼当前的记号,下一步调用谁由记号说了算,子结构的活干完就返回,树一层层地挂出来,全程只有普普通通的函数调用。
6. 错误信息少了位置就没法定位,修输入的人只好拿肉眼一行行扫。咱们的玩具定了跟 dtc 一样的标准:记号一出生就带上了行号列号,报错一律站在出错记号的头上说话。
7. 报的是“尖括号里只认数字,却读到了 'uart'”。行号列号是词法器产出记号时顺手记下的,每个记号从出生就带着位置。
8. 靠那个名叫 stack 的栈。读到 `<` 或 `[` 就压一层,读到收尾的 `>` 或 `]` 就弹一层,待在 `<>` 里读到别的名字,报错写的就是“尖括号里只认数字”。

</details>

## 延伸阅读

咱们这一篇用到的正式出处,给你备好了:

- [DTS 格式说明(上游 dtc 仓库)](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/tree/Documentation/dts-format.txt):dtc 官方的 DTS 语法描述,本章子集认的写法在这里都有正式条款。
- [Devicetree Specification v0.4](https://github.com/devicetree-org/devicetree-specification/releases/tag/v0.4):规范第 6 章是 DTS 源格式的正式定义,给节点起名的条款在 2.2.1,本仓缓存了全文副本。
