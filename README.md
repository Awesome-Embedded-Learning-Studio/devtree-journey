# DeviceTree-Journey

面向 Linux 与 U-Boot 的设备树学习与开发小仓库！

## 怎么读

你可以直接读 `documents/` 下的 markdown，也可以在本地起一个带排版的站点预览。在仓库根目录执行：

```shell
pnpm install
pnpm dev
```

命令跑通后，终端会打印本地预览地址，默认在 5173 端口，你用浏览器打开就能看到站点。要构建静态产物，你就运行 `pnpm build`，产物落在 `site/.vitepress/dist/`。

实验从 `exercises/lab/00-bootstrap` 开始，你照着每个实验自带的命令与验收条件走一遍就能复现。当前验证过的工具版本是 dtc v1.8.1，以各实验记录为准。

## 许可证

本仓原创内容采用 MIT 许可证，你可以在 [LICENSE](LICENSE) 读到全文。引入的第三方材料保留其原有许可证和来源，你在正文里能看到随文标注。
