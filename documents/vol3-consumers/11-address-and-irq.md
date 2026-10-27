---
title: "reg 怎样变成驱动能用的资源,中断号又从哪来?"
volume: 3
chapter: 12
section: 2
order: 11
description: "of_address_to_resource 按序号从 reg 里取出地址与长度,of_translate_address 顺着父节点的 ranges 一层层往上爬,每爬一层换算一次地址,空 ranges 一比一放行,of_iomap 再把翻译与映射并成一步,中断的规格由 of_irq_get 走三步换号:of_irq_parse_one 解析规格,interrupts-extended 排在头一个试,老式 interrupts 顺着 interrupt-parent 找控制器,irq_find_host 找 domain,irq_create_of_mapping 完成换号,probe 里的 platform_get_irq 转接到它身上"
status: draft
---

# reg 怎样变成驱动能用的资源,中断号又从哪来?

上一篇咱们立住了引用计数的纪律,这一篇接着收 probe 里的下一行:platform_get_resource 取到的 struct resource,它的源头就在 reg 的翻译里。翻译的活分两段走,咱们从头一段看起。

## reg 变成 struct resource:of_address_to_resource 与 of_iomap

上一章咱们留了一句话:登记设备的时候,`of_device_alloc` 把节点上的 `reg` 翻成了 struct resource,挂进了 platform 设备。probe 里咱们取它用 `platform_get_resource`,而翻译本身的活住在 `drivers/of/address.c`,入口的名字是 `of_address_to_resource`,真正干活的 `__of_address_to_resource` 咱们贴主干:

```c
	addrp = __of_get_address(dev, index, bar_no, &size, &flags);
	if (addrp == NULL)
		return -EINVAL;

	/* Get optional "reg-names" property to add a name to a resource */
	if (index >= 0)
		of_property_read_string_index(dev, "reg-names",	index, &name);

	if (flags & IORESOURCE_MEM)
		taddr = of_translate_address(dev, addrp);
	...
	if (taddr == OF_BAD_ADDR)
		return -EINVAL;
	memset(r, 0, sizeof(struct resource));
	...
	r->flags = flags;
	r->name = name ? name : dev->full_name;

	return __of_address_resource_bounds(r, taddr, size);
```

咱们把它拆成三步看。`__of_get_address` 按序号从 `reg` 里取出的是一条地址与长度,顺便看一眼可选的 `reg-names`,给 resource 起个人能读的名字。取出的地址交给 `of_translate_address` 翻译,翻译就是下一节的主角。翻译成了的地址与长度,最后被填进了 struct resource,起头的 `memset` 保证没给的成员是零。struct resource 是内核通用的资源描述,咱们填进去的是 start、end 与标志,总线的驱动、/proc/iomem 的展示认的都是它,设备树只是它的出身之一。

映射的入口 `of_iomap` 咱们也核过,它的家同样在 `drivers/of/address.c`:

```c
void __iomem *of_iomap(struct device_node *np, int index)
{
	struct resource res;

	if (of_address_to_resource(np, index, &res))
		return NULL;

	if (res.flags & IORESOURCE_MEM_NONPOSTED)
		return ioremap_np(res.start, resource_size(&res));
	else
		return ioremap(res.start, resource_size(&res));
}
```

它一步顶的是两步:咱们拿 `of_address_to_resource` 把 `reg` 翻成 resource,再拿 `ioremap` 把物理地址映射成内核的虚拟地址。设备树里写的都是物理地址,CPU 真正访问寄存器要的是虚拟地址,两步并作一步就是它存在的意思。现代驱动里更常见的写法是 `devm_platform_ioremap_resource`,probe 跑完映射就自动归还了,咱们在示意代码里用的 `platform_get_resource` 则是只取不映射,两样配合着用的情况也常见。

## ranges 的地址翻译:子地址一层层换算到根

“怎样描述和组织设备”那章咱们对 `ranges` 只认了个名字,说好了讲地址映射时再细聊,现在到还的时候了。咱们把问题立起来:子节点的 `reg` 报的是子地址空间的地址,可驱动要访问的是 CPU 眼里的物理地址,中间隔着的换算就是地址翻译。

干活的函数链从 `of_translate_address` 进,真正的主循环住在 `drivers/of/address.c` 的 `__of_translate_address` 里,咱们读它的主干:

```c
	for (;;) {
		...
		/* Switch to parent bus */
		of_node_put(dev);
		dev = parent;
		parent = get_parent(dev);

		/* If root, we have finished */
		if (parent == NULL) {
			pr_debug("reached root node\n");
			return of_read_number(addr, na);
		}
		...
		/* Apply bus translation */
		if (of_translate_one(dev, bus, pbus, addr, na, ns, pna, rprop))
			return OF_BAD_ADDR;
		...
	}
```

循环的走法是往上爬:从设备所在的节点出发,一层一层地往上爬,每爬一层就用父节点上的 `ranges` 把地址换算成父空间的写法,爬到了根,返回的地址就是 CPU 物理地址。每爬一层的头一件事,是问清楚父子各自的 `#address-cells` 与 `#size-cells`,切法变了,地址的宽度就跟着变。一层一层的换算落在 `of_translate_one` 身上,咱们看它的关键分支:

