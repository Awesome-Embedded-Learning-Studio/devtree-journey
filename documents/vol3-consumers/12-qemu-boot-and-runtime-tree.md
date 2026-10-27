---
title: "源码读完了,QEMU 里怎么对证,运行时的树又是什么样子?"
volume: 3
chapter: 12
section: 3
order: 12
description: "dumpdtb 拿参数对齐的参照树,没有 apt 就从 Debian 池子拉 6.12.95 的内核与 busybox,cpio 打一个只有 busybox 的 initramfs,补上 /bin/sh 才启动干净,启动日志与 guest 里的观察把源码读过的路一一对上,再把整棵运行时树传回主机拼回 DTB,of_core_init 把内存里的每个节点挂进 sysfs,节点变目录、属性变文件,/proc/device-tree 是 ABI 要求留下的符号链接,镜像里的字节就是驱动读到的字节,第三卷也在这里收卷交棒"
status: draft
---

# 源码读完了,QEMU 里怎么对证,运行时的树又是什么样子?

读完源码咱们再去 QEMU 里对证。实验那部分的内核、贴的日志、导出的运行时树,全部在本机真实地执行过,哪一步摔了跤咱们也照实写。

上一篇读过的路,这一篇全都派上用场:reg 的翻译、ranges 的窗口、中断的换号,咱们在真的启动日志里逐行找现场,运行时树的观察也顺路带回一程。实验的长链一气呵成,咱们从头走起。

## 在 QEMU 里把 6.12 的 arm64 内核跑起来

源码读完了,咱们去 QEMU 里对证。目标咱们定得实在:找一台 arm64 的虚拟机,内核得是 6.12 系列的,咱们跑起来看两样东西,启动日志里驱动消费设备树的现场,还有运行时树在用户空间的样子。本机的环境咱们照实交底:WSL2 里的 Arch Linux,qemu-system-aarch64 的版本是 11.1.2,dtc 的版本是 v1.8.1。计划里说好的 apt 路线在咱们的机器上走不了,`command -v apt-get apt dpkg` 的输出是空的,发行版里咱们找不到它们。咱们改走同一家软件池的直连路:包照旧从 Debian 的池子拉,只是拉的工具从 apt 换成 curl,解包用的工具是 bsdtar,咱们全程只下载不安装。咱们跑实验的日子是 2026-10-18,咱们的工作目录是 /tmp/vol3ch12。

### 拿参照树:dumpdtb 的路数接着用

“设备没工作,问题在哪一层”那章用 `-machine dumpdtb` 导出过 virt 机的树,咱们接着用同一路数。命令与导出的检查如下:

```shell
qemu-system-aarch64 -M virt -machine dumpdtb=virt.dtb -display none -serial none -nic none
ls -l virt.dtb
dtc -I dtb -O dts virt.dtb > virt.dts
```

导出的文件整整 1MiB,与那一章的数字全对得上:头部里的 totalsize 写着 0x100000,结构块的起点在 0x40、长度是 7092 字节,字符串块的长度是 569 字节,真正的树到第 7725 个字节就结束了,后面全是垫出来的零。咱们反编译回来,本章要用的几个节点是这样的:

```dts
/ {
	interrupt-parent = <0x8002>;
	model = "linux,dummy-virt";
	#size-cells = <0x02>;
	#address-cells = <0x02>;
	...
	pl011@9000000 {
		clock-names = "uartclk", "apb_pclk";
		clocks = <0x8000 0x8000>;
		interrupts = <0x00 0x01 0x04>;
		reg = <0x00 0x9000000 0x00 0x1000>;
		compatible = "arm,pl011", "arm,primecell";
	};
	...
	intc@8000000 {
		phandle = <0x8002>;
		compatible = "arm,cortex-a15-gic";
		interrupt-controller;
		#interrupt-cells = <0x03>;
		...
	};
```

这里咱们也踩了一个小失误,咱们照实记了下来:头一回导出用的全是默认的机器参数,正式启动时咱们给了 `-cpu cortex-a76 -smp 2 -m 1024M`,两份树的 phandle 编号就差了一位,根上的 `interrupt-parent` 一份写着 0x8002,另一份写的是 0x8003。参数对齐之后咱们重新导出,两边的数字才咬合。教训咱们就记一句:参照树与正式启动得出自同一套机器参数。

### 没有 apt 的机器,咱们从 Debian 池子拉包

