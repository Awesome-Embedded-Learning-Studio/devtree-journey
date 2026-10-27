---
title: "电脑上缝树怎么用怎么验,标签对不上报什么错?"
volume: 5
chapter: 17
section: 2
order: 172
description: "fdtoverlay 吃一份基础 DTB 加按顺序排列的 overlay 产物:单叠传感器,diff 报出 15a16,21,链式两份按顺序叠,__symbols__ 从两行长到三行,sensor0 在应用现场还清,叠完反编译核对的适用场景也点清。歪路的真实输出收了两条:引用基础从没定义过的 spi0,fdtoverlay 报 FDT_ERR_NOTFOUND,基础忘了带 -@ 再叠,报 FDT_ERR_BADOFFSET 加一句把病因和药方都说明白的提示,排查清单的头两行就从这两份输出来"
status: draft
---

# 电脑上缝树怎么验,标签对不上又报什么错?

上一篇把欠条记进了 `__fixups__`,还清欠条的活儿归应用器。这一篇咱们请电脑上的应用器出场,缝完了拿 diff 验一遍。

## 电脑上缝:fdtoverlay 真跑一遍

电脑上的应用器就是 fdtoverlay,它吃的输入是一份基础 DTB,外加按顺序排列的若干份 overlay 产物,缝好的树写进输出文件。咱们单叠传感器 overlay:

```shell
fdtoverlay -i base.dtb -o merged.dtb sensor-overlay.dtbo && echo OK
```

```output
OK
```

成功的时候它一声不吭,咱们补了个 `echo` 把成功换成了看得见的 OK。咱们用第一卷练下的老手艺验缝合的质量:在应用的前后各反编译一次,diff 替咱们找不同:

```shell
dtc -I dtb -O dts base.dtb > before.dts
dtc -I dtb -O dts merged.dtb > after.dts
diff before.dts after.dts
```

```output
15a16,21
>
> 		sensor@48 {
> 			status = "okay";
> 			reg = <0x48>;
> 			compatible = "acme,temp-sensor";
> 		};
```

diff 报的 15a16,21 说的是 after.dts 在 before.dts 的第 15 行之后多出了六行,位置恰好是 i2c0 的花括号合上之前。`sensor@48` 整个节点住进了 i2c0 名下,基础原有的节点一个没动,fragment 的包装也一点残渣都没留。你要核对得更细,还可以看 after.dts 里的 `__symbols__`,它的内容一个字没动,因为 sensor-overlay 里没有自己的标签,它也没改基础的标签。

链式的欠条咱们一并试。咱们用一条命令按顺序叠两份:

```shell
fdtoverlay -i base.dtb -o chained.dtb sensor-labeled-overlay.dtbo chain-overlay.dtbo && echo OK
```

```output
OK
```

咱们看缝合的结果,节选的是 sensor@48 与 `__symbols__` 的两段:

```shell
dtc -I dtb -O dts chained.dtb
```

```dts
		sensor0: sensor@48 {
			poll-interval = <0x64>;
			phandle = <0x03>;
			status = "okay";
			reg = <0x48>;
			compatible = "acme,temp-sensor";
		};
	};

	__symbols__ {
		sensor0 = "/i2c@800/sensor@48";
		i2c0 = "/i2c@800";
		uart0 = "/serial@1000";
	};
```

该发生的都发生了:头一份 overlay 把 sensor0 这个标签随节点一起交了进去,应用器把它并进了 `__symbols__`,基础的对照表从两行长到了三行。第二份 overlay 欠的 sensor0,应用器在新表里查到了 `/i2c@800/sensor@48`,它对应的 phandle 编号是 3,回填之后 `poll-interval = <0x64>` 就落在了传感器名下。引用横跨了两份文件,答案却在应用现场对上了,你若是回头想“为什么符号表要存在”,上面的输出就是回答。

电脑上叠树的适用场景也就清楚了:发布产物之前拼装,产线上按订单把配件的 overlay 叠进基础,叠完了还能反编译回来核对,跟咱们上面做的一样,第一卷的核对手艺零成本复用。凡是叠完就定型的活儿,都适合在咱们电脑上做完。

电脑上的路走到这儿全是顺的,不过缝合未必回回顺利,标签对不上的时候应用器会说什么?咱们接着往下看。

