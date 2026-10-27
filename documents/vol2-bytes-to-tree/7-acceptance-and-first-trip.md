---
title: "怎样证明读写没有改变内容,头一趟往返跑成什么样?"
volume: 2
chapter: 7
section: 1
order: 71
description: "writer 把树摊回字节,规范 v0.4 第 5 章把活分成必须算对与可以自便两类,同一棵树因此有多份合法编码,验收定在语义等价,操作上拿 dtc 反编译两边再交给 diff。rt.py 读的一头接着立树那章的思路并补上文件头与边界的核验,写的一头 write_dtb 把树模型摊回三块,头一趟拿 mini.dtb 跑往返,cmp 一声不吭,逐字节一致的来历是咱们与 dtc 都选了最省事的排布"
status: draft
---

# 进去一个 DTB,出来一个 DTB,凭什么说内容没变?

咱们在“从字节到自己的树”这一卷里已经走过了一大半的路。“这个 DTB 文件如何布局”那章认全了四个区块,“如何安全遍历所有节点”那章写出了咱们自己的遍历器(walker),“字节怎样成为可查询的树”那章又把 DTB 立成了树模型。现在咱们要把路掉个头:树模型已经在手,咱们要把它写回 DTB。写完之后还有一句更要紧的话要问:进去的是一份 DTB,出来的也是一份 DTB,凭什么说内容没有变?本篇咱们把 writer 要接的活分清楚,把咱们对“没变”的验收标准定下来,再真跑一趟往返的实验,edtc 将来的 DTB writer 的设计,咱们放到本章后面接着说。

## writer 接的活:把树摊回字节

读的方向咱们已经走熟了,写的方向就是同一张地图倒着走。树模型里装的是节点、属性和原始字节值,DTB 里摆的是文件头、内存保留区、结构块和字符串块,writer 要做的就是把前者摊平成后者。咱们把活儿分成四摊:

- 结构块:每个节点摊成 FDT_BEGIN_NODE、节点的名字、一串 FDT_PROP、子节点、FDT_END_NODE,整棵树收尾时还要补一个 FDT_END。
- 字符串块:属性名一个个拼进来,结构块里的 PROP 拿偏移(nameoff)指过来,相同的名字存一份就够。
- 文件头:十个字段按实际的排布回填,totalsize、两块的偏移和大小都要与真身对得上。
- 内存保留区:条目原样写进产物,结尾别忘了那条全零的收尾条目。

咱们翻开规范 v0.4 第 5 章,这些活在那里分成了两类。一类是必须算对的,算错了产物就不合法:

- 魔数固定是 `d00dfeed`,整数一律用大端。
- 结构块里的每个记号(token)都落在 4 字节边界上,节点的名字和属性值的后面要补零到 4 字节。
- 内存保留区整体 8 字节对齐,每条 16 字节,收尾条目是两个 0。
- PROP 的 len 必须等于值的真实字节数,空属性的长度就是 0。
- 文件头的 totalsize 要罩住整个文件,off_dt_struct、off_dt_strings、off_mem_rsvmap 指的位置必须名副其实,size_dt_struct 与 size_dt_strings 也要对得上排布。

另一类是咱们可以自便的,规范给这些地方留了自由度:

- 字符串块里名字的排列顺序随意,同一个名字重复存几份也不犯规,解析方只认偏移。
- 区块之间允许留空隙,规范的原文还给空隙留了 free space 的名分。
- FDT_NOP 记号想插就插,解析方见了会跳过。
- 属性排在子节点前面属于硬要求,但属性彼此的次序、子节点彼此的次序,规范都不管。

自便的地方带来了一个直接的后果:同一棵树的合法 DTB 编码不止一份。到了这一步,“内容没变”就有了两种说法,咱们得挑一种来当验收。

## 两种等价,验收认哪一种

