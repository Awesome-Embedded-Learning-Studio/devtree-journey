# Lab 10-symbols-overlay-chain:__symbols__ 与 overlay 的缝合链

目的:基座带 `-@` 编译,反编译看 `__symbols__` 收标签,overlay 引用基座标签编成 dtbo,fdtoverlay 缝合后用反编译 diff 看叠上去的效果,最后收一份引用基座不存在标签的 overlay 的真实报错,对应第四卷“__symbols__ 是什么,又是给谁的?”与第五卷“板子定了型还想改树,引用的答案为什么推迟?”两篇。

- 输入(本目录):`base.dts`(基座,i2c0 与 uart0 两个标签)、`sensor-overlay.dtso`(引用 &i2c0,加 sensor@48 子节点并挂 sensor0 标签)、`poll-overlay.dtso`(引用 &sensor0,加一个属性)、`bad-overlay.dtso`(引用基座不存在的 &ghost)
- 生成命令(在本目录执行):

```shell
dtc -@ -I dts -O dtb -o base.dtb base.dts
dtc -@ -I dts -O dtb -o sensor-overlay.dtbo sensor-overlay.dtso
dtc -@ -I dts -O dtb -o poll-overlay.dtbo poll-overlay.dtso
dtc -@ -I dts -O dtb -o bad-overlay.dtbo bad-overlay.dtso
```

- 实际使用版本:dtc v1.8.1 与 fdtoverlay v1.8.1,2026-10-18 本机复现
- 基座反编译命令(在本目录执行):`dtc -I dtb -O dts base.dtb > base.roundtrip.dts`。带 `-@` 的产物比不带时多两样:每个带标签的节点强制拿到 phandle(i2c0 是 0x01,uart0 是 0x02),根上多出 `__symbols__` 节点,标签做属性名、节点的完整路径做值:

```dts
	__symbols__ {
		i2c0 = "/i2c@800";
		uart0 = "/serial@1000";
	};
```

- sensor-overlay 编译的真实输出:dtc 检查的是 overlay 自己那棵树,sensor@48 编译时见不到父节点 i2c0 的 cells,reg 长度按默认值掐算,报了一串告警,产物照常生成。反编译 dtbo 时同一串告警随 stderr 再走一遍:

```output
sensor-overlay.dtso:7.3-16: Warning (reg_format): /fragment@0/__overlay__/sensor@48:reg: property has invalid length (4 bytes) (#address-cells == 2, #size-cells == 1)
sensor-overlay.dtbo: Warning (pci_device_reg): Failed prerequisite 'reg_format'
sensor-overlay.dtbo: Warning (pci_device_bus_num): Failed prerequisite 'reg_format'
sensor-overlay.dtbo: Warning (simple_bus_reg): Failed prerequisite 'reg_format'
sensor-overlay.dtbo: Warning (i2c_bus_reg): Failed prerequisite 'reg_format'
sensor-overlay.dtbo: Warning (spi_bus_reg): Failed prerequisite 'reg_format'
sensor-overlay.dtso:5.21-9.4: Warning (avoid_default_addr_size): /fragment@0/__overlay__/sensor@48: Relying on default #address-cells value
sensor-overlay.dtso:5.21-9.4: Warning (avoid_default_addr_size): /fragment@0/__overlay__/sensor@48: Relying on default #size-cells value
sensor-overlay.dtbo: Warning (avoid_unnecessary_addr_size): Failed prerequisite 'avoid_default_addr_size'
sensor-overlay.dtbo: Warning (unique_unit_address): Failed prerequisite 'avoid_default_addr_size'
```

- sensor-overlay.dtbo 的反编译(`sensor-overlay.roundtrip.dts`,真实输出)现出中间格式的原形:fragment@0 的 target 记引用、`__overlay__` 装增量,overlay 自己的标签进 `__symbols__`(路径还是 overlay 本地的),欠下的引用记进 `__fixups__`:

```dts
/dts-v1/;
/plugin/;

/ {

	fragment@0 {
		target = <&i2c0>;

		__overlay__ {

			sensor0: sensor@48 {
				compatible = "acme,temp-sensor";
				reg = <0x48>;
				status = "okay";
				phandle = <0x01>;
			};
		};
	};

	__symbols__ {
		sensor0 = "/fragment@0/__overlay__/sensor@48";
	};

	__fixups__ {
		i2c0 = "/fragment@0:target:0";
	};
};
```

- poll-overlay.dtbo 的反编译(`poll-overlay.roundtrip.dts`,真实输出)欠的是 sensor0,基座里没有这个名字,编译一声不吭:

```dts
/dts-v1/;
/plugin/;

/ {

	fragment@0 {
		target = <&sensor0>;

		__overlay__ {
			poll-interval = <0x64>;
		};
	};

	__fixups__ {
		sensor0 = "/fragment@0:target:0";
	};
};
```

- 缝合命令(在本目录执行),fdtoverlay 按参数顺序逐份应用:

```shell
fdtoverlay -i base.dtb -o merged-sensor.dtb sensor-overlay.dtbo
fdtoverlay -i base.dtb -o merged.dtb sensor-overlay.dtbo poll-overlay.dtbo
```

- 第一步的 diff(`diff base.roundtrip.dts merged-sensor.roundtrip.dts`),sensor@48 挂进 i2c@800 名下:

```output
15a16,22
>
> 		sensor0: sensor@48 {
> 			phandle = <0x03>;
> 			status = "okay";
> 			reg = <0x48>;
> 			compatible = "acme,temp-sensor";
> 		};
26a34
> 		sensor0 = "/i2c@800/sensor@48";
```

sensor@48 的 phandle 从 overlay 本地的 0x01 改写成 0x03,避开基座已占的 0x01 与 0x02。`__symbols__` 收下 sensor0,路径从 `/fragment@0/__overlay__/sensor@48` 改写成缝合后的真实路径。属性排列次序与源文件不同(phandle 排在最前),是按缝合时的合并次序写入的。

- 第二步的 diff(`diff merged-sensor.roundtrip.dts merged.roundtrip.dts`),整段 diff 只有一行:

```output
17a18
> 			poll-interval = <0x64>;
```

poll-overlay 欠的 sensor0 由第一份 overlay 贡献进 `__symbols__` 的条目还清,两份 overlay 链式接力成立。

- 坏 overlay 的真实报错(fdtoverlay 退出码 1,不生成产物):

```output
Failed to apply 'bad-overlay.dtbo': FDT_ERR_NOTFOUND
```

bad-overlay.dtbo 本身编译通过,ghost 记进了 `__fixups__`,应用的时候基座的 `__symbols__` 里查不到这个名字。

验收:重新执行四条编译命令与两条缝合命令,`__symbols__` 摘录、两份 overlay 的反编译与两段 diff 同上列记录一致,`fdtoverlay -i base.dtb -o /tmp/check.dtb bad-overlay.dtbo` 仍报上列错误且退出码为 1。