内核包咱们挑了 Debian bookworm 的 backports 源,`linux-image-6.12.95+deb12-arm64`。实验跑在 6.12 系列的内核上,与锁定的 v7.2.9 不是同一个系列,好在咱们在日志里对证的那几条路,reg 的翻译、中断的换号、运行时树的镜像,两版之间的行为没有差别,内核的日志与源码的引文仍然对得上号。下载与解开的实录如下:

```shell
cd /tmp/vol3ch12
curl -fLO "https://deb.debian.org/debian/pool/main/l/linux/linux-image-6.12.95+deb12-arm64-unsigned_6.12.95-1~bpo12+1_arm64.deb"
curl -fLO "https://deb.debian.org/debian/pool/main/b/busybox/busybox-static_1.37.0-6+b9_arm64.deb"
mkdir -p deb-kernel/root deb-busybox/root
cd deb-kernel && bsdtar -xf linux-image-*.deb && bsdtar -xpf data.tar.xz -C root
cd ../deb-busybox && bsdtar -xf busybox-static_*.deb && bsdtar -xf data.tar.xz -C root
ls deb-kernel/root/boot
```

```output
vmlinuz-6.12.95+deb12-arm64
config-6.12.95+deb12-arm64
System.map-6.12.95+deb12-arm64
```

内核包与 busybox 的个头分别是 92MB 与 2MB,两个包咱们都只解开不安装。vmlinuz 是带 EFI 头的镜像,QEMU 11.1.2 的 `-kernel` 选项直接认它,咱们不用再剥壳。busybox 是静态链接的 arm64 程序,拿它给 guest 搭一个最小的用户空间。

### 打一个只有 busybox 的 initramfs

initramfs 的搭法很朴素,咱们把 busybox 与 init 脚本摆好,再拿 cpio 打包就成了:

```shell
cd /tmp/vol3ch12
mkdir -p initramfs/bin initramfs/proc initramfs/sys initramfs/dev
cp deb-busybox/root/usr/bin/busybox initramfs/bin/busybox
ln -s busybox initramfs/bin/sh
```

`init` 的内容咱们挑关键的看,完整的活儿是挂上 proc 与 sysfs、打印咱们要的观察项,结尾再补一条关机的命令:

```sh
#!/bin/sh
/bin/busybox mount -t proc proc /proc
/bin/busybox mount -t sysfs sys /sys
echo ===BEGIN-OBS===
/bin/busybox readlink /proc/device-tree
/bin/busybox hexdump -C /proc/device-tree/pl011@9000000/reg
/bin/busybox hexdump -C /proc/device-tree/pl011@9000000/interrupts
...
/bin/busybox poweroff -f
```

咱们打包与启动的命令如下:

```shell
cd initramfs
find . -print0 | cpio --null -o -H newc -R 0:0 | gzip -1 > ../rootfs.cpio.gz
cd ..
qemu-system-aarch64 -M virt -cpu cortex-a76 -smp 2 -m 1024M \
	-kernel deb-kernel/root/boot/vmlinuz-6.12.95+deb12-arm64 \
	-initrd rootfs.cpio.gz \
	-append "earlycon console=ttyAMA0 loglevel=7" \
	-no-reboot -display none -monitor none -serial file:boot.log -nic none
```

### 头一回启动,内核说找不着 /init

第一回咱们打的包里忘了放 `/bin/sh`,内核把日志打完就摔在了起跑线:

```output
[    0.967584] Run /init as init process
[    0.968064] Failed to execute /init (error -2)
[    0.968838] Kernel panic - not syncing: No working init found.  Try passing init= option to kernel. See Linux Documentation/admin-guide/init.rst for guidance.
```

`/init` 在包里躺得好好的,error -2 报的却是找不着文件,咱们查了才明白:`init` 脚本的头一行写着 `#!/bin/sh`,内核执行脚本的时候,它要的头一件事就是把解释器打开,包里偏偏没有 `/bin/sh`,报的缺的就是它。补上指向 busybox 的符号链接重打包,第二回就干净地跑到了关机,日志的结尾是 “reboot: Power down”。

### 跑通之后,日志里全是这一章的内容

启动日志的开头几行,咱们逐行认一认出处:

