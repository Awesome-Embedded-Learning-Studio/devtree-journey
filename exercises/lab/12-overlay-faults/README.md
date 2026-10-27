# Lab 12-overlay-faults:缝树的三种真实报错与修好的对照

目的:走一条 overlay 的故障小链,收集 fdtoverlay 的三种真实报错,再拿修好后的成功应用做对照,对应讲义“电脑上缝树怎么验,标签对不上又报什么错?”(打包与欠条的底子在“增量怎么打包,引用的答案为什么等到应用那一刻?”)。

- 输入(本目录):`base.dts` 是挂了 i2c0、uart0 标签的最小核心板,`sensor-overlay.dtso` 往 i2c0 名下叠 sensor@48,`spi-overlay.dtso` 引用基础里从没定义过的 spi0
- 编译(在本目录执行):`dtc -@ -I dts -O dtb -o base.dtb base.dts` 静默通过,overlay 的编译同套路,`sensor-overlay.dtbo` 编译时报一串 reg_format 告警,缘由是编译时见不到父节点 i2c0,真假要等叠上去之后才判得清,告警原文与讲义贴的同一批,此处不重贴
- 实际使用版本:dtc v1.8.1 与 fdtoverlay v1.8.1(两位都住 /usr/sbin),2026-10-18 本机复现

故障一:基座忘带 `-@` 就编,应用时找不到 `__symbols__`:

```shell
dtc -I dts -O dtb -o base-noat.dtb base.dts
fdtoverlay -i base-noat.dtb -o noat-merged.dtb sensor-overlay.dtbo
echo $?
```

```output

Failed to apply 'sensor-overlay.dtbo': FDT_ERR_BADOFFSET
base blob does not have a '/__symbols__' node, make sure you have compiled the base blob with '-@' option
1
```

- 第二行把病因和药方都说明白了:基础产物里没有 `/__symbols__` 节点,overlay 本身没毛病,药方是带 `-@` 重编基础

故障二:overlay 引用基础里不存在的标签:

```shell
fdtoverlay -i base.dtb -o bad-merged.dtb spi-overlay.dtbo
echo $?
```

```output

Failed to apply 'spi-overlay.dtbo': FDT_ERR_NOTFOUND
1
```

- FDT_ERR_NOTFOUND 说的是应用那一刻的查找失败:应用器拿 spi0 去查基础的 `__symbols__`,表里没有这个名字,排查按 overlay 的 `__fixups__` 里欠了谁、基础的 `__symbols__` 里有没有谁的顺序走

故障三:截断的 dtbo 喂给 fdtoverlay(完好产物 306 字节,截到 100 字节):

```shell
head -c 100 sensor-overlay.dtbo > sensor-cut.dtbo
fdtoverlay -i base.dtb -o cut-merged.dtb sensor-cut.dtbo
echo $?
```

```output

Failed to apply 'sensor-cut.dtbo': FDT_ERR_BADSTRUCTURE
1
```

- 头部还完整,结构块被截出了文件的范围,fdtoverlay 报 FDT_ERR_BADSTRUCTURE,读不动的产物它不收

修好后的对照(基础带 `-@`、overlay 完整,应用加 diff 验缝合):

```shell
fdtoverlay -i base.dtb -o merged.dtb sensor-overlay.dtbo && echo OK
dtc -I dtb -O dts base.dtb > before.dts
dtc -I dtb -O dts merged.dtb > after.dts
diff before.dts after.dts
```

```output
OK
15a16,21
>
> 		sensor@48 {
> 			status = "okay";
> 			reg = <0x48>;
> 			compatible = "acme,temp-sensor";
> 		};
```

- diff 报的 15a16,21:after.dts 在 before.dts 第 15 行之后多出六行,sensor@48 整个节点住进了 i2c0 名下,基础的节点一个没动,fragment 的包装没留残渣

验收:重新执行上文的编译、截断与应用命令,三次报错与 diff 输出与上文记录相同。
