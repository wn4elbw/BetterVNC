# noVNC API

noVNC 客户端的接口由单一的 `RFB` 对象构成，每次连接实例化一个对象。

## RFB

`RFB` 对象表示与 VNC 服务器之间的一次连接。它通过一个 WebSocket 通信，该 WebSocket 必须提供标准的 RFB 协议数据流。

### 构造函数

[`RFB()`](#rfb-1)
  - 创建并返回一个新的 `RFB` 对象。

### 属性

`background`
  - 一个合法的 CSS [background][mdn-bg] 样式值，指定远程会话屏幕所在容器的背景样式。默认值为 `rgb(40, 40, 40)`（纯灰色）。

[mdn-bg]: https://developer.mozilla.org/en-US/docs/Web/CSS/background

`capabilities` *只读*
  - 一个 `Object`，指示服务器可用的可选扩展能力。部分方法仅在对应能力已设置时才可调用。定义的能力如下：

    | 名称    | 类型      | 说明
    | -------- | --------- | -----------
    | `power`  | `boolean` | 支持机器电源控制

`clippingViewport` *只读*
  - 一个 `boolean`，指示远程会话当前是否被裁剪到其容器内。仅在 `clipViewport` 启用时有意义。

`clipViewport`
  - 一个 `boolean`，指示远程会话是否应裁剪到其容器内。禁用时将显示滚动条来处理溢出。默认禁用。

`compressionLevel`
  - 一个 `int`，取值范围 `[0-9]`，控制期望的压缩等级。`0` 表示不压缩。等级 1 占用最少 CPU 但压缩率较弱，等级 9 压缩率最佳但在服务器端 CPU 消耗较高。适用于非常慢的网络连接。默认值为 `2`。

`dragViewport`
  - 一个 `boolean`，指示鼠标事件是否应控制被裁剪的远程会话的相对位置。仅在 `clipViewport` 启用时有意义。默认禁用。

`focusOnClick`
  - 一个 `boolean`，指示在收到 `mousedown` 或 `touchstart` 事件时是否自动将键盘焦点移到远程会话。默认启用。

`qualityLevel`
  - 一个 `int`，取值范围 `[0-9]`，控制期望的 JPEG 质量。`0` 表示低质量，`9` 表示高质量。默认值为 `6`。

`resizeSession`
  - 一个 `boolean`，指示每当容器尺寸变化时是否发送调整远程会话尺寸的请求。默认禁用。

`scaleViewport`
  - 一个 `boolean`，指示远程会话是否应在本地缩放以适配其容器。禁用时，若远程会话小于容器则居中显示，若大于容器则按 `clipViewport` 处理。默认禁用。

`viewOnly`
  - 一个 `boolean`，指示是否阻止向服务器发送任何事件（如按键或鼠标移动）。默认禁用。

### 事件

[`bell`](#bell)
  - 收到服务器发出的可听铃声请求时触发。

[`capabilities`](#capabilities)
  - `RFB.capabilities` 更新时触发。

[`clipboard`](#clipboard)
  - 收到来自服务器的剪贴板数据时触发。

[`clippingviewport`](#clippingviewport)
  - `RFB.clippingViewport` 更新时触发。

[`connect`](#connect)
  - `RFB` 对象完成与服务器的连接及握手时触发。

[`credentialsrequired`](#credentialsrequired)
  - 需要提供更多凭据才能继续时触发。

[`desktopname`](#desktopname)
  - 远程桌面名称变化时触发。

[`disconnect`](#disconnect)
  - `RFB` 对象断开连接时触发。

[`securityfailure`](#securityfailure)
  - 与服务器的安全协商失败时触发。

[`serververification`](#serververification)
  - 服务器身份需要用户确认时触发。

### 方法

[`RFB.approveServer()`](#rfbapproveserver)
  - 继续连接服务器。应在 [`serververification`](#serververification) 事件触发、用户已核验服务器身份后调用。

[`RFB.blur()`](#rfbblur)
  - 将键盘焦点移出远程会话。

[`RFB.clipboardPasteFrom()`](#rfbclipboardpastefrom)
  - 向服务器发送剪贴板内容。

[`RFB.disconnect()`](#rfbdisconnect)
  - 与服务器断开连接。

[`RFB.focus()`](#rfbfocus)
  - 将键盘焦点移到远程会话。

[`RFB.getImageData()`](#rfbgetimagedata)
  - 以 ImageData 数组形式返回屏幕当前内容。

[`RFB.machineReboot()`](#rfbmachinereboot)
  - 请求重启远程机器。

[`RFB.machineReset()`](#rfbmachinereset)
  - 请求强制重置远程机器。

[`RFB.machineShutdown()`](#rfbmachineshutdown)
  - 请求关闭远程机器。

[`RFB.sendCredentials()`](#rfbsendcredentials)
  - 向服务器发送凭据。应在 [`credentialsrequired`](#credentialsrequired) 事件触发后调用。

[`RFB.sendCtrlAltDel()`](#rfbsendctrlaltdel)
  - 发送 Ctrl-Alt-Del 按键序列。

[`RFB.sendKey()`](#rfbsendkey)
  - 发送一个按键事件。

[`RFB.toBlob()`](#rfbtoblob)
  - 以 Blob 编码图像文件形式返回屏幕当前内容。

[`RFB.toDataURL()`](#rfbtodataurl)
  - 以 data-url 编码图像文件形式返回屏幕当前内容。

### 详细说明

#### RFB()

`RFB()` 构造函数返回一个新的 `RFB` 对象，并开始与指定 VNC 服务器建立新连接。

##### 语法

```js
new RFB(target, urlOrChannel);
new RFB(target, urlOrChannel, options);
```

###### 参数

**`target`**
  - 一个块级 [`HTMLElement`][mdn-elem]，指定 `RFB` 对象挂载的位置。该 `HTMLElement` 的现有内容不会被改动，但 `RFB` 对象存续期间会向其中添加新元素。

[mdn-elem]: https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement

**`urlOrChannel`**
  - 一个 `DOMString`，指定要连接的 VNC 服务器。必须是合法的 WebSocket URL。也可以是 `WebSocket` 或 `RTCDataChannel`。

**`options`** *可选*
  - 一个 `Object`，指定连接方式的额外细节。

    可选选项：

    `shared`
      - 一个 `boolean`，指示是否共享远程服务器，还是断开其他已连接的客户端。默认启用。

    `credentials`
      - 一个 `Object`，指定认证时提供给服务器的凭据。可能的凭据如下：

        | 名称         | 类型        | 说明
        | ------------ | ----------- | -----------
        | `"username"` | `DOMString` | 认证用户
        | `"password"` | `DOMString` | 用户密码
        | `"target"`   | `DOMString` | 目标机器或会话

    `repeaterID`
      - 一个 `DOMString`，指定提供给遇到的 VNC repeater 的 ID。

    `wsProtocols`
      - 一个 `DOMString` 数组，指定 WebSocket 连接使用的子协议。默认空。

#### bell

服务器请求发出可听铃声时触发 `bell` 事件。

#### capabilities

每当 `RFB.capabilities` 中添加或移除条目时触发 `capabilities` 事件。`detail` 属性是一个 `Object`，其中 `capabilities` 属性包含 `RFB.capabilities` 的新值。

#### clippingviewport

每当 `RFB.clippingViewport` 在 `true` 与 `false` 之间变化时触发 `clippingviewport` 事件。`detail` 属性是一个 `boolean`，为 `RFB.clippingViewport` 的新值。

#### clipboard

服务器发送剪贴板数据时触发 `clipboard` 事件。`detail` 属性是一个 `Object`，包含 `text` 属性（`DOMString`，为剪贴板数据）。

#### credentialsrequired

服务器要求的凭据多于 [`RFB()`](#rfb-1) 中指定时触发 `credentialsrequired` 事件。`detail` 属性是一个 `Object`，包含 `types` 属性（`DOMString` 数组，列出所需凭据）。

#### connect

与服务器的全部握手完成后、连接完全建立时触发 `connect` 事件。此后 `RFB` 对象即可接收图形更新并发送输入。

#### desktopname

远程桌面名称变化时触发 `desktopname` 事件。`detail` 属性是一个 `Object`，包含 `name` 属性（`DOMString`，为新名称）。

#### disconnect

连接终止时触发 `disconnect` 事件。`detail` 属性是一个 `Object`，包含 `clean` 属性。`clean` 是一个 `boolean`，指示终止是否为正常终止。若发生意外终止或错误，`clean` 为 `false`。

#### securityfailure

握手过程在安全协商阶段失败时触发 `securityfailure` 事件。`detail` 属性是一个 `Object`，包含以下属性：

| 属性   | 类型        | 说明
| ------ | ----------- | -----------
| `status` | `long`      | 失败状态码
| `reason` | `DOMString` | **可选的** 失败原因

`status` 属性对应失败时的 [SecurityResult][rfb-secresult] 状态码。该事件不会发送状态为零的值，因为那表示安全握手成功。可选属性 `reason` 由服务器提供，因此其语言未知；不过多数服务器会发送英文。服务器也可以选择不发送原因，此时 `reason` 属性将被省略。

[rfb-secresult]: https://github.com/rfbproto/rfbproto/blob/master/rfbproto.rst#securityresult

#### serververification

服务器提供可用于验证其身份、防范中间人攻击的信息时触发 `serververification` 事件。`detail` 属性是一个 `Object`，包含 `type` 属性（`DOMString`，指定服务器提供的信息类型）。根据 `type` 的值，还可能提供其他属性：

`"RSA"`
 - 服务器身份仅通过 RSA 密钥验证。`publickey` 属性是一个 `Uint8Array`，包含无符号大端表示的公钥。

#### RFB.approveServer()

`RFB.approveServer()` 方法用于表示用户已核验 `serververification` 事件中提供的服务器身份，可以继续连接。

##### 语法

```js
RFB.approveServer();
```

#### RFB.blur()

`RFB.blur()` 方法移除远程会话的键盘焦点。此后键盘事件将不再发送给远程服务器。

##### 语法

```js
RFB.blur();
```

#### RFB.clipboardPasteFrom()

`RFB.clipboardPasteFrom()` 方法用于向远程服务器发送剪贴板数据。

##### 语法

```js
RFB.clipboardPasteFrom(text);
```

###### 参数

**`text`**
  - 一个 `DOMString`，指定要发送的剪贴板数据。

#### RFB.disconnect()

`RFB.disconnect()` 方法用于断开与当前服务器的连接。

##### 语法

```js
RFB.disconnect();
```

#### RFB.focus()

`RFB.focus()` 方法为远程会话设置键盘焦点。此后键盘事件将发送给远程服务器。

##### 语法

```js
RFB.focus();
RFB.focus(options);
```

###### 参数

**`options`** *可选*
  - 一个 `object`，提供控制焦点方式的选项。可用选项见 [`HTMLElement.focus()`][mdn-focus]。

[mdn-focus]: https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/focus

#### RFB.getImageData()

`RFB.getImageData()` 方法以 [`ImageData`][mdn-imagedata] 形式返回屏幕当前内容。

[mdn-imagedata]: https://developer.mozilla.org/en-US/docs/Web/API/ImageData

##### 语法

```js
RFB.getImageData();
```

#### RFB.machineReboot()

`RFB.machineReboot()` 方法用于请求干净重启远程机器。需要 `power` 能力已设置才生效。

##### 语法

```js
RFB.machineReboot();
```

#### RFB.machineReset()

`RFB.machineReset()` 方法用于请求强制重置远程机器。需要 `power` 能力已设置才生效。

##### 语法

```js
RFB.machineReset();
```

#### RFB.machineShutdown()

`RFB.machineShutdown()` 方法用于请求关闭远程机器。需要 `power` 能力已设置才生效。

##### 语法

```js
RFB.machineShutdown();
```

#### RFB.sendCredentials()

`RFB.sendCredentials()` 方法用于在 `credentialsrequired` 事件触发后提供缺失的凭据。

##### 语法

```js
RFB.sendCredentials(credentials);
```

###### 参数

**`credentials`**
  - 一个 `Object`，指定认证时提供给服务器的凭据。详见 [`RFB()`](#rfb-1)。

#### RFB.sendCtrlAltDel()

`RFB.sendCtrlAltDel()` 方法用于发送 *左 Ctrl*、*左 Alt*、*Delete* 按键序列。这是 [`RFB.sendKey()`](#rfbsendkey) 的便捷封装。

##### 语法

```js
RFB.sendCtrlAltDel();
```

#### RFB.sendKey()

`RFB.sendKey()` 方法用于向服务器发送一个按键事件。

##### 语法

```js
RFB.sendKey(keysym, code);
RFB.sendKey(keysym, code, down);
```

###### 参数

**`keysym`**
  - 一个 `long`，指定要发送的 RFB keysym。若指定了合法的 **`code`**，`keysym` 可以为 `0`。

**`code`**
  - 一个 `DOMString`，指定要发送的物理按键。合法值与 [`KeyboardEvent.code`][mdn-keycode] 可指定的值一致。若无法确定物理按键，则指定 `null`。

[mdn-keycode]: https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent/code

**`down`** *可选*
  - 一个 `boolean`，指定发送按下事件还是释放事件。若省略，则同时发送按下与释放事件。

#### RFB.toBlob()

`RFB.toBlob()` 方法以 [`Blob`][mdn-blob] 形式返回屏幕当前内容。

[mdn-blob]: https://developer.mozilla.org/en-US/docs/Web/API/Blob

##### 语法

```js
RFB.toBlob(callback);
RFB.toBlob(callback, type);
RFB.toBlob(callback, type, quality);
```

###### 参数

**`callback`**
  - 回调函数，接收最终生成的 [`Blob`][mdn-blob] 作为唯一参数。

**`type`** *可选*
  - 一个字符串，指定请求的图像 MIME 类型。

**`quality`** *可选*
  - 一个 `0` 至 `1` 之间的数字，指定图像质量。

#### RFB.toDataURL()

`RFB.toDataURL()` 方法以 data URL 形式返回屏幕当前内容，该 URL 可用于例如 `img` 标签的 `src` 属性。

##### 语法

```js
RFB.toDataURL();
RFB.toDataURL(type);
RFB.toDataURL(type, encoderOptions);
```

###### 参数

**`type`** *可选*
  - 一个字符串，指定请求的图像 MIME 类型。

**`encoderOptions`** *可选*
  - 一个 `0` 至 `1` 之间的数字，指定图像质量。
