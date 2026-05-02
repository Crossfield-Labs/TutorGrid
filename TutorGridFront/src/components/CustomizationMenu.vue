<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useTheme } from "vuetify";
import { Icon } from "@iconify/vue";
import { useCustomizeThemeStore } from "@/stores/customizeTheme";

interface Color {
  colorId: number;
  colorName: string;
  colorValue: string;
}

const customizeTheme = useCustomizeThemeStore();
const router = useRouter();
const theme = useTheme();
const themeDrawer = ref(false);

const currentColor = ref<Color>({
  colorId: 2,
  colorName: "grey",
  colorValue: "#344767",
});

const primaryColors = ref<Color[]>([
  {
    colorId: 1,
    colorName: "purple",
    colorValue: "#CB0C9F",
  },
  {
    colorId: 2,
    colorName: "grey",
    colorValue: "#344767",
  },
  {
    colorId: 3,
    colorName: "info",
    colorValue: "#17C1E8",
  },
  {
    colorId: 4,
    colorName: "success",
    colorValue: "#82D616",
  },
  {
    colorId: 5,
    colorName: "warning",
    colorValue: "#F2825A",
  },
  {
    colorId: 6,
    colorName: "error",
    colorValue: "#EA0606",
  },
]);

onMounted(() => {
  updatePrimaryColor(customizeTheme.primaryColor);
});

watch(currentColor, (newVal) => {
  updatePrimaryColor(newVal);
});

const updatePrimaryColor = (newColor: Color) => {
  theme.themes.value.light.colors.primary = newColor.colorValue;
  theme.themes.value.dark.colors.primary = newColor.colorValue;
  customizeTheme.setPrimaryColor(newColor);
  currentColor.value = newColor;
};

function goToSettings() {
  themeDrawer.value = false;
  void router.push("/settings");
}
</script>

<template>
  <div>
    <div class="drawer-button" @click="themeDrawer = true">
      <v-icon class="text-white">mdi-cog-outline</v-icon>
    </div>

    <v-navigation-drawer
      v-model="themeDrawer"
      location="right"
      temporary
      width="360"
      class="theme-drawer"
    >
      <div class="pa-5">
        <div class="top-area">
          <div class="d-flex align-center">
            <b>偏好设置</b>
          </div>
          <div class="text-medium-emphasis">外观与使用偏好</div>
        </div>

        <hr class="my-6" />

        <div class="theme-area">
          <b>显示主题</b>
          <div class="px-3 pt-3" v-if="customizeTheme.darkTheme">
            <v-btn
              @click="customizeTheme.darkTheme = !customizeTheme.darkTheme"
              icon
              color="grey-darken-4"
              class="text-white"
            >
              <Icon width="30" icon="line-md:moon-filled-loop" />
            </v-btn>
            <span class="ml-5">深色模式</span>
          </div>
          <div class="px-3 pt-3" v-else>
            <v-btn
              @click="customizeTheme.darkTheme = !customizeTheme.darkTheme"
              icon
              color="white"
              class="text-red"
            >
              <Icon
                width="30"
                icon="line-md:moon-filled-alt-to-sunny-filled-loop-transition"
              />
            </v-btn>
            <span class="ml-5">浅色模式</span>
          </div>
        </div>

        <hr class="my-6" />

        <div class="primary-color-area">
          <b>主色</b>
          <v-item-group
            class="mt-3"
            v-model="currentColor"
            selected-class="elevation-12"
            mandatory
          >
            <v-item
              v-for="color in primaryColors"
              :key="color.colorId"
              :value="color"
              v-slot="{ isSelected, toggle }"
            >
              <v-btn
                @click="toggle"
                class="text-white mr-1"
                icon
                size="30"
                :color="color.colorValue"
              >
                <Icon width="22" v-if="isSelected" icon="line-md:confirm" />
              </v-btn>
            </v-item>
          </v-item-group>
        </div>

        <hr class="my-6" />

        <div>
          <b>侧栏</b>
          <v-switch
            v-model="customizeTheme.miniSidebar"
            color="primary"
            class="ml-2"
            hide-details
            :label="`紧凑侧栏：${customizeTheme.miniSidebar ? '开' : '关'}`"
          />
        </div>

        <hr class="my-6" />

        <v-alert
          type="info"
          variant="tonal"
          density="comfortable"
          class="mb-4"
        >
          你可以在设置页面中管理模型、连接与搜索选项。
        </v-alert>

        <v-btn color="primary" block size="large" @click="goToSettings">
          前往设置
        </v-btn>
      </div>
    </v-navigation-drawer>
  </div>
</template>

<style lang="scss" scoped>
.drawer-button {
  position: fixed;
  background-color: #705cf6;
  top: 340px;
  right: -45px;
  z-index: 999;
  padding: 0.5rem 1rem;
  border-top-left-radius: 0.5rem;
  border-bottom-left-radius: 0.5rem;
  box-shadow: 1px 1px 9px #705cf6;
  transition: all 0.5s;
  cursor: pointer;

  &:hover {
    box-shadow: 1px 1px 18px #705cf6;
    right: 0px;
    transition: all 0.5s;
  }

  .v-icon {
    font-size: 1.3rem;
    animation: rotation 1s linear infinite;
  }

  @keyframes rotation {
    0% {
      transform: rotate(0deg);
    }

    100% {
      transform: rotate(360deg);
    }
  }
}

hr {
  background-image: linear-gradient(
    90deg,
    transparent,
    rgba(0, 0, 0, 0.4),
    transparent
  ) !important;
  background-color: transparent;
  opacity: 0.25;
  border: none;
  height: 1px;
}
</style>
