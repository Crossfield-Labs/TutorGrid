<template>
  <v-card
    variant="flat"
    rounded="lg"
    class="ai-agent pa-3"
    :class="{ 'ai-agent--selected': selected }"
  >
    <div class="d-flex align-center mb-2">
      <v-icon
        icon="mdi-robot-outline"
        size="18"
        color="warning"
        class="mr-2"
      />
      <div class="flex-fill">
        <div class="text-body-2 font-weight-medium">
          Agent · {{ task || "未命名任务" }}
        </div>
        <div class="text-caption text-medium-emphasis">
          sessionId: {{ sessionId || "—" }}
        </div>
      </div>
      <v-chip
        :color="phaseColor(currentPhase)"
        size="small"
        variant="tonal"
        class="mr-1"
      >
        {{ phaseLabel(currentPhase) }}
      </v-chip>
      <v-btn
        icon="mdi-trash-can-outline"
        size="x-small"
        variant="text"
        @click="deleteNode"
      />
    </div>

    <v-progress-linear
      :indeterminate="isRunning"
      :model-value="isRunning ? undefined : progressValue"
      :color="phaseColor(currentPhase)"
      height="4"
      rounded
      class="mb-3"
    />

    <div v-if="history.length > 0" class="ai-agent__timeline mb-2">
      <v-timeline density="compact" align="start" side="end" truncate-line="both">
        <v-timeline-item
          v-for="(ev, i) in history"
          :key="`${ev.timestamp}-${i}`"
          :dot-color="phaseColor(ev.phase)"
          size="x-small"
        >
          <div class="d-flex align-center">
            <span class="text-caption font-weight-medium">
              {{ phaseLabel(ev.phase) }}
            </span>
            <span class="text-caption text-medium-emphasis ml-2">
              {{ formatTime(ev.timestamp) }}
            </span>
          </div>
          <div v-if="ev.message" class="text-caption text-medium-emphasis">
            {{ ev.message }}
          </div>
        </v-timeline-item>
      </v-timeline>
    </div>

    <v-card
      v-if="awaitingPrompt"
      variant="flat"
      rounded="md"
      color="warning"
      class="ai-agent__await pa-3 mb-3"
    >
      <div class="d-flex align-center mb-2">
        <v-icon icon="mdi-account-question-outline" size="18" class="mr-2" />
        <span class="text-body-2 font-weight-medium">需要你的输入</span>
      </div>
      <div class="text-body-2 mb-2">{{ awaitingPrompt }}</div>
      <v-textarea
        :model-value="draft"
        variant="outlined"
        rows="2"
        auto-grow
        hide-details
        density="compact"
        placeholder="在这里输入回复…"
        bg-color="surface"
        class="mb-2"
        @update:model-value="onDraftChange"
      />
      <div class="d-flex">
        <v-spacer />
        <v-btn
          size="small"
          variant="text"
          @click="cancelAwait"
        >
          取消
        </v-btn>
        <v-btn
          size="small"
          color="warning"
          variant="flat"
          prepend-icon="mdi-send"
          :disabled="!draft.trim()"
          class="ml-2"
          @click="submitAwait"
        >
          发送
        </v-btn>
      </div>
    </v-card>

    <v-card
      v-if="finalAnswer"
      variant="flat"
      rounded="md"
      color="success"
      class="ai-agent__final pa-3 mb-3"
    >
      <div class="d-flex align-center mb-2">
        <v-icon icon="mdi-flag-checkered" size="18" class="mr-2" />
        <span class="text-subtitle-2 font-weight-bold">最终结论</span>
      </div>
      <div class="text-body-1 ai-agent__final-text">{{ finalAnswer }}</div>
    </v-card>

    <div v-if="artifacts.length > 0" class="ai-agent__artifacts">
      <v-divider class="mb-2" />
      <div class="d-flex align-center mb-1">
        <v-icon icon="mdi-paperclip" size="14" class="mr-1" />
        <span class="text-caption font-weight-medium">产物</span>
        <v-chip size="x-small" variant="tonal" class="ml-2">
          {{ artifacts.length }}
        </v-chip>
      </div>
      <v-list density="compact" class="ai-agent__artifact-list" nav>
        <v-list-item
          v-for="art in artifacts"
          :key="art.path"
          :title="art.title || basename(art.path)"
          :subtitle="art.summary || art.path"
          rounded="md"
          class="ai-agent__artifact-item"
          @click="openArtifact(art)"
        >
          <template #prepend>
            <v-icon :icon="iconForPath(art.path)" size="18" />
          </template>
          <template #append>
            <v-tooltip location="top" text="用系统默认应用打开">
              <template #activator="{ props: tipProps }">
                <v-btn
                  v-bind="tipProps"
                  icon="mdi-open-in-new"
                  size="x-small"
                  variant="text"
                  @click.stop="openArtifact(art)"
                />
              </template>
            </v-tooltip>
          </template>
        </v-list-item>
      </v-list>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { Node as ProsemirrorNode } from "@tiptap/pm/model";
import type {
  AgentArtifact,
  AgentData,
  AgentPhaseEvent,
  AgentUserState,
} from "../ai-block-types";
import { useOrchestratorStore } from "@/stores/orchestratorStore";
import { useSnackbarStore } from "@/stores/snackbarStore";
import { useWorkspaceStore } from "@/stores/workspaceStore";

const props = defineProps<{
  node: ProsemirrorNode;
  updateAttributes: (attrs: Record<string, any>) => void;
  deleteNode: () => void;
  selected?: boolean;
}>();

const orchestratorStore = useOrchestratorStore();
const snackbarStore = useSnackbarStore();
const workspaceStore = useWorkspaceStore();

