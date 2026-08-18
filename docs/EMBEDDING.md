# 嵌入与部署 noVNC 应用

本文档介绍如何嵌入和部署 noVNC 应用（含设置项与完整用户界面）。若希望在自己的应用中直接使用 noVNC 核心库，请参阅[库使用文档](LIBRARY.md)。

## 文件组成

noVNC 应用由以下文件与目录构成：

* `vnc.html` — 应用主页面，用户访问的入口。可重命名。

* `app/` — 应用的辅助文件，包含代码、图片、样式与翻译。

* `core/` — noVNC 核心库。

* `vendor/` — 应用与核心库使用的第三方辅助库。

最基本的部署方式：将这些文件通过 Web 服务器对外提供，并配置一个指向 VNC 服务器的 WebSocket 代理。

> 本项目 `webvnc.py` 已内置 HTTPS 静态文件服务与 WebSocket 代理（`/websockify`），运行后无需额外配置 Web 服务器。

## 配置参数

noVNC 应用可通过多项设置进行控制。所有参数均可在界面中调整，也可通过以下方式预设：

* 通过 URL 查询参数：

  ```
  https://www.example.com/vnc.html?reconnect=0&shared=1
  ```

  或 URL 片段：

  ```
  https://www.example.com/vnc.html#reconnect=0&shared=1
  ```

  片段形式更受推荐，因为它不会发送给服务器。

* 通过 `defaults.json` 与 `mandatory.json` 文件。

当前可用的选项如下：

* `autoconnect` — 页面加载完成后自动连接。

* `reconnect` — 连接断开后是否自动重连。

* `reconnect_delay` — 重连前等待的毫秒数。

* `host` — 要连接的 WebSocket 主机。已废弃，推荐在 `path` 中指定完整 URL。

* `port` — 要连接的 WebSocket 端口。已废弃，推荐在 `path` 中指定完整 URL。

* `encrypt` — WebSocket 连接是否使用 TLS。已废弃，推荐在 `path` 中指定完整 URL。

* `path` — 要使用的 WebSocket URL。可以是绝对 URL，也可以是相对于 `vnc.html` 的 URL。若指定了 `host`，则 `path` 会被当作 URL 中的路径部分解释。

* `password` — 若服务器需要认证，则发送该密码。

* `repeaterID` — 若检测到 VNC repeater，使用的 repeater ID。

* `shared` — noVNC 连接时是否断开其他 VNC 客户端。

* `bell` — 是否启用键盘提示音。

* `view_only` — 远程会话是否为只读模式。

* `view_clip` — 远程会话无法适配浏览器时，使用裁剪还是滚动条。

* `resize` — 远程会话尺寸与浏览器窗口不一致时的缩放方式。可选值：`off`、`scale`、`remote`。

* `quality` — 会话 JPEG 质量等级，取值 `0` 至 `9`。

* `compression` — 会话压缩等级，取值 `0` 至 `9`。

* `logging` — 控制台日志级别。可选值：`error`、`warn`、`info`、`debug`。

* `keep_device_awake` — 连接激活期间是否阻止（本地）屏幕进入休眠。适用于只读会话，避免因缺少键鼠操作导致设备休眠。

## HTTP 部署注意事项

### 浏览器缓存问题

若使用带 ETag 头的 Web 服务器提供 noVNC 文件，并在查询字符串中包含选项，升级时可能出现浏览器缓存问题，表现为红色错误框。原因：升级后用户以新的查询字符串访问，导致新版 `vnc.html` 重新加载，而浏览器复用了旧版 JavaScript 文件。为避免此问题，必须让浏览器以条件请求方式重新验证缓存文件。正确做法是让 Web 服务器在响应中提供（命名容易混淆的）`Cache-Control: no-cache` 头。

### 服务器配置示例

Apache：

```
    # 在主配置文件中
    #（Debian/Ubuntu 用户：改用 "a2enmod headers"）
    LoadModule headers_module modules/mod_headers.so

    # 在与 noVNC 相关的 <Directory> 或 <Location> 块中
    Header set Cache-Control "no-cache"
```

Nginx：

```
    # 在与 noVNC 相关的 location 块中
    add_header Cache-Control no-cache;
```
