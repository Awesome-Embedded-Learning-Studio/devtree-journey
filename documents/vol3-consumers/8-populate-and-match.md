---
title: "树上的节点,怎么变成跑起来的设备?"
volume: 3
chapter: 11
section: 1
order: 8
description: "of_platform_populate 从根往下递归,strict 模式的头一道筛选拦下没有 compatible 的 chosen 与 memory,第二道拦下 disabled 与重复登记,过关的节点被 of_device_alloc 包装成 platform 设备,递归的边界由 simple-bus 一类的默认总线表决定,配对的裁判 platform_match 里 OF 风格的比对排在最前,__of_match_node 把整张表扫完靠分数定胜者,分数是 INT_MAX/2 减去序号乘 4,对上了号以后 really_probe 把 probe 一层层请到现场"
status: draft
---

# 树上的节点,怎么变成跑起来的设备?

“Linux 何时读取 DTB”那章的收尾处,内核里的 device_node 树已经立了起来,每个节点的名字、属性和父子关系都在,unflatten_device_tree 干的活咱们也追过了。可那会儿的树只是一份躺在内存里的数据,咱们想让它动起来,就得有人把节点注册成了设备,再让驱动把设备认领了去。全卷锁定的版本是 U-Boot v2026.10 与 Linux v7.2.9,本章咱们只读 Linux 侧,引到的源码都从 kernel.org 的 v7.2.9 拉下来逐行核对过,引文里带的都是文件路径。

设备从哪儿来?咱们顺着一条主线看。内核把挑中的节点登记成 platform 设备,挂上了 platform 总线。驱动注册的时候,总线拿节点的 compatible 与驱动手里的 of_match_table 对表,对上了就调驱动的 probe。主线咱们拆成两篇走:本篇看登记挑中了哪些节点、驱动又怎么对表认领,后一篇咱们亲手编一个最小的驱动,再看 I2C 与 SPI 另走的路。

## 内核从根往下走,把挑中的节点登记成设备

登记的入口住在 `drivers/of/platform.c`。咱们顺着 initcall 阶梯去找它,挂载点在文件的末尾,只写了一行代码:

```c
arch_initcall_sync(of_platform_default_populate_init);
```

咱们往上看 of_platform_default_populate_init 的主干,它处理完 /reserved-memory 和 /firmware 这类特殊的节点后,把剩下的一切都交给了默认登记:

```c
		/* Populate everything else. */
		of_platform_default_populate(NULL, NULL, NULL);
```

咱们看到的 of_platform_default_populate 只是个转发,它把一张默认的总线匹配表,递给了真正干活的 of_platform_populate。有些 arm32 的板级代码也会自己调它,比如 `arch/arm/mach-imx/mach-imx6q.c` 里 `imx6q_init_machine` 的做法,效果与 initcall 的路是殊途同归的。咱们接着看 `of_platform_populate` 的核心循环,代码的位置也没挪,咱们还在同一个文件里读它:

```c
	root = root ? of_node_get(root) : of_find_node_by_path("/");

	device_links_supplier_sync_state_pause();
	for_each_child_of_node_scoped(root, child) {
		rc = of_platform_bus_create(child, matches, lookup, parent, true);
		if (rc)
			break;
	}
```

它从根节点的孩子们开始,把每个孩子交给了 `of_platform_bus_create` 去处理。根节点自己则不进设备的名单,咱们接下来也会看到 chosen 与 memory 这些顶层居民的下场。咱们要说的第一道筛选,就立在 `of_platform_bus_create` 的身上,严格模式下没有 compatible 的节点直接跳过:

```c
	/* Make sure it has a compatible property */
	if (strict && (!of_property_present(bus, "compatible"))) {
		pr_debug("%s() - skipping %pOF, no compatible prop\n",
			 __func__, bus);
		return 0;
	}
```

chosen 和 memory 的身上恰好没有 compatible,所以它们根本进不了设备登记,它们的信息早被更早的启动路径消费掉了。咱们在“传给 Linux 的 DTB 是哪一份”那章见过同样的处境:顶层的居民里,有的管的是启动参数,有的管的是内存布局,登记成设备的事本来就不归它们管。

咱们接着过第二道筛选,它查的是 status,代码写在 `of_platform_device_create_pdata` 的开头:

```c
	if (!of_device_is_available(np) ||
	    of_node_test_and_set_flag(np, OF_POPULATED))
		return NULL;
```

status 是 disabled 的节点,咱们看着它过不了 of_device_is_available 这一关,登记就到此打住了,不过节点还留在树上。重复登记也是不许的,of_node_test_and_set_flag 给节点立了 OF_POPULATED 标志,第二回进来就被挡了。

过了两道筛选的节点,咱们跟着它们往下走,它们就在同一个函数里被包装成了 platform 设备:

```c
	dev = of_device_alloc(np, bus_id, parent);
	if (!dev)
		goto err_clear_flag;
	...
	dev->dev.bus = &platform_bus_type;
	...
	if (of_device_add(dev) != 0) {
```

