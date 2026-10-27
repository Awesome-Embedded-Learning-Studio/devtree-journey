---
title: "树里的节点,怎么变成干活的设备?"
volume: 3
chapter: 8
section: 2
order: 2
description: "Driver Model 分两遍扫描 control FDT:绑定拿 compatible 对表,uart2 的第二个字符串被 ns16550 认走,probe 顺着 chosen 的 stdout-path 捞出串口,of_to_plat 读走 clock-frequency,横幅由此上了屏,一条链在 v2026.10 源码里走完"
status: draft
---

# 树里的节点,怎么变成干活的设备?

上一篇把 control FDT 的地址与内容都定了案,摆上桌的 uart2 节点还躺在树里没人用。本篇追消费的全程:树进了 Driver Model 之后,节点跟驱动的对表、串口被拉起来的经过,咱们一条链走到底,横幅上了屏才算收工。

版本还是上一篇锁定的 U-Boot v2026.10,咱们贴的每一处调用链,你在同样的地址都核对得上。

## 树进了 Driver Model:绑定这一步

地址定好了,树在内存里躺平了,接下来轮到消费它的框架登场。U-Boot 的驱动框架叫 Driver Model,咱们把它的中文叫法写作驱动模型,官方文档给它的三个词咱们照录:uclass 是按同一种方式工作的一组设备,driver 是与某个外设对话、把它包装成高层接口的代码,device 是驱动落在某个具体外设上的实例。驱动认领了节点之后,device 就是这对组合的产物。

咱们追到 Driver Model 的初始化,它在启动里要来两回:头一回在 U-Boot 还没搬进高内存的时候,第二回等搬家完成了再来:

```c
/* common/board_f.c:846 起,initf_dm() 内,有删节 */
	if (!CONFIG_IS_ENABLED(SKIP_EARLY_DM))
		ret = dm_init_and_scan(true);
	else
		ret = dm_init(false);
```

```c
/* common/board_r.c:267,initr_dm() 内 */
	ret = dm_init_and_scan(false);
```

两回的区别在参数上:头一回传的是 `true`,只认带启动阶段标记的节点,第二回传的是 `false`,全树的节点都要过一遍。头一个引文里的条件是给开了 SKIP_EARLY_DM 的特殊板子留的旁路,常规板子走的就是 dm_init_and_scan(true)。为什么要来两回?官方文档的动机咱们照录:

```text
/* doc/develop/driver-model/design.rst,Pre-Relocation Support 一节 */
For pre-relocation we simply call the driver model init function. Only
drivers marked with DM_FLAG_PRE_RELOC or the device tree 'bootph-all'
property are initialised prior to relocation. ...
Then post relocation we throw that away and re-init driver model again.
```

翻成白话是这样的:搬家之前的那段内存又小又紧,头一回只挑标记过的少数节点,够打横幅就够用了,等搬完了家,咱们把 Driver Model 推倒重来,把全树也重新绑了一遍。

绑定(binding)就是把节点和驱动登记成 device 的动作,它的入口链条,咱们贴真码:

```c
/* drivers/core/root.c:195 起,有删节 */
static int dm_scan_fdt_node(struct udevice *parent, ofnode parent_node,
			    bool pre_reloc_only)
{
	for (node = ofnode_first_subnode(parent_node);
	     ofnode_valid(node);
	     node = ofnode_next_subnode(node)) {
		if (!ofnode_is_enabled(node)) {
			pr_debug("   - ignoring disabled device\n");
			continue;
		}
		err = lists_bind_fdt(parent, node, NULL, NULL, pre_reloc_only);
		...
	}
}
```

咱们跟着 `dm_scan_fdt` 从根节点往下逐个逛子节点,`status` 不是 `okay` 的节点就被跳过了,剩下的交给 `lists_bind_fdt`,它就是咱们要找的对表现场:

```c
/* drivers/core/lists.c:199 起,有删节 */
int lists_bind_fdt(struct udevice *parent, ofnode node, struct udevice **devp,
		   struct driver *drv, bool pre_reloc_only)
{
	struct driver *driver = ll_entry_start(struct driver, driver);
	const int n_ents = ll_entry_count(struct driver, driver);
	...
	compat_list = ofnode_get_property(node, "compatible", &compat_length);
	...
	for (i = 0; i < compat_length; i += strlen(compat) + 1) {
		compat = compat_list + i;
		...
		for (entry = driver; entry != driver + n_ents; entry++) {
			...
			id = NULL;
			if (entry->of_match) {
				ret = driver_check_compatible(entry->of_match, &id,
							      compat);
				if (ret)
					continue;
			}

			if (pre_reloc_only) {
				if (!ofnode_pre_reloc(node) &&
				    !(entry->flags & DM_FLAG_PRE_RELOC)) {
					log_debug("Skipping device pre-relocation\n");
					return 0;
				}
			}
			...
			ret = device_bind_with_driver_data(parent, entry, name,
							   id ? id->data : 0, node,
							   &dev);
```

