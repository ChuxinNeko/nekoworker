# 验证记录

验证日期：2026-10-22（UTC）。完整镜像为 Debian bookworm + XFCE/Xvfb + Firefox ESR，桌面服务以非 root 的 agent 用户运行。

| 检查 | 结果 |
| --- | --- |
| `make check` | Ruff 检查、格式检查通过；6 个单元测试通过 |
| `./scripts/test-desktop.sh` | 隔离 Xvfb / D-Bus 的真实 GTK 桌面测试通过 |
| `sudo ./scripts/up.sh` | Docker 镜像从源码构建，Compose 等待 healthy 后返回 |
| `sudo ./scripts/test-container.sh` | 最终镜像内 GTK、Firefox 和 noVNC 测试通过 |
| 容器内 stdio MCP SDK 客户端 | 初始化、11 个工具发现、真实 AT-SPI 树读取通过 |
| 容器强制重建 | `/workspace` 中写入的探测文件保留，验证后已删除 |
| 运行权限 | agent 用户、Privileged=false、CapDrop=ALL、no-new-privileges=true |

GTK 测试通过真实 MCP Streamable HTTP 客户端完成：拒绝无凭证请求、工具发现、应用启动、原生元素树、中文语义填写、按钮动作、过期 ID 拒绝、聚焦、Unicode 剪贴板粘贴、PNG 截图、窗口枚举/切换、拖拽、滚动和坐标按钮点击。

Firefox 测试从本地 HTML 文件读取原生 AT-SPI 网页输入框，再填写中文并通过新的元素树确认文本。Firefox 使用显式无障碍策略；原生 EditableText 调用无效时走聚焦/全选/粘贴回退。

noVNC 测试验证 HTML 页面、WebSocket Upgrade、RFB 3.8 握手，并确认服务只提供 VNC 密码认证类型，不提供无密码访问。未自动化浏览器中的 noVNC 登录交互，也未做所有应用/桌面环境的兼容性认证。

本机使用 sudo 访问 Docker socket；已有 Docker 权限的用户无需 sudo。首轮安装了 Docker Engine / Compose、AT-SPI、VNC 和开发测试所需系统包。当前环境的 Docker 由手动启动的 dockerd 运行，若宿主环境重启，需要按宿主机的服务管理方式重新启动 Docker。

## 无 Docker 模式

新增 `scripts/install-native.sh`（Ubuntu/Debian 依赖安装）和 `scripts/native.sh up/down/status/stdio`，启动独立的 Xvfb、D-Bus、XFCE、MCP 与 noVNC，全部服务以普通用户运行。默认端口为 8081/6081；内部 VNC 端口自动选择。凭证与工作文件位于 `.native/`，无文件系统或网络隔离。

本机已验证：4 个托管服务 RUNNING；HTTP MCP 真实 GTK 元素树、中文填写、语义按钮动作、截图、键鼠与窗口操作通过；noVNC WebSocket/RFB 密码握手通过；stdio 初始化、11 工具发现和元素树通过；停止后立即重新启动通过；持久化目录保留。修复了停止时端口 TIME_WAIT 被误判为仍在监听的问题。`make check` 的 6 个单元测试继续通过。宿主浏览器策略未修改，本机 Firefox 兼容性未单独复测。