const data = computed<AgentData>(() => (props.node.attrs?.data as AgentData) || {});
const userState = computed<AgentUserState>(
  () => (props.node.attrs?.userState as AgentUserState) || {}
);

const task = computed(() => data.value.task || "");
const sessionId = computed(() => props.node.attrs?.sessionId || null);
const history = computed<AgentPhaseEvent[]>(() => data.value.history || []);
const currentPhase = computed(() => data.value.currentPhase || "created");
const awaitingPrompt = computed(() => data.value.awaitingPrompt || "");
const finalAnswer = computed(() => data.value.finalAnswer || "");
const artifacts = computed<AgentArtifact[]>(() => data.value.artifacts || []);
const draft = computed(() => userState.value.draft || "");

const TERMINAL_PHASES = new Set(["completed", "failed", "cancelled"]);
const isRunning = computed(() => !TERMINAL_PHASES.has(currentPhase.value));

const PHASE_ORDER = [
  "created",
  "starting",
  "planning",
  "inspecting",
  "delegating",
  "verifying",
  "completed",
];

const progressValue = computed(() => {
  const idx = PHASE_ORDER.indexOf(currentPhase.value);
  if (idx < 0) return 0;
  return Math.round((idx / (PHASE_ORDER.length - 1)) * 100);
});

const PHASE_LABEL: Record<string, string> = {
  created: "已创建",
  starting: "启动中",
  planning: "规划中",
  inspecting: "检索中",
  delegating: "委派中",
  awaiting_user: "等待输入",
  verifying: "校验中",
  interrupting: "中断中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

const PHASE_COLOR: Record<string, string> = {
  created: "grey",
  starting: "info",
  planning: "primary",
  inspecting: "primary",
  delegating: "primary",
  awaiting_user: "warning",
  verifying: "primary",
  interrupting: "warning",
  completed: "success",
  failed: "error",
  cancelled: "grey",
};

const phaseLabel = (p: string) => PHASE_LABEL[p] || p;
const phaseColor = (p: string) => PHASE_COLOR[p] || "primary";

const formatTime = (ts: number) => {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

const writeUserState = (next: AgentUserState) => {
  props.updateAttributes({
    userState: { ...userState.value, ...next },
  });
};

const onDraftChange = (val: string) => writeUserState({ draft: val });

const submitAwait = async () => {
  const v = draft.value.trim();
  if (!v) return;
  writeUserState({ submitted: v, draft: "" });
  const replyEvent: AgentPhaseEvent = {
    phase: "awaiting_user",
    message: `用户回复：${v}`,
    timestamp: Date.now(),
  };
  const newData: AgentData = {
    ...data.value,
    awaitingPrompt: "",
    history: [...history.value, replyEvent],
    currentPhase: "planning",
  };
  props.updateAttributes({ data: newData });

  if (sessionId.value && orchestratorStore.isLive) {
    try {
      await orchestratorStore.sessionInput({
        sessionId: sessionId.value,
        intent: "reply",
        text: v,
      });
    } catch (e) {
      snackbarStore.showErrorMessage(`发送回复失败：${(e as Error).message}`);
    }
  }
};

const cancelAwait = async () => {
  writeUserState({ draft: "" });
  if (sessionId.value && orchestratorStore.isLive && data.value.awaitingPrompt) {
    try {
      await orchestratorStore.sessionInput({
        sessionId: sessionId.value,
        intent: "interrupt",
        text: "用户取消等待",
      });
    } catch {
      /* ignore — local cancel still applies */
    }
  }
};

const basename = (p: string) => p.split(/[\\/]/).pop() || p;

const openArtifact = async (art: AgentArtifact) => {
  if (!art.path) return;
  const root = workspaceStore.root || "";
  let rel = art.path;
  // Strip workspace root prefix if absolute path was returned
  if (root && (art.path.startsWith(root + "\\") || art.path.startsWith(root + "/"))) {
    rel = art.path.slice(root.length + 1);
  }
  try {
    await workspaceStore.openExternal(rel);
  } catch (e) {
    snackbarStore.showErrorMessage(`无法打开：${(e as Error).message}`);
  }
};

const iconForPath = (p: string) => {
  const ext = p.split(".").pop()?.toLowerCase() || "";
  switch (ext) {
    case "md":
      return "mdi-language-markdown";
    case "json":
      return "mdi-code-json";
    case "py":
      return "mdi-language-python";
    case "ts":
    case "tsx":
      return "mdi-language-typescript";
    case "js":
    case "jsx":
      return "mdi-language-javascript";
    case "vue":
      return "mdi-vuejs";
    case "txt":
    case "log":
      return "mdi-text-box-outline";
    case "pdf":
      return "mdi-file-pdf-box";
    case "png":
    case "jpg":
    case "jpeg":
    case "gif":
    case "webp":
      return "mdi-image-outline";
    default:
      return "mdi-file-outline";
  }
};
</script>

<style scoped lang="scss">
.ai-agent {
  border: 1px solid rgba(var(--v-theme-warning), 0.32);
  background: rgba(var(--v-theme-warning), 0.03);
}

.ai-agent--selected {
  border-color: rgb(var(--v-theme-warning));
}

.ai-agent__timeline {
  max-height: 220px;
  overflow-y: auto;
  padding-right: 4px;
}

.ai-agent__timeline :deep(.v-timeline-item__body) {
  padding-block: 4px;
}

.ai-agent__artifact-list {
  background: transparent;
  padding: 0;
}

.ai-agent__artifact-item {
  cursor: pointer;
}

.ai-agent__final {
  border: 1px solid rgba(var(--v-theme-success), 0.4);
}

.ai-agent__final-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
}
</style>
