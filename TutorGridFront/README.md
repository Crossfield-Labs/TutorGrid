<br><br>

<p align='center' >
  <img  src='/src/assets/logo_light.svg' alt='Vuetify3' width='300'/>
</p>
<br><br>

<p align="center">
  <a href="https://vuejs.org/">
    <img src="https://img.shields.io/badge/vue-v3.2.47-brightgreen.svg" alt="vue">
  </a>
  <a href="https://vuetifyjs.com/">
    <img src="https://img.shields.io/badge/vuetify-v3.1.13-blue.svg" alt="element-ui">
  </a>
    <a href="https://vitejs.dev/">
    <img src="https://img.shields.io/badge/vite-v4.2.1-blueviolet.svg" alt="element-ui">
  </a>
  
  <a href="https://github.com/yangjiakai/vuetify3-admin-template-zh/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/mashape/apistatus.svg" alt="license">
  </a>
</p>

<h4 align='center'>
<a href="https://lux-zh.netlify.app">Live Demo</a>
</h4>

<br>

<p align='center'>
<b>English</b> | <a href="https://github.com/yangjiakai/vuetify3-lux-admin-template-zh/blob/main/README.zh-CN.md">简体中文</a>| <a href="https://github.com/yangjiakai/vuetify3-admin-template-zh/blob/main/README.jp.md">日本語</a>
</p>

## 📖Introduction

- No I18n Base Template For Vuetify3-Lux-Admin

## 📖 其他版本

Simplified i18n version: <a href="https://github.com/yangjiakai/vuetify3-lux-admin-template-i18n/tree/main">vuetify3-lux-admin-template-i18n</a>

Fullversion: <a href="https://github.com/yangjiakai/lux-admin-vuetify3/tree/main">vuetify3-lux-admin</a>

Nuxt3 Version: Creating

## 文档

## 📚Features

