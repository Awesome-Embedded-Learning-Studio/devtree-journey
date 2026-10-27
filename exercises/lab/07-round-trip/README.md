# Lab 07-round-trip:DTB 进 DTB 出,逐字节一致与合法的不一致

目的:用本目录的 writer.py 对 mini.dtb 做一趟 DTB 进 DTB 出的往返,第一条路线开着字符串表去重,cmp 逐字节一致算满分,第二条路线关掉去重,造出一份合法但字节不一致的产物,请 dtc 反编译两边再交给 diff,验语义等价,对应“怎样证明读写没有改变内容,头一趟往返跑成什么样?”与“怎样造出合法却不一致的 DTB?”两篇。

- 工具(本目录):`writer.py`,读的一头把 DTB 立成树模型(节点、属性按产物次序、值是原始字节、保留区条目、boot_cpuid),写的一头把树摊回四块:头 40 字节、保留区、结构块、字符串块,四块首尾相接不留空隙,字符串按首次使用的次序收进表
- 源文件(仓库内唯一来源):`../../../edtc/example/00_bootstrap/mini.dts`
- 生成命令(在本目录执行):`dtc -I dts -O dtb -o mini.dtb ../../../edtc/example/00_bootstrap/mini.dts`
- 实际使用版本:dtc v1.8.1,Python 3.14.8,2026-10-18 本机复现

## 第一条路线:去重往返,cmp 一声不吭

```console
$ python3 writer.py round-trip mini.dtb mini-rt.dtb
mini-rt.dtb: 293 字节,保留区 0 条,字符串表去重
$ cmp mini.dtb mini-rt.dtb; echo "cmp exit=$?"
cmp exit=0
```

293 字节进去,293 字节出来,cmp 一个字节都没报。逐字节一致的来历是排布的自由度两边选了同一个答案:dtc 与咱们的 writer 都让四块首尾相接,字符串都按首次使用的次序收,重名字都只存一份。

## 第二条路线:关掉去重,字节分家,树没变

```console
$ python3 writer.py round-trip mini.dtb mini-nodedup.dtb --no-dedup
mini-nodedup.dtb: 304 字节,保留区 0 条,字符串表没去重
$ cmp mini.dtb mini-nodedup.dtb; echo "cmp exit=$?"
mini.dtb mini-nodedup.dtb differ: byte 8, line 1
cmp exit=1
$ wc -c mini.dtb mini-rt.dtb mini-nodedup.dtb
293 mini.dtb
293 mini-rt.dtb
304 mini-nodedup.dtb
890 total
```

多出的 11 字节是字符串表里的第二份 `compatible\0`(10 字符加结尾符),mini.dtb 里根节点与 serial@1000 各用一次这个名字,去重时只存一份,不去重就各存各的:

```console
$ xxd -s 0xe4 mini-nodedup.dtb
000000e4: 636f 6d70 6174 6962 6c65 0023 6164 6472  compatible.#addr
000000f4: 6573 732d 6365 6c6c 7300 2373 697a 652d  ess-cells.#size-
00000104: 6365 6c6c 7300 636f 6d70 6174 6962 6c65  cells.compatible
00000114: 0072 6567 0063 6c6f 636b 2d66 7265 7175  .reg.clock-frequ
00000124: 656e 6379 0073 7461 7475 7300            ency.status.
```

字节分了家,产物依然合法:规范只要求 PROP 的 nameoff 指向一个 `\0` 结尾的名字,名字存几份、按什么次序排,规范不管。语义等价请独立的裁判来验,拿 dtc 把两边各反编译一遍,再交给 diff:

```console
$ dtc -I dtb -O dts -o from-original.dts mini.dtb
$ dtc -I dtb -O dts -o from-nodedup.dts mini-nodedup.dtb
$ diff from-original.dts from-nodedup.dts; echo "diff exit=$?"
diff exit=0
```

diff 什么都没报,两份产物解出来的是同一棵树。字节一致是语义等价的加强版,第一条路线顺手拿到了,验收线定在语义等价,第二条路线才是真正考验收线的那一趟。

验收:重新执行生成命令与两条往返命令,`cmp` 一声不吭、`wc -c` 读数、反编译 diff 与上文记录相同(293、293、304,diff 退出码 0)。
