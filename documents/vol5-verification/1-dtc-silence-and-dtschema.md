---
title: "编译成功就代表写对了吗,检查员从哪儿请?"
volume: 5
chapter: 16
section: 1
order: 161
description: "第五卷接住四卷攒下的心虚:typo.dts 拼错 compatible,no-clock.dts 缺时钟,short-reg.dts 砍掉 reg 的长度,三棵语法全对的树各编一遍,退出码全是 0,只有 reg_format 一类通用结构检查开了口,dtc 的地界与盲区当场量清。语义的知识住在 binding 里:早年是一篇篇纯文本,内核社区后来改写成 YAML schema,校验的活交给机器。咱们照官方文档装 dtschema:pip 被 externally-managed 拦下,--break-system-packages 装进 ~/.local,dtc、Python、pip、dtschema 的版本如实记下"
status: draft
---

# 编译器没吭声,树就真的写对了吗,检查员从哪儿请?

## 四卷家当攒下来,就剩这一问没验过

咱们把前四卷走完,你手里的家当已经攒了一堆:第一卷里你会编译会反编译,第二卷你把 DTB 的字节翻了个遍,第三卷里你跟着消费方把树读了进去,第四卷你又亲手造出了玩具编译器。可是家当攒得多了,咱们心里反而越虚:编译器没吭声的树,凭什么说它写对了?

第五卷的名字是“工程验证与排错”,它接的就是这一问。本章咱们干的是一件事:亲手造出语法全对、语义有病的树,看一看 dtc 的沉默。然后咱们把“什么算有病”写成一份最小的 binding,请 dt-validate 上了岗,好树和病树各验了一遍,输出原样贴给你。末尾咱们再认一认内核树里的校验目标,看看同一件事在真实工程里怎么批量地干。

动手的位置照旧在 /tmp,目录咱们开在 /tmp/vol5ch16:

```shell
mkdir -p /tmp/vol5ch16
cd /tmp/vol5ch16
```

## 拼错的 compatible,dtc 一个字都没提

头一棵树是咱们的 typo.dts,咱们把串口的名字故意拼错:

```dts
/dts-v1/;

/ {
	#address-cells = <1>;
	#size-cells = <1>;

	serial@1000 {
		compatible = "acme,serail";
		reg = <0x1000 0x100>;
	};
};
```

毛病就藏在 `compatible` 的值里:前几卷里咱们写熟了的 `acme,uart`,在这里被咱们拼成了 `acme,serail`,它是 serial 一词里 i 和 a 换了位置的样子。咱们把它交给 dtc:

```shell
dtc -I dts -O dtb -o typo.dtb typo.dts
echo $?
```

```output
0
```

咱们连一行输出都没见到,退出码稳稳地是 0,typo.dtb 也照常写出来了。名字拼错了,编译器倒是毫不在乎:它只认语法的合法性,`acme,serail` 在它眼里就是一个普普通通的字符串,至于串口的家谱里有没有这号名字,它是没法知道的。

第二棵树咱们叫它 no-clock.dts,它跟 typo.dts 的差别只有一处:`compatible` 写回了正确的 `acme,uart`,别的字咱们一个没动。它身上没有 clock-frequency 的影子,连串口该报的时钟频率都没交代,dtc 编它的时候照样一声不吭,退出码也稳稳地是 0。你可以说缺属性是毛病,dtc 倒是连眉头都不皱,因为它压根不知道一个串口节点该有什么样的属性。

不过 dtc 的检查单也不是全无作为,咱们如实交代它的地界。咱们把 reg 的第二个 cell 砍掉,只留了地址没留长度,存成 short-reg.dts 又编了一次,它就开口了:

```output
short-reg.dts:9.3-18: Warning (reg_format): /serial@1000:reg: property has invalid length (4 bytes) (#address-cells == 1, #size-cells == 1)
short-reg.dtb: Warning (pci_device_reg): Failed prerequisite 'reg_format'
short-reg.dtb: Warning (pci_device_bus_num): Failed prerequisite 'reg_format'
short-reg.dtb: Warning (simple_bus_reg): Failed prerequisite 'reg_format'
short-reg.dtb: Warning (i2c_bus_reg): Failed prerequisite 'reg_format'
short-reg.dtb: Warning (spi_bus_reg): Failed prerequisite 'reg_format'
```

reg_format 的意思咱们读一眼就懂:reg 的字节数得跟父节点的 cells 配对,配不上的它就警告。后面的五行是连锁反应,报的都是“Failed prerequisite”:reg_format 挂了,别的检查想接着查也没了前提。“构建系统实际上做了什么”那章里咱们见过同一类的 unit_address_vs_reg,告警的脾气你早就领教过:它提醒它的,编译却照样放过了,产物也照样出来了。

咱们把三棵树摆在一起看,dtc 的地界就清楚了。dtc 白送的检查单管的是所有树共享的通用结构,reg 的长度、地址与 reg 的搭配都在它的辖区里,它也不需要知道串口是什么东西。而串口该叫什么名字、该有哪些属性、值的格式长什么样,这样的知识在 dtc 里是根本不存在的,它们住进了另一个地方:binding。

地界量清了,盲区也跟着清楚:拼错的名字、缺掉的属性、没被允许的属性,咱们靠 dtc 是拦不住的。判这些毛病要用的知识住进了 binding,它长什么样,机器又怎么接手去验,咱们接着往下认。

## binding 回场:约定本身,现在写成了 YAML

