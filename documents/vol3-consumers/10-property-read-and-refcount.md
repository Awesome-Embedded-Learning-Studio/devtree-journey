---
title: "属性从哪里读,节点指针又归谁管?"
volume: 3
chapter: 12
section: 1
order: 10
description: "probe 拿到 of_node 指针之后,读属性的活儿从 of_property_read_u32 用起,返回码的约定认清楚,device_property_ 一层与 fwnode 的抽象也认个门道,读属性的调用拼进 acme 串口的 probe 里看个样子,再顺着 of_node 指针问到底:整棵 device_node 树全系统只有一份,of_node_get 与 of_node_put 靠节点内嵌的 kobject 计数,CONFIG_OF_DYNAMIC 没开时是哑实现,__free(device_node) 与 sysfs 镜像替咱们把配平的活儿包了大半"
status: draft
---

# 属性从哪里读,节点指针又归谁管?

“节点怎样变成设备、匹配到驱动”那章的收尾处,总线把设备交给了驱动的 probe,probe 拿到了开工的家当,手里攥着的就只有 `pdev->dev.of_node` 指针。寄存器的地址、中断的规格、时钟的频率,驱动要的东西全都挂在那个指针指着的节点上。咱们这一章把读取的活儿一样样办齐:读属性的函数怎么用,节点的引用谁在计数,`reg` 怎样翻译成内核通用的 struct resource,`ranges` 的映射在哪层发生,中断的规格怎样变成虚拟中断号。全卷锁定的版本是 U-Boot v2026.10 与 Linux v7.2.9,本章咱们只读 Linux 侧,引到的源码都从 kernel.org 的 v7.2.9 拉下来逐行核对过,引文里带的都是文件路径。

这一章咱们拆成三篇来读。本篇把读属性的函数认齐,节点的计数也问到底,地址的翻译与中断的解析归一篇,QEMU 里的对证与运行时树的观察收在末篇,咱们边走边交接。

## 读属性,咱们从 of_property_read_u32 用起

驱动最常干的事,咱们从读一个整数说起。“怎样描述和组织设备”那章咱们练过的 `clock-frequency = <115200>`,驱动侧取它靠的就是 `of_property_read_u32`。它的定义在 `include/linux/of.h` 的末尾,本身就是个薄薄的转发:

```c
static inline int of_property_read_u32(const struct device_node *np,
				       const char *propname,
				       u32 *out_value)
{
	return of_property_read_u32_array(np, propname, out_value, 1);
}
```

一个元素的读取转发给了数组的读取,数组的读取再往下进 `of_property_read_variable_u32_array`,真正翻属性的活在那里面。咱们写驱动的时候不必背下调用链,要记的是返回码的约定,头文件的注释交代得明明白白:

```c
 * Return: 0 on success, -EINVAL if the property does not exist,
 * -ENODATA if property does not have a value, and -EOVERFLOW if the
 * property data isn't large enough.
 *
 * The out_values is modified only if a valid u32 value can be decoded.
```

返回 0 是读到手了,`-EINVAL` 说的是属性压根不在,`-ENODATA` 与 `-EOVERFLOW` 说的是值缺了或者长度不够,而且出值指针只在成功时被改写。所以驱动里常见的写法是拿返回码当条件,读不着的属性按各自板子的实际意思决定用默认值还是报错退出。同族里咱们再认两个就够用:64 位的 `of_property_read_u64`,读字符串的 `of_property_read_string`,后者的声明与实体分别住在 `include/linux/of.h` 和 `drivers/of/property.c`。要读一串同类型的数,咱们还有按个数收的 `of_property_read_u32_array`。

另一层 API 咱们也要认得,免得读别人的驱动犯迷糊。`include/linux/property.h` 里住的是 `device_property_read_u32`:

```c
static inline int device_property_read_u32(const struct device *dev,
					   const char *propname, u32 *val)
{
	return device_property_read_u32_array(dev, propname, val, 1);
}
```