第一种说法是字节级等价:两份文件的每一个字节都相同,咱们请 `cmp` 出场的时候它一声不吭,这是最强的“没变”。第二种说法讲的是语义级等价:两份文件各自解出来的树模型相同,咱们解出来的节点、属性、字节值、内存保留区全都一样,字节排布倒是允许不同。

咱们把验收定在语义等价上,理由就藏在规范留下的自由度里。字符串表换个顺序也好、重复的名字多存几份也好、区块之间留些空隙也好,树的内容没有丝毫变化,产物倒是份份合法。咱们要是拿字节一致当验收,一份完全合法的 writer 会被判成不合格,所以语义等价才是正确的验收线。

字节一致是比语义等价更强的要求,只有当 writer 的每一项自由度都恰好选了与 dtc 相同的答案,咱们才会看到逐字节一致的结果。做到了算额外的福利,咱们的验收线不押在它身上。

咱们还得让验收可操作。咱们的做法是拿 dtc 反编译两边,再把两份反编译的文本丢给 `diff`,两份文本全同了,语义等价就算过了。裁判的人选必须独立于被测工具,咱们自己写的 reader 当然也能比树模型,但那算的只是咱们的自验,当裁判的得是 dtc。

验收的说法与裁判都定了,写工具的活还没动。接下来咱们就把它写出来:一个名叫 `rt.py` 的 python 脚本,读的一头把 DTB 立成树,写的一头把树摊回 DTB,再拿 mini.dtb 跑头一趟真格的往返。

## 头一趟真跑:mini.dtb 进去,原样的字节出来

实验目录咱们建在 /tmp/vol2ch7,输入还是仓库里的 mini.dts,咱们把它编成参照物:

```shell
mkdir -p /tmp/vol2ch7
cd /tmp/vol2ch7
dtc -I dts -O dtb -o mini.dtb /home/charliechen/devtree-journey/edtc/example/00_bootstrap/mini.dts
wc -c mini.dtb
```

```output
293 mini.dtb
```

工具是咱们写的一个 python 脚本,它的名字叫 `rt.py`。读的那半边接着“字节怎样成为可查询的树”那章立树的思路,咱们给它补上了文件头与边界的核验。写的那半边 `write_dtb` 是本篇的新货,咱们靠它把树模型摊回三块。完整的脚本贴在下面,`--no-dedup` 选项的用场下一篇就到:

