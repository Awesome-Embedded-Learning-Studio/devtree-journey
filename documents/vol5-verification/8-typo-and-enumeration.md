---
title: "compatible 少个字母为什么没人拦,内核为什么理都不理?"
volume: 5
chapter: 18
section: 2
order: 182
description: "binding 层的事故:uart 少个 t 的串在语法上合法,dtc 的退出码是 0,dtschema 装进独立 venv 后 dt-validate 又只校验对得上 schema 的节点,手误静默过了两道关,兜底是拿产物里的串跟 binding 的 const 逐字符对照。枚举与匹配层分两截讲:产物侧证据真跑,把 status 改成 disabled 的产物反编译留证,内核侧后果按机制推演并单独标注,依据是 of_platform_populate 与 of_device_is_available,有板的读者按指引补 dmesg 与 /proc/device-tree 的验证"
status: draft
---

# compatible 少个字母谁放行,内核为什么连设备都不造?

上一篇咱们验的都是产物本身,这一篇换了个问法:描述写得合不合约定?咱们看编译器的态度,再看校验工具的盲区,末了给一条谁也糊弄不过的兜底验法。

## binding 层:compatible 少个字母,编译器一声不吭

产物层与格式层考的是产物本身,binding 层考的是描述合不合约定,而 dtc 对约定一无所知。咱们把 mini.dts 里的 compatible 打错一个字母,uart 的尾巴上少个 t:

```shell
sed 's/"acme,uart"/"acme,uat"/' mini.dts > typo.dts
diff mini.dts typo.dts
```

```output
9c9
< 		compatible = "acme,uart";
---
> 		compatible = "acme,uat";
```

接着咱们编译打错的源码,看看编译器什么态度:

```shell
dtc -I dts -O dtb -o typo.dtb typo.dts
echo "exit=$?"
```

```output
exit=0
```

咱们在终端里看不到一个告警,echo 报出的退出码倒是 0。dtc 管的只是语法,打错的 `"acme,uat"` 在语法上是完全合法的字符串,手误就这么混过了编译。反编译咱们照样看得见它:

```shell
dtc -I dtb -O dts typo.dtb | grep acme
```

```output
		compatible = "acme,uat";
```

兜底的法宝是 binding。“编译成功就代表写对了吗”那章的主角就是它,咱们这里给 acme 的串口写一份最小 binding,compatible 就被咱们约定成一个定值:

```yaml
# SPDX-License-Identifier: GPL-2.0-only
%YAML 1.2
---
$id: http://devicetree.org/schemas/serial/acme,uart.yaml#
$schema: http://devicetree.org/meta-schemas/core.yaml#

title: ACME demo UART

maintainers:
  - DT Journey <course@example.invalid>

properties:
  compatible:
    const: acme,uart

  clock-frequency:
    type: integer

required:
  - compatible
  - clock-frequency

additionalProperties: true
```

有了 binding,咱们就能上校验工具。本机的系统 pip 受 PEP 668 管,咱们直接装会被它拒绝,于是把 dtschema 装进实验目录里的独立 venv:

```shell
python3 -m venv /tmp/vol5ch18/venv
/tmp/vol5ch18/venv/bin/pip install -q dtschema
/tmp/vol5ch18/venv/bin/dt-validate --version
```

```output
2026.9
```

校验用的 schema 要用 dt-mk-schema 加工一遍,咱们照办:

```shell
./venv/bin/dt-mk-schema acme,uart.yaml > processed-schema.json
```

咱们现在就造一个真违规的输入,把 mini.dts 的 clock-frequency 整行删掉再编译,让对上了约定却缺属性的产物过一遍校验:

```shell
sed '/clock-frequency/d' mini.dts > broken.dts
dtc -I dts -O dtb -o broken.dtb broken.dts
./venv/bin/dt-validate -p processed-schema.json broken.dtb
```

