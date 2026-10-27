---
title: "拼错的名字怎么又溜过去,内核树里校验怎么批量跑?"
volume: 5
chapter: 16
section: 3
order: 163
description: "bad-typo 只把 compatible 换成拼错的 acme,serail,dt-validate 一声不吭,因为 binding 拿 compatible 当钥匙,对不上就没有 schema 贴上去,开关 -m 把没人认领的 compatible 全打印出来,退出码不报错的实话也一并交代。内核树把同一件事做成了构建目标:make dt_binding_check 验约定自身,make dtbs_check 拿总 schema 批量验树,binding 带病时 dtbs_check 会跳过它,所以两个目标一起跑,DT_SCHEMA_FILES 缩小范围,末尾把 dtc 与 binding 校验两层叠着上的家底盘清,交给下一章的 overlay"
status: draft
---

# 拼错的名字怎么又溜过去,内核树里怎么批量验?

上一篇里两棵病树都挂得明明白白的,可头一篇里咱们亲手拼错的那个 compatible,还没在 dt-validate 的手里走过一遍。它的待遇怎么样?咱们把病树三号交给它。

## 拼错的名字又溜了,-m 把它请回来

病树三号就是拼错名字那类毛病的好树版:bad-typo.dts,跟 good.dts 只差 `compatible` 的值换成了 `acme,serail`。咱们把它编过去再交给 dt-validate:

```shell
dtc -I dts -O dtb -o bad-typo.dtb bad-typo.dts
dt-validate -s bindings/serial/acme,uart.yaml bad-typo.dtb
```

这一遍的输出是空的,拼错的名字又溜过去了。为什么?因为 binding 挑节点靠的就是 compatible:dt-validate 拿树上的 compatible 去对 schema 的 $id,const 对不上的时候,咱们手上就没有 schema 贴到那个节点身上,校验就直接跳过了。这个名字的拼错,恰好躲开了拿名字当钥匙的检查。

钥匙没配上的话,咱们手里还有一把 -m。它是帮助原文里的 show-unmatched,把没有任何 schema 认领的 compatible 都打印出来:

```shell
dt-validate -m -s bindings/serial/acme,uart.yaml bad-typo.dtb
```

```output
bad-typo.dtb: /: failed to match any schema with compatible: ['acme,soc1000']
bad-typo.dtb: /serial@1000: failed to match any schema with compatible: ['acme,serail']
```

第二行报的就是咱们等的正主:`acme,serail` 还没有哪份 schema 认领了它。头一行报的是根上的 `acme,soc1000`,咱们的 bindings 目录里只有一份串口 schema,根上的名字自然没人认领。内核全量跑的时候,树里成千上万的 compatible 绝大多数有正主认领,轮到 -m 报名字的,要么是拼错了,要么是新硬件还没写约定,两种情况咱们都该知道。所以咱们手动跑校验的时候,-m 这个开关是从来不省的。

还有一条咱们要如实记录:dt-validate 把错报得清清楚楚,退出码倒是 0,病树一号那遍咱们也顺手验过。咱们翻过装好的源码 dtb_validate.py,它的 main() 把诊断打印完就返回了,返回的时候,错误计数是没有捎带进退出码的。咱们想拿它写自动检查的脚本,判定要看的是输出,退出码的脸色倒是不作数。

手动跑校验的路数,到这儿就走全了。同一件事在内核树里做成了构建目标,批量地干,咱们接着认。

## 内核树里的校验目标:dt_binding_check 与 dtbs_check

“构建系统实际上做了什么”那章的末尾咱们预告过 dtbs_check,现在到了兑现的时候。前面咱们全程手敲,内核树把同一件事做成了构建目标,机制是这样的:

- make dt_binding_check 验的是约定自身。构建拿 dt-doc-validate 把 Documentation/devicetree/bindings/ 下的全部 YAML 对着元 schema 过一遍,谁的写法不合 binding 的章法,当场报出。
- make dtbs_check 验的是树。构建把配置选中的 dts 全部编成 DTB,再把全部 YAML 合成一份处理过的总 schema,拿 dt-validate 批量地验。
- 官方文档还提醒过一件事:binding 文件自身有错的话,dtbs_check 会跳过它,等于带着窟窿验树。所以两个目标要一起跑,命令就是 make dt_binding_check dtbs_check。
- 全量跑得久,文档给了 DT_SCHEMA_FILES 把范围缩小,比如 make dtbs_check DT_SCHEMA_FILES=trivial-devices.yaml 只拿一份 schema 验全部的树。

