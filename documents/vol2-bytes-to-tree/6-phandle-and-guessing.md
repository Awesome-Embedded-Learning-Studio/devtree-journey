---
title: "引用怎么落地,解读的凭据立在哪儿?"
volume: 2
chapter: 6
section: 2
order: 62
description: "标签进了产物换成 phandle 数值,索引等树挂满后再扫第二遍一次收齐,clocks 的 0x1 一查就到 clock-controller。同样四个字节的 oem-data,dtc 反编译靠 guess_value_type 按文本形状和 4 的倍数猜成 cell,咱们的界线画在原始字节与可追问的已知表上,末了看 edtc 的树模型比 tree.py 多打算了什么"
status: draft
---

# 引用怎么落地,解读的凭据立在哪儿?

## 标签进了产物只剩数字,索引把数字认回节点

树查询的手感你也有了,可引用的影子还没见过。mini.dtb 的树里没有引用,phandle 索引也就跟着空了。咱们编一份带标签引用的 ref.dts,给时钟节点挂上 clk24 的标签,再让 uart 的 clocks 引用它,末尾还添了一条四个字节的 oem-data,它的用场就在本篇:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	clk24: clock-controller {
		compatible = "demo,fixed-clock";
		clock-frequency = <24000000>;
		#clock-cells = <0>;
	};

	uart@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
		clocks = <&clk24>;
		oem-data = [01 02 3a 4f];
	};
};
```

咱们编译完接着把树立起来:

```shell
dtc -I dts -O dtb -o ref.dtb ref.dts
python3 tree.py ref.dtb
```

```output
/
    #address-cells     [cell] 0x1 (4 字节)
    #size-cells        [cell] 0x1 (4 字节)
    /clock-controller
        #clock-cells       [bytes] 00 00 00 00 (4 字节)
        clock-frequency    [cell] 0x16e3600 (4 字节)
        compatible         [string] "demo,fixed-clock" (17 字节)
        phandle            [cell] 0x1 (4 字节)
    /uart@1000
        clocks             [bytes] 00 00 00 01 (4 字节)
        compatible         [string] "acme,uart" (10 字节)
        oem-data           [bytes] 01 02 3a 4f (4 字节)
        reg                [cells] <0x1000 0x100> (8 字节)

phandle 索引(数值 -> 节点路径):
  0x1 -> /clock-controller
```

标签的下场你在“怎样描述和组织设备”那章见过:源码里的 &clk24 进了产物就换成了数字,clock-controller 的身上多出了一条 phandle 属性,属性的值是 0x1,引用处的 clocks 也变成了同样的 0x1。两处数字现在都躺在咱们的输出里,你拿数值一对,连线就算接上了。

phandle 是什么,规范 §2.3.3 说得很直白:它是节点在整个树里独一份的数值编号,别的节点想指它的时候,往属性里放的就是这个数。可属性里躺着的终究只是一个数,数自己是变不回节点的。咱们想让引用落地,就得备一张数值到节点的索引:全树扫一遍,谁的身上有 phandle 属性,就把它的数值和节点收进一张表。引用解析靠的也就是索引,你拿数字一查,一步就到了节点。

索引为什么不在挂树的时候一起建,而要等树挂满之后再扫第二遍?phandle 属性可能长在任何一个节点的身上,引用也可能指向前面的节点,挂树的中途谁也没法保证见全了。第二遍扫的时候树已经完整,咱们一张表一次收齐,后面的引用不管查多少次,都不用再碰结构块了。

咱们把引用解析当场跑一遍:

```shell
python3 -c 'import tree
root = tree.parse(open("ref.dtb", "rb").read())
index = tree.phandle_index(root)
ref = int.from_bytes(tree.find(root, "/uart@1000").props["clocks"], "big")
print("clocks 的头一个 cell 是 0x%x" % ref)
print("索引报出的节点是 " + index[ref].path)'
```

```output
clocks 的头一个 cell 是 0x1
索引报出的节点是 /clock-controller
```

uart 的 clocks 字节是 00 00 00 01,咱们按大端读出 0x1,索引一查就指到了 /clock-controller。不过还有一层约定得交代在前面:clocks 的头一个 cell 是 phandle,这是 clock binding 的约定,不在格式的管辖范围里,所以咱们的小工具只替你把字节和索引都备好,切 cell 的判断留给知道 binding 的人。

输出里还有一条值得咱们停一停,#clock-cells 印的是 [bytes]。它的值明明也是四个字节的 00 00 00 00,解读层却只报了字节,差别的原因就一条,KNOWN 表里没有它的名字。表是政策而不是魔法,你想让它印成 cell,往表里添上一行就成了。划在第五卷的 binding 数据库不归咱们这一层管,咱们认的永远是写得明明白白的小表。

小表的政策到这儿也就亮完了:表里有的名字才有解读,表外的一律只报字节。可同一份 ref.dtb 到了 dtc 手里,印法跟咱们的不一样,差别出在哪儿?咱们接着去问个明白。

## dtc 按长度猜形式,咱们的解读层按名字认

咱们在前头留了一个问号:同一份产物,dtc 会怎么印?轮到 oem-data 上场了,它的源码写法是字节串 [01 02 3a 4f],tree.py 也原样报了四个字节。可你拿 dtc 反编译 ref.dtb,它印的是另一副面孔:

```shell
dtc -I dtb -O dts ref.dtb
```

```output
/dts-v1/;

