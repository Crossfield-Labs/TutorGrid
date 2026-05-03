<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useCustomizeThemeStore } from "@/stores/customizeTheme";
import { useProjectStore, type Project } from "@/stores/projectStore";
import { useSnackbarStore } from "@/stores/snackbarStore";
import CreateProjectDialog from "@/components/dialogs/CreateProjectDialog.vue";
import EditProjectDialog from "@/components/dialogs/EditProjectDialog.vue";

const customizeTheme = useCustomizeThemeStore();
const projectStore = useProjectStore();
const snackbar = useSnackbarStore();
const router = useRouter();

const createOpen = ref(false);
const editOpen = ref(false);
const editingProject = ref<Project | null>(null);
const deleteConfirmOpen = ref(false);
const pendingDeleteId = ref<string>("");

onMounted(async () => {
  await projectStore.fetchList();
});

watch(
  () => projectStore.currentId,
  async (id) => {
    if (id) await projectStore.fetchHyperdocs(id);
  }
);

function openCreate() {
  createOpen.value = true;
}

function openEdit(project: Project) {
  editingProject.value = project;
  editOpen.value = true;
}

function askDelete(id: string) {
  pendingDeleteId.value = id;
  deleteConfirmOpen.value = true;
}

async function confirmDelete() {
  if (!pendingDeleteId.value) return;
  const ok = await projectStore.deleteProject(pendingDeleteId.value);
  if (ok) {
    snackbar.showSuccessMessage("已删除工作区");
    if (router.currentRoute.value.path.startsWith("/projects/")) {
      router.push("/board");
    }
  }
  deleteConfirmOpen.value = false;
  pendingDeleteId.value = "";
}

async function selectProject(id: string) {
  await projectStore.setCurrent(id);
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
            class="workspace-section__row"
            @click="selectProject(project.id)"
          >
            <template v-slot:append>
              <span
                v-if="project.appearance.sidebarColor"
                class="workspace-section__color-dot"
                :style="{ background: project.appearance.sidebarColor }"
                :title="`色块 ${project.appearance.sidebarColor}`"
              />
              <v-menu location="end">
                <template v-slot:activator="{ props: menuProps }">
                  <v-btn
                    v-bind="menuProps"
                    icon="mdi-dots-vertical"
                    variant="text"
                    size="x-small"
                    density="comfortable"
                    class="ml-1 workspace-section__menu-btn"
                    @click.stop
                  />
                </template>
                <v-list density="compact">
                  <v-list-item
                    prepend-icon="mdi-pencil-outline"
                    title="编辑"
                    @click="openEdit(project)"
                  />
                  <v-list-item
                    prepend-icon="mdi-delete-outline"
                    title="删除"
                    base-color="error"
                    @click="askDelete(project.id)"
                  />
                </v-list>
              </v-menu>
            </template>
          </v-list-item>
        </template>

        <!-- Hyperdoc 列表 -->
        <v-list-item
          v-for="doc in projectStore.hyperdocsByProject[project.id] ?? []"
          :key="doc.id"
          prepend-icon="mdi-file-document-outline"
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

    <CreateProjectDialog v-model="createOpen" @created="onCreated" />
    <EditProjectDialog
      v-model="editOpen"
      :project="editingProject"
      @saved="projectStore.fetchList()"
    />

    <!-- 删除确认 Dialog -->
    <v-dialog v-model="deleteConfirmOpen" max-width="400">
      <v-card>
        <v-card-title class="pa-4">
          <v-icon icon="mdi-alert-circle-outline" color="error" class="mr-2" />
          删除工作区？
        </v-card-title>
        <v-card-text>
          删除后该工作区的元数据和绑定的 Hyperdoc 元数据都会被清掉，
          但**实际文件不会被动**（仍在你选择的本地目录里）。
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteConfirmOpen = false">取消</v-btn>
          <v-btn color="error" variant="flat" @click="confirmDelete">
            删除
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
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
    margin-right: 4px;
  }

  &__menu-btn {
    opacity: 0;
    transition: opacity 0.2s;
  }

  &__row:hover &__menu-btn {
    opacity: 1;
  }
}

:deep(.v-list-group .v-list-item) {
  padding-left: 8px !important;
}

/* hover 时把整行的菜单按钮显示出来（v-list-item 里 :deep 才能命中） */
:deep(.workspace-section__row:hover) .workspace-section__menu-btn,
:deep(.workspace-section__row.v-list-item--active) .workspace-section__menu-btn {
  opacity: 1;
}
</style>