- 📖 [Vue 3.2](https://github.com/vuejs/core)
- 📖 [Vite 4.x](https://github.com/vitejs/vite)
- 📖 UI Framework [Vuetify 3](https://next.vuetifyjs.com/en/)
- 📖 TypeScript
- 📦 Component Auto Importing
- 🍍 [Pinia](https://pinia.vuejs.org/)
- 📔 `<script setup>`
- 📚 Use icons from any icon sets in [Iconify](https://icon-sets.iconify.design/)
- ☁️ Deploy on Netlify, zero-config
- 🔑 Firebase auth
- 📈 Echarts, ApexChart
- 🧭 Openai, Chatgpt
- 🌍 vue-i18n
- 📚 virtual-scroller , vuedraggable , perfect-scrollbar
- 📝 Rich Text Editor
- 📇 Responsive multi-platform adaptive

## 💬Contact Me

- Email <a href="mailto:yjkbako@gmail.com">yjkbako@gmail.com</a>
- Twitter https://twitter.com/baibaixiang
- Wechat <img  src='/src/assets/wechat-qrcode.png'  alt='DashBoard' width='300' />

## 💌Preview

<img  src='/src/assets/previews/DashBoard.png'  alt='DashBoard' />

<br>

## 📦Pre-packed

### 🏷️ UI Frameworks

- [Vuetify3](https://next.vuetifyjs.com/en/) - Vuetify is a no design skills required UI Framework with beautifully handcrafted Vue Components.

### 🏷️ Icons

- [Iconify](https://iconify.design) - use icons from any icon sets [🔍Icônes](https://icones.netlify.app/)
- [Pure CSS Icons via UnoCSS](https://github.com/antfu/unocss/tree/main/packages/preset-icons)

### 🏷️ Plugins

- [Vue Router4](https://router.vuejs.org/)
- [VueUse](https://github.com/antfu/vueuse) - collection of useful composition APIs
- [VuedDaggable](https://github.com/SortableJS/Vue.Draggable) - allowing drag-and-drop and synchronization with view model array.
- [Vue-Masonry-Wall](https://github.com/DerYeger/yeger/tree/main/packages/vue-masonry-wall) - Responsive masonry layout with SSR support and zero dependencies for Vue 3.
- [Vue-Virtual-Scroller](https://github.com/Akryum/vue-virtual-scroller) - Blazing fast scrolling of any amount of data

## 👻Try it now!

```

yarn install

yarn dev
```

### Web Console Deployment

- Default behavior remains unchanged: without extra env vars, `/` redirects to `/landing` and the app uses local `127.0.0.1` backend defaults.
- For a separate console deployment such as `console.tutorgrid.indolyn.com`, set:

```env
VITE_API_BASE_URL=https://api-tutorgrid.microindole.me
VITE_WS_URL=wss://api-tutorgrid.microindole.me/ws/orchestrator
VITE_DEFAULT_HOME_ROUTE=/board
```

```
TutorGridFront
├─ .browserslistrc
├─ .claude
│  └─ settings.local.json
├─ .dockerignore
├─ .editorconfig
├─ auto-imports.d.ts
├─ Dockerfile
├─ docs
│  ├─ Core项目介绍.md
│  ├─ MetaAgent_V4_需求规格说明书.md
│  └─ 笔记page设计.md
├─ electron
│  ├─ main.ts
│  └─ preload.ts
├─ index.html
├─ LICENSE
├─ package.json
├─ public
│  ├─ favicon.ico
│  ├─ favicon.png
│  ├─ fonts
│  │  ├─ HarmonyOS_Sans_SC_Medium.ttf
│  │  └─ HarmonyOS_Sans_SC_Regular.ttf
│  ├─ images
│  │  ├─ AppBarBackGround.png
│  │  ├─ background1.jpg
│  │  ├─ bg1.jpg
│  │  └─ boardbackground.jpg
│  └─ _redirects
├─ README.jp.md
├─ README.md
├─ README.zh-CN.md
├─ src
│  ├─ App.vue
│  ├─ assets
│  │  ├─ images
│  │  │  ├─ 404.svg
│  │  │  ├─ 500.svg
│  │  │  ├─ avatars
│  │  │  │  ├─ avatar_assistant.jpg
│  │  │  │  └─ avatar_user.jpg
│  │  │  ├─ card2
│  │  │  │  ├─ yoimiya.png
│  │  │  │  └─ yoimiya_bg.jpg
│  │  │  ├─ chat-bg-2.png
│  │  │  └─ svg1.svg
│  │  ├─ loading.svg
│  │  ├─ logo.back.png
│  │  ├─ logo.back.svg
│  │  ├─ logo.png
│  │  ├─ logo.svg
│  │  ├─ logo_dark.svg
│  │  ├─ logo_light.svg
│  │  ├─ previews
│  │  │  ├─ Card.png
│  │  │  ├─ ChatGPT.png
│  │  │  ├─ Color.png
│  │  │  ├─ DashBoard.png
│  │  │  ├─ DataTable.png
│  │  │  ├─ Gradient.png
│  │  │  ├─ Login.png
│  │  │  ├─ TaskBoard.png
│  │  │  ├─ Todo.png
│  │  │  ├─ Unsplash.png
│  │  │  └─ Unsplash2.png
│  │  ├─ wechat-qrcode.png
│  │  └─ wechat.jpg
│  ├─ components
│  │  ├─ BoardCard.vue
│  │  ├─ Breadcrumb.vue
│  │  ├─ common
│  │  │  ├─ BackToTop.vue
│  │  │  ├─ CopyBtn.vue
│  │  │  ├─ CopyLabel.vue
│  │  │  ├─ PercentTrend.vue
│  │  │  └─ Snackbar.vue
│  │  ├─ CustomizationMenu.vue
│  │  ├─ dashboard
│  │  │  ├─ SalesCard.vue
│  │  │  └─ TicketsCard.vue
│  │  ├─ FeatureCard.vue
│  │  ├─ GlobalLoading.vue
│  │  ├─ ImagePreview.vue
│  │  ├─ LoadingView.vue
│  │  ├─ navigation
│  │  │  ├─ MainMenu.vue
│  │  │  └─ MainSidebar.vue
│  │  ├─ PageTitle.vue
│  │  ├─ RichEditorMenubar.vue
│  │  ├─ toolbar
│  │  │  ├─ LanguageSwitcher.vue
│  │  │  ├─ MainAppbar.vue
│  │  │  ├─ StatusMenu.vue
│  │  │  ├─ ToolbarNotifications.vue
│  │  │  └─ ToolbarUser.vue
│  │  └─ Toolbox.vue
│  ├─ configs
│  │  ├─ currencies.ts
│  │  ├─ index.ts
│  │  ├─ locales.ts
│  │  ├─ menus
│  │  │  ├─ landing.menu.ts
│  │  │  ├─ pages.menu.ts
│  │  │  └─ ui.menu.ts
│  │  └─ navigation.ts
│  ├─ data
│  │  ├─ logos.ts
│  │  ├─ members.ts
│  │  └─ users.ts
│  ├─ layouts
│  │  ├─ AuthLayout.vue
│  │  ├─ DefaultLayout.vue
│  │  ├─ LandingLayout.vue
│  │  └─ UILayout.vue
│  ├─ locales
│  │  ├─ en.ts
│  │  ├─ ja.ts
│  │  └─ zhHans.ts
│  ├─ main.ts
│  ├─ plugins
│  │  ├─ echarts.ts
│  │  ├─ i18n.ts
│  │  ├─ plantuml.ts
│  │  └─ vuetify.ts
│  ├─ router
│  │  ├─ auth.routes.ts
│  │  ├─ index.ts
│  │  └─ landing.routes.ts
│  ├─ stores
│  │  ├─ appStore.ts
│  │  ├─ authStore.ts
│  │  ├─ customizeTheme.ts
│  │  ├─ inspirationStore.ts
│  │  ├─ knowledgeStore.ts
│  │  ├─ orchestratorStore.ts
│  │  ├─ snackbarStore.ts
│  │  └─ workspaceStore.ts
│  ├─ styles
│  │  ├─ common
│  │  │  ├─ animation.scss
│  │  │  ├─ beautify.scss
│  │  │  └─ gradients.scss
│  │  ├─ main.scss
│  │  ├─ pages
│  │  │  └─ _editor.scss
│  │  ├─ variables.scss
│  │  ├─ vuetify
│  │  │  └─ _elevations.scss
│  │  └─ _override.scss
│  ├─ test
│  │  ├─ demo.test.ts
│  │  ├─ demo.ts
│  │  └─ Demo.vue
│  ├─ types
│  │  ├─ config.d.ts
│  │  ├─ electron.d.ts
│  │  └─ env.d.ts
│  ├─ utils
│  │  ├─ aiUtils.ts
│  │  ├─ clipboardUtils.ts
│  │  ├─ colorUtils.ts
│  │  ├─ common.ts
│  │  ├─ csvToJson.ts
│  │  ├─ deepMerge.ts
│  │  ├─ formatCurrency.ts
│  │  ├─ index.ts
│  │  └─ type-chanlleges.ts
│  └─ views
│     ├─ auth
│     │  ├─ ForgotPage.vue
│     │  ├─ ResetPage.vue
│     │  ├─ SigninPage.vue
│     │  ├─ SignupPage.vue
│     │  └─ VerifyEmailPage.vue
│     ├─ document
│     │  ├─ components
│     │  │  ├─ AsidePanel.vue
│     │  │  ├─ ChatFAB.vue
│     │  │  ├─ DocumentEditor.vue
│     │  │  ├─ EditorBubbleMenu.vue
│     │  │  └─ RichEditorMenubar.vue
│     │  ├─ extensions
│     │  │  ├─ ai-block-types.ts
│     │  │  ├─ ai-block.ts
│     │  │  ├─ ai-views
│     │  │  │  ├─ Agent.vue
│     │  │  │  ├─ AiBlockDispatcher.vue
│     │  │  │  ├─ Citation.vue
│     │  │  │  ├─ Flashcard.vue
│     │  │  │  ├─ Placeholder.vue
│     │  │  │  ├─ Quiz.vue
│     │  │  │  ├─ Text.vue
│     │  │  │  └─ UnknownBlock.vue
│     │  │  ├─ markdown-parsers.ts
│     │  │  ├─ mock-ai-data.ts
│     │  │  ├─ slash-command-items.ts
│     │  │  └─ SlashCommandMenu.vue
│     │  └─ HyperdocPage.vue
│     ├─ errors
│     │  ├─ NotFoundPage.vue
│     │  └─ UnexpectedPage.vue
│     ├─ landing
│     │  ├─ HomePage.vue
│     │  └─ toolbar
│     │     ├─ components
│     │     │  ├─ Toolbar1.vue
│     │     │  ├─ Toolbar2.vue
│     │     │  ├─ Toolbar3.vue
│     │     │  ├─ Toolbar4.vue
│     │     │  └─ Toolbar5.vue
│     │     └─ ToolbarPage.vue
│     ├─ pages
│     │  ├─ BoardPage.vue
│     │  └─ DashBoard.vue
│     └─ ui
│        └─ LottieAnimationPage.vue
├─ tsconfig.electron.json
├─ tsconfig.json
├─ vite.config.ts
└─ yarn.lock

```