```output
broken.dtb: / (edts,a_demo): 'model' is a required property
	from schema $id: http://devicetree.org/schemas/root-node.yaml
broken.dtb: serial@1000 (acme,uart): 'clock-frequency' is a required property
	from schema $id: http://devicetree.org/schemas/serial/acme,uart.yaml
```

serial@1000 那一行就是咱们等的报错:节点的 compatible 对上了 `acme,uart` 的约定,required 里的 clock-frequency 却不见了。model 那两行是核心 schema 对每棵树都提的要求,咱们的演示树没写 model,所以它每回都要念叨,与串口的毛病无关。

转折在打错的产物身上。咱们把 typo.dtb 也送过同一条校验:

```shell
./venv/bin/dt-validate -p processed-schema.json typo.dtb
```

```output
typo.dtb: / (edts,a_demo): 'model' is a required property
	from schema $id: http://devicetree.org/schemas/root-node.yaml
```

serial 节点的报告一行都没有。原因在工具的工作方式:dt-validate 只校验 compatible 对得上某份 schema 的节点,手误的 `acme,uat` 对不上任何约定,节点就被静默放过了。咱们把教训记下:手误的 compatible 连校验器都骗得过,binding 层的兜底永远是拿产物里的串跟 binding 的约定逐字符对照:

```shell
dtc -I dtb -O dts typo.dtb | grep acme
grep "const:" acme,uart.yaml
```

```output
		compatible = "acme,uat";
    const: acme,uart
```

两行咱们摆在一起看,产物里的串是缺了尾巴的 `acme,uat`,binding 里的 const 还是完整的 `acme,uart`,差的就是那个 t。修复咱们照着 binding 把串改回去,重编的活儿也补上:

```shell
sed 's/"acme,uat"/"acme,uart"/' typo.dts > fixed.dts
dtc -I dts -O dtb -o fixed.dtb fixed.dts
dtc -I dtb -O dts fixed.dtb | grep "acme,u"
grep "const:" acme,uart.yaml
```

```output
		compatible = "acme,uart";
    const: acme,uart
```

修复前的产物跟 binding 的 const 差一个字母,修复后的两行就完全一致了。在真实的内核世界里,这个字母还牵着驱动的匹配表,少了尾巴上的 t,认这块设备的驱动就一个都不存在了,那个后果咱们放到下一层讲。

这一层的验法一句话:compatible 咱们要跟 binding 逐字符对照,编译器放行了不算数,校验器放行了同样不算数,对上约定的才算数。

少个 t 的后果咱们已经说过放到下一层讲,咱们这就把现场搬进内核,枚举与匹配的取证接着收。

## 枚举与匹配层:status 关着的节点,内核理都不理

到了枚举与匹配,现场就搬进内核了,咱们本机没有能启动的 aarch64 内核,手上也没接真正的板子,所以这一层咱们分两截讲:产物侧的证据真跑,内核侧的后果按机制推演,依据咱们逐条交代,推演的说法咱们都单独标注。

真实板子上它的典型长相是:树里查得到节点的身影,`/sys` 里却没有对应的设备,你在 dmesg 里连一行 probe 日志都搜不到。咱们把第一种成因做进产物里,关掉它的 status:

```shell
sed 's/status = "okay";/status = "disabled";/' mini.dts > off.dts
dtc -I dts -O dtb -o off.dtb off.dts
dtc -I dtb -O dts off.dtb | sed -n '/serial@1000/,/};/p'
```

```output
	serial@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
		clock-frequency = <0x1c200>;
		status = "disabled";
	};
```

产物侧的证据咱们拿到了:节点倒还在树里,compatible 也还是原来的 `acme,uart`,变的只有 status 的值。内核那边的事咱们只能推演,依据咱们备了两层。头一层是机制:内核在总线上枚举设备走的入口叫 of_platform_populate,它沿着容器节点逐个地造设备,造设备前的检查由 of_device_is_available 负责,它读节点的 status,值是 disabled 的时候,节点就被判成了不可用,所以设备根本不会被造出来。另一层是出处:内核官方的 usage model 文档在 Device Population 一节里写的就是这套流程,“节点怎样变成设备、匹配到驱动”那章里咱们把源码走读做完了,这里引用的函数名跟那章对得上。

