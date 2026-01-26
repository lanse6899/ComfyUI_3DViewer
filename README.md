# ComfyUI 3D查看器 插件

一个用于在 ComfyUI 中快速启动本地 3D 查看器（ve2.html）的轻量插件。

主要功能
- 启动内置 HTTP 服务器并在浏览器中打开查看器
- 自动查找 `ve2.html`，支持自定义路径与端口
- 包含节点：`🔵BB 打开3D查看器`、`🔵BB 读取图像`

快速上手
1. 将 `ComfyUI_3DViewer` 文件夹放入 ComfyUI 的 `custom_nodes` 目录
2. 重启 ComfyUI


注意
- `🔵BB 读取图像` 的 `directory` 默认指向插件文件夹
- 兼容 Python 3.7+ 与现代 Web 浏览器（支持 WebGL）


授权
个人使用免费；商用、平台或机构使用需取得作者授权。
 
许可
本项目采用 MIT 许可证授权。个人使用免费；商用、平台或机构使用请联系作者取得授权。
详细许可文本见项目根目录的 `LICENSE` 文件。
