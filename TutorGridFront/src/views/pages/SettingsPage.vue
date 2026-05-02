<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useSnackbarStore } from "@/stores/snackbarStore";
import { useKnowledgeStore } from "@/stores/knowledgeStore";

interface RuntimeConfigForm {
  planner: {
    provider: string;
    model: string;
    apiKey: string;
    apiBase: string;
    providerOptions: {
      extra_body: {
        thinking?: {
          type: string;
        };
        reasoning_effort?: string;
      };
    };
  };
  langsmith: {
    enabled: boolean;
    project: string;
    apiKey: string;
    apiUrl: string;
  };
  search: {
    tavilyApiKey: string;
  };
}

const API_BASE_URL = "http://127.0.0.1:8000";
const snackbarStore = useSnackbarStore();
const knowledgeStore = useKnowledgeStore();

// ── 知识库 ──
const kbLoading = ref(false);
const kbCourseName = computed(() => knowledgeStore.courseName || "未创建课程");
const kbFiles = computed(() => knowledgeStore.files);
const kbTotalChunks = computed(() => knowledgeStore.files.reduce((s, f) => s + (f.chunkCount || 0), 0));

async function refreshKB() {
  if (kbLoading.value) return;
  kbLoading.value = true;
  try {
    await knowledgeStore.ensureDefaultCourse();
    await knowledgeStore.refreshFiles();
  } catch {
    snackbarStore.showErrorMessage("知识库加载失败");
  } finally {
    kbLoading.value = false;
  }
}

onMounted(() => { void refreshKB(); });
const loadingConfig = ref(false);
const savingConfig = ref(false);

const configForm = reactive<RuntimeConfigForm>({
  planner: {
    provider: "deepseek",
    model: "",
    apiKey: "",
    apiBase: "",
    providerOptions: {
      extra_body: {
        thinking: {
          type: "enabled",
        },
        reasoning_effort: "high",
      },
    },
  },
  langsmith: {
    enabled: false,
    project: "TutorGrid",
    apiKey: "",
    apiUrl: "",
  },
  search: {
    tavilyApiKey: "",
  },
});

onMounted(() => {
  void loadRuntimeConfig();
});

async function loadRuntimeConfig() {
  if (loadingConfig.value) return;
  loadingConfig.value = true;
  try {
    const res = await fetch(`${API_BASE_URL}/api/config`);
    if (!res.ok) {
      throw new Error(`${res.status} ${res.statusText}`);
    }
    const data = await res.json();
    configForm.planner.provider = data?.planner?.provider || "openai_compat";
    configForm.planner.model = data?.planner?.model || "";
    configForm.planner.apiKey = data?.planner?.apiKey || "";
    configForm.planner.apiBase = data?.planner?.apiBase || "";
    configForm.planner.providerOptions = {
      extra_body: {
        thinking: {
          type:
            data?.planner?.providerOptions?.extra_body?.thinking?.type ||
            "enabled",
        },
        reasoning_effort:
          data?.planner?.providerOptions?.extra_body?.reasoning_effort ||
          "high",
      },
    };
    configForm.langsmith.enabled = Boolean(data?.langsmith?.enabled);
    configForm.langsmith.project =
      data?.langsmith?.project || "pc-orchestrator-core";
    configForm.langsmith.apiKey = data?.langsmith?.apiKey || "";
    configForm.langsmith.apiUrl = data?.langsmith?.apiUrl || "";
    configForm.search.tavilyApiKey = data?.search?.tavilyApiKey || "";
  } catch (error) {
    snackbarStore.showErrorMessage(
      `加载 AI 配置失败：${(error as Error).message}`
    );
  } finally {
    loadingConfig.value = false;
  }
}

async function saveRuntimeConfig() {
  if (savingConfig.value) return;
  savingConfig.value = true;
  try {
    const res = await fetch(`${API_BASE_URL}/api/config`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(configForm),
    });
    if (!res.ok) {
      throw new Error(`${res.status} ${res.statusText}`);
    }
    const data = await res.json();
    configForm.planner.provider = data?.planner?.provider || "openai_compat";
    configForm.planner.model = data?.planner?.model || "";
    configForm.planner.apiKey = data?.planner?.apiKey || "";
    configForm.planner.apiBase = data?.planner?.apiBase || "";
    configForm.planner.providerOptions = {
      extra_body: {
        thinking: {
          type:
            data?.planner?.providerOptions?.extra_body?.thinking?.type ||
            "enabled",
        },
        reasoning_effort:
          data?.planner?.providerOptions?.extra_body?.reasoning_effort ||
          "high",
      },
    };
    configForm.langsmith.enabled = Boolean(data?.langsmith?.enabled);
    configForm.langsmith.project =
      data?.langsmith?.project || "pc-orchestrator-core";
    configForm.langsmith.apiKey = data?.langsmith?.apiKey || "";
    configForm.langsmith.apiUrl = data?.langsmith?.apiUrl || "";
    configForm.search.tavilyApiKey = data?.search?.tavilyApiKey || "";
    snackbarStore.showSuccessMessage("AI 配置已保存");
  } catch (error) {
    snackbarStore.showErrorMessage(
      `保存 AI 配置失败：${(error as Error).message}`
    );
  } finally {
    savingConfig.value = false;
  }
}
</script>

