---
title: "一串字节,怎么变成我手里能查的树?"
volume: 2
chapter: 6
section: 1
order: 61
description: "遍历器的记号流用栈挂成节点,节点存名字路径属性表和孩子列表,属性永远有原始字节打底,解读只叠在已知类型的名字上。动手的活也在这里兑现:tree.py 七个函数把 mini.dtb 立成树,dump 的每行末尾都带字节数作证,clock-frequency 印成 0x1c200,REPL 里按路径取节点,原始字节与解读两层各拿各的"
status: draft
---

# 一串字节,怎么变成我手里能查的树?

“如何安全遍历所有节点”那章的收尾你已经见过:walk.py 走完结构块,七行属性一行行报了出来,栈深度归了零,读指针不多不少停在结构块的末端。可那七行只是当着你的面滚了过去,你想回头再问一句“serial@1000 的 reg 是什么”,它转身就忘了个干干净净,所以咱们想再问就只剩一条路:把产物从头重走一遍。遍历器交活的路数你在那章也见过了:顺着记号往前走,报到的行打印完就翻篇,内存里什么都没留下。

这一章要办的事就是把流变成树:遍历器报出来的每一个事件都由树模型接住挂好,走完之后树还稳稳地站在内存里,你想查哪条就问哪条。属性的字节照旧是老底,咱们在字节上面叠一层“已知类型”的解读,再把 phandle 的数值收成一张索引。咱们没法一口气干完这些活,本篇立的是模型的骨架,再当场把它立成树:事件怎么挂成节点?属性凭什么分两层?设计的事在这儿定下,动手的活跟着就到。

## 遍历器交回来的是一串事件,树模型把它们挂成节点

咱们把遍历器的产出说准。走结构块的循环每读到一个记号就干一件小事:读到 `FDT_BEGIN_NODE` 就宣布一个节点开了门,读到 `FDT_PROP` 就宣布一条属性到了场,读到 `FDT_END_NODE` 就宣布一个节点关了门。这样的一串宣告,习惯上叫事件流:事情一件挨着一件地报,报过的就翻篇。

树模型接的正是这串事件,接的办法你在那章见过一半:walk.py 里已经拿栈存过每层的名字,路径就是把栈里的名字用斜杠连了起来。现在咱们把栈里的名字换成货真价实的节点对象,挂在栈顶的那个就是当前开门的节点。

- 读到“节点开门”,咱们新建一个节点,挂到栈顶节点的孩子列表里,再把它压栈。根节点是特例,栈还是空的,新节点就当了根。
- 读到“一条属性”,咱们把属性名和它的原始字节放进栈顶节点的属性表,栈不用动。
- 读到“节点关门”,咱们把栈顶弹掉,爸爸重新成为当前节点。

三个事件这么走完一轮,栈空了,咱们手里的树也就挂满了。节点身上存的是四样东西:名字、路径、属性表、孩子列表。名字是查路径用的零件,路径干脆存成了节点的一个字段,查询的时候就不用每次从头拼了。属性表拿的是字典:键放的是属性名,值存的是原始字节。孩子列表保住产物里的原本次序,“怎样证明读写没有改变内容”那章把树写回产物的时候,次序不乱就是省心的凭据。

爸爸要不要存?咱们写的脚本用不着,报路径的活已经被存好的路径干了。edtc 的正式设计里倒是要留一个向上的指针,报错的时候从出事的节点一路爬回根,全程的路径都报得出来。

## 属性永远有原始字节打底,解读只叠在已知类型上

树挂起来了,属性表里躺着的却还是生字节。“怎样描述和组织设备”那章你已经知道底细:产物里的属性值只有一段字节和它的长度,尖括号和方括号都是源码层的写法,进了 DTB 就一律摊平了。所以树模型在属性上分了两层:

- 底层是原始字节,每个属性的值照原样存着,一个字节都不动。咱们不信任任何猜测,这层就是底线:解读层说岔了,字节还在,推倒重来就是。
- 上面一层是解读,只对“已知类型”的属性开放。名字认得出来,咱们才按它的形式去读:compatible 和 status 是字符串,clock-frequency、#address-cells、#size-cells、phandle 是单个 cell,reg 是一串 cell。

解读层的凭据只有一条:属性名在已知表里。表是咱们自己写的最小集,认多少全由表说了算,表外的名字一律只报字节。你想追问一句“你是怎么知道的”,解读层得答得上来:答案就是表里的那一行,而不是字节长得像什么。reg 的解读咱们还要说得更诚实一点:真要把 reg 切成地址和长度,得去读父节点上的 #address-cells 和 #size-cells,咱们的小脚本没做这一步,只是把全部字节按 cell 排着印了出来。