咱们把它干的事念成白话。头一件事是把节点的 `compatible` 属性取出来,咱们在第一卷认过它的字节样子,那是一列按书写顺序排好的字符串。接着外层循环按列表的顺序逐个取字符串,内层循环把编译期登记过的驱动全部过一遍,拿每个驱动的匹配表跟当前字符串做 `strcmp`。`ll_entry_start` 取的是链接器拼出来的驱动表,`U_BOOT_DRIVER` 宏在编译期就把驱动登记了进去,所以全部的驱动是一张现成的数组,运行时不用注册了。对表的顺序也有讲究:头一个字符串的描述最具体,越往后的越泛,匹配就按书写的顺序问。

咱们把两个字符串挨个问下来,情况是这样的:头一个 `rockchip,rk3399-uart` 在 U-Boot 的驱动表里没人认,第二个 `snps,dw-apb-uart` 则被 ns16550 驱动认走了。它的登记代码咱们贴在下面,咱们连匹配表带方法一起看:

```c
/* drivers/serial/ns16550.c:596 与 609,有删节 */
static const struct udevice_id ns16550_serial_ids[] = {
	{ .compatible = "ns16550",		.data = PORT_NS16550 },
	{ .compatible = "ns16550a",		.data = PORT_NS16550 },
	...
	{ .compatible = "snps,dw-apb-uart",	.data = PORT_NS16550 },
	{}
};

U_BOOT_DRIVER(ns16550_serial) = {
	.name	= "ns16550_serial",
	.id	= UCLASS_SERIAL,
	.of_match = ns16550_serial_ids,
	.of_to_plat = ns16550_serial_of_to_plat,
	.probe = ns16550_serial_probe,
	...
};
```

字符串对上了之后,头一遍的绑定还要过一道检查。`pre_reloc_only` 为真的那一遍里,`ofnode_pre_reloc` 检查的是节点身上的 `bootph-all` 一类标记,咱们标本板的 uart2 带着 `bootph-all`,正是 `rk3399-u-boot.dtsi` 补的那行,检查也就放行了。全绑的那一遍没有这道检查,标记也就不影响它了。

过了检查,咱们跟着进 `device_bind_with_driver_data`,它落在 device.c 的公共绑定函数里:

```c
/* drivers/core/device.c:40 起,device_bind_common(),有删节 */
	ret = uclass_get(drv->id, &uc);
	...
	dev = calloc(1, sizeof(struct udevice));
	...
	dev_set_ofnode(dev, node);
	dev->parent = parent;
	dev->driver = drv;
	dev->uclass = uc;
	...
	ret = uclass_bind_device(dev);
	...
	if (drv->bind) {
		ret = drv->bind(dev);
	}
	...
	if (uc->uc_drv->post_bind) {
		ret = uc->uc_drv->post_bind(dev);
	}
```

绑定干的事到这里清楚了:它按驱动的 `id` 找到 UCLASS_SERIAL 这个 uclass,给 device 申请了一个 `struct udevice` 的壳,把节点的引用、驱动指针、uclass 归属都填进去,再挂进父子的链表,然后通知 uclass 和驱动各自的 `bind` 钩子。此时 device 有了户口,寄存器倒是一个都没碰。它们什么时候读属性、什么时候动硬件,咱们到 probe 那一步再看。

## probe:顺着 chosen 把串口捞出来

咱们回到 `init_sequence_f` 的表里,`serial_init` 排在 `display_options` 的前面,横幅的出口是串口,所以顺序也只能这样。串口初始化的头一件事是找到该用哪个串口,`gd->fdt_blob` 在这里又出场了一次:

```c
/* drivers/serial/serial-uclass.c:32 起,有删节 */
static int serial_check_stdout(const void *blob, struct udevice **devp)
{
	int node = -1;
	const char *str, *p;
	int namelen;

	/* Check for a chosen console */
	str = fdtdec_get_chosen_prop(blob, "stdout-path");
	if (str) {
		p = strchr(str, ':');
		namelen = p ? p - str : strlen(str);
		...
		node = fdt_path_offset_namelen(blob, str, namelen);
	}
	...
	if (!uclass_get_device_by_of_offset(UCLASS_SERIAL, node, devp))
		return 0;

	/*
	 * If the console is not marked to be bound before relocation, bind it
	 * anyway.
	 */
	if (node > 0 && !lists_bind_fdt(gd->dm_root, offset_to_ofnode(node),
					devp, NULL, false)) {
		...
	}
```

它读的是 `chosen` 节点的 `stdout-path`。咱们标本板上的值是 `serial2:1500000n8`,它的前半截 serial2 是个别名,`rk3399-base.dtsi` 的 `aliases` 节点里写着 `serial2 = &uart2`,libfdt 的路径解析认得别名,一路换算到 `serial@ff1a0000` 的节点偏移。接下来的 `uclass_get_device_by_of_offset` 拿着节点偏移在 UCLASS_SERIAL 里找 device,找到之后就调起了 `device_probe`。还有一个贴心的兜底,控制台节点要是没带启动阶段标记、头一遍绑定漏了它,源码就在这里现场补了一次绑定,启动的日志可不能没有出口。

