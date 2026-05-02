把应用图标主文件放在这里。

推荐文件：
- `app-icon.png`
  - 这是唯一源图标
  - 开发态窗口图标直接使用这个文件
  - 建议至少 `512x512`
- `app-icon.ico`
  - 由 `app-icon.png` 生成
  - Windows 打包图标使用这个文件

当前代码里：
- `electron/main.ts` 会优先读取 `build/icons/app-icon.png`
- 如果这里没有图标，会回退到 `public/favicon.png`
- `package.json -> build.win.icon` 与 `build.nsis.*Icon` 会读取 `build/icons/app-icon.ico`

建议目录职责：
- `build/icons/`
  - Electron 窗口图标
  - electron-builder 打包图标
- `public/favicon.png`
  - Web / Vite / Electron 渲染页 favicon

不建议把唯一源图标放在 `src/assets/`：
- `src/assets/` 更适合页面内图片资源
- 应用品牌与打包图标更适合放在 `build/icons/`