/ {
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	clock-controller {
		compatible = "demo,fixed-clock";
		clock-frequency = <0x16e3600>;
		#clock-cells = <0x00>;
		phandle = <0x01>;
	};

	uart@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
		clocks = <0x01>;
		oem-data = <0x1023a4f>;
	};
};
```

oem-data 被印成了 `<0x1023a4f>`,`clocks` 和 `#clock-cells` 也全进了尖括号,咱们找 dtc 要个说法。dtc 手里并没有读心的法术,它做的是按形状猜。猜的算法住在 dtc 1.8.1 源码的 treesource.c 里,本仓的 edtc/reference/dtc 也留有拷贝,函数的名字叫 guess_value_type,咱们原样请出来:

```c
static enum markertype guess_value_type(struct property *prop, unsigned int offset, int len)
{
	const char *p = prop->val.val + offset;
	int nnotstring = 0, nnul = 0;
	int i;

	for (i = 0; i < len; i++) {
		if (! isstring(p[i]))
			nnotstring++;
		if (p[i] == '\0')
			nnul++;
	}

	if ((p[len-1] == '\0') && (nnotstring == 0) && (nnul <= len - nnul)) {
		if (nnul > 1)
			add_string_markers(prop, offset, len);
		return TYPE_STRING;
	} else if ((len % sizeof(cell_t)) == 0) {
		return TYPE_UINT32;
	}

	return TYPE_UINT8;
}
```

判定的次序咱们读得出三段:全部字节都算得上“像文本”,末尾的还得是零,而且零的个数不过半,就按字符串的形式印。而长度恰好被 4 整除,就按 cell 的形式印,剩下的才按字节串印。isstring 认的“像文本”也宽:可打印的字符、零,再加上几个常见的控制符都算数。oem-data 的四个字节过不了字符串那一关,长度却赶巧是 4 的倍数,于是被当成了 cell 印了出来。你拿它对“怎样描述和组织设备”那章的 bytes-four 现象,规则严丝合缝:那章里四个字节的字节串回来印成了 `<0x1023a4f>`,凭的就是同一段代码。

dtc 为什么能这么干?因为从 DTB 读进来的属性身上没有任何类型的注记,格式里给的本来就只有名字和字节,猜形状成了反编译器唯一的依据。猜测也谈不上丢了信息,字节倒是一个都没动,印法只是给你看的。可猜出来的形式一旦被人当成了凭据,责任就换了主人:产物里存的是字节,类型是读的人添上去的,猜错了得怪读的人,文件本身是一点错都没有的。

咱们自己的工具因此把界线画在了接口上,一共画了两道。头一道管字节:原始字节你永远拿得到,想绕过解读的时候随时都行,直接摸到那几个十六进制的字节。第二道管解读:解读层永远经得起你的追问,凭据只有已知表里的名字,名字不在表里的就明说不知道,一个形状的字都不猜。解码与猜测的分界也就落在了这里:解码认的是出处,猜测看的是长相。

分界立好了,咱们的小工具该交代的也就交代完了。挂树、两层属性、phandle 索引这三样活怎么进 edtc 的正式设计,接下来咱们看打算。

## edtc 的树模型打算怎么摆

树模型的三样活,咱们一步一步地干了下来:事件挂成了节点,属性分了两层,phandle 也收成了索引。课堂上的东西到这儿就齐了,可 edtc 的工程打算怎么接手,咱们还没有交代过。

edtc 的工程现状你在上一章就知道了:DTB reader 还没动工,工程还停在输入与环境的那一层,所以下面写的是设计,而不是代码回顾。树模型对应规划里的里程碑 M2,它要接的活就是本章的三样:挂树、两层属性、phandle 索引。

结构上咱们打算照搬 tree.py 的骨架:节点存名字、路径、属性表、孩子列表,属性表的值一律是原始字节,解读层不进结构的芯子,挂在查询接口的旁边。比脚本多出来的是一个向上的父指针,报错的时候要带上全程的路径,好从出事的节点一路爬回根。phandle 索引在树挂满之后的第二遍建立,规范的 §2.3.3 里还提过一个退役的旧写法 `linux,phandle`,咱们只会在老产物里见到它,所以索引把两个名字都认了下来。