probe 的主干在 device.c,咱们按顺序数它请了哪些帮手:

```c
/* drivers/core/device.c:485 起,有删节 */
int device_probe(struct udevice *dev)
{
	...
	ret = device_of_to_plat(dev);
	...
	/* Ensure all parents are probed */
	if (dev->parent) {
		ret = device_probe(dev->parent);
	}
	...
	ret = uclass_pre_probe_device(dev);
	...
	if (drv->probe) {
		ret = drv->probe(dev);
	}

	ret = uclass_post_probe_device(dev);
	...
```

头一件请出来的帮手是 `device_of_to_plat`,它调驱动自己的 `of_to_plat` 方法,把节点里的属性读进驱动的平台数据。ns16550 的实现读的正是咱们摆过的那几样:

```c
/* drivers/serial/ns16550.c:533,有删节 */
int ns16550_serial_of_to_plat(struct udevice *dev)
{
	...
	addr = not_xpl() ? dev_read_addr_size(dev, &size) :
		dev_read_addr(dev);
	...
	plat->reg_offset = dev_read_u32_default(dev, "reg-offset", 0);
	plat->reg_shift = dev_read_u32_default(dev, "reg-shift", 0);
	plat->reg_width = dev_read_u32_default(dev, "reg-io-width", 1);

	if (!plat->clock)
		plat->clock = dev_read_u32_default(dev, "clock-frequency", 0);
```

`reg` 给它换来寄存器的基址,`reg-shift` 与 `reg-io-width` 则定下寄存器的排布,`clock-frequency` 给出的是输入时钟。你在第一卷改过的那个属性,如今第二次上了岗,读到的 24000000 恰是 `rk3399-u-boot.dtsi` 写进去的数。内核同源的树里原本没有它,时钟的值要靠完整的时钟驱动去算,U-Boot 等不起这样的排场,它干脆在自己的增补里把数写死。改树的、读树的、被读的数,三方在源码里对上了茬。

属性读齐了,probe 的正戏开锣,ns16550 的 probe 调 `ns16550_init`,把硬件初始化到能收发的程度。再往后 uclass 的收尾钩子跑完,`serial_init` 把设备记进了 `gd->cur_serial_dev`,`display_options` 的横幅就从这块串口出去了。你在开发板上见过的头一行 `U-Boot 2026.10-...`,走的路数就是上面这一整条。

搬到高内存之后的那第二遍,还多了一件事。`initr_of_live` 的差事是调用 `of_live_build`,它把平铺的 control FDT 展开成活树,live tree 的意思就是节点带指针、可以直接遍历的形态。活树落地了之后还有一次 `of_alias_scan`,它把 `chosen` 和别名解析的结果缓存了下来。搬完家后的 `initr_dm` 把全树重新绑定,咱们追过的链条会整体再走一遍,只是范围从带标记的少数节点换成了全树。

一条链到这里走圆了:绑定对表、probe 捞出串口、`of_to_plat` 读齐了属性,横幅上了屏。U-Boot 的答法咱们攥在手里了,同一道题 Linux 那边的答法,咱们到下一篇里对照着看。

## 本节自检

文章读完了,你拿下面的小问题验一验自己。

1. 同一个节点的 compatible 列表有两个字符串,U-Boot 按什么顺序对表?咱们标本板的 uart2 最终对上了哪个驱动的哪条表项?
2. 绑定与 probe 的分工分别是什么?`of_to_plat` 读到的 `clock-frequency` 是谁写进树里的,为什么内核同源的树里没有它?

<details>
<summary>参考答案(想好再展开)</summary>

1. 按 compatible 列表的书写顺序,从最具体的字符串问起。uart2 的头一个字符串没人认领,第二个 `snps,dw-apb-uart` 对上了 `ns16550_serial_ids` 表里的同名表项,接手的驱动是 `ns16550_serial`。
2. 绑定登记户口:创建 `struct udevice`,填上节点、驱动与 uclass 归属,不碰硬件。probe 让硬件动起来:头一步经 `of_to_plat` 读属性,后面才调驱动的 probe 方法。`clock-frequency` 是 `rk3399-u-boot.dtsi` 写进 control FDT 的,内核同源的树里时钟靠完整的时钟驱动计算,没有写死的这个属性。

</details>

## 延伸阅读

本篇的机制叙述与源码引用,咱们在官方文档里都找到了正本:

- [U-Boot: Driver Model](https://docs.u-boot.org/en/latest/develop/driver-model/index.html):Driver Model 的文档入口,uclass、driver、device 的定义与设计动机在这里展开。
- [U-Boot: Driver Model Design](https://docs.u-boot.org/en/latest/develop/driver-model/design.html):绑定与 probe 的详细设计,启动前后两遍初始化的说明也在这篇。
