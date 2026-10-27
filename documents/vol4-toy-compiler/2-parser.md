---
title: "递归下降的语法器怎么把记号挂成树?"
volume: 4
chapter: 13
section: 2
order: 132
description: "toyparse.py 的下半段是树模型加语法器加打印器:每条文法配一个函数,parse_member 多看一个记号分属性和子节点,demo.dts 试跑整棵树都解了出来,打印器照 dtc 反编译的猜法把混合值印成四个 cell"
status: draft
---

# 记号怎么一层层挂成树?

记号切好了,挂树的活儿轮到语法器。上一篇的词法器只交出了一串线性的记号,咱们这一篇贴 toyparse.py 的下半段,把树一层层地挂出来,贴完了就拿 demo.dts 试跑,看整棵树怎么回到咱们的眼前。

## 语法器:递归下降,把记号挂成树

下半段的代码接着贴,树模型、语法器和打印器就都在里面了。咱们照着“从字节到自己的树”那卷的老原则办:树模型不记源码的写法,落进去的只有字节。

```python
# ---------- 树模型 ----------

class Node:
    def __init__(self, name, line):
        self.name = name
        self.line = line
        self.props = []     # [(属性名, 原始字节)]
        self.children = []


# ---------- 语法:递归下降,把记号挂成树 ----------

class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0

    def peek(self):
        j = self.i
        return self.toks[j] if j < len(self.toks) else None

    def take(self):
        tok = self.peek()
        if tok is None:
            raise DTSError(self.last_line, 1, "文件到这里就结束了,语法还没写完")
        self.i += 1
        return tok

    @property
    def last_line(self):
        return self.toks[self.i - 1].line if self.i else 1

    def want(self, kind, value, what):
        tok = self.peek()
        if tok is None:
            raise DTSError(self.last_line, 1, f"这里该是{what},文件却到头了")
        if tok.kind != kind or tok.value != value:
            raise DTSError(tok.line, tok.col,
                           f"这里该是{what},却读到了 {tok.value!r}")
        return self.take()

    def parse_file(self):
        self.want("dir", "/dts-v1/", "开头的 /dts-v1/ 指令")
        self.want("punct", ";", "跟在 /dts-v1/ 后面的分号")
        root = self.parse_node(is_root=True)
        if self.peek() is not None:
            tok = self.peek()
            raise DTSError(tok.line, tok.col, "根节点都关上了,后面又多出了东西")
        return root

    def parse_node(self, is_root=False):
        head = self.take()
        if is_root:
            if head.kind != "punct" or head.value != "/":
                raise DTSError(head.line, head.col, "这里该是根节点的 /")
            name = "/"
        else:
            if head.kind != "name":
                raise DTSError(head.line, head.col, "这里该是节点名,却读到了别的")
            name = head.value
            nxt = self.peek()
            if nxt and nxt.kind == "punct" and nxt.value == "@":
                self.take()
                unit = self.take()
                if unit.kind not in ("name", "num"):
                    raise DTSError(unit.line, unit.col, "@ 后面该是单元地址")
                name = f"{name}@{unit.raw}"
        self.want("punct", "{", f"节点 {name} 名字后面的 {{")
        node = Node(name, head.line)
        while True:
            tok = self.peek()
            if tok is None:
                raise DTSError(self.last_line, 1, f"节点 {name} 还欠一个 }}")
            if tok.kind == "punct" and tok.value == "}":
                self.take()
                self.want("punct", ";", f"节点 {name} 的 }} 后面的分号")
                return node
            self.parse_member(node)

    def parse_member(self, node):
        name_tok = self.take()
        if name_tok.kind != "name":
            raise DTSError(name_tok.line, name_tok.col,
                           "这里该是属性名或子节点名,却读到了 "
                           f"{name_tok.value!r}")
        nxt = self.peek()
        if nxt is None:
            raise DTSError(name_tok.line, name_tok.col,
                           f"{name_tok.value} 后面文件就到头了")
        if nxt.kind == "punct" and nxt.value == "=":
            node.props.append((name_tok.value, self.parse_property(name_tok.value)))
        elif nxt.kind == "punct" and nxt.value == ";":
            self.take()
            node.props.append((name_tok.value, b""))
        elif nxt.kind == "punct" and nxt.value in ("{", "@"):
            self.i -= 1
            node.children.append(self.parse_node())
        else:
            raise DTSError(name_tok.line, name_tok.col,
                           f"属性 {name_tok.value} 后面该是 =、分号或 {{,却读到了 {nxt.value!r}")

    def parse_property(self, name):
        self.want("punct", "=", "=")
        data = b""
        while True:
            data += self.parse_piece()
            nxt = self.peek()
            if nxt and nxt.kind == "punct" and nxt.value == ",":
                self.take()
                continue
            break
        self.want("punct", ";", f"属性 {name} 写完后的分号")
        return data

    def parse_piece(self):
        tok = self.take()
        if tok.kind == "str":
            return tok.value.encode() + b"\x00"
        if tok.kind == "punct" and tok.value == "<":
            out = b""
            while True:
                nxt = self.peek()
                if nxt is None:
                    raise DTSError(self.last_line, 1,
                                   "cells 还没闭上,文件就到头了")
                if nxt.kind == "punct" and nxt.value == ">":
                    self.take()
                    return out
                if nxt.kind != "num":
                    raise DTSError(nxt.line, nxt.col,
                                   f"cells 里该是数字,却读到了 {nxt.value!r}")
                self.take()
                out += nxt.value.to_bytes(4, "big")
        if tok.kind == "punct" and tok.value == "[":
            out = bytearray()
            while True:
                nxt = self.peek()
                if nxt is None:
                    raise DTSError(self.last_line, 1,
                                   "字节串还没闭上,文件就到头了")
                if nxt.kind == "punct" and nxt.value == "]":
                    self.take()
                    return bytes(out)
                if nxt.kind != "byte":
                    raise DTSError(nxt.line, nxt.col,
                                   f"字节串里该是两位十六进制,却读到了 {nxt.value!r}")
                self.take()
                out.append(nxt.value)
        raise DTSError(tok.line, tok.col,
                       "属性值该是字符串、<cells> 或 [字节],却读到了 "
                       f"{tok.value!r}")


# ---------- 打印:照 dtc 反编译的猜法,把字节显示回人样 ----------

def show_prop(data):
    if not data:
        return ""
    if data[-1] == 0:
        parts = data[:-1].split(b"\x00")
        if all(32 <= b < 127 for part in parts for b in part):
            return ", ".join(f'"{part.decode()}"' for part in parts)
    if len(data) % 4 == 0:
        cells = [int.from_bytes(data[k:k + 4], "big") for k in range(0, len(data), 4)]
        return "<" + " ".join(f"0x{c:x}" for c in cells) + ">"
    return "[" + " ".join(f"{b:02x}" for b in data) + "]"


def dump(node, depth=0):
    pad = "\t" * depth
    print(f"{pad}{node.name} {{")
    for name, data in node.props:
        if data:
            print(f"{pad}\t{name} = {show_prop(data)};")
        else:
            print(f"{pad}\t{name};")
    for child in node.children:
        dump(child, depth + 1)
    print(f"{pad}}};")


def main():
    with open(sys.argv[1], encoding="utf-8") as fh:
        src = fh.read()
    try:
        root = Parser(lex(src)).parse_file()
    except DTSError as exc:
        print(f"{sys.argv[1]}: {exc}", file=sys.stderr)
        raise SystemExit(1)
    dump(root)


if __name__ == "__main__":
    main()
```

