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
    languageAlias: { dts: 'c' },
    // 注册空语法保留 output 语义标签(article-code.css 的终端输出卡片),照抄 tamcpp
    languages: [{ name: 'output', scopeName: 'text.output', patterns: [] }],
    // 表格卡片包装,article-table.css 的挂点(自 tamcpp 移植)
    config(md) {
      md.use(tableWrapPlugin)
    },
  },
  themeConfig: {
    nav: [
      { text: '第 0 卷 · 先认识设备树', link: '/vol0-introduction/01-why-device-tree' },
    ],
    sidebar: {
      '/': [
        {
          text: '第 0 卷 · 先认识设备树',
          items: [
            { text: '0.1 为什么需要设备树?', link: '/vol0-introduction/01-why-device-tree' },
            { text: '0.2 设备树长什么样,谁跟它打交道?', link: '/vol0-introduction/02-shape-and-roles' },
            { text: '0.3 DTS、DTB、dtc 都是什么?', link: '/vol0-introduction/03-dts-dtb-dtc' },
          ],
        },
      ],
    },
  },
})
