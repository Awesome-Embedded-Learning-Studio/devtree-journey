---
title: "一份最小的 binding 要写什么,好树病树各报什么?"
volume: 5
chapter: 16
section: 2
order: 162
description: "schema 学内核的目录规范住进 bindings/serial/,文件放错位置 dt-doc-validate 当场抱怨 $id 对不上,不到三十行的 acme,uart.yaml 把身份、属性约束、必需清单、属性把关写齐,元 schema 给它自身做体检,安静地过了。dt-validate 收 DTB,咱们拿 dtc 编过去再交:根上缺 model 与 compatible 被 root-node.yaml 拦下,补齐的 good.dts 干净过关,bad-missing 缺必需属性、bad-prop 多写没被允许的 clock_freq,报错逐段读出谁、错在哪、按谁的约定判的"
status: draft
---

# 咱们的第一份 binding 怎么写,好树病树各报什么?

检查员上一篇里已经到岗了,可它们验的是 schema,咱们手头一份都还没有。本篇咱们就给 ACME 的串口写一份不到三十行的最小 binding,把验树要紧的东西写齐。动手的目录还是上一篇开下的 /tmp/vol5ch16。

## 咱们的最小 binding,不到三十行

schema 文件咱们放进 bindings/serial/ 子目录,学的是内核的目录规范:内核把全部的约定放在 Documentation/devicetree/bindings/ 之下,按类安了家。为什么非要带一个 serial/ 子目录?咱们头一回把文件直接丢在 /tmp/vol5ch16 下跑 dt-doc-validate,它抱怨了:

```output
/tmp/vol5ch16/acme,uart.yaml: $id: Cannot determine base path from $id, relative path/filename doesn't match actual path or filename
	 $id: http://devicetree.org/schemas/serial/acme,uart.yaml
	file: /tmp/vol5ch16/acme,uart.yaml
```

抱怨说的是:$id 里声称的路径,跟文件实际待的位置对不上。咱们把文件挪进 serial/ 子目录,再跑就安静了。内核的布局不是随便摆的,咱们信它一回,一遍折腾就省下了。文件的全名是 `bindings/serial/acme,uart.yaml`,内容咱们贴在下面:

```yaml
# SPDX-License-Identifier: GPL-2.0-only OR BSD-2-Clause
%YAML 1.2
---
$id: http://devicetree.org/schemas/serial/acme,uart.yaml#
$schema: http://devicetree.org/meta-schemas/core.yaml#

title: ACME training UART

maintainers:
  - Devtree Journey <course@example.com>

properties:
  compatible:
    const: acme,uart

  reg:
    maxItems: 1

  clock-frequency:
    description: baud-rate source clock in Hz

required:
  - compatible
  - reg
  - clock-frequency

additionalProperties: false
```

咱们按块读。头一行 SPDX 是内核仓库的惯例,每一份 schema 的开头都带着许可证声明,后面两行是 YAML 文档的版本与开栏记号。`$id` 给了 schema 一个正式的地址,别的 schema 想引用它的时候,认的就是这个地址。`$schema` 说的是它自己要遵守的元 schema,也就是验 schema 用的 schema,咱们要判断 binding 自身写得合不合格,听元 schema 的。title 和 maintainers 是给人看的门面,出了问题该找谁,门面上就写了。

咱们把重活都安排在 properties 里,给每个属性配上了一条约束。`compatible` 的约束用了 const,意思就是合法的值只有 `acme,uart` 一个。`reg` 用 maxItems 限了组数,一组就是一个地址加一个长度,多出来的组它不收。`clock-frequency` 咱们只写了 description,值的类型约束由元 schema 兜底。required 把三个名字列成了必需,缺了任何一个它就报错。末尾的 additionalProperties: false 是关门的那句话:除了 properties 里列过的,别的属性都不许再往节点上写了。

schema 的关键字族比咱们写的多得多,咱们只取了验树要紧的最小一撮:身份、属性约束、必需清单、属性把关。想看全的,咱们把官方文档收进了延伸阅读。

binding 自身咱们也验了:`dt-doc-validate bindings/serial/acme,uart.yaml` 跑下去,它安安静静地过了。给检查员做体检的,就是 dtschema 自带的元 schema。

约定自身的体检过了,尺子立起来了。咱们就拿它量树,好树和病树各自的输出,咱们原样贴给你。

## 好树过,病树挂:输出原样贴

dt-validate 收的输入是 DTB,帮助原文写的就是“devicetree DTB input file(s)”,所以咱们拿 dtc 把树编过去再交。头一遍咱们拿的树,根上的 model 和 compatible 也都没写,核心 schema 立刻提了意见:

```output
good.dtb: /: 'compatible' is a required property
	from schema $id: http://devicetree.org/schemas/root-node.yaml
good.dtb: /: 'model' is a required property
	from schema $id: http://devicetree.org/schemas/root-node.yaml
```

提意见的是 root-node.yaml,它是 dtschema 自带的核心 schema 之一,管的是根节点:根上得报自己的 model 和 compatible。咱们给根补上两行,得到了好树的最终版 good.dts:

```dts
/dts-v1/;

/ {
	compatible = "acme,soc1000";
	model = "ACME Lab Board";

	#address-cells = <1>;
	#size-cells = <1>;

	serial@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
		clock-frequency = <115200>;
	};
};
```

