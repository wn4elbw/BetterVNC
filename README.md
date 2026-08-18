# webvnc — Windows 远程管理工具

webvnc 是一个单文件、跨平台的远程管理工具，内置纯 Python 实现的 VNC Server，并集成
HTTPS 文件管理器和命令行终端。在 Windows 上运行后，即可通过浏览器远程查看和控制本机屏幕、
管理文件、执行命令，无需安装任何外部软件（如 TigerVNC、x11vnc、websockify 等）。

> 本项目基于 [noVNC](https://github.com/novnc/noVNC)（MPL-2.0）构建，使用其网页客户端前端，
> 后端由本仓库自带的 `webvnc.py` 提供 VNC Server、HTTPS 服务、文件管理与命令执行能力。

## 功能特性

- **自带 VNC Server**：纯 Python 实现 RFB 003.008 协议，无密码，共享本机屏幕
  - Windows 下通过 Pillow 抓取真实屏幕，ctypes 调用 user32 模拟键鼠输入
  - 非 Windows 平台自动切换为虚拟屏幕演示模式（便于调试预览）
- **HTTPS 文件管理**：浏览器左侧面板，从根目录浏览文件树，支持
  - 上传、下载文件
  - 新建文件夹、重命名、移动
  - 打包为 zip 下载
- **命令行终端**：浏览器底部面板，直接运行命令并获取输出
- **一键启动**：仅需 Python 3 + Pillow 运行库，运行 `python webvnc.py` 即启动
- **无点击连接**：打开页面自动连接远程桌面

## 环境要求

| 项目 | 说明 |
| ---- | ---- |
| 操作系统 | 推荐 Windows（完整功能：真实屏幕共享 + 键鼠控制） |
| Python | 3.8 及以上 |
| 运行库 | Pillow（`pip install pillow`） |
| 浏览器 | 任意现代浏览器（Chrome / Edge / Firefox / Safari） |

## 快速开始

```bash
# 1. 安装运行库
pip install pillow

# 2. 启动服务
python webvnc.py

# 3. 浏览器访问
#    本机： https://127.0.0.1:6080/vnc.html
#    远程： https://<本机IP>:6080/vnc.html
```

首次启动会自动生成自签名 HTTPS 证书（`cert.pem` / `key.pem`），浏览器首次访问时
需要点击「高级」→「继续访问」信任该证书。

## 命令行参数

| 参数 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `--host` | `0.0.0.0` | Web 服务监听地址 |
| `--port` | `6080` | HTTPS 端口 |
| `--vnc-host` | `0.0.0.0` | 内置 VNC Server 监听地址 |
| `--vnc-port` | `5900` | VNC 端口 |
| `--token` | 无 | 访问令牌，保护文件/命令 API（建议设置） |
| `--no-https` | 关闭 | 使用 HTTP 而非 HTTPS |

示例：

```bash
# 指定端口并启用访问令牌
python webvnc.py --port 8443 --vnc-port 5901 --token mysecret

# 纯 HTTP 模式（内网或代理场景）
python webvnc.py --no-https --port 6080
```

## 界面说明

访问 `/vnc.html` 后页面分为三部分：

- **中央**：远程桌面画面，打开即自动连接，可直接键鼠操作
- **左侧「文件管理」面板**：浏览根目录文件树；工具栏提供刷新、上级、驱动器、上传、
  新建文件夹、下载、改名、移动、打包 zip 等操作；双击目录进入，双击文件下载
- **底部「命令行」面板**：输入命令回车执行，实时显示输出与退出码（Windows 使用
  cmd，其他平台使用 sh）

## 项目结构

```
webvnc.py              # 主程序（VNC Server + HTTPS 服务 + 文件/命令 API）
vnc.html               # noVNC 网页客户端（已移除点击连接页面）
app/                   # noVNC 前端资源及自定义面板（fm.js / term.js / panels.css）
core/                  # noVNC 核心库（RFB 客户端）
cert.pem / key.pem     # 首次运行自动生成的自签名证书
```

## 安全提示

- 本工具不设密码且具有全盘文件与命令执行能力，请仅在可信网络环境使用
- 对外开放服务时务必使用 `--token` 设置访问令牌，并配合防火墙限制来源 IP
- HTTPS 使用自签名证书，通信经过加密但证书不受公信 CA 信任

## 许可证

- 本项目前端基于 [noVNC](https://github.com/novnc/noVNC)（MPL-2.0）
- `webvnc.py` 为本仓库新增代码