<template>
  <div class="pa-5">
    <v-row dense>
      <v-col cols="12" lg="8">
        <v-card min-height="420">
          <v-card-title class="d-flex align-center">
            <v-icon color="primary" class="mr-3">mdi-tune-variant</v-icon>
            <div>
              <div class="font-weight-bold">偏好设置</div>
              <div class="text-body-2 text-medium-emphasis">
                管理模型、连接与搜索选项
              </div>
            </div>
            <v-spacer />
            <v-btn
              icon="mdi-refresh"
              variant="text"
              size="small"
              :loading="loadingConfig"
              @click="loadRuntimeConfig"
            />
          </v-card-title>
          <v-card-text>
            <v-row dense>
              <v-col cols="12" md="6">
                <v-sheet class="pa-4 rounded border h-100">
                  <div class="d-flex align-center mb-3">
                    <v-icon color="primary" class="mr-2">mdi-robot-outline</v-icon>
                    <span class="font-weight-bold">AI 模型</span>
                  </div>
                  <v-select
                    v-model="configForm.planner.provider"
                    label="Provider"
                    :items="['deepseek', 'openai_compat']"
                    variant="solo"
                    density="comfortable"
                    class="mb-2"
                  />
                  <v-text-field
                    v-model="configForm.planner.model"
                    label="Model"
                    variant="solo"
                    density="comfortable"
                    class="mb-2"
                  />
                  <v-text-field
                    v-model="configForm.planner.apiBase"
                    label="API Base"
                    placeholder="https://api.example.com/v1"
                    variant="solo"
                    density="comfortable"
                    class="mb-2"
                  />
                  <v-text-field
                    v-model="configForm.planner.apiKey"
                    label="API Key"
                    type="password"
                    autocomplete="off"
                    variant="solo"
                    density="comfortable"
                    class="mb-3"
                  />
                  <v-switch
                    :model-value="configForm.planner.providerOptions.extra_body.thinking?.type === 'enabled'"
                    color="primary"
                    inset
                    hide-details
                    label="启用 Thinking 模式"
                    class="mb-3"
                    @update:model-value="
                      configForm.planner.providerOptions.extra_body.thinking = {
                        type: $event ? 'enabled' : 'disabled',
                      }
                    "
                  />
                  <v-select
                    v-model="configForm.planner.providerOptions.extra_body.reasoning_effort"
                    label="推理强度"
                    :items="['low', 'medium', 'high']"
                    variant="solo"
                    density="comfortable"
                    hide-details
                  />
                </v-sheet>
              </v-col>

              <v-col cols="12" md="6">
                <v-sheet class="pa-4 rounded border h-100">
                  <div class="d-flex align-center mb-3">
                    <v-icon color="info" class="mr-2">mdi-web</v-icon>
                    <span class="font-weight-bold">联网搜索</span>
                  </div>
                  <v-text-field
                    v-model="configForm.search.tavilyApiKey"
                    label="Tavily API Key"
                    type="password"
                    autocomplete="off"
                    variant="solo"
                    density="comfortable"
                    class="mb-4"
                  />

                  <div class="d-flex align-center mb-3">
                    <v-icon color="secondary" class="mr-2">mdi-chart-timeline-variant</v-icon>
                    <span class="font-weight-bold">LangSmith</span>
                  </div>
                  <v-switch
                    v-model="configForm.langsmith.enabled"
                    color="primary"
                    inset
                    hide-details
                    label="启用 LangSmith"
                    class="mb-3"
                  />
                  <v-text-field
                    v-model="configForm.langsmith.project"
                    label="Project"
                    variant="solo"
                    density="comfortable"
                    class="mb-2"
                  />
                  <v-text-field
                    v-model="configForm.langsmith.apiUrl"
                    label="API URL"
                    variant="solo"
                    density="comfortable"
                    class="mb-2"
                  />
                  <v-text-field
                    v-model="configForm.langsmith.apiKey"
                    label="API Key"
                    type="password"
                    autocomplete="off"
                    variant="solo"
                    density="comfortable"
                    hide-details
                  />
                </v-sheet>
              </v-col>
            </v-row>

            <!-- 知识库管理 -->
            <v-divider class="my-4" />
            <div class="px-4">
              <div class="d-flex align-center mb-3">
                <v-icon color="success" class="mr-2">mdi-database-outline</v-icon>
                <span class="font-weight-bold">知识库管理</span>
                <v-spacer />
                <v-btn
                  size="small"
                  variant="tonal"
                  color="success"
                  :loading="kbLoading"
                  @click="refreshKB"
                >
                  刷新
                </v-btn>
              </div>
              <v-row dense>
                <v-col cols="12" sm="6">
                  <div class="text-caption text-grey-darken-1 mb-1">课程</div>
                  <div class="text-body-2 font-weight-medium">{{ kbCourseName }}</div>
                </v-col>
                <v-col cols="12" sm="6">
                  <div class="text-caption text-grey-darken-1 mb-1">文件 / 分块</div>
                  <div class="text-body-2 font-weight-medium">
                    {{ kbFiles.length }} 个文件 · {{ kbTotalChunks }} 个分块
                  </div>
                </v-col>
              </v-row>
              <v-list v-if="kbFiles.length" density="compact" class="mt-2" lines="one">
                <v-list-item
                  v-for="f in kbFiles.slice(0, 5)"
                  :key="f.fileId"
                  :title="f.fileName"
                  :subtitle="f.chunkCount ? `${f.chunkCount} chunks` : '等待索引'"
                >
                  <template #prepend>
                    <v-icon
                      :icon="f.fileExt === 'pdf' ? 'mdi-file-pdf-box' : f.fileExt === 'pptx' ? 'mdi-file-powerpoint-box' : 'mdi-file-outline'"
                      size="18"
                    />
                  </template>
                  <template #append>
                    <v-chip
                      v-if="f.parseStatus === 'done'"
                      size="x-small"
                      color="success"
                      variant="tonal"
                    >
                      已就绪
                    </v-chip>
                    <v-chip
                      v-else-if="f.parseError"
                      size="x-small"
                      color="error"
                      variant="tonal"
                    >
                      失败
                    </v-chip>
                    <v-chip v-else size="x-small" color="warning" variant="tonal">
                      处理中
                    </v-chip>
                  </template>
                </v-list-item>
              </v-list>
              <div v-if="kbFiles.length > 5" class="text-caption text-grey mt-1">
                还有 {{ kbFiles.length - 5 }} 个文件…
              </div>
              <div v-if="!kbFiles.length && !kbLoading" class="text-caption text-grey my-3">
                知识库中暂无文件。在多人协作板中导入文件即可自动加入知识库。
              </div>
            </div>
          </v-card-text>
          <v-divider />
          <v-card-actions class="pa-4">
            <v-spacer />
            <v-btn
              color="primary"
              size="large"
              :loading="savingConfig"
              @click="saveRuntimeConfig"
            >
              保存配置
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>

      <v-col cols="12" lg="4">
        <v-card min-height="420">
          <v-card-title class="d-flex align-center">
            <v-icon color="secondary" class="mr-3">mdi-shield-check-outline</v-icon>
            <span class="font-weight-bold">当前状态</span>
          </v-card-title>
          <v-card-text>
            <v-list density="comfortable">
              <v-list-item>
                <template #prepend>
                  <v-icon color="primary">mdi-robot-outline</v-icon>
                </template>
                <v-list-item-title>当前 Provider</v-list-item-title>
                <v-list-item-subtitle>
                  {{ configForm.planner.provider || "未设置" }}
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item>
                <template #prepend>
                  <v-icon color="success">mdi-brain</v-icon>
                </template>
                <v-list-item-title>当前模型</v-list-item-title>
                <v-list-item-subtitle>
                  {{ configForm.planner.model || "未设置" }}
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item>
                <template #prepend>
                  <v-icon color="info">mdi-link-variant</v-icon>
                </template>
                <v-list-item-title>API Base</v-list-item-title>
                <v-list-item-subtitle>
                  {{ configForm.planner.apiBase || "未设置" }}
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item>
                <template #prepend>
                  <v-icon color="warning">mdi-head-cog-outline</v-icon>
                </template>
                <v-list-item-title>Thinking 模式</v-list-item-title>
                <v-list-item-subtitle>
                  {{ configForm.planner.providerOptions.extra_body.thinking?.type === "enabled" ? "已启用" : "未启用" }}
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item>
                <template #prepend>
                  <v-icon color="warning">mdi-speedometer</v-icon>
                </template>
                <v-list-item-title>推理强度</v-list-item-title>
                <v-list-item-subtitle>
                  {{ configForm.planner.providerOptions.extra_body.reasoning_effort || "未设置" }}
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item>
                <template #prepend>
                  <v-icon color="warning">mdi-web</v-icon>
                </template>
                <v-list-item-title>联网搜索</v-list-item-title>
                <v-list-item-subtitle>
                  {{ configForm.search.tavilyApiKey ? "已配置" : "未配置" }}
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item>
                <template #prepend>
                  <v-icon color="secondary">mdi-chart-timeline-variant</v-icon>
                </template>
                <v-list-item-title>LangSmith</v-list-item-title>
                <v-list-item-subtitle>
                  {{ configForm.langsmith.enabled ? "已启用" : "未启用" }}
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>

            <v-divider class="my-4" />

            <div class="d-flex flex-wrap ga-2">
              <v-chip color="primary" variant="tonal">
                {{ configForm.planner.apiKey ? "API Key 已填写" : "API Key 未填写" }}
              </v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>
