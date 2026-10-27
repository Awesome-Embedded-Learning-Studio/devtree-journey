---
title: "自己写个最小驱动能编过吗,别的总线又怎么走?"
volume: 3
chapter: 11
section: 2
order: 9
description: "dts 里备一个 acme,uart 的节点,驱动只填一条 of_match_table 表项,probe 里用 of_match_device 与 of_property_read_string 亲眼验货,再在 WSL2 的 6.18 内核树上把 acme_uart_min.ko 真的编出来,挨过的报错、modinfo 报出的别名与两句实话原样交代,末篇看 I2C 与 SPI 的登记:控制器自己是 platform 设备,孩子却由 of_i2c_register_devices 与 of_register_spi_devices 各自登记成 i2c_client 与 spi_device,匹配用的仍是同一套 of_match_table"
status: draft
---

# 自己写个最小驱动能编过吗,别的总线又怎么走?

上一篇的收尾处,配对的规则与 probe 的汇合点咱们都读过了。源码咱们读了很多,可真的配对一次都没亲眼见过,咱们本篇来补上:写一个最小的 platform 驱动,再在本机把它真的编出来。

## 写一个最小驱动,把链路亲手走一遍

光看别人走路是不够的,咱们自己也要踩一遍。咱们给驱动备一个节点,dts 的写法全是老朋友:

```dts
/ {
	soc {
		compatible = "simple-bus";
		#address-cells = <1>;
		#size-cells = <1>;

		serial@10004000 {
			compatible = "acme,uart";
			reg = <0x10004000 0x100>;
			status = "okay";
		};
	};
};
```

咱们把 soc 节点挂上 simple-bus 的身份,串口节点写好了 compatible 与 reg,登记的条件也就齐了。接下来登场的是驱动本体,完整的源文件如下:

```c
// SPDX-License-Identifier: GPL-2.0
/*
 * acme_uart_min.c - 观察设备树匹配的最小 platform 驱动
 *
 * 不碰任何硬件寄存器,只把 probe 与 remove 收到的东西打印出来,
 * 用来观察一个设备树节点怎样被 platform 总线认领。
 */

#include <linux/module.h>
#include <linux/mod_devicetable.h>
#include <linux/of.h>
#include <linux/of_device.h>
#include <linux/platform_device.h>

static int acme_uart_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	const struct of_device_id *match;
	const char *first_compat = NULL;

	match = of_match_device(dev->driver->of_match_table, dev);
	if (match)
		dev_info(dev, "matched of_device_id, compatible \"%s\"\n",
			 match->compatible);

	of_property_read_string(dev->of_node, "compatible", &first_compat);
	dev_info(dev, "probe: node %pOF, first compatible \"%s\"\n",
		 dev->of_node, first_compat);

	return 0;
}

static void acme_uart_remove(struct platform_device *pdev)
{
	dev_info(&pdev->dev, "remove: node %pOF\n", pdev->dev.of_node);
}

static const struct of_device_id acme_uart_of_match[] = {
	{ .compatible = "acme,uart" },
	{ /* 结尾留空,匹配表到此为止 */ }
};
MODULE_DEVICE_TABLE(of, acme_uart_of_match);

static struct platform_driver acme_uart_driver = {
	.probe  = acme_uart_probe,
	.remove = acme_uart_remove,
	.driver = {
		.name = "acme-uart",
		.of_match_table = acme_uart_of_match,
	},
};
module_platform_driver(acme_uart_driver);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("minimal platform driver to observe devicetree matching");
```

咱们一段段看。`of_match_table` 里只放了一条 `acme,uart`,与 dts 里串口节点的写法一字不差。匹配表末尾的空表项是终止符,内核扫表的时候靠它知道何时停。`MODULE_DEVICE_TABLE` 会把表里的 compatible 编进模块的别名,设备注册时内核发的 uevent 带着同样的字符串,udev 也就据此自动装载了模块,机器冷插拔的接续咱们不在本章展开。

