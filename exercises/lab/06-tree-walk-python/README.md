# Lab 06-tree-walk-python:结构块立成树,phandle 收成索引

目的:用本目录的 walker.py 从结构块把 DTB 解成树并打印,再用带标签引用的 ref.dtb 收一张 phandle 索引,对应“一串字节,怎么变成我手里能查的树?”与“引用怎么落地,解读的凭据立在哪儿?”两篇。

- 工具(本目录):`walker.py`,一百行,栈式遍历结构块挂树,节点存名字、路径、属性表、孩子列表,属性按产物次序保留,值一律是原始字节
- 解读分两层:属性名在已知类型表里才按形式印(cell、cells、string),表外只报十六进制字节,不猜形状,防线从简只验魔数与栈配平
- 带引用的输入(本目录):`ref.dts`,时钟节点挂 `clk24` 标签,uart 的 `clocks` 引用它,另有一条四字节 `oem-data`
- 生成命令(在本目录执行):`dtc -I dts -O dtb -o mini.dtb ../../../edtc/example/00_bootstrap/mini.dts` 与 `dtc -I dts -O dtb -o ref.dtb ref.dts`
- 实际使用版本:dtc v1.8.1,Python 3.14.8,2026-10-18 本机复现

## 全树打印

```console
$ python3 walker.py mini.dtb
/
    compatible         [string] "edts,a_demo" (12 字节)
    #address-cells     [cell] 0x1 (4 字节)
    #size-cells        [cell] 0x1 (4 字节)
    /serial@1000
        compatible         [string] "acme,uart" (10 字节)
        reg                [cells] <0x1000 0x100> (8 字节)
        clock-frequency    [cell] 0x1c200 (4 字节)
        status             [string] "okay" (5 字节)

树里没有 phandle 属性,索引是空的
```

七条属性全部对上,clock-frequency 印成 0x1c200,mini.dtb 的树里没有引用,索引如实报空。

## phandle 索引

```console
$ python3 walker.py ref.dtb
/
    #address-cells     [cell] 0x1 (4 字节)
    #size-cells        [cell] 0x1 (4 字节)
    /clock-controller
        compatible         [string] "demo,fixed-clock" (17 字节)
        clock-frequency    [cell] 0x16e3600 (4 字节)
        #clock-cells       [bytes] 00 00 00 00 (4 字节)
        phandle            [cell] 0x1 (4 字节)
    /uart@1000
        compatible         [string] "acme,uart" (10 字节)
        reg                [cells] <0x1000 0x100> (8 字节)
        clocks             [bytes] 00 00 00 01 (4 字节)
        oem-data           [bytes] 01 02 3a 4f (4 字节)

phandle 索引(数值 -> 节点路径):
  0x1 -> /clock-controller
```

两处读数值得对着看:clock-controller 身上多出的 `phandle` 是 0x1,uart 的 `clocks` 四个字节也是 `00 00 00 01`,数值一对,引用的连线就接上了。索引是树挂满之后扫第二遍收的,因为 phandle 可能长在任何节点身上,挂树中途见不全。`#clock-cells` 与 `oem-data` 同为四字节却只印 [bytes],原因就一条:名字不在已知类型表里,表是政策而不是魔法。

验收:重新执行两条生成命令,两次 `python3 walker.py` 的输出与上文记录相同。