查询接口的样子也就两层都露在了外面:你按路径找到节点,按属性名取到的既有解读也有原始字节。“这个 DTB 文件如何布局”那章解文件头的时候你手工干过同样的活,现在咱们把它交给代码。

骨架定住了,动手的活接下来就到:咱们照着设计写 tree.py,当场立起 mini.dtb 的树。

## 动手:tree.py 把 mini.dtb 立成树

动手的家什还是老三样,本仓验证的工具是 dtc v1.8.1,实验咱们照旧搬进 /tmp/vol2ch6 里做,跑命令的日子是 2026-10-18。咱们照旧在 /tmp 里开工,编的还是老熟人 mini.dts:

```shell
mkdir -p /tmp/vol2ch6
cd /tmp/vol2ch6
dtc -I dts -O dtb -o mini.dtb /home/charliechen/devtree-journey/edtc/example/00_bootstrap/mini.dts
```

脚本咱们存成 tree.py,全文的篇幅是一百二十多行,函数拆成了七个,咱们让每个函数只干一件事:

```python
#!/usr/bin/env python3
"""tree.py:把一个 DTB 立成树并打印,REPL 里也能 import 来查。"""
import struct
import sys

BEGIN_NODE, END_NODE, PROP, NOP, END = 1, 2, 3, 4, 9

# 已知类型的属性:名字 -> 值的形式。表外的名字只报原始字节,不猜。
KNOWN = {
    "compatible": "strings",
    "status": "strings",
    "clock-frequency": "u32",
    "#address-cells": "u32",
    "#size-cells": "u32",
    "phandle": "u32",
    "reg": "u32 list",
}


class Node:
    def __init__(self, name, path):
        self.name = name      # 节点名,根节点是空串
        self.path = path      # 从根到这里的完整路径
        self.props = {}       # 属性名 -> 值的原始字节
        self.children = []    # 孩子,按产物里的先后排


def read_cstr(buf, pos):
    end = buf.index(b"\0", pos)
    return buf[pos:end].decode("ascii"), end + 1


def interpret(name, data):
    """按已知类型解读属性,返回(形式, 文本)。表外的名字只报字节。"""
    kind = KNOWN.get(name)
    if kind == "u32" and len(data) == 4:
        return "cell", "0x%x" % struct.unpack(">I", data)[0]
    if kind == "u32 list" and len(data) % 4 == 0:
        cells = struct.unpack(">%dI" % (len(data) // 4), data)
        return "cells", "<" + " ".join("0x%x" % c for c in cells) + ">"
    if kind == "strings" and data.endswith(b"\0"):
        if all(32 <= b < 127 for b in data[:-1]):
            text = '"%s"' % '" "'.join(data[:-1].decode("ascii").split("\0"))
            return "string", text
    return "bytes", data.hex(" ")


def parse(blob):
    """走一遍结构块,把记号流挂成树。边界防线见遍历器那章,这里从简。"""
    (magic, _total, off_struct, off_strings, _rsv, _ver, _comp,
     _cpu, size_strings, size_struct) = struct.unpack_from(">10I", blob, 0)
    if magic != 0xD00DFEED:
        raise SystemExit("魔数对不上,这不是 DTB 文件")
    strings = blob[off_strings:off_strings + size_strings]
    root, stack, pos = None, [], off_struct
    while pos < off_struct + size_struct:
        token = struct.unpack_from(">I", blob, pos)[0]
        pos += 4
        if token == BEGIN_NODE:      # 开门:建节点,挂到栈顶名下
            name, pos = read_cstr(blob, pos)
            pos = (pos + 3) & ~3
            if stack:
                node = Node(name, stack[-1].path.rstrip("/") + "/" + name)
                stack[-1].children.append(node)
            else:
                node = Node(name, "/")
                root = node
            stack.append(node)
        elif token == PROP:          # 属性:原始字节挂到栈顶节点
            length, nameoff = struct.unpack_from(">II", blob, pos)
            pos += 8
            data = blob[pos:pos + length]
            pos = (pos + length + 3) & ~3
            name, _ = read_cstr(strings, nameoff)
            stack[-1].props[name] = data
        elif token == END_NODE:      # 关门:弹栈
            stack.pop()
        elif token == END:
            break
    return root


def dump(node, depth=0):
    pad = "    " * depth
    print(pad + node.path)
    for name, data in sorted(node.props.items()):
        form, text = interpret(name, data)
        print("%s    %-18s [%s] %s (%d 字节)" % (pad, name, form, text, len(data)))
    for child in node.children:
        dump(child, depth + 1)


def phandle_index(root):
    """树挂满之后扫一遍,收齐 phandle 数值到节点的映射。"""
    index = {}
    stack = [root]
    while stack:
        node = stack.pop()
        data = node.props.get("phandle")
        if data and len(data) == 4:
            index[struct.unpack(">I", data)[0]] = node
        stack.extend(node.children)
    return index


def find(root, path):
    """按路径找节点,比如 /serial@1000。"""
    node = root
    for part in filter(None, path.split("/")):
        node = next((c for c in node.children if c.name == part), None)
        if node is None:
            raise SystemExit("找不到节点: " + path)
    return node


if __name__ == "__main__":
    root = parse(open(sys.argv[1], "rb").read())
    dump(root)
    index = phandle_index(root)
    print()
    if index:
        print("phandle 索引(数值 -> 节点路径):")
        for value in sorted(index):
            print("  0x%x -> %s" % (value, index[value].path))
    else:
        print("树里没有 phandle 属性,索引是空的")
```

