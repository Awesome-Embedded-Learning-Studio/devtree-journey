# Lab 05-bad-blobs:四个坏产物,换 dtc 的四句真报错

目的:在完好的 mini.dtb 上各动几处字节造出四种坏产物,连同完好对照一起喂给 `dtc -I dtb -O dts`,把参考实现拒绝坏产物的原话收下来,对应“补零补在哪几条缝里,坏产物能立起哪些防线?”一篇。坏产物本身不入库,复现命令就是本目录的全部家当。

- 源文件(仓库内唯一来源):`../../../edtc/example/00_bootstrap/mini.dts`,坏产物全部从它编出的 mini.dtb 改起
- 实际使用版本:dtc v1.8.1,2026-10-18 本机复现
- 四种坏法,每种只动一个地方:
  - `trunc200.dtb`:`head -c 200` 拦腰裁断,文件头声称 totalsize 0x125(293),磁盘上只剩 200 字节
  - `bad-magic.dtb`:第 0 字节 `d0` 改成 `ff`,魔数 `d00dfeed` 破了
  - `bad-struct-off.dtb`:偏移 8 的 off_dt_struct 从 `0000 0038` 改成 `0000 1000`,结构块的起点被指到产物外
  - `bad-opcode.dtb`:偏移 0x38 是结构块首记号,从 `FDT_BEGIN_NODE`(0x1)改成谁都不认的 0x7

## 复现命令(在本目录执行)

```shell
dtc -I dts -O dtb -o mini.dtb ../../../edtc/example/00_bootstrap/mini.dts
head -c 200 mini.dtb > trunc200.dtb
python3 -c 'd = bytearray(open("mini.dtb", "rb").read()); d[0] = 0xff; open("bad-magic.dtb", "wb").write(bytes(d))'
python3 -c 'import struct; d = bytearray(open("mini.dtb", "rb").read()); struct.pack_into(">I", d, 8, 0x1000); open("bad-struct-off.dtb", "wb").write(bytes(d))'
python3 -c 'import struct; d = bytearray(open("mini.dtb", "rb").read()); struct.pack_into(">I", d, 0x38, 0x00000007); open("bad-opcode.dtb", "wb").write(bytes(d))'
```

## 五次喂给 dtc 的原样输出

完好的对照先上,退出码 0,整棵树完好地回来了:

```console
dtc -I dtb -O dts mini.dtb; echo "exit=$?"
/dts-v1/;

/ {
	compatible = "edts,a_demo";
	#address-cells = <0x01>;
	#size-cells = <0x01>;

	serial@1000 {
		compatible = "acme,uart";
		reg = <0x1000 0x100>;
		clock-frequency = <0x1c200>;
		status = "okay";
	};
};
exit=0
```

四个坏产物挨个上,退出码全是 1:

```console
dtc -I dtb -O dts trunc200.dtb; echo "exit=$?"
FATAL ERROR: EOF before reading 293 bytes of DT blob
exit=1
dtc -I dtb -O dts bad-magic.dtb; echo "exit=$?"
FATAL ERROR: Blob has incorrect magic number
exit=1
dtc -I dtb -O dts bad-struct-off.dtb; echo "exit=$?"
FATAL ERROR: DT structure offset exceeds total size
exit=1
dtc -I dtb -O dts bad-opcode.dtb; echo "exit=$?"
FATAL ERROR: Device tree blob doesn't begin with FDT_BEGIN_NODE (begins with 0x00000007)
exit=1
```

四句报错各守一道防线:截断拦在按 totalsize 读整份产物那一步,连结构块的门都没摸到。魔数是进门的第一问,答不上就整个拒收。off_dt_struct 出界拦在结构块开工前,起点落在产物外直接判死。生面孔记号拦在结构块的第一句,dtc 认的头一个记号必须是 `FDT_BEGIN_NODE`,0x7 连报错里都原样印了出来。

验收:按上面的复现命令重造四个坏产物再各喂一次 `dtc -I dtb -O dts`,得到与上面相同的输出与退出码(对照 0,四个坏产物全 1),随后坏产物可随手删去。