咱们看它包装进了什么。of_device_alloc 把节点上的 reg 翻译成 struct resource,再把 device_node 挂到设备的 of_node 成员上,挂的动作是 `device_set_node(&dev->dev, of_fwnode_handle(of_node_get(np)))`,顺手还拿走了一个引用。dev->dev.bus 也指向了 platform_bus_type,设备从此有了自己的总线。of_device_add 最后调的是 device_add,它把设备交进了通用驱动模型,匹配的机器就从那里开始转。

咱们回到 `of_platform_bus_create`,还有一段决定递归边界的代码:

```c
	dev = of_platform_device_create_pdata(bus, bus_id, platform_data, parent);
	if (!dev || !of_match_node(matches, bus))
		return 0;

	for_each_child_of_node_scoped(bus, child) {
		rc = of_platform_bus_create(child, matches, lookup, &dev->dev, strict);
```

节点自己登记完了,只有它匹配 matches 参数指向的总线表,内核才继续往它的孩子走,咱们把默认的总线表也找出来了。它如今不住在全局:早年导出的 of_default_bus_match_table 收进了 `of_platform_default_populate` 的函数体内,当一张局部的 static 表用:

```c
	static const struct of_device_id match_table[] = {
		{ .compatible = "simple-bus", },
		{ .compatible = "simple-mfd", },
		{ .compatible = "isa", },
		...
	};
```

咱们这下明白了 /soc 节点为什么总写着 `compatible = "simple-bus"`:少了这一行,它底下挂的一串外设就没人往下登记。咱们反过来说,一个孩子能不能进 platform 的名单,看的是父亲的身份,孩子自己说了不算。

登记的活到这里就看完了:入口住在 `drivers/of/platform.c`,两道筛选拦下了进不了名单的节点,递归的边界由父亲的身份决定。名单上的设备都挂上了 platform 总线,等的就是驱动手里的 of_match_table。对表的具体规则是什么,咱们接着追。

## compatible 与 of_match_table 怎么对上号

设备这边挂上了总线,咱们把另一半挪到驱动那里看。咱们写的驱动调用 `module_platform_driver` 宏,它展开后替咱们调 `platform_driver_register`。翻到 `drivers/base/platform.c` 里的 `__platform_driver_register`,它的骨干只有四行代码:

```c
	drv->driver.owner = owner;
	drv->driver.bus = &platform_bus_type;
	drv->driver.mod_name = mod_name;

	return driver_register(&drv->driver);
```

驱动的 bus 成员也指向了 platform_bus_type,设备与驱动就这样站到了同一条总线上。mod_name 参数把模块名也在这儿一并登记了。配对的裁判是总线的 match 回调,platform 总线的裁判叫 `platform_match`,咱们把它的主干读一遍:

```c
static int platform_match(struct device *dev, const struct device_driver *drv)
{
	struct platform_device *pdev = to_platform_device(dev);
	struct platform_driver *pdrv = to_platform_driver(drv);
	int ret;

	/* When driver_override is set, only bind to the matching driver */
	ret = device_match_driver_override(dev, drv);
	if (ret >= 0)
		return ret;

	/* Attempt an OF style match first */
	if (of_driver_match_device(dev, drv))
		return 1;
	...
	/* fall-back to driver name match */
	return (strcmp(pdev->name, drv->name) == 0);
}
```

咱们接着往下追。override 的判断收进了公共助手 `device_match_driver_override`,OF 风格的匹配还是排在 ACPI、id_table 和驱动名的前面,设备树来的设备走的就是它。链子往下穿了四层。`of_driver_match_device` 是 `include/linux/of_device.h` 里的内联函数,它调的下一层是 `drivers/of/device.c` 里的 `of_match_device`,再往下一层的 `of_match_node` 与真正比对的活,都落在 `drivers/of/base.c` 的 `__of_match_node` 身上:

```c
	for (; matches->name[0] || matches->type[0] || matches->compatible[0]; matches++) {
		score = __of_device_is_compatible(node, matches->compatible,
						  matches->type, matches->name);
		if (score > best_score) {
			best_match = matches;
			best_score = score;
		}
	}
```

内核把匹配表从头扫到了尾,给节点打的分互相比着,分数最高的留下。分数怎么算的?咱们看打分函数 `__of_device_is_compatible` 里命中的那一刻:

```c
	if (compat && compat[0]) {
		prop = __of_find_property(device, "compatible", NULL);
		for (cp = of_prop_next_string(prop, NULL); cp;
		     cp = of_prop_next_string(prop, cp), index++) {
			if (of_compat_cmp(cp, compat, strlen(compat)) == 0) {
				score = INT_MAX/2 - (index << 2);
				break;
			}
		}
```

它把节点 compatible 属性里的字符串逐个拿出来与表项比对,命中的得分是 INT_MAX/2 减去序号乘 4。序号小的得分高,所以顺序真正要紧的一侧在节点那里:compatible 列表的第一个字符串是最具体的身份,越往后写的越像兼容旧款的通名。“怎样描述和组织设备”那章咱们练过的写法,到这里有了直接的机械后果。