本章咱们手动跑的流程,其实就是同一件事的原样还原:验约定自身的那遍是 dt-doc-validate,合成总表的是 dt-mk-schema,验树的是 dt-validate。咱们本机没有内核树,不过机制咱们认下了,你要真在内核树上跑,官方文档里连步骤都写好了,出处咱们收进了延伸阅读。

## 两层检查叠着上,谁也替不了谁

第五卷开了头,咱们把家底盘一盘。dtc 的告警管的是通用结构,reg 的长度、地址与 reg 的搭配都在它的辖区里,认识串口的活儿它也不用干。binding 校验管的是一类硬件的约定,compatible 认不认、必需的属性齐不齐、属性集越没越界,前提是有人把约定写成了 schema。而且两层是叠着上的:树得过 dtc 的语法关编成 DTB,才有资格交到 dt-validate 的手里,语法关都过不了的树,根本到不了约定的跟前。

你在第四卷亲手造的那个玩具编译器,走的也是同一条线:语法过了,语义却没了人管。现在你知道该请谁补这一层了,也知道它算不上编译器的升级,它是编译器身后的另一位检查员。

校验补上了,描述也写得合了约定,不过板子有可能还是起不来,毛病就藏在了描述之外:驱动认不认、资源给没给对、硬件焊没焊。排错的活儿,咱们留给本卷后面的章节接着干。

## 下一章:描述在不同阶段叠加

咱们的工具箱还缺一件大活:树编好之后,还能不能改?开机流程的不同阶段里,描述是死的还是活的?“构建系统实际上做了什么”那章的末尾咱们见过 __symbols__ 的脸,当时说过它是给 overlay 备下的记号。下一章的题目是“怎样在不同阶段叠加修改?”,咱们到那章把 overlay 正式请出场:基础树、__symbols__ 和插件怎么接上,树是怎么一层层叠出来的,你都会亲手做一遍。

## 本节自检

文章读完了,你拿五个小问题验一验自己,想好了再展开参考答案。

1. 拼错的 compatible 为什么连 dt-validate 都不报?-m 干的是什么活?
2. 咱们实测里 dt-validate 报了错,退出码是多少?写脚本的人该怎么判?
3. make dt_binding_check 和 make dtbs_check 各验什么?官方文档为什么让两个一起跑?
4. 手动流程里,验约定自身、合成总表、验树的活各归哪位检查员?
5. 语法关都过不了的树,到得了约定的跟前吗?为什么?

<details>
<summary>参考答案(想好再展开)</summary>

1. binding 挑节点靠 compatible,名字拼错了,没有任何 schema 认领那个节点,校验就直接跳过了。-m 打印所有没人认领的 compatible,拼错的名字就现了形。
2. 退出码是 0。判定要盯着输出,不能只看退出码,咱们翻过 dtb_validate.py,它的 main() 从不把错误计数放进退出码。
3. dt_binding_check 拿元 schema 验 binding 自身,dtbs_check 拿合成的总 schema 验编出来的树。binding 文件自身有错时 dtbs_check 会跳过它,所以两个要一起跑。
4. 验约定自身的是 dt-doc-validate,把零散 YAML 合成总表的是 dt-mk-schema,拿 schema 验树的是 dt-validate。
5. 到不了。两层是叠着上的,树得过 dtc 的语法关编成 DTB,才有资格交到 dt-validate 的手里。

</details>

## 延伸阅读

本篇的机制叙述咱们都对过官方文档,出处咱们列在下面:

- [Writing devicetree bindings in json-schema](https://docs.kernel.org/devicetree/bindings/writing-schema.html):内核官方的 schema 写作文档,dt_binding_check 与 dtbs_check 的用法、DT_SCHEMA_FILES 的写法都在这里,本篇引用的内核侧说法出于此。
