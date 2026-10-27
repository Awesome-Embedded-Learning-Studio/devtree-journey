import { defineConfig } from 'vitepress'
import { tableWrapPlugin } from './plugins/table-wrap-plugin'

// 内容源直接指向 documents/,site/ 只放配置,不拷贝内容。
// 文中链接指向 edtc 源码与 exercises 实验等 srcDir 之外的文件,先放开死链检查。
export default defineConfig({
  title: 'DeviceTree-Journey',
  description: '面向 Linux 与 U-Boot 的设备树学习与开发小仓库',
  // 项目页挂在 org.github.io/devtree-journey/ 子路径下,资源引用要带前缀
  base: '/devtree-journey/',
  srcDir: '../documents',
  ignoreDeadLinks: true,
  markdown: {
    // 设备树源码无原生 grammar,借 C 的语法表高亮
    languageAlias: { dts: 'c', dtsi: 'c' },
    // 注册空语法保留 output 语义标签(article-code.css 的终端输出卡片),照抄 tamcpp
    languages: [{ name: 'output', scopeName: 'text.output', patterns: [] }],
    // 表格卡片包装,article-table.css 的挂点(自 tamcpp 移植)
    config(md) {
      md.use(tableWrapPlugin)
    },
  },
  themeConfig: {
    nav: [
      { text: '第 0 卷 · 先认识设备树', link: '/vol0-introduction/1-why-device-tree' },
      { text: '第 1 卷 · 先用起来', link: '/vol1-first-use/1-first-change' },
    ],
    sidebar: {
      '/': [
        {
          text: '第 0 卷 · 先认识设备树',
          items: [
            { text: '1. 为什么需要设备树?', link: '/vol0-introduction/1-why-device-tree' },
            { text: '2. 设备树长什么样,谁跟它打交道?', link: '/vol0-introduction/2-shape-and-roles' },
            { text: '3. DTS、DTB、dtc 都是什么?', link: '/vol0-introduction/3-dts-dtb-dtc' },
            { text: '4. 谁会使用设备树?', link: '/vol0-introduction/4-who-uses-device-tree' },
          ],
        },
        {
          text: '第 1 卷 · 先用起来',
          items: [
            { text: '1. 改一个数,产物的字节动了哪里?', link: '/vol1-first-use/1-first-change' },
            { text: '2. 一个设备怎么写才算写得清楚?', link: '/vol1-first-use/2-names-and-values' },
            { text: '3. reg 里的数字怎么切?', link: '/vol1-first-use/3-cells-and-standard-props' },
            { text: '4. 一堆文件怎么分工才算管得住?', link: '/vol1-first-use/4-organize-across-files' },
            { text: '5. cpp 和 dtc 怎么接力,头文件去哪里找?', link: '/vol1-first-use/5-cpp-dtc-relay' },
            { text: '6. dtc 的告警和 __symbols__ 是给谁的,真实构建里谁在替咱们敲?', link: '/vol1-first-use/6-warnings-symbols-and-kbuild' },
          ],
        },
        {
          text: '第 2 卷 · 从字节到自己的树',
          items: [
            { text: '1. DTB 排成哪几块,前 40 个字节怎么亲手读出来?', link: '/vol2-bytes-to-tree/1-layout-and-hands-on' },
            { text: '2. 内存保留区在向谁报备什么,末尾两块的地盘怎么圈?', link: '/vol2-bytes-to-tree/2-mem-reserve-and-blocks' },
            { text: '3. 结构块里的记号怎么认,怎么用栈把整棵树读回来?', link: '/vol2-bytes-to-tree/3-tokens-and-stack-walk' },
            { text: '4. 补零补在哪几条缝里,坏产物能立起哪些防线?', link: '/vol2-bytes-to-tree/4-align-and-bad-blobs' },
            { text: '5. 一串字节,怎么变成我手里能查的树?', link: '/vol2-bytes-to-tree/5-tree-model-and-tree-py' },
            { text: '6. 引用怎么落地,解读的凭据立在哪儿?', link: '/vol2-bytes-to-tree/6-phandle-and-guessing' },
            { text: '7. 怎样证明读写没有改变内容,头一趟往返跑成什么样?', link: '/vol2-bytes-to-tree/7-acceptance-and-first-trip' },
            { text: '8. 怎样造出合法却不一致的 DTB?', link: '/vol2-bytes-to-tree/8-no-dedup' },
            { text: '9. 怎样跟参考实现对拍,writer 的设计与验收怎么立?', link: '/vol2-bytes-to-tree/9-diff-testing-and-writer-plan' },
          ],
        },
        {
          text: '第 3 卷 · U-Boot 与 Linux 如何消费设备树',
          items: [
            { text: '1. U-Boot 的两棵树怎么分清,control FDT 又从哪儿来?', link: '/vol3-consumers/1-uboot-two-trees' },
            { text: '2. 树里的节点,怎么变成干活的设备?', link: '/vol3-consumers/2-dm-bind-probe' },
            { text: '3. 同一道对表题差在哪,亲手编一棵 control FDT 是什么样子?', link: '/vol3-consumers/3-matching-diff-and-hand-build' },
            { text: '4. booti 的第三个参数交给了谁,跳进内核之前树又被改了什么?', link: '/vol3-consumers/4-booti-and-fixups' },
            { text: '5. 没有板子怎么亲眼看见改动,交接又按什么约定?', link: '/vol3-consumers/5-overlay-rehearsal-and-handoff' },
            { text: '6. Linux 何时读取 DTB?', link: '/vol3-consumers/6-kernel-first-read' },
            { text: '7. 第二遍读怎样把字节立成树,QEMU 生成的树里都躺着什么?', link: '/vol3-consumers/7-unflatten-and-virt-dump' },
            { text: '8. 树上的节点,怎么变成跑起来的设备?', link: '/vol3-consumers/8-populate-and-match' },
            { text: '9. 自己写个最小驱动能编过吗,别的总线又怎么走?', link: '/vol3-consumers/9-minimal-driver-and-buses' },
            { text: '10. 属性从哪里读,节点指针又归谁管?', link: '/vol3-consumers/10-property-read-and-refcount' },
            { text: '11. reg 怎样变成驱动能用的资源,中断号又从哪来?', link: '/vol3-consumers/11-address-and-irq' },
            { text: '12. 源码读完了,QEMU 里怎么对证,运行时的树又是什么样子?', link: '/vol3-consumers/12-qemu-boot-and-runtime-tree' },
          ],
        },
        {
          text: '第 4 卷 · 从自己的树到玩具 edtc',
          items: [
            { text: '1. 全量文法圈哪一块,词法器怎么切出记号?', link: '/vol4-toy-compiler/1-grammar-and-lexer' },
            { text: '2. 递归下降的语法器怎么把记号挂成树?', link: '/vol4-toy-compiler/2-parser' },
            { text: '3. 坏输入进来,报错怎么指着位置说话?', link: '/vol4-toy-compiler/3-bad-inputs' },
            { text: '4. 树模型怎么写回第一个 DTB,edtc 的前端怎么接手?', link: '/vol4-toy-compiler/4-writer-and-edtc-plan' },
            { text: '5. 引用为什么能写在标签前面?', link: '/vol4-toy-compiler/5-forward-references' },
            { text: '6. phandle 的号是谁分的,按什么顺序分?', link: '/vol4-toy-compiler/6-phandle-allocation' },
            { text: '7. 同一个引用回填出什么字节,写错的树怎么拦?', link: '/vol4-toy-compiler/7-backfill-and-errors' },
            { text: '8. __symbols__ 是什么,又是给谁的?', link: '/vol4-toy-compiler/8-symbols-and-edtc-plan' },
            { text: '9. 真树标本读出什么差距,扩展的队伍怎么排?', link: '/vol4-toy-compiler/9-specimens-and-extension-queue' },
            { text: '10. 玩具支持什么、拒绝什么,怎么写下来?', link: '/vol4-toy-compiler/10-matrix-and-rejection' },
            { text: '11. 拿 imx51-babbage 当试金石,扩展路线怎么排,第四卷怎么收工?', link: '/vol4-toy-compiler/11-touchstone-and-roadmap' },
          ],
        },
        {
          text: '第 5 卷 · 工程验证与排错',
          items: [
            { text: '1. 编译成功就代表写对了吗,检查员从哪儿请?', link: '/vol5-verification/1-dtc-silence-and-dtschema' },
            { text: '2. 一份最小的 binding 要写什么,好树病树各报什么?', link: '/vol5-verification/2-minimal-binding-and-validate' },
            { text: '3. 拼错的名字怎么又溜过去,内核树里校验怎么批量跑?', link: '/vol5-verification/3-unmatched-and-kernel-checks' },
            { text: '4. 板子定了型还想改树,引用的答案为什么推迟?', link: '/vol5-verification/4-fragments-and-fixups' },
            { text: '5. 电脑上缝树怎么用怎么验,标签对不上报什么错?', link: '/vol5-verification/5-fdtoverlay-and-apply-errors' },
            { text: '6. 板子的引导阶段与内核里怎么叠,三个位置怎么挑?', link: '/vol5-verification/6-uboot-kernel-positions' },
            { text: '7. 设备没工作从哪一层查起,产物旧了坏了怎么验?', link: '/vol5-verification/7-map-stale-and-broken-blob' },
            { text: '8. compatible 少个字母为什么没人拦,内核为什么理都不理?', link: '/vol5-verification/8-typo-and-enumeration' },
            { text: '9. 树没毛病为什么交出去的是另一棵,清单怎么收?', link: '/vol5-verification/9-wrong-tree-and-checklist' },
          ],
        },
      ],
    },
  },
})
