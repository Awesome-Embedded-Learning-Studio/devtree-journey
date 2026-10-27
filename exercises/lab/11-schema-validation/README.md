# Lab 11-schema-validation:最小 binding 上岗,好树病树各报什么

目的:给 ACME 串口写一份最小 binding,请 dt-validate 验一棵好树和两棵病树,末了让拼错的 compatible 现形,对应讲义“咱们的第一份 binding 怎么写,好树病树各报什么?”与“拼错的名字怎么又溜过去,内核树里怎么批量验?”。

- 工具安装:本机的 dt-validate 来自 `pip3 install --user --break-system-packages dtschema`,装进 `~/.local`,`dt-validate --version` 报 `2026.9`,读者机器上没装时照这条装,与 dtc v1.8.1 一起于 2026-10-18 本机复现
- binding(本目录):`bindings/serial/acme,uart.yaml` 学内核的目录规范住进 `serial/` 子目录,`compatible` 定值 `acme,uart`,`required` 列 compatible、reg、clock-frequency,`additionalProperties: false` 把没列过的属性全拦下
- binding 自身体检(在本目录执行):`dt-doc-validate bindings/serial/acme,uart.yaml`,输出为空,退出码 0
- 编译(在本目录执行,四棵树同一个套路,dtc 一声不吭,退出码全是 0):`dtc -I dts -O dtb -o good.dtb good.dts`,病树换文件名即可

三次校验(命令一律 `dt-validate -s bindings/serial/acme,uart.yaml <dtb>`,在本目录执行):

- 好树 `good.dtb`:输出为空,退出码 0,干干净净过
- 病树一 `bad-missing.dtb`(`bad-missing.dts` 少写了 clock-frequency):

```output
bad-missing.dtb: serial@1000 (acme,uart): 'clock-frequency' is a required property
	from schema $id: http://devicetree.org/schemas/serial/acme,uart.yaml
```

- 病树二 `bad-prop.dtb`(`bad-prop.dts` 在串口节点多写 `clock_freq = <57600>;`):

```output
bad-prop.dtb: serial@1000 (acme,uart): 'clock_freq' does not match any of the regexes: '^pinctrl-[0-9]+$'
	from schema $id: http://devicetree.org/schemas/serial/acme,uart.yaml
bad-prop.dtb: serial@1000 (acme,uart): clock_freq: b'\x00\x00\xe1\x00' is not of type 'object', 'integer', 'array', 'boolean', 'null'
	from schema $id: http://devicetree.org/schemas/dt-core.yaml
```

- 退出码的实话:病树一的报错齐全,紧跟的 `echo $?` 报 0,dt-validate 不把错误计数捎进退出码,写脚本判定时盯输出,退出码不作数

手误的 compatible:

- 病树三 `bad-typo.dts` 只把值拼成 `acme,serail`,`dt-validate -s bindings/serial/acme,uart.yaml bad-typo.dtb` 输出为空,名字对不上就没有 schema 认领,校验直接跳过
- 加 `-m` 才现形:`dt-validate -m -s bindings/serial/acme,uart.yaml bad-typo.dtb`

```output
bad-typo.dtb: /: failed to match any schema with compatible: ['acme,soc1000']
bad-typo.dtb: /serial@1000: failed to match any schema with compatible: ['acme,serail']
```

- 第二行是等的正主,头一行报的是根上的 `acme,soc1000`,本目录只有一份串口 schema,根的名字自然没人认领,手动跑校验时 `-m` 从来不省

验收:重新执行四条编译命令与上文的校验命令,四次校验的输出与退出码与上文记录相同。