```python
#!/usr/bin/env python3
"""迷你 round-trip:读 DTB 立起树模型,再把树模型写回 DTB。"""
import struct
import sys

FDT_BEGIN_NODE, FDT_END_NODE, FDT_PROP, FDT_NOP, FDT_END = 1, 2, 3, 4, 9
MAGIC = 0xD00DFEED
HDR = struct.Struct(">10I")   # 文件头的十个字段,全部大端 u32


class BadDtb(Exception):
    """输入算不上一个能读的 DTB。"""


def _check(ok, why):
    if not ok:
        raise BadDtb(why)


def read_dtb(path):
    """DTB 文件读成 {"cpuid", "rsv", "root"} 的树模型。"""
    buf = open(path, "rb").read()
    _check(len(buf) >= HDR.size, f"文件只有 {len(buf)} 字节,装不下 40 字节的文件头")
    (magic, totalsize, off_struct, off_strings, off_rsv, version,
     _last_comp, cpuid, size_strings, size_struct) = HDR.unpack_from(buf)
    _check(magic == MAGIC, f"魔数是 0x{magic:08x},我认的却是 d00dfeed")
    _check(version == 17, f"版本号是 {version},我只读 17")
    _check(totalsize <= len(buf), f"文件头声称共 {totalsize} 字节,文件却只有 {len(buf)} 字节")
    _check(off_struct + size_struct <= totalsize, "结构块的偏移加长度越过了文件尾")
    _check(off_strings + size_strings <= totalsize, "字符串块的偏移加长度越过了文件尾")

    rsv = []
    pos = off_rsv
    while True:
        _check(pos + 16 <= len(buf), "内存保留区凑不出一个完整条目")
        addr, size = struct.unpack_from(">QQ", buf, pos)
        pos += 16
        if (addr, size) == (0, 0):
            break
        rsv.append((addr, size))

    def u32():
        nonlocal pos
        _check(off_struct <= pos <= off_struct + size_struct - 4, "结构块读到了界外")
        value = struct.unpack_from(">I", buf, pos)[0]
        pos += 4
        return value

    def cstr(limit):
        nonlocal pos
        end = buf.find(b"\0", pos)
        _check(pos <= end < limit, "节点名没有结束符")
        text = buf[pos:end].decode()
        pos = (end + 1 + 3) & ~3          # 跳过补齐的零字节
        return text

    def prop_name(nameoff):
        start = off_strings + nameoff
        _check(off_strings <= start < off_strings + size_strings, "属性名的偏移越出了字符串块")
        end = buf.find(b"\0", start)
        _check(start <= end < off_strings + size_strings, "属性名没有结束符")
        return buf[start:end].decode()

    def node():
        nonlocal pos
        label = cstr(off_struct + size_struct)
        props, kids = [], []
        while True:
            token = u32()
            if token == FDT_NOP:
                continue
            if token == FDT_PROP:
                length, nameoff = u32(), u32()
                _check(pos + length <= off_struct + size_struct, "属性值越过了结构块")
                value = bytes(buf[pos:pos + length])
                pos = (pos + length + 3) & ~3
                props.append((prop_name(nameoff), value))
            elif token == FDT_BEGIN_NODE:
                kids.append(node())
            elif token == FDT_END_NODE:
                return {"name": label, "props": props, "children": kids}
            else:
                raise BadDtb(f"认不出的记号 0x{token:08x}")

    pos = off_struct
    _check(u32() == FDT_BEGIN_NODE, "结构块不是从 BEGIN_NODE 开的头")
    root = node()
    _check(u32() == FDT_END, "根节点收尾之后没有等到 END")
    return {"cpuid": cpuid, "rsv": rsv, "root": root}


def write_dtb(tree, path, dedup=True):
    """树模型写回 DTB 文件,dedup=False 时字符串表不去重。"""
    out = bytearray(HDR.size)                       # 文件头占位,最后回填
    for addr, size in tree["rsv"]:
        out += struct.pack(">QQ", addr, size)
    out += struct.pack(">QQ", 0, 0)                 # 内存保留区的结尾条目

    strings = bytearray()
    seen = {}

    def stroff(text):
        if dedup and text in seen:
            return seen[text]
        offset = len(strings)
        strings.extend(text.encode() + b"\0")
        seen[text] = offset
        return offset

    def pad4(block):
        while len(block) % 4:
            block += b"\0"

    def emit(node):
        block.extend(struct.pack(">I", FDT_BEGIN_NODE))
        block.extend(node["name"].encode() + b"\0")
        pad4(block)
        for key, value in node["props"]:
            block.extend(struct.pack(">III", FDT_PROP, len(value), stroff(key)))
            block.extend(value)
            pad4(block)
        for kid in node["children"]:
            emit(kid)
        block.extend(struct.pack(">I", FDT_END_NODE))

    off_struct = len(out)
    block = bytearray()
    emit(tree["root"])
    block.extend(struct.pack(">I", FDT_END))
    out += block

    off_strings = len(out)
    out += strings

    out[0:HDR.size] = HDR.pack(MAGIC, len(out), off_struct, off_strings,
                               HDR.size, 17, 16, tree["cpuid"],
                               len(strings), len(block))
    open(path, "wb").write(out)
    return len(out)


def main():
    if len(sys.argv) < 4 or sys.argv[1] != "round-trip":
        sys.exit("用法: rt.py round-trip <进.dtb> <出.dtb> [--no-dedup]")
    src, dst = sys.argv[2], sys.argv[3]
    dedup = "--no-dedup" not in sys.argv
    try:
        tree = read_dtb(src)
    except BadDtb as error:
        sys.exit(f"拒收 {src}: {error}")
    size = write_dtb(tree, dst, dedup=dedup)
    print(f"{dst}: {size} 字节,内存保留区 {len(tree['rsv'])} 条,字符串表{'去重' if dedup else '没去重'}")


if __name__ == "__main__":
    main()
```