表项长的是什么样子?咱们去看 of_device_id 的正本,它的家在 `include/linux/device-id/of.h`:mod_devicetable.h 如今是聚合的壳,各家的匹配表拆去了 `include/linux/device-id/` 目录,of_device_id 住进了同目录的 `of.h`,字段倒是一个都没改:

```c
struct of_device_id {
	char name[32];
	char type[32];
	char compatible[128];
	const void *data;
};
```

咱们平时只填 compatible,name 和 type 是给老式节点留的退路。data 留给驱动挂自己的数据,匹配命中了以后,probe 里也就能把它取回来了,咱们马上在最小驱动里用一次。

对上了号,总线下一步调的就是 probe,咱们去看汇合的现场。汇合点在 `drivers/base/dd.c` 的 `really_probe`,它把设备与驱动都备齐了,转手就调了 `call_driver_probe`:

```c
static int call_driver_probe(struct device *dev, const struct device_driver *drv)
{
	int ret = 0;

	if (dev->bus->probe)
		ret = dev->bus->probe(dev);
	else if (drv->probe)
		ret = drv->probe(dev);
```

platform 总线是带着 `bus->probe` 的,所以头一站是 `drivers/base/platform.c` 里的 `platform_probe`,它做完时钟与电源域的准备,再调驱动自己的 probe 函数。咱们在头文件里写的那个 probe 回调,就是这样被一层层请到现场的。方向反过来也是一样的:驱动晚于设备注册时,`driver_register` 会让新驱动把总线上已有的设备再对一遍表,两头不管谁晚到了,配对也耽误不了。

配对的规则到这里就读完了。设备登记了,驱动注册了,打分的公式也见了,可咱们还一次都没亲眼见过真的配对。下一篇咱们自己写一个最小的 platform 驱动,把配对的链路亲手走一遍。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. of_platform_populate 从哪个节点开始往下走?根节点自己会被登记成设备吗?
2. chosen 和 memory 为什么没有变成设备?它们的信息被谁消费了?
3. status = "disabled" 的节点与被 /delete-node/ 删掉的节点,在登记流程眼里差别是什么?
4. soc 节点为什么总写着 compatible = "simple-bus"?少了这一行,它底下挂的外设会怎样?
5. 匹配表里有两条表项都能配上节点的 compatible 列表,内核按什么规则挑一条?分数怎么算?
6. of_device_id 结构体里咱们平时填的是哪个成员?name 与 type 又是给谁留的?
7. 驱动晚于设备注册的时候,配对还会不会发生?靠的是什么?

<details>
<summary>参考答案(想好再展开)</summary>

1. 从根节点的孩子开始,of_platform_populate 用 for_each_child_of_node_scoped 逐个把孩子交给 of_platform_bus_create。根自己不登记,只被标上 OF_POPULATED_BUS。
2. 它们身上没有 compatible,strict 模式的第一道筛选就跳过了。chosen 的启动参数与 memory 的布局在更早的启动路径里就被读取,登记成设备不归它们管。
3. disabled 的节点留在树上,of_device_is_available 拦住了登记,驱动永远等不到它。删掉的节点连字节都不在产物里,登记流程根本见不到它。
4. 只有节点自己匹配 matches 参数指向的总线表,内核才继续往它的孩子走,默认的总线表收进了 of_platform_default_populate 的函数体内,收的就是 simple-bus、simple-mfd、isa。少了这一行,它底下挂的一串外设就没人往下登记。
5. `__of_match_node` 把整张表扫完,每条表项经 `__of_device_is_compatible` 打分,最高分胜出,同分时前面的表项留下。命中的得分是 INT_MAX/2 减去序号乘 4,序号是字符串在节点 compatible 列表里的位置,所以列表越靠前的字符串越占便宜。
6. 平时只填 compatible。name 和 type 是给老式节点留的退路,data 留给驱动挂自己的数据,匹配命中了以后,probe 里也就能把它取回来。
7. 会发生。driver_register 会让新驱动把总线上已有的设备再对一遍表,两头不管谁晚到了,配对也耽误不了。

</details>

## 延伸阅读

内核官方文档与本章核对过的源码,给你备好了:

- [Linux and the Devicetree](https://docs.kernel.org/devicetree/usage-model.html):内核消费设备树的官方用法说明,of_platform_populate 的定位在“Device Population”一节。
- 源码核对清单,全部拉自 <https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/> 加路径再加 ?h=v7.2.9:drivers/of/platform.c、include/linux/of_platform.h、arch/arm/mach-imx/mach-imx6q.c。
- [The Linux Kernel Device Model](https://docs.kernel.org/driver-api/driver-model/overview.html):总线、设备、驱动三者关系的官方总览,kobject 与 sysfs 的图景也在这里,本章刻意没铺开的部分归它讲。
- 源码核对清单,全部拉自 <https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/> 加路径再加 ?h=v7.2.9:drivers/of/base.c、drivers/of/device.c、drivers/base/platform.c、drivers/base/dd.c、include/linux/of_device.h、include/linux/device-id/of.h。
