# NekoWorker

给 AI Agent 使用的完整 Linux 桌面，支持 Docker 和无 Docker 的本机部署。通过 MCP 操作桌面应用、系统窗口、文件管理器、终端和浏览器；通过 AT-SPI 元素树提供纯文本模型可读的界面信息，通过 noVNC 供人实时观察和接管。

当前为单桌面 MVP。每个 Compose 项目启动一套独立桌面；不内置 LLM，也不绑定某个模型供应商。

## 不使用 Docker（Ubuntu / Debian）

```bash
./scripts/install-native.sh   # 首次安装依赖，需要 sudo；Python 环境属于普通用户
./scripts/native.sh up        # 普通用户启动，不使用 sudo
./scripts/native.sh status
./scripts/native.sh down      # 停止，保留文件
```

此模式创建独立 Xvfb 显示、D-Bus 会话、XFCE 桌面和应用配置目录。MCP 工具与 Docker 模式相同。默认地址为桌面 <http://127.0.0.1:6081/vnc.html> 和 MCP <http://127.0.0.1:8081/mcp>，可与 Docker 模式同时运行。凭证保存于 `.native/credentials.json`，文件/日志/桌面配置保存在权限为 700 的 `.native/`。工作目录为 `.native/workspace`。启动自动等待全部服务运行并通过健康检查。

```bash
./scripts/native.sh up --mcp-port 8082 --desktop-port 6082 --vnc-port 5902
./scripts/native.sh stdio     # Agent stdio 接入，复用该桌面的 X11 和 D-Bus
# 独立实例；--state-dir 放在 up / down / status / stdio 子命令之前
./scripts/native.sh --state-dir /tmp/neko-second up --mcp-port 8083 --desktop-port 6083 --vnc-port 5903
```

这是桌面会话隔离，**没有文件系统、进程或网络隔离**。应用以启动用户的权限运行，可以访问该用户的宿主机文件；单独设置 HOME 并不构成沙箱。需要安全边界但不想使用 Docker 时，可在独立用户或虚拟机内部署。

此安装脚本不改写宿主浏览器的系统策略，也不自动安装 Ubuntu 的 Snap Firefox。可自行安装浏览器；Firefox 要开启无障碍支持时，在该实例使用的浏览器配置中设置 `accessibility.force_disabled=-1`；Chromium/Electron 可使用 `--force-renderer-accessibility`。原生 GTK 应用无需这些浏览器配置。日志见 `.native/launcher.log` 与 `.native/*-stderr-*.log`。主机重启后需重新执行 `up`。

## Docker 一键部署

需要 Linux Docker Engine、Docker Compose v2、Python 3。首次构建需要联网下载 Debian、桌面及 Python 依赖，建议至少 2 核 / 4 GB 内存。

```bash
./scripts/up.sh
# 或 make up
```

首次自动创建权限为 600 的 `.env`，写入随机 MCP Token 和 VNC 密码。启动脚本等待容器健康检查通过后返回。

- 桌面：<http://127.0.0.1:6080/vnc.html>，输入 `.env` 中 `NEKO_VNC_PASSWORD`。
- MCP：<http://127.0.0.1:8080/mcp>，Streamable HTTP，使用 `Authorization: Bearer <NEKO_TOKEN>`。
- 健康检查：<http://127.0.0.1:8080/healthz>，检查 MCP 进程与 X11 连通性，不要求 Token；不代表每个应用的 AT-SPI 都正常。

```bash
docker compose logs -f
docker compose down           # 停止，保留桌面文件和工作区
docker compose up -d --wait    # 再次启动
# docker compose down -v 会删除持久数据，不用于日常停止
```

可参考 `.env.example` 调整分辨率、资源、端口、绑定地址和构建镜像源。启动后修改 `.env`，再运行 `docker compose up -d`。默认仅绑定宿主机回环地址。远程使用建议 SSH 转发两个端口；如自行开放监听，需自行配置 TLS 和网络访问控制。VNC 是传统八字符密码认证，无内置 TLS；MCP Token 可执行桌面用户权限内的任意程序，不应给不可信 Agent。容器没有宿主 Docker socket、特权模式或宿主目录挂载。

桌面用户为 UID 1000 的 `agent`，无 sudo。`/home/agent` 和 `/workspace` 是命名持久卷。应用可通过 `desktop_launch` 启动；安装额外系统包请修改 Dockerfile 后重建。

## Agent 接入

支持远程 MCP 的客户端通常可使用以下配置，字段名以客户端为准：

```json
{
  "mcpServers": {
    "nekoworker": {
      "url": "http://127.0.0.1:8080/mcp",
      "headers": {"Authorization": "Bearer <从 .env 读取 NEKO_TOKEN>"}
    }
  }
}
```

也可在已运行的桌面容器内用 stdio（复用 MCP 服务进程的 D-Bus 地址）：

