---
layout: home
title: "欢迎来到设备树的世界!"
description: "面向 Linux 与 U-Boot 的设备树学习与开发小仓库"

hero:
  name: "DeviceTree-Journey"
  text: "设备树学习与开发小仓库"
  tagline: "既能顺着读下去,也能按问题查,还能亲手实现一条小型工具链。五卷正文已全部试写完毕(草稿),源码走读锁定 Linux v7.2.9 与 U-Boot v2026.10。"
  actions:
    - theme: brand
      text: 从第 0 卷开始读!
      link: /vol0-introduction/1-why-device-tree
    - theme: alt
      text: 来 GitHub 转转
      link: https://github.com/Awesome-Embedded-Learning-Studio/devtree-journey

features:
  - title: "第 0 卷 · 先认识设备树"
    details: "从让串口打出一个字符讲起,看清设备树长什么样、谁跟它打交道,再亲手把 DTS 编译成 DTB。四篇导读试写中。"
    icon: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="6" r="3"/><circle cx="19" cy="6" r="3"/><circle cx="12" cy="18" r="3"/><path d="M7 8l3.5 7"/><path d="M17 8l-3.5 7"/></svg>'
    link: /vol0-introduction/1-why-device-tree
    linkText: 开始阅读

  - title: "edtc · 亲手写工具链（WIP）"
    details: "仓库里的 C++ 工程,目标是实现一条小型设备树编译工具链。从最小可编译示例起步,跟课程文档同步生长。"
    icon: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 12-8.373 8.373a1 1 0 1 1-3-3L12 9"/><path d="m18 15 4-4"/><path d="m21.5 11.5-1.914-1.914A2 2 0 0 1 19 8.172V7l-2.26-2.26a6 6 0 0 0-4.202-1.756L9 2.96l.92.82A6.18 6.18 0 0 1 12 8.4V10l2 2h1.172a2 2 0 0 1 1.414.586L18.5 14.5"/></svg>'
    link: https://github.com/Awesome-Embedded-Learning-Studio/devtree-journey/tree/main/edtc
    linkText: 看源码

  - title: "实验 · exercises（WIP）"
    details: "每个实验自带命令与验收条件,照着走一遍就能复现。lab/00 到 lab/13 共十四组,从最小编译到毕业排错,当前验证过的工具版本是 dtc v1.8.1。"
    icon: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2v6a2 2 0 0 0 .245.96l5.51 10.08A2 2 0 0 1 18 22H6a2 2 0 0 1-1.755-2.96l5.51-10.08A2 2 0 0 0 10 8V2"/><path d="M6.453 15h11.094"/><path d="M8.5 2h7"/></svg>'
    link: https://github.com/Awesome-Embedded-Learning-Studio/devtree-journey/tree/main/exercises
    linkText: 进实验室
---