这一层不问固件的出身,设备树来的设备与 ACPI 来的设备走同一个入口,底下靠 fwnode 的抽象转发。device_node 结构体的定义咱们在 `include/linux/of.h` 里核对过,开头几行是这样的:

```c
struct device_node {
	const char *name;
	phandle phandle;
	const char *full_name;
	struct fwnode_handle fwnode;

	struct	property *properties;
	...
	struct	device_node *parent;
	struct	device_node *child;
	struct	device_node *sibling;
```

内嵌的 `fwnode` 成员就是那层抽象的接头,设备树这边的实现挂在它身上。咱们挑函数的原则也简单:只服务设备树的板子,用 `of_` 开头的函数最直接,想同时兼容两种固件来源的驱动,就换 `device_property_` 开头的写法,两层的返回码约定是一致的。

咱们把读属性的 API 拼进一个 probe 里看看样子。上一章的 acme 串口节点咱们添一行 `clock-frequency`,probe 里咱们多读几样东西:

```dts
		serial@10004000 {
			compatible = "acme,uart";
			reg = <0x10004000 0x100>;
			clock-frequency = <115200>;
			status = "okay";
		};
```

```c
static int acme_res_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	u32 clock_frequency = 0;
	const char *first_compat = NULL;
	struct resource *mem;
	int irq;

	of_property_read_u32(dev->of_node, "clock-frequency", &clock_frequency);
	of_property_read_string(dev->of_node, "compatible", &first_compat);

	mem = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	irq = platform_get_irq_optional(pdev, 0);

	dev_info(dev, "probe: node %pOF\n", dev->of_node);
	dev_info(dev, "compatible \"%s\", clock-frequency %u Hz\n",
		 first_compat ? first_compat : "(missing)", clock_frequency);
	if (mem)
		dev_info(dev, "mem resource %pR\n", mem);
	if (irq > 0)
		dev_info(dev, "irq %d\n", irq);
	else
		dev_info(dev, "no irq, reason code %d\n", irq);

	return 0;
}
```

后面两行取资源和取中断的调用,咱们在下一篇里分别把它们追到底。整段代码咱们在本机真编过,编译的记录与环境的实话都收在实验那篇里。

属性读到手了,本篇咱们靠的都是函数与返回码的约定,probe 的示意代码里也见过了读取的样子。不过这些 API 个个都拿 device_node 指针当参数,指针指着的节点归谁管、用完了谁来收,咱们就把这件事问到底。

## 树是共享的,节点的引用得有人计数

读属性的 API 都拿 device_node 指针当参数,咱们顺势问一句:这样的指针,指着的东西归谁管?答案得从树的一生说起。启动时 `unflatten_device_tree` 把 DTB 摊开成一棵 device_node 的树,`drivers/of/fdt.c` 里它的注释把活儿概括成一句:“把设备树摊开,造出 struct device_node 组成的树”。整台系统里的这棵树只有一份,根上挂着的是 `of_root`,驱动的 probe、内核的各路查找、用户空间的镜像,大家拿到的都是同一批节点的指针。谁用了谁登记,用完了注销,咱们说的引用计数就是这套登记。

计数的实体咱们在 v7.2.9 里核对过,它挂在节点内嵌的 kobject 上。`drivers/of/dynamic.c` 里的两个函数一眼见底:

```c
struct device_node *of_node_get(struct device_node *node)
{
	if (node)
		kobject_get(&node->kobj);
	return node;
}
EXPORT_SYMBOL(of_node_get);

void of_node_put(struct device_node *node)
{
	if (node)
		kobject_put(&node->kobj);
}
```

咱们看 get 的调用把计数加一,put 的调用把计数减一,减到了零就由 `of_node_release` 收尾。头文件给 `of_node_init` 写的注释把规则说全了:

```c
 * On return the device_node refcount is set to one.  Use of_node_put()
 * on @node when done to free the memory allocated for it.  If the node
 * is NOT a dynamic node the memory will not be freed. The decision of
 * whether to free the memory will be done by node->release(), which is
 * of_node_release().
 */
```

