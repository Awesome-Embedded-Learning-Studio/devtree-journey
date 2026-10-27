---
title: "第二遍读怎样把字节立成树,QEMU 生成的树里都躺着什么?"
volume: 3
chapter: 10
section: 2
order: 7
description: "unflatten_device_tree 在两条架构路径里都排在 paging_init 之后,arm64 多一道 acpi_disabled 的岔口,__unflatten_device_tree 分两遍干活,头一遍只数大小,第二遍从 memblock 领内存立节点,尾部埋 0xdeadbeef 哨兵,device_node 的字段分身份与形状两拨认,再用 QEMU 的 dumpdtb 导出 virt 机自己生成的树,file 报的 size 正好 1MiB,memory 的 reg 折出基址 0x40000000 与 1GiB,chosen 里机型自带的 rng-seed 读过就抹,56 个节点的 virt.dtb 留给下一章当观察对象"
status: draft
---

# 第二遍读怎样把字节立成树,QEMU 生成的树里都躺着什么?

头一遍扫描取走了启动急用的几样,树本身还平平地躺在内存里,`initial_boot_params` 指着的仍是平坦的 DTB。第二遍读的活是把字节立成一棵树,咱们这一篇看它排在什么时机,立起来的节点又长什么模样。

## 第二遍读:unflatten_device_tree 把树立起来

第二遍的时机,两条架构路径咱们分开看。arm64 的 `setup_arch` 后半段:

```c
	paging_init();

	acpi_table_upgrade();

	/* Parse the ACPI tables for possible boot-time configuration */
	acpi_boot_table_init();

	if (acpi_disabled)
		unflatten_device_tree();
```

咱们再抄 arm32 的同一个函数:

```c
	early_ioremap_reset();

	paging_init(mdesc);
	kasan_init();
	request_standard_resources(mdesc);
	...
	unflatten_device_tree();
```

两边都把树立起来排在了 `paging_init` 之后:常规页表铺好了,memblock 分出来的内存有了映射,树这时候才有了住的地方。arm64 多了一个条件,`acpi_disabled` 不成立的时候就整棵跳过,那是 ACPI 与 DT 二选一的世界,咱们只沿着 DT 的路走。而 arm32 那边没有这道岔口,它的调用干脆得很。

干活的函数在 `drivers/of/fdt.c`,咱们看主干:

```c
void __init unflatten_device_tree(void)
{
	void *fdt = initial_boot_params;

	/* Save the statically-placed regions in the reserved_mem array */
	fdt_scan_reserved_mem_late();

	/* Populate an empty root node when bootloader doesn't provide one */
	if (!fdt) {
		...
	}
	__unflatten_device_tree(fdt, NULL, &of_root,
				early_init_dt_alloc_memory_arch, false);

	/* Get pointer to "/chosen" and "/aliases" nodes for use everywhere */
	of_alias_scan(early_init_dt_alloc_memory_arch);
```

咱们再认一认原料与产物:原料还是 `initial_boot_params` 指着的平坦 DTB,产物则交给了全局的 `of_root`。开头的 `fdt_scan_reserved_mem_late` 把静态安置的保留区记进 reserved_mem 数组,注释交代它是早前扫描的收尾。中间的 if 留的是退路:遇上引导程序不交树的情况,内核就拿一份内建的空根补位,咱们照样能等到一棵树立起来。ACPI 的岔口咱们在 arm64 的调用方那里见过了,函数自己就不再查这道判断了。真下手的是 `__unflatten_device_tree`,它一共分了两遍,代码里的注释写得明明白白:

```c
	/* First pass, scan for size */
	size = unflatten_dt_nodes(blob, NULL, dad, NULL);
	if (size <= 0)
		return NULL;

	size = ALIGN(size, 4);
	...
	/* Allocate memory for the expanded device tree */
	mem = dt_alloc(size + 4, __alignof__(struct device_node));
	...
	*(__be32 *)(mem + size) = cpu_to_be32(0xdeadbeef);
	...
	/* Second pass, do actual unflattening */
	ret = unflatten_dt_nodes(blob, mem, dad, mynodes);
```

