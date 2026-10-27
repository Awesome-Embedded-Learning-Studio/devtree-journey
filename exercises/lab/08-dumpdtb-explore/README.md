# Lab 08-dumpdtb-explore:导出 QEMU 生成的设备树

目的:用 dumpdtb 导出 QEMU virt 机自己生成的 DTB,记录文件大小与 file 读数,反编译后核对 memory、chosen、pl011 三类关键节点,数出全树规模,对应第三卷“Linux 何时读取 DTB?”、“第二遍读怎样把字节立成树,QEMU 生成的树里都躺着什么?”与“源码读完了,QEMU 里怎么对证,运行时的树又是什么样子?”的实验部分。

- 生成命令(在本目录执行):`qemu-system-aarch64 -machine virt,dumpdtb=virt.dtb -m 1G -cpu cortex-a57 -display none`。dumpdtb 是导出即退的机型属性,不用起完整的 guest
- 实际使用版本:qemu-system-aarch64 11.1.2 与 dtc v1.8.1,2026-10-18 本机复现
- 文件大小:`ls -l virt.dtb` 报 1048576 字节,正好 1MiB,而结构块只有 7160 字节、字符串块 569 字节,其余是垫出来的零。file 读数:

```output
virt.dtb: Device Tree Blob version 17, size=1048576, boot CPU=0, string block size=569, DT structure block size=7160
```

- 反编译命令(在本目录执行):`dtc -I dtb -O dts virt.dtb > virt.roundtrip.dts`,三类关键节点与节点计数都摘自这份反编译
- 三类关键节点,摘自 `virt.roundtrip.dts`。memory 的 reg 按根节点 2+2 的 cells 折出基址 0x40000000 与 1GiB,对应命令行的 `-m 1G`。chosen 里没有 bootargs,这条命令没传 `-append`,rng-seed 与 kaslr-seed 是机型每次开机随机生成的。pl011 的 clocks 两处引用都指向 phandle 0x8000,即树里的 apb-pclk 时钟节点,chosen 的 stdout-path 指回它:

```dts
	memory@40000000 {
		reg = <0x00 0x40000000 0x00 0x40000000>;
		device_type = "memory";
	};

	chosen {
		stdout-path = "/pl011@9000000";
		rng-seed = <0xd473751 0xd6a0cea3 0xbadea6f8 0x81b6f31c 0x9e021a46 0x23f8d4e4 0xf08fc040 0xcd755dc5>;
		kaslr-seed = <0x5d65295d 0xaaddb42e>;
	};

	pl011@9000000 {
		clock-names = "uartclk", "apb_pclk";
		clocks = <0x8000 0x8000>;
		interrupts = <0x00 0x01 0x04>;
		reg = <0x00 0x9000000 0x00 0x1000>;
		compatible = "arm,pl011", "arm,primecell";
	};
```

- 节点计数,命令与真实输出:

```shell
python3 -c "
import re
text = open('virt.roundtrip.dts').read()
nodes = re.findall(r'^\t*[a-zA-Z0-9,._+-]+(@[0-9A-Fa-f]+)? \{$', text, re.M)
print('节点总数:', len(nodes))
print('带单元地址的:', sum(1 for n in nodes if n))
"
```

```output
节点总数: 56
带单元地址的: 43
```

- 随机字段:导出两次各反编译一份再 diff,全树只有 chosen 里 rng-seed 与 kaslr-seed 两行不同,真实输出如下。比对时把这两行跳过,其余逐行一致,file 读数两次也相同。字节级的差异是种子的 40 个字节,再加 stdout-path 字符串结尾处一个没被 QEMU 清零的对齐填充字节,三次导出它分别取 0x1c、0x8b、0xa1,填充不进反编译的结果:

```output
397,398c397,398
< 		rng-seed = <0xd473751 0xd6a0cea3 0xbadea6f8 0x81b6f31c 0x9e021a46 0x23f8d4e4 0xf08fc040 0xcd755dc5>;
< 		kaslr-seed = <0x5d65295d 0xaaddb42e>;
---
> 		rng-seed = <0xe645618c 0xc2b6f0f1 0x770a960a 0xe36335e1 0x3b69a90c 0xc9386e7c 0x7f47f51e 0x6fa0734a>;
> 		kaslr-seed = <0x4f0f8140 0x95a1e6c3>;
```

验收:重新执行生成命令与反编译命令,file 读数、节点计数与上文记录相同;两次导出各反编译一份(如 `/tmp/dump-a.dts`、`/tmp/dump-b.dts`),执行 `diff <(grep -Ev 'rng-seed|kaslr-seed' /tmp/dump-a.dts) <(grep -Ev 'rng-seed|kaslr-seed' /tmp/dump-b.dts)`,输出为空且退出码 0。rng-seed 与 kaslr-seed 每次导出的值都不同,属预期,比对时按上面说明跳过。
