#!/usr/bin/env python3
"""writer.py:DTB 进 DTB 出的迷你往返,读的一头立树,写的一头摊回字节。"""
import struct, sys

BEGIN, END_NODE, PROP, NOP, END = 1, 2, 3, 4, 9
MAGIC = 0xD00DFEED
HDR = struct.Struct(">10I")     # 文件头十个字段,全部大端 u32

def read_dtb(path):
    """读成 {"cpuid", "rsv", "root"},属性保持产物次序,值是原始字节。"""
    buf = open(path, "rb").read()
    h = HDR.unpack_from(buf)
    magic, total, off_struct, off_strings, off_rsv, ver = h[:6]
    cpuid, size_strings, size_struct = h[7], h[8], h[9]
    if magic != MAGIC:
        raise SystemExit("魔数 0x%08x 不是 d00dfeed,拒收" % magic)
    if ver != 17:
        raise SystemExit("版本号 %d 不是 17,拒收" % ver)
    if total > len(buf) or off_struct + size_struct > total \
            or off_strings + size_strings > total:
        raise SystemExit("文件头声称的范围越过了文件尾,拒收")
    rsv, pos = [], off_rsv
    while True:
        if pos + 16 > len(buf):
            raise SystemExit("内存保留区凑不出一个完整条目,拒收")
        addr, size = struct.unpack_from(">QQ", buf, pos)
        pos += 16
        if (addr, size) == (0, 0):
            break
        rsv.append((addr, size))
    strings = buf[off_strings:off_strings + size_strings]
    limit = off_struct + size_struct
    pos = [off_struct]

    def u32():
        if not off_struct <= pos[0] <= limit - 4:
            raise SystemExit("结构块读到了界外,拒收")
        pos[0] += 4
        return struct.unpack_from(">I", buf, pos[0] - 4)[0]

    def cstr():
        end = buf.index(b"\0", pos[0], limit)
        name = buf[pos[0]:end].decode()
        pos[0] = (end + 1 + 3) & ~3
        return name

    def prop_name(nameoff):
        start = off_strings + nameoff
        if not off_strings <= start < off_strings + size_strings:
            raise SystemExit("属性名的偏移越出了字符串块,拒收")
        end = strings.index(b"\0", nameoff)
        return strings[nameoff:end].decode()

    def node():
        name = cstr()
        props, children = [], []
        while True:
            tok = u32()
            if tok == PROP:
                length, nameoff = u32(), u32()
                if pos[0] + length > limit:
                    raise SystemExit("属性值越过了结构块,拒收")
                props.append((prop_name(nameoff), bytes(buf[pos[0]:pos[0] + length])))
                pos[0] = (pos[0] + length + 3) & ~3
            elif tok == BEGIN:
                children.append(node())
            elif tok == END_NODE:
                return {"name": name, "props": props, "children": children}
            elif tok == NOP:
                continue
            else:
                raise SystemExit("认不出的记号 0x%08x,拒收" % tok)

    if u32() != BEGIN:
        raise SystemExit("结构块不是从 BEGIN_NODE 开的头,拒收")
    root = node()
    if u32() != END:
        raise SystemExit("根节点收尾之后没有等到 END,拒收")
    return {"cpuid": cpuid, "rsv": rsv, "root": root}

def write_dtb(tree, path, dedup=True):
    """树摊回三块:头、保留区、结构块、字符串块首尾相接,不留空隙。"""
    out = bytearray(HDR.size)                    # 文件头占位,最后回填
    for addr, size in tree["rsv"]:
        out += struct.pack(">QQ", addr, size)
    out += struct.pack(">QQ", 0, 0)              # 保留区全零收尾
    strings, seen = bytearray(), {}

    def stroff(text):
        if dedup and text in seen:
            return seen[text]
        seen[text] = len(strings)
        strings.extend(text.encode() + b"\0")
        return seen[text]

    def emit(node):
        block.extend(struct.pack(">I", BEGIN))
        block.extend(node["name"].encode() + b"\0")
        while len(block) % 4:
            block.append(0)
        for key, value in node["props"]:
            block.extend(struct.pack(">III", PROP, len(value), stroff(key)))
            block.extend(value)
            while len(block) % 4:
                block.append(0)
        for kid in node["children"]:
            emit(kid)
        block.extend(struct.pack(">I", END_NODE))

    off_struct = len(out)
    block = bytearray()
    emit(tree["root"])
    block.extend(struct.pack(">I", END))
    out += block
    off_strings = len(out)
    out += strings
    out[0:HDR.size] = HDR.pack(MAGIC, len(out), off_struct, off_strings, HDR.size,
                               17, 16, tree["cpuid"], len(strings), len(block))
    open(path, "wb").write(out)
    return len(out)

if __name__ == "__main__":
    if len(sys.argv) < 4 or sys.argv[1] != "round-trip":
        raise SystemExit("用法: writer.py round-trip <进.dtb> <出.dtb> [--no-dedup]")
    src, dst = sys.argv[2], sys.argv[3]
    dedup = "--no-dedup" not in sys.argv
    tree = read_dtb(src)
    size = write_dtb(tree, dst, dedup=dedup)
    print("%s: %d 字节,保留区 %d 条,字符串表%s" % (dst, size, len(tree["rsv"]),
                                              "去重" if dedup else "没去重"))