compatible 对不上匹配表是同一层的另一种成因,咱们把上一层的 `acme,uat` 拖到内核里看它的下场:节点倒是可用,设备也造了,驱动的匹配表里却找不到 `acme,uat` 的影子,匹配这件事就落空了,probe 也就轮不上了。成因不同的两种毛病,症状倒是同一个:设备都缺席了。

有板子的读者可以把运行侧的验证补上,咱们本机没跑,给出的是排查指引:

```shell
cat /proc/device-tree/serial@1000/status
dmesg | grep -i serial
```

修复的动作就是把 status 改回去再重编,咱们真跑一遍:

```shell
sed 's/status = "disabled";/status = "okay";/' off.dts > on.dts
dtc -I dts -O dtb -o on.dtb on.dts
dtc -I dtb -O dts on.dtb | grep status
```

```output
		status = "okay";
```

产物侧的修复前后对照就是两次反编译:关着的时候 status 的值是 disabled,改回来就变回了 okay。运行侧的对照咱们如实标注为推演:换上 okay 的产物重启,咱们按机制推演,设备就该出现了,dmesg 里也应当看得到 probe 的记录,而验证它需要你手上的板子。

这一层的验法一句话:咱们在树里查节点,再查设备名单里的缺席,最后查 probe 日志里的驱动行踪,三样对上位了,断点在哪一环也就清楚了。

这一层的两截证据咱们都收了,还剩最后一层的事故,树倒是好好的,交到内核手里的却不是它。

## 本节自检

文章读完了,你拿六个小问题验一验自己,想好了再展开参考答案。

1. compatible 手误为什么骗过了 dtc,也骗过了 dt-validate?binding 层的兜底办法是什么?
2. model 那两行的报错为什么每回都来?它与串口的毛病有没有关系?
3. 造真违规的输入时,咱们删掉的是 mini.dts 的哪一行?等到的报错说的是哪一个节点?
4. status 值为 disabled 的节点,内核为什么连设备都不给它造?咱们引用了哪两个函数名?
5. status 关着与 compatible 对不上匹配表是同一层的两种成因,它们的症状有什么相同的地方?
6. 有板子的读者补运行侧的验证,咱们给的两条指引是什么?

<details>
<summary>参考答案(想好再展开)</summary>

1. dtc 管的只有语法,打错的串在语法上合法。dt-validate 只校验对得上 schema 的节点,`acme,uat` 对不上任何约定,节点被静默放过。兜底是拿产物里的串跟 binding 的 const 逐字符对照。
2. model 是核心 schema 对每棵树都提的要求,咱们的演示树没写 model,所以它每回都要念叨,与串口的毛病无关。
3. 删掉的是 mini.dts 里 clock-frequency 的整行,等到的报错说的正是 serial@1000 缺了 clock-frequency。
4. 入口是 of_platform_populate,造设备前的检查由 of_device_is_available 负责,它读节点的 status,读到 disabled 节点就被判成不可用,设备不造,匹配与 probe 都轮不到。
5. 症状是同一个,设备都缺席了,一个是设备根本没造,另一个是设备造了、匹配却落了空。
6. `cat /proc/device-tree/serial@1000/status` 与 `dmesg | grep -i serial`,咱们本机没跑,给出的是排查指引。

</details>

## 延伸阅读

枚举与匹配层的推演咱们标过出处,正本是内核的官方文档:

- [Linux and the Devicetree(内核官方 usage model)](https://docs.kernel.org/devicetree/usage-model.html):内核消费设备树的权威叙述,Device Population 一节讲的正是 of_platform_populate 与设备生成的链路,枚举与匹配层推演的出处在这里。