解读层的已知表,在 C++ 里就落成了一张常量表,内容从咱们这一章的最小集起步:字符串认 compatible 和 status,按单个 cell 认的有 clock-frequency、#address-cells、#size-cells 和 phandle,reg 认的是一串 cell。往后咱们要不要认更多,判据你已经写过:认得有出处,出处写在表边上的注释里。binding 级别的解读,比如 clocks 的头一个 cell 是 phandle,咱们不塞进表里,那属于第五卷的领地。

树模型还是咱们两股输入的汇合点:DTB reader 从产物立树,DTS 前端到了第四卷再从源码立树,汇进的都是同一个模型,只是那边的节点会再宽一点,源码位置和标签这些编译期的信息也得有地方住,原始字节这一层却是两边共用的底座。下一章的 DTB writer 同样只吃树模型:进去的是树,出来的是产物。writer 接活的前提只有一个:树模型把字节一个不丢地保住了,而“有没有丢”要怎么证明,就是下一章的正题。

## 交棒:下一章,怎样证明读写没有改变内容

树立住了,查询的两层接口也通了,咱们手里现在有一棵能查的树。可工具链的另一半还没影:进去的是一份 DTB,出来的又是一份 DTB,凭什么说内容没变?下一章“怎样证明读写没有改变内容”就干这件事:咱们给树模型配一个把树写回 DTB 的 writer,往返咱们也真跑一遍,把没变的验收标准也定下来。树模型的字节保没保住,结果到那一章见分晓。

## 本节自检

文章读完了,你拿九个小问题验一验自己,想好了再展开参考答案。

1. ref.dtb 里 #clock-cells 的值也是四个字节,tree.py 为什么只印 [bytes]?想让它印成 cell 得改哪里?
2. phandle 索引为什么要等树挂满之后再建第二遍?没有索引的话,一次引用解析得付出什么代价?
3. clocks 的头一个 cell 是 phandle,这条约定住在格式里还是 binding 里?
4. oem-data 同样是四个字节,dtc 反编译把它印成了什么?tree.py 为什么只报字节?
5. “产物里只存字节,类型是读的人猜的”,这句话给咱们自己的工具立了哪两条界线?
6. guess_value_type 判形式按什么次序走?
7. edtc 的节点比 tree.py 多存了一个什么?图的是什么?
8. phandle 索引为什么把 `linux,phandle` 也认了下来?
9. 第四卷的 DTS 前端也要立树,它和 DTB reader 共用的是哪一层?

<details>
<summary>参考答案(想好再展开)</summary>

1. 因为 KNOWN 表里没有 #clock-cells 的名字,解读层只认表。往表里添一行,它就印成 cell 了。
2. phandle 属性可能长在任何一个节点上,挂树的中途见不全,树挂满之后扫第二遍才能一次收齐。没有索引就得全树搜一遍找匹配的数值,引用多了,每条引用都要重搜。
3. 住在 clock binding 的约定里,不在格式的管辖范围里,所以小工具只替你把字节和索引都备好,切 cell 的判断留给知道 binding 的人。
4. dtc 把它印成了 `<0x1023a4f>`,四个字节被按 cell 猜了。tree.py 的凭据只有已知表,oem-data 不在表里,所以只报字节,不猜形状。
5. 原始字节永远拿得到,解读层永远可追问凭据。解码认的是出处,出处就是已知表,猜测看的是长相,咱们的工具不做看长相的事。
6. 全部字节都算得上像文本,末尾的还得是零,零的个数又不过半,就按字符串的形式印。长度恰好被 4 整除,就按 cell 的形式印,剩下的才按字节串印。
7. 一个向上的父指针。报错的时候要带上全程的路径,好从出事的节点一路爬回根。
8. 那是规范 §2.3.3 里提过的退役旧写法,咱们只会在老产物里见到它,所以索引把两个名字都认了下来。
9. 原始字节这一层。两边汇进的是同一个树模型,只是源码那边的节点会再宽一点,源码位置和标签这些编译期的信息也得有地方住。

</details>

## 延伸阅读

咱们本篇的条款与源码出处,给你备好了:

- [Devicetree Specification 官方页](https://www.devicetree.org/specifications/):phandle 的条款在 §2.3.3,属性值只是一段字节的定性在第 5 章的结构块一节,本仓 `.claude/materials/` 缓存了 v0.4 全文副本可核对。
- [dtc 源码 treesource.c(官方仓库)](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/tree/treesource.c):guess_value_type 与 isstring 都住在这里,本仓 edtc/reference/ 留有 1.8.1 的源码拷贝,git 不跟踪,磁盘上能翻到。

咱们引用的条款来自规范 v0.4(本仓缓存副本),正文里的命令、脚本与输出全部在本机真实运行过,验证环境的版本是 dtc v1.8.1 与 Python 3.14.8,验证的日子是 2026-10-18。
