
import menuLanding from "./menus/landing.menu";
import menuUI from "./menus/ui.menu";

// 注：原 "Pages" 区块（权限页面）已迁移；
// "工作区"目录由 components/navigation/WorkspaceSection.vue 动态渲染
// （数据源：projectStore），不再走 navigation.ts 静态配置。

export default {
  menu: [
    {
      text: "",
      items: [
        {
          text: "仪表盘",
          link: "/dashboard",
          icon: "mdi-view-dashboard-outline",
        },
        {
          text: "多人协作板",
          link: "/board",
          icon: "mdi-draw",
        },
        {
          text: "偏好设置",
          link: "/settings",
          icon: "mdi-cog-outline",
        },
      ],
    },

    {
      text: "Landing",
      items: [...menuLanding],
    },
    {
      text: "UI - Theme Preview",
      items: menuUI,
    },
  ],
};