probe 收到的参数是一个 platform_device 指针,它的 dev.of_node 成员指着节点的 device_node。咱们在“Linux 何时读取 DTB”那章里追过它的出生,登记设备的时候,`device_set_node` 把它挂到了设备的 of_node 成员上。probe 的头一件事咱们选了 `of_match_device`。总线配对的时候内核已经扫过一遍表,咱们在这里自己再问一次,就能拿到命中的表项,表项 data 里挂的自用数据也就到手了。接着咱们用 `of_property_read_string` 从节点里读出 compatible 的头一个字符串。成套的读属性 API 留给下一章,咱们在这里只借一个函数用一用,亲眼看一看节点的属性确实住在 of_node 里。

remove 是设备卸载或驱动退出时被调用的回调,咱们让它打印一句,方便咱们对照生命周期。`module_platform_driver` 宏把注册与注销都包进了 `module_init` 和 `module_exit`,咱们连手写的功夫都省了。

### 在本机把它真的编出来

板子咱们暂时不上,编译本身在本机是能做的。咱们跑代码的机器是 WSL2 的 x86 内核:

```shell
uname -r
```

```output
6.18.33.2-microsoft-standard-WSL2
```

编外部模块的惯例是用 `/lib/modules/$(uname -r)/build`,可微软的 WSL 内核没有随发行版发布头文件包,那个 build 目录在咱们机器上并不存在。咱们就把对应版本的内核源码克隆下来自己准备,咱们用的仓库是 `microsoft/WSL2-Linux-Kernel`,克隆的标签与运行版本一字不差,配置直接取自运行中的内核。

```shell
git clone --depth 1 --branch linux-msft-wsl-6.18.33.2 \
	https://github.com/microsoft/WSL2-Linux-Kernel.git wsl-kernel
cd wsl-kernel
zcat /proc/config.gz > .config
make olddefconfig
make -j16 LOCALVERSION= modules_prepare
```

咱们给模块这边准备的 Makefile 是外部模块的标准两行:

```make
obj-m += acme_uart_min.o

KDIR ?= /tmp/vol3ch11/wsl-kernel

all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) modules
```

咱们头一回编的时候挨了报错,编译器说咱们少包含了头文件。报错的原文是:

```output
acme_uart_min.c:20:17: error: implicit declaration of function 'of_match_device'
   20 |         match = of_match_device(dev->driver->of_match_table, dev);
      |                 ^~~~~~~~~~~~~~~
```

咱们少写的那一行就是 `#include <linux/of_device.h>`,of_match_device 的声明就住在里面,补上之后就好了。咱们改完再编,一次就编过了:

```shell
make
```

```output
make -C /tmp/vol3ch11/wsl-kernel M=/tmp/vol3ch11/acme-uart LOCALVERSION= modules
make[1]: Entering directory '/tmp/vol3ch11/wsl-kernel'
make[2]: Entering directory '/tmp/vol3ch11/acme-uart'
  CC [M]  acme_uart_min.o
  MODPOST Module.symvers
  CC [M]  acme_uart_min.mod.o
  CC [M]  .module-common.o
  LD [M]  acme_uart_min.ko
make[2]: Leaving directory '/tmp/vol3ch11/acme-uart'
make[1]: Leaving directory '/tmp/vol3ch11/wsl-kernel'
```

咱们用 modinfo 再验一下产物的身份:

```shell
modinfo acme_uart_min.ko | grep -E "^filename|^vermagic|^alias"
```

```output
filename:       /tmp/vol3ch11/acme-uart/acme_uart_min.ko
alias:          of:N*T*Cacme,uartC*
alias:          of:N*T*Cacme,uart
vermagic:       6.18.33.2-microsoft-standard-WSL2 SMP preempt mod_unload modversions
```

