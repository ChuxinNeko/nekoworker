# 来源说明

部署设计参考用户提供的 `/home/ubuntu/Octop` 本地源码，主要参考 Dockerfile、Compose 的资源/卷/环境变量/健康检查配置方式。未复制其业务实现；NekoWorker 的 AT-SPI、X11、MCP 和进程启动实现为本项目新增。上游镜像标签中声明的地址为 https://github.com/TencentCloud/orca ，未将该地址视为当前本地检出的版本来源证明。

为保留上游权利声明，附本地 Octop LICENSE 原文：

```
MIT License

Copyright (c) 2026 Octop

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

```

接口参考：

- [MCP 官方 Python SDK v1 文档](https://py.sdk.modelcontextprotocol.io/v1/)
- [GNOME AT-SPI Accessible 接口](https://gnome.pages.gitlab.gnome.org/at-spi2-core/devel-docs/doc-org.a11y.atspi.Accessible.html)
- [Mozilla Firefox Preferences 企业策略](https://firefox-admin-docs.mozilla.org/reference/policies/preferences/)