`binding` 这个词你认得,“设备树长什么样”那篇里咱们跟它打过照面,四方分工的桌子那篇里也摆过:硬件给的是事实,设备树给的是描述,binding 管的是约定,驱动管的是实现。binding 在桌上管的是约定:这类硬件该怎么写、哪些属性必须写、值的格式长什么样、compatible 怎么起名,全由它说了算。写成一句话的版本就是:binding 是一类硬件的描述约定,咱们拿它当量树的尺子。

咱们把镜头拉回早年:binding 那时是一篇篇纯文本说明,靠的是人眼。内核社区后来把约定改写成了 YAML schema,校验的活从此交给了机器。YAML 里写的其实是 json-schema 的一个子集,皮是 YAML 的样子,骨子里是一条条机器可读的约束。

咱们把叫法统一一下:约定叫 binding,写成的 YAML 文件叫 schema,拿 schema 验树的命令咱们马上请出场。

## 装检查员:dtschema 的真实安装记录

机器校验的活由 dtschema 这个 Python 包来干,它一口气装了三位检查员:验 binding 自身的是 dt-doc-validate,把零散 YAML 合成总表的是 dt-mk-schema,拿 schema 验树的是 dt-validate。咱们照官方文档的路子敲:

```shell
pip3 install --user dtschema
```

咱们本机的 pip 把请求拒绝了,它交回的输出是:

```output
error: externally-managed-environment

× This environment is externally managed
╰─> To install Python packages system-wide, try 'pacman -S
    python-xyz', where xyz is the package you want.
```

提示的后半段还建议用 venv 或者 pipx,大方向是同一个意思:发行版把系统的 Python 标成了受管理的,pip 这才拦下了咱们。咱们本机的系统是 Arch 一系,pipx 偏偏没有装,再装它就得动包管理器了,提权的活咱们不干。于是咱们换成了用户级的强行安装:命令还是 --user 的路子,加了一个 --break-system-packages,东西进的地方照样只有 ~/.local,系统的目录咱们一个字节都不碰:

```shell
pip3 install --user --break-system-packages dtschema
```

```output
Installing collected packages: rfc3987, pylibfdt, ruamel.yaml, rpds-py, referencing, jsonschema-specifications, jsonschema, dtschema
Successfully installed dtschema-2026.9 jsonschema-4.26.0 jsonschema-specifications-2025.9.1 pylibfdt-1.7.2.post2 referencing-0.37.0 rfc3987-1.3.8 rpds-py-2026.9.1 ruamel.yaml-0.19.1
```

装好的命令进了 ~/.local/bin,不在 PATH 里的话咱们把它加进来,咱们再跟新检查员打个照面:

```shell
export PATH="$HOME/.local/bin:$PATH"
dt-validate --version
```

```output
2026.9
```

版本咱们如实记下,跑命令的日子是 2026-10-18:dtc 用的是 v1.8.1,Python 用的是 3.14.8,pip 用的是 26.2.1,dtschema 装的是 2026.9。

三位检查员到岗了,可它们验的是 schema,咱们手头还没有一份。下一篇咱们就给 ACME 的串口写一份最小的 binding,体检的活儿交给 dt-doc-validate。

## 本节自检

文章读完了,你拿四个小问题验一验自己,想好了再展开参考答案。

1. dtc 的检查和 binding 校验各管哪一层?哪些毛病 dtc 从头到尾发现不了?
2. 咱们把 reg 的第二个 cell 砍掉之后,dtc 开口了吗?报的 reg_format 说的什么事,后面五条 Failed prerequisite 又是怎么回事?
3. binding、schema、dt-validate 各指的是什么?
4. 咱们本机的 pip 头一回为什么把请求拒了?后来咱们怎么装上的,系统的目录动没动?

<details>
<summary>参考答案(想好再展开)</summary>

1. dtc 管语法和一部分通用结构,比如 reg 的长度、单元地址与 reg 的搭配。名字拼错、必需属性缺失、属性不在允许范围里,它发现不了,因为那需要“这类硬件该怎么写”的知识,而它没有。
2. 开口了。reg_format 说的是 reg 的字节数得跟父节点的 cells 配对,配不上它就警告。后面五条是连锁反应,reg_format 挂了,别的检查没了前提,报的就都是 Failed prerequisite。编译倒是照样放过了,产物也照样出来了。
3. binding 是一类硬件的描述约定,schema 是约定写成的 YAML 文件,dt-validate 是拿 schema 验树的命令。早年 binding 是一篇篇纯文本说明,靠的是人眼,内核社区后来把约定改写成了 YAML schema,校验的活从此交给了机器。
4. 发行版把系统的 Python 标成了受管理的,pip 这才拦下了咱们。咱们沿 --user 的路子加了 --break-system-packages 再装,东西进的地方只有 ~/.local,系统的目录一个字节都没碰。

</details>

## 延伸阅读

本篇的机制叙述咱们都对过官方文档,出处咱们列在下面:

- [Writing devicetree bindings in json-schema](https://docs.kernel.org/devicetree/bindings/writing-schema.html):内核官方的 schema 写作文档,dtschema 的安装在这里,dt_binding_check 与 dtbs_check 的用法、DT_SCHEMA_FILES 的写法也在这里。

- [dt-schema 仓库](https://github.com/devicetree-org/dt-schema):dtschema 包的老家,三位检查员的源码与 README 都在这里,装的是哪个版本、支持哪些参数,这里都能对上。