```output
[    0.000000] Linux version 6.12.95+deb12-arm64 (debian-kernel@lists.debian.org) (aarch64-linux-gnu-gcc-12 (Debian 12.2.0-14deb12u1) 12.2.0, GNU ld (GNU Binutils for Debian) 2.40) #1 SMP Debian 6.12.95-1~bpo12+1 (2026-07-05)
[    0.000000] Machine model: linux,dummy-virt
[    0.000000] earlycon: pl11 at MMIO 0x0000000009000000 (options '')
[    0.000000] printk: legacy bootconsole [pl11] enabled
[    0.000000] psci: probing for conduit method from DT.
[    0.000000] psci: PSCIv1.1 detected in firmware.
```

命令行里咱们只写了一个 `earlycon`,内核却知道串口的住址是 0x09000000,依据是树上 chosen 节点里的 `stdout-path`,它指着的正是 `/pl011@9000000`。`Machine model` 打的 `linux,dummy-virt` 是根上 model 属性的原文,psci 那两行说的是固件接口的探测也从树上取的路由。再看消费侧最直接的一行:

```output
[    0.280079] 9000000.pl011: ttyAMA0 at MMIO 0x9000000 (irq = 13, base_baud = 0) is a PL011 rev1
```

这一行咱们前后都对上了:MMIO 0x9000000 是 `reg` 经 `of_address_to_resource` 翻译再映射后的地址,irq = 13 是 `interrupts = <0x00 0x01 0x04>` 经 `of_irq_get` 的链子换回来的虚拟中断号,咱们在源码里读过的两条路,在日志里各留下了一个数。`ranges` 的消费也有现场,PCI 主桥的驱动把窗口逐条打了出来:

```output
[    0.534408] pci-host-generic 4010000000.pcie: host bridge /pcie@10000000 ranges:
[    0.534919] pci-host-generic 4010000000.pcie:       IO 0x003eff0000..0x003effffff -> 0x0000000000
[    0.535430] pci-host-generic 4010000000.pcie:      MEM 0x0010000000..0x003efeffff -> 0x0010000000
```

桥节点 `ranges` 里的每条窗口,驱动用 `of_range` 的迭代器读出来再打印,咱们在上一篇末尾点过的名字,在这里跑给你看了。guest 里跑的观察咱们也贴上实录:

```output
--- readlink-proc-device-tree
/sys/firmware/devicetree/base
--- pl011-reg
00000000  00 00 00 00 09 00 00 00  00 00 00 00 00 00 10 00  |................|
00000010
--- pl011-interrupts
00000000  00 00 00 00 00 00 00 01  00 00 00 04              |...............|
0000000c
```

咱们把字节逐项对上:`reg` 的 16 个字节用大端排着,头两个 cell 拼出的地址是 0x09000000,后两个 cell 给出的长度是 0x1000,与 dumpdtb 里的 `<0x00 0x9000000 0x00 0x1000>` 一个字都不差。`interrupts` 的 12 个字节就是三个 cell 的本体,驱动拿 `of_property_read_u32_index` 逐个读出来的也正是它们。

### 把整棵运行时树传回主机,拼回 DTB

guest 里咱们能看几个文件,咱们干脆把整棵树搬回主机。串口是现成的通道,咱们把树打包压缩再 base64,顺着日志就传了出来:

```sh
/bin/busybox tar cf - -C /proc/device-tree . | /bin/busybox gzip | /bin/busybox base64
```

主机这一边从日志里裁出 base64 的段落,解码与解包都做完了,咱们拿 dtc 从目录拼回 DTB:

```shell
sed -n '/===BEGIN-TARBALL-B64===/,/===END-TARBALL-B64===/p' boot.log | sed '1d;$d' | tr -d '\r\n' | base64 -d | gzip -d | bsdtar -xf - -C runtime-tree
dtc -I fs -O dtb -o runtime-tree.dtb runtime-tree
ls -l runtime-tree.dtb virt.dtb
```

```output
.rw-r--r-- 8.1k  runtime-tree.dtb
.rw-r--r-- 1.0M   virt.dtb
```

拼回的 DTB 是 8.1KB,装的都是树的真内容,没有 QEMU 垫的那 1MiB 零。咱们把它与参数对齐的参照树各自反编译再对,数值全都咬上了:pl011 的 reg、interrupts,GIC 的三格声明,platform-bus 的 ranges,phandle 的编号,五项咱们全对上了。出入剩下的只有顺序,sysfs 的目录项按名字排序回读,QEMU 的原版按生成的次序写,两份树同一个内容不同的排法。dtc 从目录读树时对 phandle 引用发了几条警告,那是它在目录输入下不维护引用表的局限,产物里的数值原样都在,反编译回来的结果照样能读。镜像里的每个节点还多带一个 `name` 文件,dtc 拼回时把它略掉了,产物里也没有 name 的属性。这套往返证明的事很实在:运行时的那棵树,内容完整地活着,而且能还原成 DTB 的形状。

