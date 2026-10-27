---
title: "坏输入进来,报错怎么指着位置说话?"
volume: 4
chapter: 13
section: 3
order: 133
description: "三份坏输入真跑一遍:少分号的报错落在 reg 冒头的地方,值没收尾的被词法器的栈半路拦下,少了右花括号的只能报停下来的地方,dtc 对同类输入也是一个脾气"
status: draft
---

# 三份坏输入,报错指得准不准?

好输入咱们喂过了,整棵树也都顺利地解了出来。可坏输入进了咱们的解析器,报错能不能把人带到出错的地方,咱们这一篇就拿三份坏文件验一验。

## 三份坏输入,报错得指着位置说话

解析器的成色,坏输入说了算。咱们造三份:头一份少了分号,第二份的值没收住尾,第三份少了右花括号。三份咱们都真跑一遍,报错的原文原样贴出来。

头一份抹掉 `compatible` 后面的分号,咱们存成 nosemi.dts:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	uart@1000 {
		compatible = "acme,uart"
		reg = <0x1000 0x100>;
	};
};
```

```shell
python3 toyparse.py nosemi.dts
```

```output
nosemi.dts: 9:3: 这里该是属性 compatible 写完后的分号,却读到了 'reg'
```

报错的位置落在第 9 行第 3 列,正好是 `reg` 冒头的地方。真正的缺失其实在上一行,解析器能知道的只有自己读到了什么:轮到收分号的节骨眼,眼前来的是 `reg`,于是位置就落在了 `reg` 的头上。有这样的指法,写错的人已经够定位了。你看,少写分号的场合,报错能指到离伤口最近的地方。

第二份的毛病是值没收尾:`reg` 的右尖括号丢了,分号直接顶了上来,咱们把它存成 badcells.dts:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	uart@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100;
		status = "okay";
	};
};
```

```shell
python3 toyparse.py badcells.dts
```

```output
badcells.dts: 9:22: 尖括号还没闭上,却读到了 ';'
```

你看,第二个输入连语法层的门都没进,词法器的栈在半路就把它拦下了:读到的分号还待在尖括号的地盘里,报错的位置在第 9 行第 22 列,正是那个分号的住址。词法层把得住值的收尾,语法层的报错就省了一类。

第三份少了根节点的收尾,咱们把最后那行 `};` 整个抹掉,文件的名字就叫 noclose.dts:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	keys {
		compatible = "acme,gpio-keys";
		autorepeat;
	};
```

```shell
python3 toyparse.py noclose.dts
```

```output
noclose.dts: 10:1: 节点 / 还欠一个 }
```

报错的位置落在第 10 行,那是文件最后一个记号的位置。少了收尾记号的输入,解析器走到文件的尽头才发现欠了东西,缺口在哪它是给不出答案的,只能把自己停下的地方报出来。咱们顺手拿 dtc 试同一份输入:

```shell
dtc -I dts -O dtb -o /dev/null noclose.dts
```

```output
Error: noclose.dts:10.4-11.1 syntax error
FATAL ERROR: Unable to parse input tree
```

dtc 的位置也是第 10 行的末尾,跟咱们的玩具一个脾气,找缺口的活儿交还给人。这类报错的精度天生就差一截,咱们能做的是把欠的东西说个明白,“欠在哪”就交给写树的人了。

三份坏输入的报错咱们都验过了,位置的指法也算靠谱。树模型读到这一步就算立稳了,咱们接下来把它写回 DTB,亲手编出第一个属于自己的产物。

## 本节自检

这一篇读完了,你拿两个小问题验一验自己,想好了再展开参考答案。

1. noclose.dts 的报错为什么落在第 10 行?这一类报错为什么指不到真正的缺口?
2. badcells.dts 的报错是哪一层给的?语法器为什么没机会出手?

<details>
<summary>参考答案(想好再展开)</summary>

1. 落在第 10 行,那是文件最后一个记号的位置。少了收尾记号,解析器只能走到尽头才发现欠了东西,缺口在哪它给不出答案,报错只能指在停下来的地方。dtc 对这类输入也一样。
2. 词法器给的。读到的分号还待在尖括号的地盘里,词法器的栈在半路就把它拦下了。词法层把得住值的收尾,语法层的报错就省了一类。

</details>