咱们把它跑起来:

```shell
python3 tree.py mini.dtb
```

```output
/
    #address-cells     [cell] 0x1 (4 字节)
    #size-cells        [cell] 0x1 (4 字节)
    compatible         [string] "edts,a_demo" (12 字节)
    /serial@1000
        clock-frequency    [cell] 0x1c200 (4 字节)
        compatible         [string] "acme,uart" (10 字节)
        reg                [cells] <0x1000 0x100> (8 字节)
        status             [string] "okay" (5 字节)

树里没有 phandle 属性,索引是空的
```

咱们挑几行读一读。每行的末尾都带着字节数,那是原始字节这一层在场的凭据,解读的那一栏印得再漂亮,字节数也照样报了出来,这就是底线的做派。clock-frequency 印成了 0x1c200,十进制的原值正是 115200,“改一行 DTS,产物发生了什么”那章你见过它的字节 00 01 c2 00,现在解读层替你把大端换算做了。compatible 印出来的字符串带着引号,结尾的那个零没印出来,但字节数那栏写的是 12:`edts,a_demo` 的十一个字符加一个结尾的零,全都算在里面了。

查询的两层接口,咱们拿 python3 的 -c 当场试:

```shell
python3 -c 'import tree
root = tree.parse(open("mini.dtb", "rb").read())
uart = tree.find(root, "/serial@1000")
print(uart.path)
print(uart.props["clock-frequency"].hex(" "))
print(tree.interpret("clock-frequency", uart.props["clock-frequency"]))
print(tree.interpret("reg", uart.props["reg"]))'
```

```output
/serial@1000
00 01 c2 00
('cell', '0x1c200')
('cells', '<0x1000 0x100>')
```

find 按路径找到了 serial@1000,咱们再从属性表里取 clock-frequency,原始字节和解读各拿各的,两层都握在了手里。你留意 interpret 对表外名字的待遇:名字不在 KNOWN 表里的时候,它干脆连试都省了,直接把字节印给你。

树立住了,查询的两层接口也就通了。产物里还没有引用的影子,标签的下场怎么样,咱们下一篇接着看。

## 本节自检

文章读完了,你拿六个小问题验一验自己,想好了再展开参考答案。

1. 遍历器报出的三个事件分别让树模型干什么?栈在其中的角色是什么?
2. 节点身上存了哪四样东西?路径为什么干脆存在节点身上?
3. 属性的两层各管什么?底层为什么一个字节都不动?
4. dump 的每一行末尾都印着字节数,它在替哪一层作证?
5. compatible 印着 12 字节,字符串本身只有 11 个字符,多出来的 1 字节是什么?
6. 在 REPL 里按路径找到节点之后,原始字节和解读各怎么拿?

<details>
<summary>参考答案(想好再展开)</summary>

1. 开门建节点挂到栈顶名下并压栈,属性的字节放进栈顶节点的属性表,关门弹栈。栈里放的是从根到当前节点的各级节点,栈顶就是当前节点。
2. 名字、路径、属性表、孩子列表。路径存在节点身上,查询的时候就不用每次从根拼下来,报路径也随手就有。
3. 底层照原样存着原始字节,上层只对已知类型的属性做解读。咱们不信任任何猜测,解读层说岔了,字节还在,推倒重来就是。
4. 替原始字节那一层作证。解读的那一栏印得再漂亮,字节数也照样报了出来,这就是底线的做派。
5. 结尾的那个零。11 个字符加一个结尾的零,合起来是 12 字节,零没印出来,字节数把它算了进去。
6. 属性表按名字取到的是原始字节,interpret 按名字和字节报出解读,两层各拿各的。

</details>
