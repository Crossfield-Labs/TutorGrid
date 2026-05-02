<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useCustomizeThemeStore } from "@/stores/customizeTheme";
import { useProjectStore } from "@/stores/projectStore";
import CreateProjectDialog from "@/components/dialogs/CreateProjectDialog.vue";

const customizeTheme = useCustomizeThemeStore();
const projectStore = useProjectStore();
const router = useRouter();

const dialogOpen = ref(false);

onMounted(async () => {
  await projectStore.fetchList();
});

// 切换 currentId 时把所有 Hyperdoc 列表预拉一遍（懒加载也可，先简单做）
watch(
  () => projectStore.currentId,
  async (id) => {
    if (id) await projectStore.fetchHyperdocs(id);
  }
);

function openCreate() {
  dialogOpen.value = true;
}

async function selectProject(id: string) {
  await projectStore.setCurrent(id);
  // 跳转到工作区主页（BoardPage）
  router.push(`/projects/${id}`);
}

async function onCreated(id: string) {
  await selectProject(id);
}
</script>

<template>
  <div class="workspace-section">
    <div
      v-if="!customizeTheme.miniSidebar"
      class="d-flex align-center pa-1 mt-2 text-overline"
    >
      <span class="flex-fill">工作区</span>
      <v-btn
        size="x-small"
        icon="mdi-plus"
        variant="text"
        density="comfortable"
        @click="openCreate"
      />
    </div>

    <v-list class="menu-list" nav dense color="primary">
      <v-list-item
        v-if="projectStore.list.length === 0 && !projectStore.loading"
        prepend-icon="mdi-folder-plus-outline"
        density="compact"
        @click="openCreate"
      >
        <v-list-item-title class="text-caption text-medium-emphasis">
          点击 + 新建工作区
        </v-list-item-title>
      </v-list-item>

      <v-list-group
        v-for="project in projectStore.list"
        :key="project.id"
        :value="project.id"
      >
        <template v-slot:activator="{ props }">
          <v-list-item
            v-bind="props"
            :prepend-icon="
              projectStore.currentId === project.id
                ? 'mdi-folder-open-outline'
                : 'mdi-folder-outline'
            "
            :title="project.name"
            :active="projectStore.currentId === project.id"
            density="compact"
            @click="selectProject(project.id)"
          >
            <template
              v-if="project.appearance.sidebarColor"
              v-slot:append
            >
              <span
                class="workspace-section__color-dot"
                :style="{ background: project.appearance.sidebarColor }"
              />
            </template>
          </v-list-item>
        </template>

        <!-- Hyperdoc 列表 -->
        <v-list-item
          v-for="doc in projectStore.hyperdocsByProject[project.id] ?? []"
          :key="doc.id"
          :prepend-icon="'mdi-file-document-outline'"
          :title="doc.title"
          :to="`/hyperdoc/${doc.id}`"
          density="compact"
        />

        <v-list-item
          v-if="(projectStore.hyperdocsByProject[project.id] ?? []).length === 0"
          prepend-icon="mdi-information-outline"
          density="compact"
        >
          <v-list-item-title class="text-caption text-medium-emphasis">
            暂无 Hyperdoc
          </v-list-item-title>
        </v-list-item>
      </v-list-group>
    </v-list>

    <CreateProjectDialog v-model="dialogOpen" @created="onCreated" />
  </div>
</template>

<style scoped lang="scss">
.workspace-section {
  &__color-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 1px solid rgba(0, 0, 0, 0.15);
  }
}

:deep(.v-list-group .v-list-item) {
  padding-left: 8px !important;
}
</style>
