# site/ · 站点配置

本目录只放 VitePress 的配置与主题,不放任何课程内容,组织方式参考 `Tutorial_AwesomeModernCPP` 的 `site/` 方案,但更轻:配置里 `srcDir` 直接指向 `../documents`,内容原地读取,没有同步脚本。喜欢直接读 markdown 的读者可以完全无视本目录。

- 开发预览:`pnpm dev`(仓库根目录执行)
- 构建:`pnpm build`,产物在 `site/.vitepress/dist/`
- 内容源:`documents/`,在网站看来是纯 markdown,构建不改动它
