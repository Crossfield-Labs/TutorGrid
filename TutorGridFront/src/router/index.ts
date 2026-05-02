import { createRouter, createWebHistory } from "vue-router";

import LandingRoutes from "./landing.routes";
import AuthRoutes from "./auth.routes";

export const routes = [
  {
    path: "/",
    redirect: "/board",
    meta: {},
  } as any,
  {
    path: "/dashboard",
    meta: {
      requiresAuth: true,
      layout: "landing",
    },
    component: () => import("@/views/pages/DashBoard.vue"),
  },
  {
    path: "/board",
    meta: {
      requiresAuth: true,
      layout: "landing",
    },
    component: () => import("@/views/pages/BoardPage.vue"),
  },
  {
    path: "/settings",
    meta: {
      requiresAuth: true,
      layout: "landing",
    },
    component: () => import("@/views/pages/SettingsPage.vue"),
  },
  {
    path: "/hyperdoc/:id",
    meta: {
      requiresAuth: true,
      layout: "landing",
    },
    component: () => import("@/views/document/HyperdocPage.vue"),
  },
  {
    path: "/tasks/:taskId",
    meta: {
      requiresAuth: true,
      layout: "landing",
    },
    component: () => import("@/views/pages/TaskDetailsPage.vue"),
  },
  {
    path: "/:pathMatch(.*)*",
    name: "error",
    component: () =>
      import(/* webpackChunkName: "error" */ "@/views/errors/NotFoundPage.vue"),
  },
  ...LandingRoutes,
  ...AuthRoutes,


];


export const dynamicRoutes = [];

const router = createRouter({
  history: createWebHistory(),
  // hash模式：createWebHashHistory，history模式：createWebHistory
  // process.env.NODE_ENV === "production"

  routes: routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    } else {
      return { top: 0 };
    }
  },
});

export default router;