```shell
dtc -I dts -O dtb -o good.dtb good.dts
dt-validate -s bindings/serial/acme,uart.yaml good.dtb
echo $?
```

```output
0
```

咱们见到的输出是空的,退出码也是稳定的 0,好树干干净净地过了。

病树一号咱们叫它 bad-missing.dts,它跟 good.dts 的差别只有一行。serial@1000 的身上没写 clock-frequency,dtc 编它的时候依旧沉默,咱们换 dt-validate 上场:

```shell
dtc -I dts -O dtb -o bad-missing.dtb bad-missing.dts
dt-validate -s bindings/serial/acme,uart.yaml bad-missing.dtb
```

```output
bad-missing.dtb: serial@1000 (acme,uart): 'clock-frequency' is a required property
	from schema $id: http://devicetree.org/schemas/serial/acme,uart.yaml
```

咱们把报错逐段读:bad-missing.dtb 是被验的文件,serial@1000 是被验的节点,括号里的 `acme,uart` 是它挂出的 compatible,中间那句说的是缺了必需属性 clock-frequency,from schema $id 指回了咱们写的 binding。谁、错在哪、按谁的约定判的,三样它都给齐了。dtc 一路沉默的毛病,到了这一层现了形。

病树二号管的是“属性没被允许”的毛病。咱们在好树的串口节点里多写一行 `clock_freq = <57600>;`,把 clock-frequency 的名字抄错了样子,存成了 bad-prop.dts。dtc 倒是照旧一声不吭,dt-validate 的反应是:

```output
bad-prop.dtb: serial@1000 (acme,uart): 'clock_freq' does not match any of the regexes: '^pinctrl-[0-9]+$'
	from schema $id: http://devicetree.org/schemas/serial/acme,uart.yaml
bad-prop.dtb: serial@1000 (acme,uart): clock_freq: b'\x00\x00\xe1\x00' is not of type 'object', 'integer', 'array', 'boolean', 'null'
	from schema $id: http://devicetree.org/schemas/dt-core.yaml
```

咱们看头一条,它报的就是正主:约定里没有 clock_freq 的名额,additionalProperties: false 把它拦下了,报错的措辞借了正则白名单的腔调,读出来的意思就是“这个属性名不在允许的范围里”。第二条是核心 schema 附赠的检查,它把值的类型也顺带对了一遍。属性名抄错了,在这层也藏不住了。

缺属性的、多写属性的两棵病树,到了这一层都现了形。可咱们还有一类老毛病没试:拼错的 compatible。它在 dt-validate 眼皮底下是什么待遇,咱们下一篇看。

## 本节自检

文章读完了,你拿六个小问题验一验自己,想好了再展开参考答案。

1. 咱们的 schema 为什么要放进 bindings/serial/ 子目录?当初文件直接放在 /tmp/vol5ch16 下的时候,dt-doc-validate 抱怨了什么?
2. $id 和 $schema 各是干什么的?
3. 咱们的最小 binding 里,required 和 additionalProperties: false 各管什么?
4. dt-validate 收的输入是什么?咱们每回都拿哪条命令把树编过去?
5. 头一遍验树,root-node.yaml 提了什么意见?咱们怎么补上的?
6. 病树一号的报错,谁、错在哪、按谁的约定判的,三样都给齐了吗?

<details>
<summary>参考答案(想好再展开)</summary>

1. 它抱怨 $id 里声称的路径,跟文件实际待的位置对不上。咱们把文件挪进 serial/ 子目录再跑就安静了。内核把全部的约定放在 Documentation/devicetree/bindings/ 之下,按类安了家,咱们学的就是它的目录规范。
2. $id 给 schema 一个正式的地址,别的 schema 想引用它的时候,认的就是这个地址。$schema 说的是它自己要遵守的元 schema,验 binding 自身写得合不合格,听元 schema 的。
3. required 列出缺了就报错的必需属性。additionalProperties: false 把 properties 里没列过的属性全部拦下,属性名抄错就藏不住了。
4. 收的是 DTB,帮助原文写的就是“devicetree DTB input file(s)”。咱们每回都拿 dtc 把 dts 编成 DTB,再交给 dt-validate。
5. 它说根上缺了 model 和 compatible。root-node.yaml 是 dtschema 自带的核心 schema 之一,管的是根节点。咱们给根补上两行,得到了好树的最终版 good.dts。
6. 都给齐了。bad-missing.dtb 是被验的文件,serial@1000 是被验的节点,括号里的 acme,uart 是它挂出的 compatible,中间那句说的是缺了必需属性 clock-frequency,from schema $id 指回了咱们写的 binding。

</details>

## 延伸阅读

本篇写 schema 的说法咱们都对过官方文档,出处咱们列在下面:

- [Writing devicetree bindings in json-schema](https://docs.kernel.org/devicetree/bindings/writing-schema.html):内核官方的 schema 写作文档,schema 的关键字族比咱们写的多得多,想看全的在这里看。

- [Writing devicetree bindings](https://docs.kernel.org/devicetree/bindings/writing-bindings.html):binding 设计层面的守则,“设备树长什么样”那篇就引过它,想写正经 binding 的时候按它过一遍。
