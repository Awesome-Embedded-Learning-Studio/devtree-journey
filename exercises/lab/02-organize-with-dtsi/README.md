# Lab 02-organize-with-dtsi:用 dtsi 分文件,合并、覆盖、删除一次看全

目的:把芯片级的 soc.dtsi 用 /include/ 拼进板级 board.dts,编成 DTB 再反编译,核对合并、覆盖、删除三件事都生效,对应讲义"一个设备怎么写才算写得清楚?"到"一堆文件怎么分工才算管得住?"几篇。

- 输入文件(本目录):
  - `soc.dtsi`:公共描述。根节点 `compatible = "acme,soc1000"`,带 `clk24` 标签的时钟节点,带 `uart0` 标签的串口(出厂 `status = "disabled"`),外加本板没焊的 `dsp@3000`
  - `board.dts`:`/include/ "soc.dtsi"` 引入公共部分,根节点补 `model` 和自己的 `leds`,用 `&uart0` 给串口补 `clock-frequency` 并把 `status` 改回 `"okay"`,用 `/delete-node/ dsp@3000;` 删掉不合身的节点
- 生成命令(在本目录执行):
  - `dtc -I dts -O dtb -o board.dtb board.dts`
  - `dtc -I dtb -O dts -o board.roundtrip.dts board.dtb`
- 实际使用版本:dtc v1.8.1,2026-10-18 本机复现,两条命令均无告警
- 产物核对(`board.roundtrip.dts` 全文见文末):
  - 合并:`serial@1000` 里 dtsi 的老属性 `compatible`、`reg`、`clocks` 都还在,dts 补的 `clock-frequency = <0x1c200>` 也进来了,根上多了板级的 `model` 和 `leds`,产物里只剩一棵完整的树
  - 覆盖:`status = "okay"`,dtsi 里写的 `"disabled"` 被后写的同名属性赢掉了
  - 删除:`dsp@3000` 在产物里整个不存在,字节都不占
  - 标签:源码里的 `&clk24` 进产物变成 `clocks = <0x01>`,`clock-controller` 被 dtc 自动补上 `phandle = <0x01>`,标签名本身没进产物

验收:重新执行两条生成命令,得到的 `board.roundtrip.dts` 与文末记录的全文逐字一致。

`board.roundtrip.dts` 全文(真实输出):

```dts
/dts-v1/;

/ {
	compatible = "acme,soc1000";
	#address-cells = <0x01>;
	#size-cells = <0x01>;
	model = "ACME Lab Board";

	clock-controller {
		compatible = "acme,fixed-clock";
		clock-frequency = <0x16e3600>;
		#clock-cells = <0x00>;
		phandle = <0x01>;
	};

	serial@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
		clocks = <0x01>;
		status = "okay";
		clock-frequency = <0x1c200>;
	};

	leds {
		compatible = "acme,leds";
	};
};
```
