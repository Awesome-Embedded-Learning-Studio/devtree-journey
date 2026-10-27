---
title: "reg 里的数字怎么切?"
volume: 1
chapter: 2
section: 2
order: 22
description: "#address-cells 和 #size-cells 是写在父节点上的声明,孩子的 reg 照着声明切成地址和长度,声明缺了 dtc 按默认的 2 和 1 解读,声明还不隔代传递,结尾把常见的标准属性点一圈"
status: draft
---

# reg 里排着一串数,谁是地址、谁是长度?

上一篇咱们办完了描述的前一半:节点有名有姓,属性的值认全了五种写法。描述的家当还差一件,就是这一路反复在写的 `reg`:那串数里哪几个算地址?哪几个算长度?本篇咱们就办这件事,结尾再把常见的标准属性点一圈。咱们的套路不变:认一种写法就编译一回,再到产物里看它变成了什么。动手的位置照旧,你在自己电脑上建一个工作目录:

```shell
mkdir -p /tmp/dt-ch2
cd /tmp/dt-ch2
```

本仓验证的工具是 dtc v1.8.1,咱们跑命令的日子是 2026-10-18。

## cells 定的是 reg 里数字的切法

cells 这个词咱们在“DTS、DTB、dtc 都是什么”那篇见过一面:它是设备树里数字的计量单位,一个 cell 就是四个字节的大端整数。光有单位其实还不够,`reg` 里排的是一串数,哪几个算地址、哪几个算长度?轮到 `#address-cells` 和 `#size-cells` 出场了。它们是写在父节点上的声明:前一条说的是“孩子写地址用几个 cell”,后一条说的是“孩子写长度用几个 cell”。孩子的 `reg` 就照着声明来切:地址的数在前,长度的数在后。

咱们写一份 cells.dts,一棵树里同时住下了两套切法:

```dts
/dts-v1/;

/ {
	#address-cells = <2>;
	#size-cells = <1>;

	serial@10010000 {
		compatible = "demo,uart";
		reg = <0x0 0x10010000 0x1000>;
	};

	soc {
		#address-cells = <1>;
		#size-cells = <1>;

		timer@3000 {
			compatible = "demo,timer";
			reg = <0x3000 0x40>;
		};
	};
};
```

咱们编译再反编译:

```shell
dtc -I dts -O dtb -o cells.dtb cells.dts
dtc -I dtb -O dts cells.dtb
```

咱们拿到的过程输出干干净净,反编译的树跟源码结构一致,数值也全回来了:

```dts
/dts-v1/;

/ {
	#address-cells = <0x02>;
	#size-cells = <0x01>;

	serial@10010000 {
		compatible = "demo,uart";
		reg = <0x00 0x10010000 0x1000>;
	};

	soc {
		#address-cells = <0x01>;
		#size-cells = <0x01>;

		timer@3000 {
			compatible = "demo,timer";
			reg = <0x3000 0x40>;
		};
	};
};
```

咱们把两套切法的读法各走一遍:根上声明了 2 和 1,`serial` 的 `reg` 就是三个数,头两个数 `0x0` 和 `0x10010000` 拼成一个 64 位的完整地址 0x10010000,最后的 `0x1000` 则是长度,@ 后面写的正是拼出来的那个地址。高位的 cell 填了 0,真实的地址就落在了低 32 位上。`soc` 自己声明了 1 和 1,于是 `timer` 的 `reg` 只有两个数。同一份文件里的两套切法并存不悖,谁的孩子听谁的。

产物里还有个值得咱们留意的地方:反编译回来的树里,`#address-cells = <0x02>` 这样的声明原样待着。咱们在产物里找不到 `reg` 的类型说明,解读的约定本身就是树里的普通属性,想消费 `reg` 的软件,都得回头读一读父节点上的这两行声明。

声明能不能省掉?咱们做一份 defaults.dts,把两行声明从根上删了,里面留一个带 `reg` 的子节点:

```dts
/dts-v1/;

/ {
	uart@1000 {
		compatible = "demo,uart";
		reg = <0x1000 0x100>;
	};
};
```

咱们编译它并拿 grep 滤掉连坐的告警:

```shell
dtc -I dts -O dtb -o defaults.dtb defaults.dts 2>&1 | grep -v "Failed prerequisite"
```

咱们滤掉了连坐的告警,剩下的三行是实打实的提醒:

```output
defaults.dts:6.3-24: Warning (reg_format): /uart@1000:reg: property has invalid length (8 bytes) (#address-cells == 2, #size-cells == 1)
defaults.dts:4.12-7.4: Warning (avoid_default_addr_size): /uart@1000: Relying on default #address-cells value
defaults.dts:4.12-7.4: Warning (avoid_default_addr_size): /uart@1000: Relying on default #size-cells value
```