```bash
docker compose exec -T desktop sh -c 'export DBUS_SESSION_BUS_ADDRESS="$(cat /tmp/runtime-agent/session-bus)"; exec nekoworker --transport stdio'
```

示例 MCP SDK 客户端见 [examples/client.py](examples/client.py)。

## 桌面能力

| 工具 | 用途 |
| --- | --- |
| `desktop_tree` | 读取应用元素树，包含 ID、父节点、角色、名称、状态、文本、边界、动作；按应用筛选，限制深度/节点数 |
| `desktop_element` | 按 ID 执行元素声明的动作，或 focus / set_text |
| `desktop_screenshot` | 返回整个桌面 PNG，供多模态模型补充观察 |
| `desktop_click` / `desktop_drag` / `desktop_scroll` | 桌面坐标键鼠操作 |
| `desktop_key` / `desktop_type_text` | X11 组合键、Unicode 剪贴板粘贴（含中文） |
| `desktop_windows` / `desktop_focus_window` | 列举与切换系统窗口 |
| `desktop_launch` | 启动任意桌面用户程序，参数列表不经 shell 展开 |

推荐循环：`desktop_tree → desktop_element → desktop_tree`。树返回的 `actions` 是应用真实声明的动作名称，不保证都叫 `click`。需要输入时优先 `set_text`（原生填入无效时自动聚焦、全选并粘贴，会改写剪贴板）；不可编辑元素可聚焦后 `desktop_type_text`。粘贴工具会改写剪贴板，终端通常用 `desktop_type_text(text="命令", paste_keys="ctrl+shift+v")`。应用状态变化异步发生，每次操作后需重新观察。

元素 ID 属于最近一次树快照，下次读取树会使旧 ID 失效。执行时还检查路径、角色、名称和应用 PID；这是尽力校验，界面在校验与动作之间仍可能变化，同名同角色的替换元素也无法完全识别。不要把 ID 当永久选择器。一个桌面只让一个 Agent 控制；并发客户端会共享焦点、剪贴板和快照。

## 元素树覆盖范围

使用系统 AT-SPI，无需注入浏览器 DOM。GTK 应用通常有较好的树；Firefox、Qt、Electron 的效果取决于应用的无障碍实现。镜像已设置 GTK/Qt 无障碍环境变量，并通过 Firefox 企业策略强制启用无障碍接口；Chromium/Electron 应用建议显式传入 `--force-renderer-accessibility`。自绘 Canvas、游戏、部分远程桌面应用可能没有可用元素，此时仍需要键鼠和截图；本项目不把这些界面虚构为可读元素。

树省略角色为 password text 的文本，但应用可能在其他元素中暴露敏感内容，截图也可能包含密码、个人数据。树按预算截断并明确返回 `truncated`；Firefox 等层级较深的应用可用 `max_depth=30` 并按应用筛选。每次操作在单独子进程中执行，默认 20 秒超时，避免一个应用的 D-Bus 卡住整个 MCP 服务。

## 实现结构

```text
Agent ── MCP HTTP + Bearer / stdio ── MCP 服务
                                       │ 限时工作进程
                                       ├─ AT-SPI → 原生应用元素树 / 语义动作
                                       ├─ X11 → 窗口 / 键鼠 / 截图
                                       └─ 应用进程 → 桌面用户权限
人 ── noVNC + VNC 密码 ── x11vnc ── 同一个 XFCE/Xvfb 桌面
```

所有服务使用同一用户、DISPLAY 和 D-Bus 会话。Supervisor 管理并重启进程，tini 回收孤儿。MCP 使用官方 Python SDK 的维护版本线 `mcp>=1.28,<2`；当前交付不包含多租户容器调度、录屏、OCR 或独立管理控制台。

参考了本地 Octop 的 `docker/Dockerfile`、`docker/docker-compose.yml` 和 `src/octop/infra/backend/docker_spec.py` 中的 Docker/Compose、持久化、健康检查和资源参数模式，桌面控制实现独立编写。来源及许可证见 [docs/attribution.md](docs/attribution.md)。

## 本地开发与验证

Linux 需安装 Xvfb、AT-SPI、GTK、D-Bus、xdotool、xclip、wmctrl。Python 虚拟环境必须能读取系统包（pyatspi / GI 不从 pip 安装）：

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e '.[dev]'
make check
./scripts/test-desktop.sh
```

集成测试在独立 Xvfb 和 D-Bus 会话启动 GTK 测试程序，用真实 MCP HTTP 客户端验证鉴权、工具发现、元素树、中文填写、按钮动作、截图、过期 ID 和键鼠粘贴。不会操作当前登录桌面。

容器集成验证：`./scripts/test-container.sh`，额外验证 noVNC WebSocket/RFB 密码握手与 Firefox 网页输入框的元素树和中文填写。Python 运行依赖已锁定在 `requirements.lock`，镜像构建从该文件安装。
