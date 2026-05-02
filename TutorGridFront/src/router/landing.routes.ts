export default [
  {
    path: "/landing",
    name: "landing-home",
    component: () =>
      import(/* webpackChunkName: "landing-home" */ "@/views/landing/HomePage.vue"),
    meta: {
      requiresAuth: false,
      layout: "blank",
    },
  },
  {
    path: "/landing/toolbar",
    name: "landing-toolbar",
    component: () =>
      import(
        /* webpackChunkName: "landing-toolbar" */ "@/views/landing/toolbar/ToolbarPage.vue"
      ),
    meta: {
      requiresAuth: true,
      layout: "landing",
    },
  },
];