节点造出来时的计数是一,用完了咱们就 put 掉。静态树上的节点其实不会被释放,会被释放的是运行时动态添进来的节点,比如 overlay 加载的那些。咱们再看一个容易误会的分支:没开 `CONFIG_OF_DYNAMIC` 的内核里,get 与 put 都成了空操作,`include/linux/of.h` 里给出的就是下面这几行:

```c
/* Dummy ref counting routines - to be implemented later */
static inline struct device_node *of_node_get(struct device_node *node)
{
	return node;
}
static inline void of_node_put(struct device_node *node) { }
```

所以咱们在驱动里写 get 与 put 不亏,配置开了它们就是真的计数,没开的配置下也不碍事,规范的写法在两边都成立。

要咱们手工配平的场合其实不多,内核替咱们把常见的活儿包了。上一章咱们用过的 `for_each_child_of_node_scoped`,循环一退出它就自动 put 了。下一篇要读的 `__of_translate_address`,开头两行就是现成的例子,咱们从 `drivers/of/address.c` 原样抄来:

```c
	struct device_node *dev __free(device_node) = of_node_get(node);
	struct device_node *parent __free(device_node) = get_parent(dev);
```

`__free` 标记的指针出了作用域就自动调 put,函数提前返回了也不漏,咱们连手工的 put 都省了。用户空间的镜像也来凑一份,`drivers/of/kobj.c` 里 `__of_attach_node_sysfs` 的结尾:

```c
	for_each_property_of_node(np, pp)
		__of_add_property_sysfs(np, pp);

	of_node_get(np);
	return 0;
```

镜像把每个节点挂进 sysfs 的时候,镜像自己拿走了一个引用,免得树都散了文件还在。咱们要记的纪律就一条:拿着节点指针跨函数、跨生命周期存的时候,get 与 put 就成对地出现,谁登记的谁注销。

计数的纪律立住了,probe 的示意代码里还剩两行没收尾的活,头一行取的是资源,后一行取的是中断。下一篇咱们就追头一行,看 reg 里的地址怎样一层层换算到 CPU 眼里的物理地址。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. 节点上没有 `clock-frequency` 这个属性,`of_property_read_u32` 返回什么?出值指针会被改写吗?
2. 只服务设备树的板子,与想同时兼容两种固件来源的驱动,各挑哪一层的读属性函数?两层的返回码约定一致吗?
3. 想读一串同类型的整数,同族里哪个函数按个数收?
4. 没开 `CONFIG_OF_DYNAMIC` 的内核里,`of_node_get` 是什么行为?驱动的 get 与 put 为什么照样要写?
5. `__free(device_node)` 标记的指针出了作用域会怎样?比手工配平好在哪里?
6. 镜像把节点挂进 sysfs 的时候,`__of_attach_node_sysfs` 的结尾为什么要 `of_node_get(np)`?

<details>
<summary>参考答案(想好再展开)</summary>

1. 返回 `-EINVAL`。出值指针只在解码成功时被改写,读失败时保持原值,所以常见写法是让变量带上默认值再调它。
2. 只服务设备树的板子,用 `of_` 开头的函数最直接,想同时兼容两种固件来源的驱动,就换 `device_property_` 开头的写法,两层的返回码约定是一致的。
3. `of_property_read_u32_array`,咱们拿它按个数收一串同类型的数。
4. 它是返回原指针的哑实现,计数没有发生。写上 get 与 put 是规范动作,配置开着的内核里它们就是真计数,动态节点也真的靠它决定何时释放。
5. 出了作用域就自动调 put,函数提前返回了也不漏,咱们连手工的 put 都省了。
6. 镜像把每个节点挂进 sysfs 的时候,镜像自己拿走了一个引用,免得树都散了文件还在。

</details>

## 延伸阅读

probe 与驱动模型的官方上下文,给你备好了:

- [Device drivers infrastructure](https://docs.kernel.org/driver-api/infrastructure.html):驱动模型与设备核心的官方总览,`of_node` 一类成员在结构体说明里散见,probe 生命周期的上下文归它讲。
