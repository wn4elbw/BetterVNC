# 使用 noVNC JavaScript 库

本文档介绍如何在自己的 VNC 客户端应用中集成并使用 noVNC JavaScript 库。若希望嵌入包含完整用户界面的 noVNC 应用，请参阅[嵌入与部署文档](EMBEDDING.md)。

## API

noVNC 的对外 API 由名为 `RFB` 的单一对象构成。该对象的正式文档见 [API 文档](API.md)。

## 示例

noVNC 附带一个名为 `vnc_lite.html` 的精简示例应用。该示例未使用 noVNC 的全部特性，但足以展示基本用法。

## 模块转换

noVNC 使用 ECMAScript 6 模块编写。旧版 Node.js 不支持该语法，若需在旧版 Node.js 中使用 noVNC，必须先对模块进行转换。

noVNC 提供了转换脚本，步骤如下：

 1. 安装 Node.js
 2. 在 noVNC 目录下运行 `npm install`

转换结果输出到 `lib/` 目录。
