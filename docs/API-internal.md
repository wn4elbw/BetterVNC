# 1. 内部模块

noVNC 客户端由多个负责渲染、输入、网络等功能的内部模块组成。每个模块都设计为跨浏览器且彼此独立。

注意：这些模块的 API 不保证稳定，本文档的维护程度也不如官方对外 API。

## 1.1 模块列表

* __Keyboard__（core/input/keyboard.js）：键盘输入事件处理器，支持非美式键盘，将 keyDown/keyUp 事件转换为 X11 keysym 值。

* __Display__（core/display.js）：基于 HTML5 canvas 元素的高效 2D 渲染抽象层。

* __Clipboard__（core/clipboard.js）：剪贴板事件处理器。

* __Websock__（core/websock.js）：来自 websockify 的 Websock 客户端，支持透明二进制数据。API 见 [Websock API](https://github.com/novnc/websockify-js/wiki/websock.js)。

## 1.2 回调

对 Mouse、Keyboard、Display、Clipboard 对象，回调函数以配置属性的方式赋值（与 RFB 对象相同）。WebSock 模块提供名为 `on` 的方法，接收两个参数：回调事件名与回调函数。

## 2. 模块

## 2.1 Keyboard 模块

### 2.1.1 配置属性

无

### 2.1.2 方法

| 名称   | 参数 | 说明
| ------ | ---------- | ------------
| grab   | ()         | 开始捕获键盘事件
| ungrab | ()         | 停止捕获键盘事件

### 2.1.3 回调

| 名称       | 参数           | 说明
| ---------- | -------------------- | ------------
| onkeypress | (keysym, code, down) | 按键按下/释放处理器

## 2.2 Display 模块

### 2.2.1 配置属性

| 名称         | 类型  | 模式 | 默认值 | 说明
| ------------ | ----- | ---- | ------- | ------------
| scale        | float | RW   | 1.0     | 显示区域缩放系数 0.0 - 1.0
| clipViewport | bool  | RW   | false   | 使用视口裁剪
| width        | int   | RO   |         | 显示区域宽度
| height       | int   | RO   |         | 显示区域高度

### 2.2.2 方法

| 名称               | 参数                                              | 说明
| ------------------ | ------------------------------------------------- | ------------
| viewportChangePos  | (deltaX, deltaY)                                  | 相对当前位置移动视口
| viewportChangeSize | (width, height)                                   | 改变视口尺寸
| absX               | (x)                                               | 返回相对远程显示的 X 坐标
| absY               | (y)                                               | 返回相对远程显示的 Y 坐标
| resize             | (width, height)                                   | 设置宽度与高度
| flip               | (from_queue)                                      | 将渲染画布内容更新到可见画布
| pending            | ()                                                | 检查渲染队列中是否有待处理项
| flush              | ()                                                | 恢复处理渲染队列（非空时）
| fillRect           | (x, y, width, height, color, from_queue)          | 绘制实心矩形
| copyImage          | (old_x, old_y, new_x, new_y, width, height, from_queue) | 复制矩形区域
| imageRect          | (x, y, width, height, mime, arr)                  | 用图片绘制矩形
| blitImage          | (x, y, width, height, arr, offset, from_queue)    | 将像素（R,G,B,A）绘制到显示区
| drawImage          | (img, x, y)                                       | 绘制图片并记录损坏区域
| autoscale          | (containerWidth, containerHeight)                 | 缩放显示

## 2.3 Clipboard 模块

### 2.3.1 配置属性

无

### 2.3.2 方法

| 名称           | 参数        | 说明
| --------------- | ----------- | ------------
| writeClipboard  | (text)      | 异步向剪贴板写入文本
| grab            | ()          | 开始捕获剪贴板事件
| ungrab          | ()          | 停止捕获剪贴板事件

### 2.3.3 回调

| 名称    | 参数 | 说明
| ------- | ---- | ------------
| onpaste | (text) | 目标获得焦点并完成异步剪贴板读取后调用
