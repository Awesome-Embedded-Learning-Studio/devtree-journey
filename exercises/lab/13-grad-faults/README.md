# Lab 13-grad-faults:五层排查卡片,病在哪一层

目的:毕业实验,五层各埋一个小故障,做成排查卡片,每层给现象一句话、取证命令一条、修复动作一句话,对应讲义“设备没工作从哪一层查起,旧产物与坏产物怎么验?”、“compatible 少个字母谁放行,内核为什么连设备都不造?”与“交出去的为什么是另一棵树,带走的清单长什么样?”。

- 实际使用版本:dtc v1.8.1,dt-validate 2026.9(`pip3 install --user --break-system-packages dtschema` 装进 `~/.local`),2026-10-18 本机复现
- 板子与输入(本目录):A 板的 `board-a-old.dts` 与 `board-a.dts` 只差 clock-frequency 一行(115200 改 9600),`board-a-stale.dtb` 是改动之前编的产物,B 板 `board-b.dts` 的串口住在 0x2000,binding 是 `bindings/serial/acme,uart.yaml`
- 病树与损伤产物的生成(在本目录执行):

```shell
dtc -I dts -O dtb -o board-a-stale.dtb board-a-old.dts
sed 's/clock-frequency = <115200>;/clock-frequency = <9600>;/' board-a-old.dts > board-a.dts
dtc -I dts -O dtb -o board-a.dtb board-a.dts
head -c 200 board-a.dtb > board-a-cut.dtb
sed '/clock-frequency/d' board-a.dts > board-a-noclock.dts
dtc -I dts -O dtb -o board-a-noclock.dtb board-a-noclock.dts
sed 's/status = "okay";/status = "disabled";/' board-a.dts > board-a-off.dts
dtc -I dts -O dtb -o board-a-off.dtb board-a-off.dts
dtc -I dts -O dtb -o board-b.dtb board-b.dts
```

## 卡片一 构建产物层:改了源码没重编

- 现象:板 A 的波特率改成了 9600,设备的表现纹丝不动
- 取证(在本目录执行):`dtc -I dtb -O dts board-a-stale.dtb | grep clock-frequency`

```output
		clock-frequency = <0x1c200>;
```

产物里还是旧值,0x1c200 换算回来是 115200,而 board-a.dts 里写的已经是 9600,交出去的是一份旧产物。

- 修复:把缺的那次编译补上(`dtc -I dts -O dtb -o board-a.dtb board-a.dts`),同一条取证在 board-a.dtb 上报 `<0x2580>`,换算回来正是 9600

## 卡片二 格式层:产物被截断,读它的一方拒收

- 现象:拷贝时缺了尾巴的产物,机器起不来,读它的 dtc 当场拒收
- 取证:`dtc -I dtb -O dts board-a-cut.dtb`

```output
FATAL ERROR: EOF before reading 331 bytes of DT blob
```

头部里的 totalsize 写着整棵树 331 字节,文件只剩 200 字节,dtc 照头部报的数去读,读到末尾还差,于是报了 EOF,退出码 1。

- 修复:把完整的 board-a.dtb 重新交过去,交之前拿同一条反编译自己验读,读得出开头五行才算完整

## 卡片三 binding 层:缺了必需属性,dt-validate 抓住

- 现象:串口节点少写了 clock-frequency,dtc 一声不吭,校验器一开口才见病
- 取证:`dt-validate -s bindings/serial/acme,uart.yaml board-a-noclock.dtb`

```output
board-a-noclock.dtb: serial@1000 (acme,uart): 'clock-frequency' is a required property
	from schema $id: http://devicetree.org/schemas/serial/acme,uart.yaml
```

紧跟的 `echo $?` 报 0,dt-validate 不把错误计数捎进退出码,脚本判定盯输出。

- 修复:把 clock-frequency 补回去重编,补齐的 board-a.dtb 过同一条校验,输出为空

## 卡片四 枚举与匹配层:status 关着,内核理都不理

- 现象:树里查得到节点,设备名单里却缺席(内核侧按机制推演,of_platform_populate 枚举时 of_device_is_available 读到 disabled 就不造设备,本机没板,未实测)
- 取证:`dtc -I dtb -O dts board-a-off.dtb | grep status`

```output
		status = "disabled";
```

- 修复:把 status 改回 okay 重编,board-a.dtb 的同一条 grep 报 `status = "okay";`

## 卡片五 传递层:交出去的是另一棵树

- 现象:板 B 烧进了板 A 的产物,串口没了动静
- 取证:`for f in board-a.dtb board-b.dtb; do echo "== $f"; dtc -I dtb -O dts $f | grep -m1 model; done`

```output
== board-a.dtb
	model = "ACME Board A";
== board-b.dtb
	model = "ACME Board B Rev 2";
```

大小也分得出两份:wc -c 报 331 与 335。file(1) 把两份都认成 Device Tree Blob version 17,分得出大小、分不出板子,身份的定论要靠反编译里的 model 与串口地址(板 B 的 serial@2000 住在 0x2000)。

- 修复:换回 board-b.dtb,烧写前拿这条取证核对 model 与板子对得上

验收:重新执行上文的生成命令,各卡取证输出与上文记录相同。
