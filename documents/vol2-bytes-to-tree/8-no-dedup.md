---
title: "怎样造出合法却不一致的 DTB?"
volume: 2
chapter: 7
section: 2
order: 72
description: "rt2.dts 专挑对齐与去重的软肋,往返照样逐字节一致,关掉去重后产物大了 19 字节、四处字节分家,dtc 反编译两边文本全同,语义等价的验收线拿到了活例子"
status: draft
---

# 字节分了家的两份 DTB,凭什么是同一棵树?

上一篇的结尾留了一个活要干:逐字节一致的头一趟让语义等价显得多余,咱们得造一个合法却不一致的活例子。本篇咱们接着干,工具还是上一篇的 `rt.py`:输入专挑对齐与去重的软肋,字符串表的去重再故意关掉,让两份合法的产物在字节上分家。咱们再请 dtc 把两边各读一遍,看树的内容到底变没变。

## 第二趟:保留区、奇长的值、空属性一起上

咱们造一份内容更刁的 `rt2.dts`,专挑对齐与去重的软肋下手:

```dts
/dts-v1/;

/memreserve/ 0x40000000 0x2000;

/ {
	compatible = "demo,roundtrip";
	#address-cells = <1>;
	#size-cells = <1>;
	notes = "abc";
	snippet = [11 22 33];
	empty-prop;
	a {
		compatible = "demo,leds";
		snippet = [de ad];
	};
};
```

咱们的每一行都有用意:`/memreserve/` 让内存保留区有了真条目,`snippet` 的 3 字节值要补 1 个零,`empty-prop` 是长度为 0 的空属性,子节点的名字 `a` 连结束符才 2 字节也要补齐,名字 `compatible` 与 `snippet` 各出现了两次,字符串表的去重有了用武之地。咱们接着编译、往返、比对:

```shell
dtc -I dts -O dtb -o rt2.dtb rt2.dts
wc -c rt2.dtb
python3 rt.py round-trip rt2.dtb rt2-out.dtb
cmp rt2.dtb rt2-out.dtb
echo "cmp 的退出码 $?"
```

```output
307 rt2.dtb
rt2-out.dtb: 307 字节,内存保留区 1 条,字符串表去重
cmp 的退出码 0
```

带保留区的输入也逐字节一致了。咱们把文件头请出来核一遍数:

```shell
xxd rt2.dtb | head -5
```

```output
00000000: d00d feed 0000 0133 0000 0048 0000 00f4  .......3...H....
00000010: 0000 0028 0000 0011 0000 0010 0000 0000  ...(............
00000020: 0000 003f 0000 00ac 0000 0000 4000 0000  ...?........@...
00000030: 0000 0000 0000 2000 0000 0000 0000 0000  ...... .........
00000040: 0000 0000 0000 0000 0000 0001 0000 0000  ................
```

这些数咱们在读方向都认过,现在它们是咱们自己写出来的:保留区从 0x28 也就是 40 字节的地方起,一条真条目加一条收尾条目一共占了 32 字节,结构块从 0x48 起了头,它的长度是 0xac,字符串块的起点是 0xf4,长度 0x3f 也就是十进制的 63 字节,totalsize 的 0x133 换算过来就是 307。

## 故意不去重:字节分了家,树没变

现在咱们把字符串表的去重关掉,让每个属性名都存自己的一份:

```shell
python3 rt.py round-trip rt2.dtb rt2-nodedup.dtb --no-dedup
cmp rt2.dtb rt2-nodedup.dtb
echo "cmp 的退出码 $?"
cmp -l rt2.dtb rt2-nodedup.dtb | wc -l
wc -c rt2.dtb rt2-nodedup.dtb
```

```output
rt2-nodedup.dtb: 326 字节,内存保留区 1 条,字符串表没去重
rt2.dtb rt2-nodedup.dtb differ: byte 8, line 1
cmp 的退出码 1
cmp: EOF on ‘rt2.dtb’ after byte 307
4
307 rt2.dtb
326 rt2-nodedup.dtb
633 total
```

字节分家了,产物大了 19 字节。两份文件重合的前 307 个字节里,`cmp -l` 只报了 4 处不同,咱们把这 4 处解出来看:

```shell
diff <(xxd rt2.dtb) <(xxd rt2-nodedup.dtb)
```

