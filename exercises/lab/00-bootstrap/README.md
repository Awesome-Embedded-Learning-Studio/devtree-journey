# Lab 00-bootstrap:最小设备树的第一次编译

目的:把最小 DTS 编译成 DTB 并核对产物字节,对应 `standalone-repo.md` 第二节迁入验收与第五节 M0。

- 源文件(仓库内唯一来源):`../../../edtc/example/00_bootstrap/mini.dts`
- 生成命令(在本目录执行):`dtc -I dts -O dtb -o mini.dtb ../../../edtc/example/00_bootstrap/mini.dts`
- 实际使用版本:dtc v1.8.1,2026-10-11 本机复现
- 产物核对:与 `edtc/documents/notes/00.md` 记录的 `xxd` 输出一致,总大小 0x125,魔数 `d00d feed`

验收:重新执行生成命令,产物按上文核对一条对上(与 `edtc/documents/notes/00.md` 记录的 `xxd` 输出一致,总大小 0x125,魔数 `d00d feed`)。