头一遍干的是只数大小,字节是一个都不写的,咱们接着往下看:到了第二遍开始前,它从 memblock 领了一整块内存,尾部还埋了个 `0xdeadbeef` 当哨兵,第二遍写完了回头查哨兵还在不在,越界了会告警。两遍的划分与 dtc 编译时的两遍有几分神似,只是方向反了过来:dtc 把树摊平成了字节,内核把字节立成了树。

那每个节点是怎么立起来的呢?咱们看 `populate_node` 的核心几行:

```c
	np = unflatten_dt_alloc(mem, sizeof(struct device_node) + len,
				__alignof__(struct device_node));
	if (!dryrun) {
		char *fn;
		of_node_init(np);
		np->full_name = fn = ((char *)np) + sizeof(*np);

		memcpy(fn, pathp, len);

		if (dad != NULL) {
			np->parent = dad;
			np->sibling = dad->child;
			dad->child = np;
		}
	}

	populate_properties(blob, offset, mem, np, pathp, dryrun);
	if (!dryrun) {
		np->name = of_get_property(np, "name", NULL);
		if (!np->name)
			np->name = "<NULL>";
	}
```

咱们看它立节点的手法:每个节点都分到了一块内存,`full_name` 就搭在了结构体后面,父指针、孩子链、兄弟链三下全接好了,属性由 `populate_properties` 挂了上去。挂孩子用的是头插,遍历完次序是倒的,收尾的 `reverse_nodes` 再把孩子们的次序翻回文档顺序。现代 DTB 里 name 属性省了,`populate_properties` 就从单元名里现补了一条,补的就是 @ 前面的段,`serial@1000` 的 name 就是 serial。phandle 也在同一次遍历里进了它的 `np->phandle`。

## 立起来之后,内核眼里的节点长什么样

结构体的正本在 `include/linux/of.h`,咱们整段抄来:

```c
struct device_node {
	const char *name;
	phandle phandle;
	const char *full_name;
	struct fwnode_handle fwnode;

	struct	property *properties;
	struct	property *deadprops;	/* removed properties */
	struct	device_node *parent;
	struct	device_node *child;
	struct	device_node *sibling;
#if defined(CONFIG_OF_KOBJ)
	struct	kobject kobj;
#endif
	unsigned long _flags;
	void	*data;
#if defined(CONFIG_SPARC)
	unsigned int unique_id;
	struct of_irq_controller *irq_trans;
#endif
};
```

属性的单子也在同一个文件里,条件编译的字段咱们略去:

```c
struct property {
	char	*name;
	int	length;
	void	*value;
	struct property *next;
	...
};
```

咱们把字段分两拨看。管身份的有三样,`name` 指着单元名里 @ 前面的段,`full_name` 带上了地址,`phandle` 是别的节点引用它时用的编号。管形状的也有三样,`parent`、`child`、`sibling` 三根指针把节点织回一棵真正的树,`properties` 挂的是属性的单链表,`deadprops` 收着被删掉的旧属性。剩下的几个字段里,`fwnode` 是接进通用设备模型的接口,`kobj` 是 sysfs 那边的挂钩,`data` 留给各子系统放自己的东西。

平坦与立起来的差别,到这儿你能说清楚了:DTB 的属性挤在一整块字节里,父子关系靠的是结构块的嵌套,查找靠的是游走。device_node 里属性成了链表上的成员,父子关系成了真实指针,查找靠的则是指针行走。咱们的 edtc reader 在第二卷读的是前一种,内核的设备模型要的是后一种。

device_node 的模样你到这儿认全了,咱们看的却全是源码里的树。咱们换个手法,把 QEMU 生成的 virt.dtb 导出来,亲手看一眼内核读到的树。

## 亲手导一棵:QEMU 生成的树,内核读到就是它

