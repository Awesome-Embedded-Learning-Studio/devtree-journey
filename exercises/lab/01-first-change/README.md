# Lab 01-first-change:改一行 DTS,核对产物里的变化

目的:把改过一个属性值的 DTS 编译成 DTB,与 lab 00 的基线产物逐字节对比,看清一行源码改动怎样落进产物,对应 `../../../documents/vol1-first-use/1-first-change.md`。

- 源文件(本目录):`mini-9600.dts`,由 `../../../edtc/example/00_bootstrap/mini.dts` 改一行得来
- 与 mini.dts 的差异(仅第 11 行):`clock-frequency = <115200>;` 改为 `clock-frequency = <9600>;`
- 生成命令(在本目录执行):`dtc -I dts -O dtb -o mini-9600.dtb mini-9600.dts`
- 实际使用版本:dtc v1.8.1,2026-10-18 本机复现
- 产物核对:大小仍为 293 字节,与按 lab 00 命令重编出的基线 `mini.dtb` 相比仅偏移 0xc1、0xc2、0xc3 三个字节不同(十六进制行 `0001 c200` 变为 `0000 2580`),反编译可见 `clock-frequency = <0x2580>;`

验收:重新执行生成命令,产物按上文核对一条逐项对上(大小、三处偏移差异、反编译读数)。
