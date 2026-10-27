#!/usr/bin/env python3
"""walker.py:把 DTB 从结构块解成树打印,树挂满后再扫一遍收 phandle 索引。"""
import struct, sys

BEGIN, END_NODE, PROP, NOP, END = 1, 2, 3, 4, 9
# 已知类型表:名字在表里才解读,表外只报原始字节,不猜。
U32 = {"clock-frequency", "#address-cells", "#size-cells", "phandle"}
CELLS = {"reg"}
STR = {"compatible", "status"}

class Node:
    def __init__(self, name, path):
        self.name, self.path = name, path
        self.props = {}        # 属性名 -> 原始字节,保持产物里的次序
        self.children = []

def parse(blob):
    h = struct.unpack_from(">10I", blob, 0)
    magic, total, off_struct, off_strings = h[0], h[1], h[2], h[3]
    size_strings, size_struct = h[8], h[9]
    if magic != 0xD00DFEED:
        raise SystemExit("魔数 0x%08x 不是 d00dfeed,拒收" % magic)
    strings = blob[off_strings:off_strings + size_strings]
    root, stack, pos, end = None, [], off_struct, off_struct + size_struct
    while pos < end:
        tok = struct.unpack_from(">I", blob, pos)[0]
        pos += 4
        if tok == BEGIN:                      # 开门:名字 \0 结尾,补零到 4
            stop = blob.index(b"\0", pos)
            name = blob[pos:stop].decode()
            pos = (stop + 1 + 3) & ~3
            parent = stack[-1] if stack else None
            node = Node(name, parent.path.rstrip("/") + "/" + name if parent else "/")
            if parent:
                parent.children.append(node)
            else:
                root = node
            stack.append(node)
        elif tok == PROP:                     # 属性:len、nameoff、值,补零到 4
            length, nameoff = struct.unpack_from(">II", blob, pos)
            pos += 8
            value = blob[pos:pos + length]
            pos = (pos + length + 3) & ~3
            stop = strings.index(b"\0", nameoff)
            stack[-1].props[strings[nameoff:stop].decode()] = value
        elif tok == END_NODE:                # 关门:弹栈
            stack.pop()
        elif tok == NOP:
            pass
        elif tok == END:
            break
        else:
            raise SystemExit("认不出的记号 0x%08x,拒收" % tok)
    if stack:
        raise SystemExit("结构块走完栈里还有 %d 个门没关,拒收" % len(stack))
    return root

def render(name, value):
    # 解读层:凭据只有已知类型表里的名字,长度对不上也退回字节。
    if name in U32 and len(value) == 4:
        return "[cell] 0x%x" % struct.unpack(">I", value)[0]
    if name in CELLS and value and len(value) % 4 == 0:
        cells = struct.unpack(">%dI" % (len(value) // 4), value)
        return "[cells] <" + " ".join("0x%x" % c for c in cells) + ">"
    if name in STR and value.endswith(b"\0") and value != b"\0":
        text = value[:-1].decode("ascii", "replace")
        if all(32 <= ord(c) < 127 for c in text):
            return '[string] "%s"' % text.replace("\0", '" "')
    return "[bytes] " + value.hex(" ")

def dump(node, depth=0):
    pad = "    " * depth
    print(pad + node.path)
    for name, value in node.props.items():
        print("%s    %-18s %s (%d 字节)" % (pad, name, render(name, value), len(value)))
    for child in node.children:
        dump(child, depth + 1)

def phandle_index(root):
    # 树挂满之后扫第二遍:phandle 数值 -> 节点路径。
    index, stack = {}, [root]
    while stack:
        node = stack.pop()
        value = node.props.get("phandle")
        if value and len(value) == 4:
            index[struct.unpack(">I", value)[0]] = node.path
        stack.extend(node.children)
    return index

if __name__ == "__main__":
    root = parse(open(sys.argv[1], "rb").read())
    dump(root)
    index = phandle_index(root)
    print()
    if index:
        print("phandle 索引(数值 -> 节点路径):")
        for value in sorted(index):
            print("  0x%x -> %s" % (value, index[value]))
    else:
        print("树里没有 phandle 属性,索引是空的")