## 报错什么样:标签在基础里找不到

顺利的路走完了,咱们再故意走两条歪路,把真实的报错拿来读。头一条:overlay 引用了基础里不存在的标签。咱们写一份 spi-overlay.dtso,引用基础从没定义过的 spi0:

```dts
/dts-v1/;
/plugin/;

&spi0 {
	flash@0 {
		compatible = "acme,spi-flash";
		reg = <0>;
		status = "okay";
	};
};
```

编译照旧通过了,咱们没见到任何报错,插件模式本来就是允许欠引用的。报错出现在应用的时候:

```shell
fdtoverlay -i base.dtb -o bad-merged.dtb spi-overlay.dtbo
echo $?
```

```output
Failed to apply 'spi-overlay.dtbo': FDT_ERR_NOTFOUND
1
```

FDT_ERR_NOTFOUND 是 libfdt 的说法,意思是应用器拿着 spi0 去查基础的 `__symbols__`,基础的表里查不到这个名字。定位的思路也就顺了:报错说的是应用那一刻的查找失败,咱们要查的地方按顺序是 overlay 的 `__fixups__` 里欠了谁、基础的 `__symbols__` 里有没有谁,两边的名字要是没对上,病根也就找到了。

第二条歪路更常见:标签的拼写没问题,基础却忘了带 `-@` 编译。咱们把同一份基础不带 `-@` 又编了一份,又把同一份 overlay 叠了上去:

```shell
dtc -I dts -O dtb -o base-noat.dtb base.dts
fdtoverlay -i base-noat.dtb -o noat-merged.dtb sensor-overlay.dtbo
echo $?
```

```output
Failed to apply 'sensor-overlay.dtbo': FDT_ERR_BADOFFSET
base blob does not have a '/__symbols__' node, make sure you have compiled the base blob with '-@' option
```

输出的原文连提示带劝告一共两行(前面还带着一个空行),退出码报了 1。第二行把病因和药方都说明白了:基础产物里没有 `/__symbols__` 节点,请确认基础是带着 `-@` 编的。咱们手里的 sensor-overlay 没有任何毛病,病根全在基础的产物里。往后你在板子上叠 overlay 碰了壁,咱们排查清单的头两行就是它们:基础带没带符号表,overlay 欠的标签表里有没有。

电脑上的实验到这儿收尾,叠树的位置还剩下板子上的两处,咱们下一篇按官方文档的口径走。

## 本节自检

文章读完了,你拿四个小问题验一验自己,想好了再展开参考答案。

1. 链式的两份 overlay 按顺序叠进基础,`__symbols__` 发生了什么变化?chain-overlay 欠的 sensor0 是怎么还上的?
2. diff 报的 15a16,21 说的是什么?fragment 的包装留下了残渣吗?
3. 基础忘了带 `-@` 编译,`fdtoverlay` 报了什么?输出的哪一句把病因和药方都说清了?
4. FDT_ERR_NOTFOUND 说的是哪一刻的失败?顺着报错,咱们按什么顺序查?

<details>
<summary>参考答案(想好再展开)</summary>

1. 头一份 overlay 把 sensor0 这个标签随节点一起交了进去,应用器把它并进了 `__symbols__`,基础的对照表从两行长到了三行。第二份 overlay 欠的 sensor0,应用器在新表里查到了 `/i2c@800/sensor@48`,它对应的 phandle 编号是 3,回填之后 `poll-interval = <0x64>` 就落在了传感器名下。
2. after.dts 在 before.dts 的第 15 行之后多出了六行,位置恰好是 i2c0 的花括号合上之前,`sensor@48` 整个节点住进了 i2c0 名下,基础原有的节点一个没动,fragment 的包装也一点残渣都没留。
3. 报了 FDT_ERR_BADOFFSET,外加一句“基础产物里没有 /__symbols__ 节点,请确认基础带 -@ 编译”。病因是基础缺符号表,药方就是带 `-@` 重编基础,overlay 本身没毛病。
4. 报错说的是应用那一刻的查找失败,应用器拿着 spi0 去查基础的 `__symbols__`,基础的表里查不到这个名字。咱们按顺序查 overlay 的 `__fixups__` 里欠了谁、基础的 `__symbols__` 里有没有谁,两边的名字要是没对上,病根也就找到了。

</details>
