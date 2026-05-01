<!--
* @Component:
* @Maintainer: J.K. Yang
* @Description:
-->
<script setup lang="ts">
import { useDisplay } from "vuetify";
import { useCustomizeThemeStore } from "@/stores/customizeTheme";
import ToolbarUser from "./ToolbarUser.vue";
import { onMounted, onUnmounted, ref } from "vue";

const { mdAndUp } = useDisplay();
const customizeTheme = useCustomizeThemeStore();

const winApi = (window as any).metaAgent?.window;
const isMaximized = ref(false);
let offMaxChange: (() => void) | undefined;

onMounted(async () => {
  if (!winApi) return;
  isMaximized.value = await winApi.isMaximized();
  offMaxChange = winApi.onMaximizedChanged((v: boolean) => {
    isMaximized.value = v;
  });
});

onUnmounted(() => {
  offMaxChange?.();
});

const onMinimize = () => winApi?.minimize();
const onToggleMaximize = () => winApi?.toggleMaximize();
const onClose = () => winApi?.close();
</script>

<template>
  <!-- ---------------------------------------------- -->
  <!--App Bar -->
  <!-- ---------------------------------------------- -->
  <v-app-bar
    :density="mdAndUp ? 'default' : 'compact'"
    image="/images/AppBarBackGround.png"
    :elevation="20"
    class="app-drag"
  >
    <!-- ---------------------------------------------- -->
    <!-- search input mobil -->
    <!-- ---------------------------------------------- -->

    <div class="px-2 d-flex align-center justify-space-between w-100">
      <!-- ---------------------------------------------- -->
      <!-- NavIcon -->
      <!-- ---------------------------------------------- -->
      <v-app-bar-nav-icon
        class="no-drag"
        @click="customizeTheme.mainSidebar = !customizeTheme.mainSidebar"
      ></v-app-bar-nav-icon>

      <v-spacer></v-spacer>

      <div class="d-flex align-center no-drag">
        <ToolbarUser />
        <div class="window-controls ml-2 d-flex align-center">
          <v-btn
            variant="text"
            size="small"
            icon
            class="win-btn"
            @click="onMinimize"
          >
            <v-icon size="18">mdi-minus</v-icon>
          </v-btn>
          <v-btn
            variant="text"
            size="small"
            icon
            class="win-btn"
            @click="onToggleMaximize"
          >
            <v-icon size="16">
              {{ isMaximized ? "mdi-window-restore" : "mdi-checkbox-blank-outline" }}
            </v-icon>
          </v-btn>
          <v-btn
            variant="text"
            size="small"
            icon
            class="win-btn win-close"
            @click="onClose"
          >
            <v-icon size="18">mdi-close</v-icon>
          </v-btn>
        </div>
      </div>
    </div>
  </v-app-bar>
</template>

<style scoped lang="scss">
.app-drag {
  -webkit-app-region: drag;
}

.no-drag,
.no-drag * {
  -webkit-app-region: no-drag;
}

.window-controls .win-btn {
  width: 36px;
  height: 32px;
  border-radius: 6px;
}

.window-controls .win-close:hover {
  background-color: #e81123 !important;
  color: #fff !important;
}
</style>