```output
1c1
< 00000000: d00d feed 0000 0133 0000 0048 0000 00f4  .......3...H....
---
> 00000000: d00d feed 0000 0146 0000 0048 0000 00f4  .......F...H....
3c3
< 00000020: 0000 003f 0000 00ac 0000 0000 4000 0000  ...?........@...
---
> 00000020: 0000 0052 0000 00ac 0000 0000 4000 0000  ...?........@...
13c13
< 000000c0: 0000 0003 0000 000a 0000 0000 6465 6d6f  ............demo
---
> 000000c0: 0000 0003 0000 000a 0000 003f 6465 6d6f  ...........?demo
15c15
< 000000e0: 0000 002c dead 0000 0000 0002 0000 0002  ...,............
---
> 000000e0: 0000 004a dead 0000 0000 0002 0000 0002  ...J............
20c20,21
< 00000130: 6f70 00                                  op.
---
> 00000130: 6f70 0063 6f6d 7061 7469 626c 6500 736e  op.compatible.sn
> 00000140: 6950 7065 7400                           ippet.
```

四处差异咱们挨个认。第 8 字节起是 totalsize 的末位,0x133 变成了 0x146,文件大了 19 字节。第 36 字节落在 size_dt_strings 的地盘,63 变成了 82,多出的正是第二份 `compatible` 和第二份 `snippet` 的 19 字节。第 204 与 228 字节是两个重复属性的 nameoff,它们从指向第一份改成了指向自己的复本。文件尾部多出的内容,xxd 的字符列直接念了出来,`compatible` 与 `snippet` 各多存了一份。

326 字节的产物合法吗?咱们请裁判出场:

```shell
dtc -I dtb -O dts rt2.dtb > ref2.dts
dtc -I dtb -O dts rt2-nodedup.dtb > nodedup2.dts
diff ref2.dts nodedup2.dts
echo "diff 的退出码 $?"
```

```output
diff 的退出码 0
```

反编译的文本全同,连一个字节的差别都没有。咱们看裁判读出的树长成的样子,内存保留区也好好地待在原处:

```dts
/dts-v1/;

/memreserve/	0x0000000040000000 0x0000000000002000;
/ {
	compatible = "demo,roundtrip";
	#address-cells = <0x01>;
	#size-cells = <0x01>;
	notes = "abc";
	snippet = [11 22 33];
	empty-prop;

	a {
		compatible = "demo,leds";
		snippet = [de ad];
	};
};
```

咱们拿到的是同一棵树,两份不同的字节,dtc 都读出了一样的内容,这就是语义等价的活例子。验收线画在这里的理由,现在有实物撑着了:去重与否是 writer 的自由度,两边的产物都完全合法,咱们要是拿字节一致当验收,不去重的产物就要蒙冤。

验收线的道理有了实物撑着,往返的实验到这里也跑通了。实验背后还压着一套没说明白的工作纪律,裁判的出身也还没交代,下一篇咱们把这两件事一起补上。

## 本节自检

这一篇读完了,你拿四个小问题验一验自己,想好了再展开参考答案。

1. rt2.dts 的每一行都有用意。`snippet` 的 3 字节值、`empty-prop`、子节点的名字 `a`,各自考的是哪一样?
2. 字符串表不去重让 rt2 的产物大了多少字节?多出的字节里装的是什么?
3. 两份文件重合的前 307 个字节里,`cmp -l` 报的 4 处不同分别落在哪些字段上?文件尾部多出的内容又是谁?
4. 326 字节的产物合法吗?裁判怎么判的?

<details>
<summary>参考答案(想好再展开)</summary>

1. `snippet` 的 3 字节值要补 1 个零,`empty-prop` 是长度为 0 的空属性,子节点的名字 `a` 连结束符才 2 字节也要补齐。
2. 大了 19 字节,装的是第二份 `compatible` 和第二份 `snippet`,也就是 `compatible\0snippet\0` 的第二份拷贝。
3. 第 8 字节起是 totalsize 的末位,0x133 变成了 0x146。第 36 字节落在 size_dt_strings 的地盘,63 变成了 82。第 204 与 228 字节是两个重复属性的 nameoff,它们从指向第一份改成了指向自己的复本。文件尾部多出的是 `compatible` 与 `snippet` 各一份,那部分 `cmp` 拿 EOF 报的。
4. 合法。咱们拿 dtc 反编译两边,两份文本丢给 `diff`,退出码 0,反编译读出的树连内存保留区都好好地待在原处,咱们拿到的就是同一棵树。

</details>