咱们看到 vermagic 的开头与 uname -r 一致,两条 alias 都是 `MODULE_DEVICE_TABLE` 生成的 of: 别名,字符串里的 acme,uart 就是咱们写在匹配表里的那一行。咱们也要交代两句实话:机制与源码引文全部按锁定的 v7.2.9 核对,本机编译检查用的是 WSL 的 6.18,接口是一致的,代码原样编过了。加载与真实 probe 的输出要 root 权限,咱们把这一步留给实验环境,咱们不假装跑过。

驱动写好了,模块也在本机真的编了出来,能验的咱们都验了,加载与 probe 的现场留给实验环境。咱们还剩一段链路没看:I2C 与 SPI 的孩子不走 platform 的登记,它们跟着自己的总线另走一条路,咱们接着追。

platform 总线的登记、配对到最小驱动,咱们在前一篇里都追过了源码。总线的位置咱们再来看一眼:platform 其实是个兜底,找不到更专门总线的设备,收留的活才轮到它。I2C 和 SPI 的控制器自己通常就是 platform 设备,登记它们的是上一篇里的递归流程,可它们的孩子走的是另一条路,枚举的方式是跟着总线走的。

## I2C 与 SPI:子设备的枚举跟着总线走

咱们把下一站挪到 I2C,入口在控制器驱动注册 adapter 的时刻。`drivers/i2c/i2c-core-base.c` 里 `i2c_register_adapter` 的尾部有这么一行:

```c
	/* create pre-declared device nodes */
	of_i2c_register_devices(adap);
```

咱们去看干活的函数,`of_i2c_register_devices` 的家在 `drivers/i2c/i2c-core-of.c`,它扫的是 adapter 节点的孩子们:

```c
	for_each_available_child_of_node(bus, node) {
		if (of_node_test_and_set_flag(node, OF_POPULATED))
			continue;

		client = of_i2c_register_device(adap, node);
```

扫孩子用的 `for_each_available_child_of_node` 与 platform 那边一个脾气,status 不可用的孩子它也不理,这一点咱们在 platform 那边见过。每个孩子就这样注册成了 `i2c_client`,地址从哪里来?同一文件里的 `of_i2c_get_board_info` 读的就是孩子的 reg:

```c
	ret = of_property_read_u32(node, "reg", &addr);
```

咱们在“怎样描述和组织设备”那章记过的说法,在这里用上了:reg 的含义随父节点的地址空间变,换到 I2C 的子节点上,报的就是器件的总线地址。

SPI 的剧本几乎一样,咱们直接看代码。`drivers/spi/spi.c` 的 `spi_add_controller` 里:

```c
	/* Register devices from the device tree and ACPI */
	of_register_spi_devices(ctlr);
```

`of_register_spi_devices` 同样扫的是控制器的可用孩子,咱们接着看它扫孩子的样子:

```c
	for_each_available_child_of_node(ctlr->dev.of_node, nc) {
		if (of_node_test_and_set_flag(nc, OF_POPULATED))
			continue;
		spi = of_register_spi_device(ctlr, nc);
```

咱们接着看注册的结果:孩子这回注册成了 `spi_device`,reg 被解读成了片选号,`spi-max-frequency` 被读进了 `max_speed_hz`。OF_POPULATED 的标志两边都在用,同一个节点也就不会被登记两遍了,`i2c_client` 与 `spi_device` 也顶不了 platform 设备的名分。

到了匹配的环节,I2C 与 SPI 跟 platform 用的是同一套思路。`i2c_device_match` 与 `spi_match_device` 的开头咱们都核对过,头一件事同样是 OF 风格的比对,i2c 的入口是 `i2c_of_match_device`,SPI 的入口是 `of_driver_match_device`,两条入口最后都汇进了 `of_match_device`。所以咱们写 I2C 器件驱动时,`of_match_table` 与 compatible 的用法一点没变,要变的只有登记的总线,probe 收到的结构体也换成了 `i2c_client` 或 `spi_device`。咱们再把对照说全:PCI 和 USB 的设备身份由总线自己枚举出来,设备树里连写它们的地方都没有,树里写的就是枚举不出来的那部分硬件。I2C 总线自己问不出器件的地址,地址这才写进了树里。