### 模块实验还差的环境,咱们照实说

规划里本章还想在 guest 里跑一个自己编的模块,这步咱们没能走完,缺的东西咱们开个清单。guest 侧要有匹配 6.12.95+deb12-arm64 的构建环境,aarch64 的交叉编译器加内核头,本机的发行版是 Arch,没有现成的 aarch64 工具链。编出来的模块还得塞进 initramfs,进了 guest 才有轮到 insmod 的机会。示意代码咱们在 x86 这头做过编译检查,借的是“节点怎样变成设备、匹配到驱动”那章留下的 WSL 内核树,一回就编过了:

```output
  CC [M]  acme_res.o
  MODPOST Module.symvers
  CC [M]  acme_res.mod.o
  CC [M]  .module-common.o
  LD [M]  acme_res.ko
```

编译检查用的内核是 6.18.33.2 的 WSL 内核,接口与 v7.2.9 的一致,加载与 probe 的现场咱们不装样子,留给环境补齐的实验。

实验走完了,咱们把树也传回来拼成了 DTB,可 guest 里 readlink 的指向还没交代。/proc/device-tree 与 /sys/firmware/devicetree/base 的关系,内存里的树与镜像的关系,咱们接着把运行时树的机关说完,第三卷的收卷也在这里交棒。

## 运行时树:/proc/device-tree 是内存里那棵树的镜像

guest 里的 `readlink` 输出咱们再单独看,它指的方向藏着运行时树的全部机关。v7.2.9 的源码里,`/proc/device-tree` 的本尊是个符号链接,创建它的代码在 `drivers/of/base.c` 的 `of_core_init` 里:

```c
void __init of_core_init(void)
{
	struct device_node *np;
	...
	of_kset = kset_create_and_add("devicetree", NULL, firmware_kobj);
	...
	for_each_of_allnodes(np) {
		__of_attach_node_sysfs(np);
		...
	}
	...
	/* Symlink in /proc as required by userspace ABI */
	if (of_root)
		proc_symlink("device-tree", NULL, "/sys/firmware/devicetree/base");
}
```

真身的住址是 `/sys/firmware/devicetree/base`,`of_core_init` 把内存里的每个节点都过了一遍 `__of_attach_node_sysfs`,节点变成了目录,属性变成了普通文件,文件里装的就是属性值的字节。`/proc/device-tree` 是给用户空间留的老地址,注释里说明它是 ABI 的要求,两个名字指的是同一份镜像。咱们 guest 里 `ls /proc/device-tree` 看到的串口、中断控制器、virtio 设备,目录的形状与 DTB 反编译出来的树一模一样,chosen 里还多了一段 QEMU 注入的 `bootargs`,内容就是咱们 `-append` 给的那串参数。

镜像与 DTB 文件的关系,咱们一句话说准:DTB 是启动时传进来的字节流,内核把它摊开成内存里的 device_node 树,树才是内核活着时真正用的数据,镜像又把同一份数据摆回文件系统的形状给咱们看。所以从镜像原则上能拼回一份 DTB,咱们也真拼成了,拼回的产物与原版内容一致而排法不同。用它调试的姿势也顺理成章:在板子上咱们 `hexdump -C /proc/device-tree/<节点>/reg`,看到的字节就是驱动读到的字节,树传对了没有、fixup 改了没改,咱们当场就能验。

## 收卷:第三卷走完,交棒下一卷

第三卷的行程到这里走完了。U-Boot 侧咱们看了两篇,“U-Boot 自己也用设备树吗”那章分清了 control FDT 与 working FDT 的差事,“传给 Linux 的 DTB 是哪一份”那章跟上了启动命令的路径,把交给内核的那棵树追到了传递约定。Linux 侧咱们看了三篇,“Linux 何时读取 DTB”那章看着树在内存里立了起来,“节点怎样变成设备、匹配到驱动”那章看完了节点变设备、驱动对上号,到了本章咱们再往下,驱动把地址、中断、属性一样样读了走。导读卷的“谁会使用设备树”那篇里说过的消费方,咱们在锁定的源码版本里从接树到用树走了个通盘,消费链的故事讲完整了。