警告把答案印出来了:声明缺了,dtc 就按默认的 2 和 1 来解读,你的两个 cell 立刻不够数,8 字节的 `reg` 对不上 3 个 cell 的期望长度。规范也是这么定的:声明缺了的时候消费方就按 2 和 1 假定,而有子节点的节点应当把声明写全。咱们不省这几个字节,声明写全了才踏实。

声明还有个不隔代传递的脾气,咱们用一份 inherit.dts 验证。文件里的根上声明了 1 和 1,`soc` 节点什么声明都没写,`timer` 的 `reg` 写两个数:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	soc {
		timer@3000 {
			compatible = "demo,timer";
			reg = <0x3000 0x40>;
		};
	};
};
```

咱们猜想的情形是隔代生效,`timer` 的两个数就该正合适,可实际的警告给出了另一个答案:

```shell
dtc -I dts -O dtb -o inherit.dtb inherit.dts 2>&1 | grep -v "Failed prerequisite"
```

```output
inherit.dts:10.4-24: Warning (reg_format): /soc/timer@3000:reg: property has invalid length (8 bytes) (#address-cells == 2, #size-cells == 1)
inherit.dts:8.14-11.5: Warning (avoid_default_addr_size): /soc/timer@3000: Relying on default #address-cells value
inherit.dts:8.14-11.5: Warning (avoid_default_addr_size): /soc/timer@3000: Relying on default #size-cells value
```

`timer` 的爸爸是 `soc`,这一层的声明是空的,dtc 就按默认的 2 和 1 来查 `timer`,根上声明的 1 和 1 在这里帮不上忙。想让 `soc` 的孩子按 1 和 1 切,咱们就得把声明写到 `soc` 自己身上。

## 常见的标准属性,咱们点一圈

规范把一批常用属性定成了标准属性,咱们把打过照面的和新认识的排成一张表:

| 属性 | 值的写法 | 它管什么 |
| ---- | -------- | -------- |
| compatible | 字符串或字符串列表 | 报“我跟哪种操作方式兼容”,驱动拿它对表 |
| model | 字符串 | 板子的型号名,主要给人看 |
| reg | cells | 设备在父地址空间里的起始地址和长度 |
| status | 字符串 | okay 启用,disabled 禁用,缺省当 okay 处理 |
| phandle | 单个 cell | 节点的编号,引用靠它指过来 |
| ranges | cells 列表 | 子地址怎么映射回父地址,咱们只认个名字 |

“设备树长什么样”那篇里你认识过 compatible,驱动匹配的接头就是它。status 管设备的启用状态,okay 和 disabled 之外还有留给保留设备和故障设备的值。phandle 是这一章的新面孔,咱们到下一篇讲标签的小节里见到它。ranges 负责子地址空间到父地址空间的映射,咱们在这里只认个名字,讲地址映射的时候再跟它细聊。

描述的事到这一篇就办齐了:名字、值的写法、`reg` 的切法,常用属性咱们也点了一圈。可真实板子的描述常常分在好几个文件里,公共的部分谁写、板子自己的东西谁补、不合身的怎么改,这些组织的事,咱们下一篇接着办。

## 本节自检

文章读完了,你拿下面的小问题验一验自己。

1. 根声明 `#address-cells = <2>`、`#size-cells = <1>`,`reg = <0x2 0x3000 0x40>` 的地址是多少?长度是多少?
2. 两行 cells 声明整个缺了的时候,dtc 按几和几解读 `reg`?这个缺省值是谁定的?
3. 根声明了 1 和 1,`soc` 什么都没声明,`soc` 的孩子按几切 `reg`?依据从哪儿来?
4. 想消费 `reg` 的软件,光读 `reg` 本身够不够?还得回头看什么?

<details>
<summary>参考答案(想好再展开)</summary>

1. 地址是 0x200003000,头两个 cell 拼起来算地址。长度是 0x40,只占一个 cell。
2. 按默认的 2 和 1 解读,8 字节的 `reg` 对不上 3 个 cell 的期望长度,警告把这件事印了出来。规范也是这么定的,声明缺了的时候消费方就按 2 和 1 假定。
3. 按默认的 2 和 1 切。声明不隔代传递,爸爸没声明,dtc 就按规范的缺省值解读。
4. 不够。产物里找不到 `reg` 的类型说明,解读的约定本身就是树里的普通属性,消费的软件都得回头读父节点上的 `#address-cells` 和 `#size-cells` 两行声明。

</details>

## 延伸阅读

本篇的条款出处与工具文档,给你备好了:

- [Devicetree Specification 官方页](https://www.devicetree.org/specifications/):标准属性在 §2.3,本仓缓存的是 v0.4 版本。

咱们引用的条款来自规范 v0.4(本仓缓存副本),正文里的命令与输出全部在本机真实运行过,验证环境的版本是 dtc v1.8.1,验证的日子是 2026-10-18。