内核侧的观察,没有开发板咱们也能做:QEMU 的 virt 机型每次开机都自己生成一棵设备树,交给内核的正是它。dumpdtb 是机型的属性,咱们不背参数,它的用法咱们从 `-machine virt,help` 的输出里核对过了,两行咱们抄在下面:

```output
  dtb=<string>           - Linux kernel device tree file
  dumpdtb=<string>       - Dump current dtb to a file and quit
```

那行 quit 的意思是导出即退,所以咱们不用起完整的 guest。命令咱们真跑:

```shell
cd /tmp/vol3ch10
qemu-system-aarch64 -machine virt,dumpdtb=virt.dtb -m 1G -cpu cortex-a57 -display none
```

命令安静地退出了,目录里多出了 virt.dtb。本机的 QEMU 是 11.1.2,dtc 用的还是 v1.8.1,实验的日子是 2026-10-18。咱们拿 file 看一眼:

```shell
file virt.dtb
```

```output
virt.dtb: Device Tree Blob version 17, size=1048576, boot CPU=0, string block size=569, DT structure block size=7160
```

header 报的 size 正好 1MiB,可结构块只占了 7160 字节,字符串块的份额是 569 字节,剩下的地盘是空位,第二卷讲产物布局时你见过这道排版。反编译咱们只挑要看的地方:

```shell
dtc -I dtb -O dts virt.dtb > virt.dts
```

咱们看根节点的开头几行:

```dts
/ {
	interrupt-parent = <0x8002>;
	dma-coherent;
	model = "linux,dummy-virt";
	#size-cells = <0x02>;
	#address-cells = <0x02>;
	compatible = "linux,dummy-virt";
```

根上的 `#address-cells` 与 `#size-cells` 都是 2,咱们在前文认识的 `early_init_dt_scan_root` 读的就是它们,`dt_root_addr_cells` 与 `dt_root_size_cells` 拿到的值也都是 2。memory 节点的样子是这样:

```dts
	memory@40000000 {
		reg = <0x00 0x40000000 0x00 0x40000000>;
		device_type = "memory";
	};
```

reg 里躺着的是四个 cell,咱们用 python 按两个地址 cell 加两个大小 cell 折一折:

```python
reg = [0x00, 0x40000000, 0x00, 0x40000000]
addr_cells, size_cells = 2, 2

a = 0
for c in reg[:addr_cells]:
    a = (a << 32) | c
s = 0
for c in reg[addr_cells:addr_cells + size_cells]:
    s = (s << 32) | c
print(f"基址 0x{a:x},大小 0x{s:x} 字节,合 {s >> 30} GiB")
```

```output
基址 0x40000000,大小 0x40000000 字节,合 1 GiB
```

折出来的基址是 0x40000000,折出的大小是 1GiB,咱们命令行里 `-m 1G` 给的内存被 QEMU 写成了一条 reg。`early_init_dt_scan_memory` 认的就是这一行,`memblock_add` 收到的 base 与 size 也正是它。咱们再看 chosen:

```dts
	chosen {
		stdout-path = "/pl011@9000000";
		rng-seed = <0x38ce59d4 0x50df1b8d 0xf0685eb1 0x8260eafb 0xa8204915 0xbab95b10 0x59a0f929 0x30a1d0db>;
		kaslr-seed = <0x6d576ce5 0x67984099>;
	};
```

咱们没给内核,咱们也没传 -append,chosen 里就没了 bootargs,early scan 拿到的命令行是空的。rng-seed 与 kaslr-seed 是机型自带的,它的下场你在源码里见过了,读到之后就被 `fdt_nop_property` 当场抹掉了。stdout-path 指着的 pl011 节点就挂在这棵树上,compatible 写的是 `arm,pl011`。整棵树的规模,咱们也用 python 数了数:

```python
import re
text = open('virt.dts').read()
nodes = re.findall(r'^\t*[a-zA-Z0-9,._+-]+(@[0-9A-Fa-f]+)? \{$', text, re.M)
print("节点总数:", len(nodes))
print("带单元地址的:", sum(1 for n in nodes if n))
```

```output
节点总数: 56
带单元地址的: 43
```

virt.dtb 咱们留在 /tmp/vol3ch10 里别删,“节点怎样变成设备、匹配到驱动?”的那章正要拿它当观察对象:树上的 pl011 和别的节点谁会被登记成设备,谁像 chosen 与 memory 一样只当启动阶段的信使,到那边咱们接着追。unflatten 立起来的 device_node,正是驱动匹配要用的原料。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. unflatten_device_tree 在 ARM64 与 ARM32 的 setup_arch 里各排在什么之后?arm64 的附加条件是哪个变量?
2. `__unflatten_device_tree` 的两遍各干什么活?尾部埋的哨兵值是哪个,查它为了什么?
3. struct device_node 里哪些字段管属性,哪些字段管树的形状?name 属性缺失的时候,unflatten 怎么把它补出来?
4. 挂孩子用的头插带来什么后果?收尾由谁把次序翻了回来?
5. dumpdtb 的用法咱们是从哪里核对的?导出的时候为什么不用起完整的 guest?
6. file 给 virt.dtb 报了多大的 size?结构块与字符串块各占多少,剩下的地盘是什么?
7. memory 节点的 reg 折出来的是什么?咱们命令行里的哪个参数变成了它?
8. chosen 里为什么没有 bootargs?rng-seed 与 kaslr-seed 是谁给的,rng-seed 的下场是什么?
9. 整棵树咱们数出了多少个节点?virt.dtb 为什么留在 /tmp/vol3ch10 里别删?

<details>
<summary>参考答案(想好再展开)</summary>

1. 都排在 `paging_init` 之后。arm64 的条件是 `acpi_disabled` 为真,ACPI 启用的时候整棵树跳过。arm32 无条件调用。
2. 头一遍只数大小,字节是一个都不写的。第二遍开始前,它从 memblock 领了一整块内存,尾部埋了 `0xdeadbeef` 当哨兵,第二遍写完了回头查哨兵还在不在,越界了会告警。
3. `properties` 与 `deadprops` 管属性,`parent`、`child`、`sibling` 管形状。name 缺失时 `populate_properties` 从单元名里截出 @ 之前的段,现补一条 name 属性,所以 `serial@1000` 的 name 是 serial。
4. 头插让遍历完的次序是倒的,收尾的 `reverse_nodes` 把孩子们的次序翻回文档顺序。
5. 从 `-machine virt,help` 的输出里核对过,两行输出咱们抄在了正文里。输出里那行 quit 的意思是导出即退,所以咱们不用起完整的 guest。
6. header 报的 size 正好 1MiB。结构块只占了 7160 字节,字符串块的份额是 569 字节,剩下的地盘是空位。
7. 折出来的基址是 0x40000000,折出的大小是 1GiB。命令行里 `-m 1G` 给的内存被 QEMU 写成了一条 reg。
8. 咱们没给内核,咱们也没传 -append,chosen 里就没了 bootargs。rng-seed 与 kaslr-seed 是机型自带的,rng-seed 读到之后就被 `fdt_nop_property` 当场抹掉了。
9. 节点总数是 56,带单元地址的是 43。“节点怎样变成设备、匹配到驱动?”那章正要拿它当观察对象。

</details>

## 延伸阅读

第二遍读与 `device_node` 的正本、of_ 打头的 API 手册,入口都给你备好了:

- [Linux v7.2.9 的 drivers/of/fdt.c](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/of/fdt.c?h=v7.2.9):unflatten 的正本,第二遍读的引文都出自这里。
- [Linux: DeviceTree Kernel API](https://docs.kernel.org/devicetree/kernel-api.html):内核侧操作设备树的 API 手册,of_ 打头的查找与读取函数在这儿有正式说明。
