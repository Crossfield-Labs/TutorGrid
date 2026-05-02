
import menuLanding from "./menus/landing.menu";
import menuUI from "./menus/ui.menu";
import menuPages from "./menus/pages.menu";

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
      items: [
        ...menuLanding,

      ],
    },
    {
      text: "UI - Theme Preview",
      items: menuUI,
    },
    {
      text: "Pages",
      items: menuPages,
    },

  ],
};