头一趟咱们这么跑:

```shell
python3 rt.py round-trip mini.dtb mini-out.dtb
cmp mini.dtb mini-out.dtb
echo "cmp 的退出码 $?"
```

```output
mini-out.dtb: 293 字节,内存保留区 0 条,字符串表去重
cmp 的退出码 0
```

头一趟的结果居然是逐字节一致。咱们没有刻意模仿 dtc,咱们的排布选的都是最省事的几种:字符串表按头一回遇见的顺序追加,相同的名字只存了一份,名字与值的后面补零到 4 字节,区块之间的空隙一点不留。从逐字节一致的结果倒推,dtc 在这几处做的也是同样的选择,两边就凑出了同一份字节。

不过这个结果让语义等价显得多余了,咱们需要一个合法却不一致的活例子,把验收线的道理撑起来。造活例子的活,咱们放到下一篇:输入专挑对齐与去重的软肋,再把字符串表的去重故意关掉。

## 本节自检

这一篇读完了,你拿六个小问题验一验自己,想好了再展开参考答案。

1. writer 的活里,哪些数必须算对?哪些排布可以自便?各举两例。
2. 语义等价与字节等价,咱们的验收认哪一种?为什么不认另一种?
3. 验收怎么落到能跑的比对上?裁判为什么必须是独立的 dtc,而不能是咱们自己的 reader?
4. rt.py 的两半各叫什么名字?读的那半边除了接着“字节怎样成为可查询的树”那章立树的思路,本篇还给它补上了什么?
5. 头一趟往返跑完,cmp 的退出码是多少?咱们并没有刻意模仿 dtc,产物为什么还能逐字节一致?
6. 逐字节一致的结果反而给咱们带来了什么新麻烦?

<details>
<summary>参考答案(想好再展开)</summary>

1. 必须算对的:PROP 的 len 与值真实字节数一致,文件头的偏移与大小和排布对得上,记号 4 字节对齐,保留区 8 字节对齐加全零收尾条目。可以自便的:字符串表里名字的顺序与重复,区块之间的空隙,FDT_NOP 的使用,同层属性或子节点彼此的次序。
2. 认语义等价。因为同一棵树有多种合法字节编码,拿字节一致当验收会把合法 writer 判成不合格,字节一致只算与 dtc 排布巧合时的福利。
3. 拿 dtc 反编译两边,再把两份反编译的文本丢给 `diff`,两份文本全同了,语义等价就算过了。裁判的人选必须独立于被测工具,咱们自己写的 reader 也能比树模型,但那算的只是咱们的自验,当裁判的得是 dtc。
4. 读的一半是 `read_dtb`,写的一半是 `write_dtb`。读的那半边补上了文件头与边界的核验。
5. 退出码 0。因为咱们的排布选的都是最省事的几种:字符串表按头一回遇见的顺序追加,相同的名字只存了一份,名字与值的后面补零到 4 字节,区块之间的空隙一点不留。dtc 在这几处做的也是同样的选择,两边就凑出了同一份字节。
6. 它让语义等价显得多余了,咱们需要一个合法却不一致的活例子,把验收线的道理撑起来。

</details>

## 延伸阅读

咱们用到的机制与出处,正式的文档都在这里:

- [Devicetree Specification v0.4](https://www.devicetree.org/specifications/):第 5 章是扁平格式(DTB)的权威定义,文件头、对齐与记号协议都在这里,本仓 `.claude/materials/` 缓存了全文副本。
