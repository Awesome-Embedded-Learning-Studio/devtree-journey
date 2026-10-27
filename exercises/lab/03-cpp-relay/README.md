# Lab 03-cpp-relay:cpp 展开宏与 #include,dtc 接力编成 DTB

目的:亲手跑通构建系统里的那对工具。三个文件接力:宏头 `include/acme-regs.h`、芯片级 `soc.dtsi`、板级 `board.dts`(用 #include 引入前两个),cpp 把它们归拢成一份纯文本,dtc 再编成 DTB,反编译核对宏展开与合并。另做一次不带预处理的对照,最后带 `-@` 编一回,看产物里的 `__symbols__`,对应讲义"构建系统实际上做了什么?"到"真实构建里谁在替咱们敲命令?"几篇。

- 输入文件(本目录):
  - `include/acme-regs.h`:四个宏,`ACME_UART_BASE`、`ACME_UART_SZ`、`ACME_LED_BASE` 是数字,`STATUS_OKAY` 是字符串
  - `soc.dtsi`:芯片级描述,串口的 `reg = <ACME_UART_BASE ACME_UART_SZ>` 全交给宏写,节点挂 `uart0` 标签
  - `board.dts`:`#include <acme-regs.h>` 用尖括号,只查 `-I` 给的路径,`#include "soc.dtsi"` 用引号,连当前目录一起查。板级补 `model` 和挂 `led0` 标签的 led,`reg` 与 `status` 也用宏写
- 生成命令(在本目录执行):
  - `cpp -nostdinc -I include -undef -D__DTS__ -x assembler-with-cpp board.dts -o board.pp.dts`
  - `dtc -I dts -O dtb -o board.dtb board.pp.dts`
  - `dtc -I dtb -O dts -o board.roundtrip.dts board.dtb`
  - `dtc -@ -I dts -O dtb -o board-sym.dtb board.pp.dts`
  - `dtc -I dtb -O dts -o board-sym.roundtrip.dts board-sym.dtb`
- 实际使用版本:dtc v1.8.1,cpp GCC 16.2.1,2026-10-18 本机复现
- 产物核对:
  - `board.pp.dts`(全文见下):四个宏全被消费,`reg` 与 `status` 的位置上是字面量 `0x1000 0x100`、`0x8 0x4`、`"okay"`,acme-regs.h 原地只留一行行标记,soc.dtsi 的全文嵌了进来,`#address-cells` 开头也是井号却被原样放行
  - `board.roundtrip.dts`(全文见下):两份根节点合成一棵树,宏写的值回来是 `0x1000 0x100` 与 `0x08 0x04`,标签 uart0、led0 不在
  - `board-sym.roundtrip.dts`(全文见下):`board.dtb` 359 字节,`board-sym.dtb` 478 字节,多出来的是 `__symbols__` 对照表和两个自动补上的 `phandle`,标签也跟着描了回来

对照:同一个 `board.dts` 不带预处理直接喂 dtc,命令 `dtc -I dts -O dtb -o fail.dtb board.dts`,真实输出如下,退出码 1,没有生成任何文件:

```output
Error: board.dts:3.1-9 syntax error
FATAL ERROR: Unable to parse input tree
```

验收:重新执行五条生成命令,`board.pp.dts` 与两份 `.roundtrip.dts` 同文末记录的全文逐字一致,两份 dtb 的大小同产物核对(359 与 478 字节)。

`board.pp.dts` 全文(真实输出,行首的 `# 数字 "文件名"` 是 cpp 的行标记):

```dts
# 0 "board.dts"
# 0 "<built-in>"
# 0 "<command-line>"
# 1 "board.dts"
/dts-v1/;

# 1 "include/acme-regs.h" 1
# 4 "board.dts" 2
# 1 "soc.dtsi" 1
/ {
 compatible = "acme,soc1000";
 #address-cells = <1>;
 #size-cells = <1>;

 uart0: serial@1000 {
  compatible = "acme,uart";
  reg = <0x1000 0x100>;
 };
};
# 5 "board.dts" 2

/ {
 model = "ACME Lab Board";

 led0: led@8 {
  compatible = "acme,led";
  reg = <0x8 0x4>;
  status = "okay";
 };
};
```

`board.roundtrip.dts` 全文(真实输出):

```dts
/dts-v1/;

/ {
	compatible = "acme,soc1000";
	#address-cells = <0x01>;
	#size-cells = <0x01>;
	model = "ACME Lab Board";

	serial@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
	};

	led@8 {
		compatible = "acme,led";
		reg = <0x08 0x04>;
		status = "okay";
	};
};
```

`board-sym.roundtrip.dts` 全文(真实输出):

```dts
/dts-v1/;

/ {
	compatible = "acme,soc1000";
	#address-cells = <0x01>;
	#size-cells = <0x01>;
	model = "ACME Lab Board";

	uart0: serial@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
		phandle = <0x01>;
	};

	led0: led@8 {
		compatible = "acme,led";
		reg = <0x08 0x04>;
		status = "okay";
		phandle = <0x02>;
	};

	__symbols__ {
		uart0 = "/serial@1000";
		led0 = "/led@8";
	};
};
```