下一卷的名字是“从自己的树到玩具 edtc”。第二卷的“从字节到自己的树”咱们从 DTB 的字节里读出过树,第四卷从源码那一头写起:解析 DTS 的活归咱们,标签和引用怎样变成二进制的活也归咱们,再一步步逼近真实的输入。等到咱们的小编译器产出第一个 DTB,咱们拿真正的内核加载它,这一卷读过的消费链就是验货的尺子。咱们下一卷见。

## 本节自检

文章读完了,你拿下面的小问题验一验自己,想好了再展开参考答案。

1. 头一回启动,`/init` 明明在包里,内核为什么报 error -2?补了什么才跑通?
2. 头一回导出的参照树与正式启动的树,phandle 的编号差了一位,问题出在哪里?教训是哪一句?
3. 整棵运行时树怎样从 guest 传回主机?主机一侧又拿什么拼回 DTB?
4. 规划里想在 guest 里跑自己编的模块,这一步为什么没走完?缺的东西有哪些?
5. `/proc/device-tree` 与 `/sys/firmware/devicetree/base` 是什么关系?从镜像拼回的 DTB 与原版会有哪些不同?
6. 在板子上想验树传对了没有、fixup 改了没改,咱们当场能做什么?
7. DTB 文件、内存里的 device_node 树、用户空间的镜像,三者的关系用原文的话怎么说?

<details>
<summary>参考答案(想好再展开)</summary>

1. `init` 脚本的头一行写着 `#!/bin/sh`,内核执行脚本的时候,它要的头一件事就是把解释器打开,包里偏偏没有 `/bin/sh`,报的缺的就是它。补上指向 busybox 的符号链接重打包,第二回就干净地跑到了关机。
2. 两份树用的机器参数不一样,一份是默认参数,正式启动给了 `-cpu cortex-a76 -smp 2 -m 1024M`。参数对齐之后重新导出,两边的数字才咬合。教训就是参照树与正式启动得出自同一套机器参数。
3. 串口是现成的通道,咱们把树打包压缩再 base64,顺着日志就传了出来。主机这一边从日志里裁出 base64 的段落,解码与解包都做完了,再拿 dtc 从目录拼回 DTB。
4. guest 侧要有匹配 6.12.95+deb12-arm64 的构建环境,aarch64 的交叉编译器加内核头,本机的发行版是 Arch,没有现成的 aarch64 工具链。编出来的模块还得塞进 initramfs,进了 guest 才有轮到 insmod 的机会。示意代码咱们在 x86 这头做过编译检查,借的是“节点怎样变成设备、匹配到驱动”那章留下的 WSL 内核树。
5. 前者是后者的符号链接,真身挂在 sysfs,创建的代码在 `of_core_init`,给 /proc 留链接是用户空间 ABI 的要求。拼回的 DTB 内容一致而顺序不同,镜像按名字排序回读,原版按生成顺序写,name 一类的镜像附产物也不会进产物。
6. 在板子上咱们 `hexdump -C /proc/device-tree/<节点>/reg`,看到的字节就是驱动读到的字节,树传对了没有、fixup 改了没改,咱们当场就能验。
7. DTB 是启动时传进来的字节流,内核把它摊开成内存里的 device_node 树,树才是内核活着时真正用的数据,镜像又把同一份数据摆回文件系统的形状给咱们看。

</details>

## 延伸阅读

内核官方文档与本章核对过的源码,给你备好了:

- [Linux and the Devicetree](https://docs.kernel.org/devicetree/usage-model.html):内核消费设备树的官方用法说明,设备登记与匹配的图景在这里,本卷后三章的官方对照。
- 源码核对清单,全部拉自 <https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/> 加路径再加 ?h=v7.2.9:include/linux/of.h、include/linux/property.h、include/linux/fwnode.h、include/linux/of_address.h、include/linux/of_irq.h、drivers/of/base.c、drivers/of/address.c、drivers/of/irq.c、drivers/of/dynamic.c、drivers/of/kobj.c、drivers/of/fdt.c、drivers/of/property.c、drivers/base/platform.c。

咱们本章的源码引文全部在 Linux v7.2.9 核对,QEMU 实验用的内核是 Debian 打包的 6.12.95+deb12-arm64,模拟器的版本是 QEMU 11.1.2,验证的日子是 2026-10-18。
