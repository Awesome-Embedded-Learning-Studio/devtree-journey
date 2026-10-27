# Lab 09-phandle-allocation:观察 phandle 的发号规律

目的:三份小 dts 各藏一种情形,编译反编译后读 phandle 数值的分配规律,第四份重复标签的源文件收下真实报错,对应第四卷“phandle 的号是谁分的,按什么顺序分?”一篇。

- 输入(本目录):`order.dts`(标签定义顺序与引用顺序故意相反)、`twolabel-idle.dts`(一个节点挂两个标签,另有一个标签闲置)、`explicit.dts`(两个节点手写显式 phandle)、`dup-label.dts`(两个节点抢同一个标签)
- 生成命令(在本目录执行):`dtc -I dts -O dtb -o order.dtb order.dts`,反编译 `dtc -I dtb -O dts order.dtb > order.roundtrip.dts`,另外两份正常源文件同一路数换文件名。三份编译全部静默通过
- 实际使用版本:dtc v1.8.1,2026-10-18 本机复现
- 观察一,号跟着引用被回填的顺序走:`order.dts` 里 clk1 定义在前、clk2 在后,taker@2000 引用 &clk2、taker@3000 引用 &clk1。反编译产物里定义靠后的 clock@104 拿 0x01、定义靠前的 clock@100 拿 0x02,发号跟的是引用兑现的次序,标签在源码里的定义顺序被抛在一边。读数命令与输出:

```shell
grep -E 'clock@|taker@|phandle =|clocks =' order.roundtrip.dts
```

```output
	clock@100 {
		phandle = <0x02>;
	clock@104 {
		phandle = <0x01>;
	taker@2000 {
		clocks = <0x01>;
	taker@3000 {
		clocks = <0x02>;
```

- 观察二,号认节点不认标签,闲置标签不发号:`twolabel-idle.dts` 给 clock@100 挂 fast 与 fclk 两个标签,clocks 里的两处引用都回填成 0x01,没人引用的 idleclk(clock@104)连 phandle 属性都没有。`twolabel-idle.roundtrip.dts` 反编译全文(真实输出):

```dts
/dts-v1/;

/ {
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	clock@100 {
		compatible = "demo,clock";
		reg = <0x100 0x04>;
		#clock-cells = <0x00>;
		phandle = <0x01>;
	};

	clock@104 {
		compatible = "demo,clock";
		reg = <0x104 0x04>;
		#clock-cells = <0x00>;
	};

	taker@2000 {
		compatible = "demo,taker";
		reg = <0x2000 0x10>;
		clocks = <0x01 0x01>;
	};
};
```

- 观察三,手写号原样保留,自动号避开已占的号:`explicit.dts` 给 clk1 手写 0x21、给 clk3 手写 0x1,留给自动分配的 clk2 与 clk4 拿到 0x02 与 0x03。计数器从 1 起步只往前走,碰到已占的号就跳过,引用处回填手写值。读数命令与输出:

```shell
grep -E 'clock@|taker@|phandle =|clocks =' explicit.roundtrip.dts
```

```output
	clock@100 {
		phandle = <0x21>;
	clock@104 {
		phandle = <0x02>;
	clock@108 {
		phandle = <0x01>;
	clock@10c {
		phandle = <0x03>;
	taker@2000 {
		clocks = <0x21 0x02 0x01 0x03>;
```

- 重复标签的报错,真实输出,退出码 2,产物不生成:

```output
dup-label.dts:13.18-17.4: ERROR (duplicate_label): /clock@104: Duplicate label 'clk1' on /clock@104 and /clock@100
ERROR: Input tree has errors, aborting (use -f to force output)
```

验收:重新执行三份正常源文件的编译与反编译,两条 grep 读数与 `twolabel-idle.roundtrip.dts` 全文同上文记录一致,`dtc -I dts -O dtb -o dup-label.dtb dup-label.dts` 仍报上列两条错误且退出码为 2。