## 回头看 compatible:从描述的写法到匹配的键

导读卷的“设备树长什么样”那篇讲四方分工的时候,compatible 当的就是最忙的接头。“怎样描述和组织设备”那章咱们把它当标准属性练了写法,表里的话是“报‘我跟哪种操作方式兼容’,驱动拿它对表”。到了本章,那句话落进了源码。节点交出去的是 compatible 属性里的字符串列表,顺序还承载着亲疏的信息。驱动备下的是 of_match_table 里的表项。中间牵线的,是 platform_match 调下来的一串函数。写树的人从此多了一层自觉:binding 定下的字符串一个字符都不能走样,顺序也不是排版的趣味,它们直接决定了设备有没有人认领。

节点成了设备,驱动也认领了它,这一跳就算走完了。咱们的行程还剩最后一程,说的是驱动在 probe 里的活儿。reg 翻出来的 struct resource 怎么取,clocks、interrupts 的引用怎么解,读属性的一整套 OF API 长什么样,下一章的题目就是“驱动怎样读取资源和属性?”,咱们在那里接着走。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. probe 里的 pdev->dev.of_node 指向的对象,最早是哪一章的哪个函数立起来的?
2. modinfo 报出的两条 of: 别名是谁编进模块的?别名里的 acme,uart 对应咱们写在哪里的那一行?
3. 头一回编译挨的报错说的是什么?补上哪一行就好了?
4. I2C 控制器的孩子为什么不是 platform 设备?谁把它们登记成了什么?
5. PCI 和 USB 的设备身份从哪里来?设备树里为什么没有写它们的地方?
6. SPI 控制器的孩子节点上,reg 与 spi-max-frequency 各被读成了什么?

<details>
<summary>参考答案(想好再展开)</summary>

1. “Linux 何时读取 DTB”那章里 unflatten_device_tree 建立的 device_node。登记设备时 of_device_alloc 调 device_set_node 把它挂到了设备的 of_node 上。
2. MODULE_DEVICE_TABLE 把表里的 compatible 编进了模块的别名。acme,uart 对应咱们写在匹配表里的那一条表项,设备注册时内核发的 uevent 带着同样的字符串,udev 也就据此自动装载了模块。
3. 编译器报 implicit declaration of function 'of_match_device'。咱们少写的是 `#include <linux/of_device.h>`,of_match_device 的声明就住在里面,补上之后再编,一次就编过了。
4. I2C 控制器节点匹配 simple-bus 后,它的孩子轮不到 platform 枚举去收。控制器驱动注册 adapter 时,of_i2c_register_devices 扫可用孩子,把每个孩子登记成 i2c_client,总线地址读自孩子的 reg。
5. PCI 和 USB 的设备身份由总线自己枚举出来。树里写的就是枚举不出来的那部分硬件,I2C 总线自己问不出器件的地址,地址这才写进了树里。
6. reg 被解读成了片选号,spi-max-frequency 被读进了 max_speed_hz。OF_POPULATED 的标志两边都在用,同一个节点不会被登记两遍。

</details>

## 延伸阅读

内核官方文档与本章核对过的源码,给你备好了:

- [Platform Devices and Drivers](https://docs.kernel.org/driver-api/driver-model/platform.html):platform 设备与驱动的官方说明,probe 与 remove 的生命周期讲得细。
- 源码核对清单,全部拉自 <https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/> 加路径再加 ?h=v7.2.9:include/linux/mod_devicetable.h、include/linux/device-id/of.h、include/linux/of_device.h、include/linux/platform_device.h。
- 源码核对清单,全部拉自 <https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/> 加路径再加 ?h=v7.2.9:drivers/i2c/i2c-core-base.c、drivers/i2c/i2c-core-of.c、drivers/spi/spi.c。

咱们本章的源码引文全部在 Linux v7.2.9 核对,本机编译验证用的 WSL 内核是 6.18.33.2,验证的日子是 2026-10-18。