每一条文法在代码里都有一个对应的函数,咱们列个对照表:

| 文法的那一条 | 对应的函数 | 它干的活 |
| ---- | ---- | ---- |
| 文件与根节点 | `parse_file()` | 认开头的指令,把根节点交出来 |
| 节点与节点体 | `parse_node()` | 认名字与 `@`,一层层往下钻 |
| 属性还是子节点 | `parse_member()` | 多看一个记号再定身份 |
| 值的拼接 | `parse_property()` | 逗号隔开的片段拼成一段字节 |
| 三种片段 | `parse_piece()` | 字符串、cells、字节串各认各的 |

咱们想分清属性和子节点,靠的就是多看一个记号:名字开头的两种东西长得一样,名字后面跟 `=` 或分号的是属性,跟 `{` 或 `@` 的是子节点。`parse_member` 的做法是多看一个记号再定身份,定完把读过的位置退回去,退回去的位置由 `parse_node` 接着用。节点套节点怎么办?`parse_node` 里再调 `parse_node` 就是了,递归下降里的机关就这些,靠的就是文法本身的形状。

文件敲全了,咱们拿 demo.dts 试跑:

```shell
python3 toyparse.py demo.dts
```

```output
/ {
	compatible = "acme,demo-board", "acme,demo-soc";
	model = "Acme Demo Board";
	#address-cells = <0x1>;
	#size-cells = <0x1>;
	uart@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
		clock-frequency = <0x1c200>;
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
		poll-interval = <0x14>;
		key-codes = <0x1c 0x1d 0x35 0x65736300>;
	};
};
```

整棵树都解出来了,形状也照源码的样子回来了。值得你盯一眼的是 `key-codes` 那一行:源码里咱们写的是 `<0x1c 0x1d 0x35>, "esc"` 的混合值,两段拼起来的 16 个字节进了树模型,打印器照 dtc 反编译的猜法把它印成了四个 cell。猜法的规则你在“怎样描述和组织设备”那章已经见过了:像文本又以零收尾的按字符串印,长度被 4 整除的按 cells 印,剩下的按字节串印。树模型里没有源码写法的事,留下的只有字节,形式猜得跟源码的不一样,也不算解析器的错。

树解出来了,打印也像模像样了,可咱们手里还只有好输入。解析器的成色,咱们下一篇请坏输入来当考官,看咱们的报错怎么指着位置说话。

## 本节自检

这一篇读完了,你拿三个小问题验一验自己,想好了再展开参考答案。

1. `parse_member` 分属性和子节点,为什么得多看一个记号?
2. 树模型里属性值存的是什么?打印器凭什么把 key-codes 印成了 cells?
3. 节点套节点,递归下降靠什么一层层挂下去?

<details>
<summary>参考答案(想好再展开)</summary>

1. 名字开头的属性和子节点长得一样,得看名字后面跟的是 `=`、分号还是 `{`、`@` 才能定身份,所以 `parse_member` 多看一个记号,定完再把位置退回去。
2. 存的只有原始字节。打印器照搬 dtc 反编译的猜法:像文本又以零收尾的按字符串印,长度被 4 整除的按 cells 印,剩下的按字节印。key-codes 的 16 个字节被 4 整除,又夹着印不出来的字节,就成了四个 cell。
3. 靠的就是文法本身的形状。`parse_node` 里再调 `parse_node` 就是了,子结构的活干完就返回,全程只有普普通通的函数调用。

</details>