```c
	ranges = of_get_property(parent, rprop, &rlen);
	if (ranges == NULL && !of_empty_ranges_quirk(parent) &&
	    strcmp(rprop, "dma-ranges")) {
		pr_debug("no ranges; cannot translate\n");
		return 1;
	}
	if (ranges == NULL || rlen == 0) {
		offset = of_read_number(addr, na);
		/* set address to zero, pass flags through */
		memset(addr + pbus->flag_cells, 0, (pna - pbus->flag_cells) * 4);
		pr_debug("empty ranges; 1:1 translation\n");
		goto finish;
	}

	pr_debug("walking ranges...\n");
```

父节点身上缺了 `ranges`,翻译默认就过不去了。`ranges` 在而长度为零,语义是父子的地址一模一样,原样地放行。非空的 `ranges` 则一条条过:每条的构成是子地址加父地址加长度,子地址落进哪条的范围,父地址就按命中条目的基址偏移算出来。咱们拿 QEMU 的 virt 机的真树做例子,实验那篇咱们导出来的树里有个现成的节点:

```dts
	platform-bus@c000000 {
		interrupt-parent = <0x8002>;
		ranges = <0x00 0x00 0xc000000 0x2000000>;
		#address-cells = <0x01>;
		#size-cells = <0x01>;
		compatible = "qemu,platform", "simple-bus";
	};
```

子节点声明地址用 1 个 cell、长度用 1 个 cell,根上声明的是 2 加 2,所以那几格数字咱们读成三条:子地址的读数是 0x0,父地址的读数是 0x0c000000,长度的读数是 0x2000000。咱们导出的这棵 virt 树里,platform-bus 的下面暂时一个孩子都没挂,咱们就把算术当一道练习:假若有个孩子报了子地址 0x0,爬过了这一层,它手里的地址就换成了 0x0c000000,再往上一步就到了根,循环就收工了,CPU 最终拿到的物理地址就是 0x0c000000。空 `ranges` 的真例树上也有:中断控制器 `intc@8000000` 自己声明了空的 `ranges`,它底下的 `v2m@8020000` 报的地址是 0x08020000,爬过了这一层原样不动,启动日志里的 `GICv2m: range[mem 0x08020000-0x08020fff]` 就是这段翻译的产物。上一章咱们讲过 `simple-bus` 的身份让登记往下走,这一章咱们补上它的另一面:总线节点背上的 `ranges`,就是孩子们地址进入父空间的翻译表。

想自己逐条读 `ranges` 的驱动,`include/linux/of_address.h` 备了 `of_range_parser` 与 `for_each_of_range` 的迭代器,PCI 桥的驱动就靠它解析桥上的窗口,咱们认个名字就好。实验那篇的启动日志里,pci-host-generic 驱动打印的那几行 ranges 窗口,就是它跑起来的现场。

地址的路走通了,probe 的示意代码里还剩最后一行没收尾的活,platform_get_irq_optional 取的中断号从哪来。interrupts 属性里躺的只是几个 cell,咱们接着追那段从规格到虚拟中断号的路。

## 中断号从哪来:of_irq_get 走的解析链

`interrupts` 属性里躺的只是几个 cell,virt 机的树上串口节点的写法是 `interrupts = <0x00 0x01 0x04>`。可驱动要的是 Linux 的虚拟中断号,就像日志里的那个 irq = 13。中间隔着的东西就是中断控制器:三个 cell 是给控制器看的中断规格,规格交给控制器的解析规则,换回来的则是一个全系统唯一的号,咱们接下来追的就是这段路。

入口咱们选 `of_irq_get`,它的家在 `drivers/of/irq.c`:

```c
int of_irq_get(struct device_node *dev, int index)
{
	int rc;
	struct of_phandle_args oirq;
	struct irq_domain *domain;

	rc = of_irq_parse_one(dev, index, &oirq);
	if (rc)
		return rc;

	domain = irq_find_host(oirq.np);
	if (!domain) {
		rc = -EPROBE_DEFER;
		goto out;
	}

	rc = irq_create_of_mapping(&oirq);
out:
	of_node_put(oirq.np);

	return rc;
}
```

三步的分工清楚。`of_irq_parse_one` 把规格解析了出来,装进 `oirq` 的是控制器节点的指针加一串参数。`irq_find_host` 拿控制器节点找它的 irq domain,一无所获时返回的是 `-EPROBE_DEFER`,probe 收到这个码就知道控制器的驱动还没就位,咱们晚点还会再等到一次机会。找到了 domain,`irq_create_of_mapping` 完成最后的换号。domain 的内部怎么造号、层级怎么叠,那都是中断子系统的大文章,咱们止步在入口,延伸阅读里给官方文档指了路。

规格的解析咱们接着看 `of_irq_parse_one` 的主干,咱们还在同一个文件里:

```c
	struct device_node __free(device_node) *p = NULL;
	...
	/* Try the new-style interrupts-extended first */
	res = of_parse_phandle_with_args(device, "interrupts-extended",
					"#interrupt-cells", index, out_irq);
	if (!res) {
		p = out_irq->np;
	} else {
		/* Look for the interrupt parent. */
		p = of_irq_find_parent(device);
		/* Get size of interrupt specifier */
		if (!p || of_property_read_u32(p, "#interrupt-cells", &intsize))
			return -EINVAL;
		...
		/* Copy intspec into irq structure */
		out_irq->np = p;
		out_irq->args_count = intsize;
		for (i = 0; i < intsize; i++) {
			res = of_property_read_u32_index(device, "interrupts",
							(index * intsize) + i,
							out_irq->args + i);
			if (res)
				return res;
		}
	}

	/* Check if there are any interrupt-map translations to process */
	return of_irq_parse_raw(addr_buf, out_irq);
```

新式的 `interrupts-extended` 自己带着控制器的引用,`of_parse_phandle_with_args` 一步就解出了控制器与参数,所以它排在头一个试。老式的 `interrupts` 里只有裸的 cell,控制器是谁咱们得顺着 `interrupt-parent` 往上找,`of_irq_find_parent` 干的就是这个活,设备自己没写的话就继承父节点的。找到了控制器,切 cell 的依据从它身上的 `#interrupt-cells` 读,virt 机根上的 `interrupt-parent` 指着 GIC 的 `intc@8000000`,它声明了 `#interrupt-cells = <3>`,所以串口的三个 cell 按三格一组切开:头一格的 0 是 SPI 类型的共享外设中断,第二格的 1 是编号,第三格的 4 是触发方式的标志,细含义归 GIC 的 binding 文档管。收尾的 `of_irq_parse_raw` 再处理 interrupt-map 一类的级联翻译,咱们不追。开头声明的 p 带着 `__free(device_node)` 标记,函数收尾手动调 of_node_put(p) 的写法也就退场了,上一篇认过的自动配平,内核自己的代码里也在这么用。

probe 里咱们通常不直接调 `of_irq_get`,写的是 `platform_get_irq`。这层转接咱们在 `drivers/base/platform.c` 里核对过:

```c
	if (is_of_node(fwnode)) {
		ret = of_irq_get(to_of_node(fwnode), num);
		if (ret > 0 || ret == -EPROBE_DEFER)
			goto out;
	}
```

设备的出身是设备树时,platform 层就把中断的取得转给了 `of_irq_get`,ACPI 来的设备走旁边的分支。更老的封装 `irq_of_parse_and_map` 还在源码里,注释说它是解析加映射的连招,新代码里咱们用 `of_irq_get` 就好。

解析链走到了 domain 的门口,咱们按说好的止步。源码里的路都读完了,读到的对不对,咱们去 QEMU 里跑一个真的内核对证,下一篇就是那场实验的开场。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. `of_iomap` 一步顶两步,分开来看是哪两步?各自解决什么问题?
2. 父节点身上没有 `ranges`,`of_translate_one` 默认怎么处理?`ranges` 长度为零又是什么语义?
3. virt 树里 `platform-bus@c000000` 的 `ranges = <0x00 0x00 0xc000000 0x2000000>`,假若有个孩子报了子地址 0x0,爬过这一层之后,它手里的地址变成了多少?
4. `interrupts-extended` 与 `interrupts`,of_irq_parse_one 头一个试的是哪个?老式属性里切 cell 的依据从哪里读?
5. virt 机上串口的 `interrupts = <0x00 0x01 0x04>`,日志里 irq = 13,中间发生了什么?
6. `irq_find_host` 一无所获时返回什么?probe 收到它该怎么想?

<details>
<summary>参考答案(想好再展开)</summary>

1. 一步是 `of_address_to_resource` 把 `reg` 翻译成 struct resource,一步是 `ioremap` 把物理地址映射成内核虚拟地址。前者管翻译,后者管让 CPU 访问得到。
2. 没有 `ranges` 时翻译默认失败,地址换不过去。长度为零的 `ranges` 语义是父子的地址一模一样,原样放行。
3. 换成了 0x0c000000,再往上一步就到了根,循环就收工了,CPU 最终拿到的物理地址就是 0x0c000000。
4. 头一个试 `interrupts-extended`,它自带控制器的引用,一步就能解出。老式 `interrupts` 的切法从 interrupt-parent 找到的控制器节点身上的 `#interrupt-cells` 读。
5. 解析链顺着根上的 interrupt-parent 找到 GIC,按它的三格声明切开规格,irq domain 把这份规格映射成全系统的虚拟中断号 13,串口驱动拿到的就是它。
6. 返回 `-EPROBE_DEFER`,probe 收到这个码就知道控制器的驱动还没就位,咱们晚点还会再等到一次机会。

</details>

## 延伸阅读

中断子系统往深处走的官方文档,给你备好了:

- [The irq_domain Interrupt Number Mapping Library](https://docs.kernel.org/core-api/irq/irq-domain.html):中断号映射库的官方文档,`irq_create_of_mapping` 背后的 domain 机制在这里,本章止步的那个入口往里走就是它。
