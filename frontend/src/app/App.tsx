import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CssBaseline,
  Divider,
  FormControl,
  FormControlLabel,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  ThemeProvider,
  Typography,
  createTheme,
} from "@mui/material";
import { SessionList } from "../features/sessions/SessionList";
import { StatePanel } from "../features/state-panel/StatePanel";
import { Timeline } from "../features/timeline/Timeline";
import { KnowledgeWorkbench } from "../features/knowledge/KnowledgeWorkbench";
import { MemoryWorkbench } from "../features/memory/MemoryWorkbench";
import {
  buildWsUrl,
  createClient,
  type ArtifactTile,
  type KnowledgeChunk,
  type KnowledgeCourse,
  type KnowledgeFile,
  type KnowledgeJob,
  type MemorySearchResult,
  type RagQueryResult,
  type SessionArtifactItem,
  type SessionErrorItem,
  type SessionSnapshot,
  type TimelineEvent,
  type TraceEntry,
  type UiSession,
} from "../lib/ws-client";

type ClientHandle = ReturnType<typeof createClient>;
type PlannerSettings = {
  provider: string;
  model: string;
  apiBase: string;
  apiKey: string;
};

type LangSmithSettings = {
  enabled: boolean;
  project: string;
  apiKey: string;
  apiUrl: string;
};

type MemorySettings = {
  enabled: boolean;
  autoCompact: boolean;
  compactOnComplete: boolean;
  compactOnFailure: boolean;
  retrievalScope: string;
  retrievalStrength: string;
  cleanupEnabled: boolean;
  cleanupIntervalHours: number;
};

type SettingsFeedback = {
  severity: "success" | "info" | "warning" | "error";
  message: string;
};

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#0b57d0",
    },
    background: {
      default: "#f6f7f9",
      paper: "#ffffff",
    },
  },
  shape: {
    borderRadius: 10,
  },
  typography: {
    fontFamily: '"Google Sans","Roboto","Segoe UI","PingFang SC","Microsoft YaHei",sans-serif',
  },
});

export function App() {
  const defaultWsUrl = buildWsUrl();
  const [sessions, setSessions] = useState<UiSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string>("");
  const [timelinesBySession, setTimelinesBySession] = useState<Record<string, TimelineEvent[]>>({});
  const [liveEventsBySession, setLiveEventsBySession] = useState<Record<string, TimelineEvent | null>>({});
  const [snapshotsBySession, setSnapshotsBySession] = useState<Record<string, SessionSnapshot>>({});
  const [traceBySession, setTraceBySession] = useState<Record<string, TraceEntry[]>>({});
  const [errorsBySession, setErrorsBySession] = useState<Record<string, SessionErrorItem[]>>({});
  const [artifactsBySession, setArtifactsBySession] = useState<
    Record<string, { items: SessionArtifactItem[]; tiles: ArtifactTile[] }>
  >({});
  const [connectionState, setConnectionState] = useState("未连接");
  const [serverUrl, setServerUrl] = useState(defaultWsUrl);
  const [settingsUrl, setSettingsUrl] = useState(defaultWsUrl);
  const [view, setView] = useState<"workspace" | "knowledge" | "memory" | "settings">("workspace");
  const [composerValue, setComposerValue] = useState("");
  const [pendingTaskId, setPendingTaskId] = useState<string>("");
  const [plannerSettings, setPlannerSettings] = useState<PlannerSettings>({
    provider: "openai_compat",
    model: "",
    apiBase: "",
    apiKey: "",
  });
  const [langsmithSettings, setLangsmithSettings] = useState<LangSmithSettings>({
    enabled: false,
    project: "pc-orchestrator-core",
    apiKey: "",
    apiUrl: "",
  });
  const [memorySettings, setMemorySettings] = useState<MemorySettings>({
    enabled: true,
    autoCompact: true,
    compactOnComplete: true,
    compactOnFailure: true,
    retrievalScope: "global",
    retrievalStrength: "standard",
    cleanupEnabled: true,
    cleanupIntervalHours: 24,
  });
  const [isConfigLoading, setIsConfigLoading] = useState(true);
  const [isConfigSaving, setIsConfigSaving] = useState(false);
  const [isMemoryCleanupRunning, setIsMemoryCleanupRunning] = useState(false);
  const [isMemoryReindexing, setIsMemoryReindexing] = useState(false);
  const [isMemorySearching, setIsMemorySearching] = useState(false);
  const [settingsFeedback, setSettingsFeedback] = useState<SettingsFeedback | null>(null);
  const [memoryFeedback, setMemoryFeedback] = useState<SettingsFeedback | null>(null);
  const [memorySearchResult, setMemorySearchResult] = useState<MemorySearchResult | null>(null);
  const [knowledgeFeedback, setKnowledgeFeedback] = useState<SettingsFeedback | null>(null);
  const [knowledgeCourses, setKnowledgeCourses] = useState<KnowledgeCourse[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState("");
  const [knowledgeFiles, setKnowledgeFiles] = useState<KnowledgeFile[]>([]);
  const [knowledgeChunks, setKnowledgeChunks] = useState<KnowledgeChunk[]>([]);
  const [knowledgeJobs, setKnowledgeJobs] = useState<KnowledgeJob[]>([]);
  const [ragResult, setRagResult] = useState<RagQueryResult | null>(null);
  const [isKnowledgeLoadingCourses, setIsKnowledgeLoadingCourses] = useState(false);
  const [isKnowledgeCreatingCourse, setIsKnowledgeCreatingCourse] = useState(false);
  const [isKnowledgeDeletingCourse, setIsKnowledgeDeletingCourse] = useState(false);
  const [isKnowledgeLoadingCourseData, setIsKnowledgeLoadingCourseData] = useState(false);
  const [isKnowledgeIngestingFile, setIsKnowledgeIngestingFile] = useState(false);
  const [isKnowledgeQueryingRag, setIsKnowledgeQueryingRag] = useState(false);
  const [isKnowledgeReembeddingCourse, setIsKnowledgeReembeddingCourse] = useState(false);
  const [isKnowledgeReindexingCourse, setIsKnowledgeReindexingCourse] = useState(false);

  const clientRef = useRef<ClientHandle | null>(null);
  const selectedSessionIdRef = useRef(selectedSessionId);

  useEffect(() => {
    selectedSessionIdRef.current = selectedSessionId;
  }, [selectedSessionId]);

  const selectedSession = useMemo(
    () => sessions.find((session) => session.sessionId === selectedSessionId) ?? null,
    [selectedSessionId, sessions],
  );
  const terminalStatuses = new Set(["COMPLETED", "FAILED", "CANCELLED"]);
  const selectedSnapshot = selectedSessionId ? snapshotsBySession[selectedSessionId] ?? selectedSession?.snapshot ?? null : null;
  const selectedTimeline = selectedSessionId ? timelinesBySession[selectedSessionId] ?? [] : [];
  const selectedLiveEvent = selectedSessionId ? liveEventsBySession[selectedSessionId] ?? null : null;
  const selectedStatus = selectedSnapshot?.status ?? selectedSession?.status ?? "";
  const selectedTrace = selectedSessionId ? traceBySession[selectedSessionId] ?? [] : [];
  const selectedErrors = selectedSessionId ? errorsBySession[selectedSessionId] ?? [] : [];
  const selectedArtifacts = selectedSessionId ? artifactsBySession[selectedSessionId] ?? { items: [], tiles: [] } : { items: [], tiles: [] };

  useEffect(() => {
    setSettingsUrl(serverUrl);
  }, [serverUrl]);

  useEffect(() => {
    const client = createClient({
      url: serverUrl,
      onOpen: () => {
        setConnectionState("已连接");
        requestSessionList(client);
        setIsConfigLoading(true);
        requestConfig(client);
        setIsKnowledgeLoadingCourses(true);
        requestKnowledgeCourseList(client);
        const currentSessionId = selectedSessionIdRef.current;
        if (currentSessionId) {
          requestSessionHistory(client, currentSessionId);
          requestSessionSnapshot(client, currentSessionId);
          requestSessionTrace(client, currentSessionId);
          requestSessionErrors(client, currentSessionId);
          requestSessionArtifacts(client, currentSessionId);
        }
      },
      onClose: () => setConnectionState("已断开"),
      onError: () => setConnectionState("连接异常"),
      onEvent: (message) => {
        if (message.type !== "event") {
          return;
        }

        if (message.event === "orchestrator.session.list") {
          const items = Array.isArray(message.payload?.items) ? (message.payload.items as UiSession[]) : [];
          setSessions((current) => mergeSessionLists(current, items));
          setSelectedSessionId((current) => current || items[0]?.sessionId || "");
          return;
        }

        if (message.event === "orchestrator.config.get" || message.event === "orchestrator.config.set") {
          const planner = message.payload?.planner;
          const memory = message.payload?.memory;
          const langsmith = message.payload?.langsmith;
          if (planner && typeof planner === "object") {
            setPlannerSettings({
              provider: getString((planner as Record<string, unknown>).provider) ?? "openai_compat",
              model: getString((planner as Record<string, unknown>).model) ?? "",
              apiBase: getString((planner as Record<string, unknown>).apiBase) ?? "",
              apiKey: getString((planner as Record<string, unknown>).apiKey) ?? "",
            });
          }
          if (langsmith && typeof langsmith === "object") {
            setLangsmithSettings({
              enabled: Boolean((langsmith as Record<string, unknown>).enabled ?? false),
              project: getString((langsmith as Record<string, unknown>).project) ?? "pc-orchestrator-core",
              apiKey: getString((langsmith as Record<string, unknown>).apiKey) ?? "",
              apiUrl: getString((langsmith as Record<string, unknown>).apiUrl) ?? "",
            });
          }
          if (memory && typeof memory === "object") {
            setMemorySettings({
              enabled: Boolean((memory as Record<string, unknown>).enabled ?? true),
              autoCompact: Boolean((memory as Record<string, unknown>).autoCompact ?? true),
              compactOnComplete: Boolean((memory as Record<string, unknown>).compactOnComplete ?? true),
              compactOnFailure: Boolean((memory as Record<string, unknown>).compactOnFailure ?? true),
              retrievalScope: getString((memory as Record<string, unknown>).retrievalScope) ?? "global",
              retrievalStrength: getString((memory as Record<string, unknown>).retrievalStrength) ?? "standard",
              cleanupEnabled: Boolean((memory as Record<string, unknown>).cleanupEnabled ?? true),
              cleanupIntervalHours: Number((memory as Record<string, unknown>).cleanupIntervalHours ?? 24) || 24,
            });
          }
          setIsConfigLoading(false);
        if (message.event === "orchestrator.config.set") {
          setIsConfigSaving(false);
          setSettingsFeedback({ severity: "success", message: "设置已保存。" });
        }
        return;
      }

      if (message.event === "orchestrator.knowledge.course.list") {
        const items = Array.isArray(message.payload?.items) ? message.payload.items : [];
        const nextCourses = items
          .map((item) => mapKnowledgeCourse(item as Record<string, unknown>))
          .filter((item): item is KnowledgeCourse => item !== null);
        setKnowledgeCourses(nextCourses);
        setIsKnowledgeLoadingCourses(false);
        setSelectedCourseId((current) =>
          nextCourses.some((course) => course.courseId === current) ? current : nextCourses[0]?.courseId || "",
        );
        return;
      }

      if (message.event === "orchestrator.knowledge.course.create") {
        setIsKnowledgeCreatingCourse(false);
        setKnowledgeFeedback({ severity: "success", message: "课程创建成功。" });
        requestKnowledgeCourseList(client);
        return;
      }

      if (message.event === "orchestrator.knowledge.course.delete") {
        setIsKnowledgeDeletingCourse(false);
        setKnowledgeFeedback({ severity: "success", message: "课程已删除。" });
        setSelectedCourseId("");
        setKnowledgeFiles([]);
        setKnowledgeChunks([]);
        setKnowledgeJobs([]);
        requestKnowledgeCourseList(client);
        return;
      }

      if (message.event === "orchestrator.knowledge.file.list") {
        const items = Array.isArray(message.payload?.items) ? message.payload.items : [];
        const nextFiles = items
          .map((item) => mapKnowledgeFile(item as Record<string, unknown>))
          .filter((item): item is KnowledgeFile => item !== null);
        setKnowledgeFiles(nextFiles);
        setIsKnowledgeLoadingCourseData(false);
        return;
      }

      if (message.event === "orchestrator.knowledge.chunk.list") {
        const items = Array.isArray(message.payload?.items) ? message.payload.items : [];
        const nextChunks = items
          .map((item) => mapKnowledgeChunk(item as Record<string, unknown>))
          .filter((item): item is KnowledgeChunk => item !== null);
        setKnowledgeChunks(nextChunks);
        setIsKnowledgeLoadingCourseData(false);
        return;
      }

      if (message.event === "orchestrator.knowledge.job.list") {
        const items = Array.isArray(message.payload?.items) ? message.payload.items : [];
        const nextJobs = items
          .map((item) => mapKnowledgeJob(item as Record<string, unknown>))
          .filter((item): item is KnowledgeJob => item !== null);
        setKnowledgeJobs(nextJobs);
        setIsKnowledgeLoadingCourseData(false);
        return;
      }

      if (message.event === "orchestrator.knowledge.file.ingest") {
        setIsKnowledgeIngestingFile(false);
        const status = getString(message.payload?.status) ?? "unknown";
        const chunkCount = Number(message.payload?.chunkCount ?? 0) || 0;
        const errorText = getString(message.payload?.error) ?? "";
        if (status === "success") {
          setKnowledgeFeedback({
            severity: "success",
            message: `文件入库成功，生成 ${chunkCount} 个分块。`,
          });
        } else {
          setKnowledgeFeedback({
            severity: "error",
            message: `文件入库失败：${errorText || "未知错误"}`,
          });
        }
        if (selectedCourseId) {
          requestKnowledgeCourseData(client, selectedCourseId);
        }
        return;
      }

      if (message.event === "orchestrator.knowledge.file.delete") {
        setKnowledgeFeedback({ severity: "success", message: "文件已删除。" });
        if (selectedCourseId) {
          requestKnowledgeCourseData(client, selectedCourseId);
        }
        return;
      }

      if (message.event === "orchestrator.knowledge.rag.query") {
        setIsKnowledgeQueryingRag(false);
        const ragPayload = mapRagQueryResult(message.payload as Record<string, unknown>);
        setRagResult(ragPayload);
        setKnowledgeFeedback({ severity: "success", message: "RAG 查询完成。" });
        return;
      }

      if (message.event === "orchestrator.knowledge.course.reembed") {
        setIsKnowledgeReembeddingCourse(false);
        const updatedCount = Number(message.payload?.updatedCount ?? 0) || 0;
        const chunkCount = Number(message.payload?.chunkCount ?? 0) || 0;
        setKnowledgeFeedback({
          severity: "success",
          message: `课程重嵌入完成：updated=${updatedCount}, chunk=${chunkCount}`,
        });
        return;
      }

      if (message.event === "orchestrator.knowledge.course.reindex") {
        setIsKnowledgeReindexingCourse(false);
        const backend = getString(message.payload?.indexBackend) ?? "none";
        const chunkCount = Number(message.payload?.chunkCount ?? 0) || 0;
        setKnowledgeFeedback({
          severity: "success",
          message: `课程索引重建完成：backend=${backend}, chunk=${chunkCount}`,
        });
        return;
      }

      if (message.event === "orchestrator.memory.cleanup") {
        setIsMemoryCleanupRunning(false);
        const deleted = Number(message.payload?.deletedDocuments ?? 0);
        const duplicates = Number(message.payload?.duplicateDocuments ?? 0);
        const emptyDocuments = Number(message.payload?.emptyDocuments ?? 0);
        const messageText = `记忆整理完成：共清理 ${deleted} 条，其中重复 ${duplicates} 条、空文档 ${emptyDocuments} 条。`;
        setSettingsFeedback({ severity: "success", message: messageText });
        setMemoryFeedback({ severity: "success", message: messageText });
        return;
      }

      if (message.event === "orchestrator.memory.reindex") {
        const backend = getString(message.payload?.indexBackend) ?? "none";
        const documentCount = Number(message.payload?.documentCount ?? 0) || 0;
        setIsMemoryReindexing(false);
        const messageText = `Memory 索引重建完成：backend=${backend}, documents=${documentCount}`;
        setSettingsFeedback({
          severity: "success",
          message: messageText,
        });
        setMemoryFeedback({
          severity: "success",
          message: messageText,
        });
        return;
      }

      if (message.event === "orchestrator.memory.search") {
        setIsMemorySearching(false);
        const payload = mapMemorySearchResult(message.payload as Record<string, unknown>);
        setMemorySearchResult(payload);
        setMemoryFeedback({
          severity: "success",
          message: `记忆检索完成，命中 ${(payload?.items.length ?? 0).toString()} 条。`,
        });
        return;
      }

      if (message.event === "orchestrator.session.failed" && isMemoryReindexing) {
        const errorMessage = getString(message.payload?.message) ?? "Unknown error";
        setIsMemoryReindexing(false);
        setSettingsFeedback({ severity: "error", message: `Memory 索引重建失败：${errorMessage}` });
        setMemoryFeedback({ severity: "error", message: `Memory 索引重建失败：${errorMessage}` });
        return;
      }

      if (message.event === "orchestrator.session.failed" && isMemoryCleanupRunning) {
        const errorMessage = getString(message.payload?.message) ?? "Unknown error";
        setIsMemoryCleanupRunning(false);
        setSettingsFeedback({ severity: "error", message: `记忆整理失败：${errorMessage}` });
        setMemoryFeedback({ severity: "error", message: `记忆整理失败：${errorMessage}` });
        return;
      }

      if (message.event === "orchestrator.session.failed" && isMemorySearching) {
        const errorMessage = getString(message.payload?.message) ?? "Unknown error";
        setIsMemorySearching(false);
        setMemoryFeedback({ severity: "error", message: `记忆检索失败：${errorMessage}` });
        return;
      }

      if (
        message.event === "orchestrator.session.failed" &&
        (isKnowledgeCreatingCourse ||
          isKnowledgeDeletingCourse ||
          isKnowledgeIngestingFile ||
          isKnowledgeQueryingRag ||
          isKnowledgeReembeddingCourse ||
          isKnowledgeReindexingCourse ||
          isKnowledgeLoadingCourseData)
      ) {
        const errorMessage = getString(message.payload?.message) ?? "Unknown error";
        setIsKnowledgeCreatingCourse(false);
        setIsKnowledgeDeletingCourse(false);
        setIsKnowledgeIngestingFile(false);
        setIsKnowledgeQueryingRag(false);
        setIsKnowledgeReembeddingCourse(false);
        setIsKnowledgeReindexingCourse(false);
        setIsKnowledgeLoadingCourseData(false);
        setIsKnowledgeLoadingCourses(false);
        setKnowledgeFeedback({ severity: "error", message: `知识库操作失败：${errorMessage}` });
        return;
      }

      if (message.event === "orchestrator.session.history" && message.sessionId) {
        const items = Array.isArray(message.payload?.items) ? message.payload.items : [];
        const historyItems = items
          .map((item, index) => mapHistoryItem(item as Record<string, unknown>, index))
          .filter((item): item is TimelineEvent => item !== null);
        const history = historyItems.filter((item) => isPersistentTimelineEvent(item.event ?? "", item.kind));
        const lastLiveEvent = [...historyItems]
          .reverse()
          .find((item) => !isPersistentTimelineEvent(item.event ?? "", item.kind)) ?? null;
        setTimelinesBySession((current) => ({
          ...current,
          [message.sessionId as string]: history,
        }));
        setLiveEventsBySession((current) => ({
          ...current,
          [message.sessionId as string]: lastLiveEvent,
        }));
        return;
      }

        if (message.event === "orchestrator.session.trace" && message.sessionId) {
          const items = Array.isArray(message.payload?.items) ? message.payload.items : [];
          setTraceBySession((current) => ({
            ...current,
            [message.sessionId as string]: items
              .map((item) => mapTraceItem(item as Record<string, unknown>))
              .filter((item): item is TraceEntry => item !== null),
          }));
          return;
        }

        if (message.event === "orchestrator.session.errors" && message.sessionId) {
          const items = Array.isArray(message.payload?.items) ? message.payload.items : [];
          setErrorsBySession((current) => ({
            ...current,
            [message.sessionId as string]: items
              .map((item) => mapErrorItem(item as Record<string, unknown>))
              .filter((item): item is SessionErrorItem => item !== null),
          }));
          return;
        }

        if (message.event === "orchestrator.session.artifacts" && message.sessionId) {
          const items = Array.isArray(message.payload?.items) ? message.payload.items : [];
          const tiles = Array.isArray(message.payload?.tiles) ? message.payload.tiles : [];
          setArtifactsBySession((current) => ({
            ...current,
            [message.sessionId as string]: {
              items: items
                .map((item) => mapArtifactItem(item as Record<string, unknown>))
                .filter((item): item is SessionArtifactItem => item !== null),
              tiles: tiles
                .map((item) => mapArtifactTile(item as Record<string, unknown>))
                .filter((item): item is ArtifactTile => item !== null),
            },
          }));
          return;
        }

        const sessionId = message.sessionId;
        if (!sessionId) {
          return;
        }
        if (pendingTaskId && message.taskId === pendingTaskId) {
          setSelectedSessionId(sessionId);
          setPendingTaskId("");
        }
        const payload = message.payload ?? {};
        const snapshot = isRecord(payload.snapshot) ? (payload.snapshot as SessionSnapshot) : null;

        if (snapshot) {
          setSnapshotsBySession((current) => ({
            ...current,
            [sessionId]: {
              ...(current[sessionId] ?? {}),
              ...snapshot,
            },
          }));
        }

        const shouldPromote =
          message.event !== "orchestrator.session.snapshot" &&
          message.event !== "orchestrator.session.history" &&
          message.event !== "orchestrator.session.list";
        setSessions((current) => upsertSession(current, sessionId, payload, snapshot, shouldPromote));
        setSelectedSessionId((current) => current || sessionId);

        if (message.event === "orchestrator.session.snapshot") {
          return;
        }

        const nextEvent = mapRealtimeEvent(message.event, payload);
        if (!nextEvent) {
          return;
        }
        if (isPersistentTimelineEvent(message.event, nextEvent.kind)) {
          setTimelinesBySession((current) => {
            const existing = current[sessionId] ?? [];
            return {
              ...current,
              [sessionId]: [...existing, nextEvent],
            };
          });
          setLiveEventsBySession((current) => ({
            ...current,
            [sessionId]: null,
          }));
        } else {
          setLiveEventsBySession((current) => ({
            ...current,
            [sessionId]: nextEvent,
          }));
        }

        const currentSessionId = selectedSessionIdRef.current;
        if (currentSessionId === sessionId) {
          requestSessionTrace(client, sessionId);
          if (message.event.endsWith(".failed")) {
            requestSessionErrors(client, sessionId);
          }
          if (message.event.includes(".artifact.") || message.event.endsWith(".tile")) {
            requestSessionArtifacts(client, sessionId);
          }
        }
      },
    });

    clientRef.current = client;
    client.connect();

    return () => {
      client.close();
      clientRef.current = null;
    };
  }, [pendingTaskId, serverUrl]);

  useEffect(() => {
    if (!selectedSessionId) {
      return;
    }
    const client = clientRef.current;
    if (!client) {
      return;
    }
    requestSessionHistory(client, selectedSessionId);
    requestSessionSnapshot(client, selectedSessionId);
    requestSessionTrace(client, selectedSessionId);
    requestSessionErrors(client, selectedSessionId);
    requestSessionArtifacts(client, selectedSessionId);
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedCourseId) {
      setKnowledgeFiles([]);
      setKnowledgeChunks([]);
      setKnowledgeJobs([]);
      setRagResult(null);
      return;
    }
    setRagResult(null);
    const client = clientRef.current;
    if (!client) {
      return;
    }
    setIsKnowledgeLoadingCourseData(true);
    requestKnowledgeCourseData(client, selectedCourseId);
  }, [selectedCourseId]);

  const prepareNewTask = () => {
    setComposerValue("");
    setSelectedSessionId("");
  };

  const handleSelectSession = (sessionId: string) => {
    setSelectedSessionId(sessionId);
    setComposerValue("");
  };

  const handleRenameSession = (sessionId: string, title: string) => {
    const normalized = title.trim();
    if (!normalized) {
      return;
    }
    setSessions((current) =>
      current.map((session) =>
        session.sessionId === sessionId
          ? {
              ...session,
              displayTitle: normalized,
            }
          : session,
      ),
    );
  };

  const handleSubmit = () => {
    const client = clientRef.current;
    if (!client) {
      return;
    }
    const trimmed = composerValue.trim();
    const hasActiveSession = Boolean(selectedSessionId) && !terminalStatuses.has(selectedStatus);
    const awaitingInput = Boolean(selectedSnapshot?.awaitingInput);

    if (!hasActiveSession) {
      if (!trimmed) {
        return;
      }
      const requestId = crypto.randomUUID();
      client.send({
        type: "req",
        id: requestId,
        method: "orchestrator.session.start",
        taskId: requestId,
        nodeId: "desktop-gui",
        params: {
          runner: "pc_subagent",
          workspace: ".",
          task: trimmed,
          goal: trimmed,
        },
      });
      setPendingTaskId(requestId);
      setComposerValue("");
      return;
    }

    if (!trimmed) {
      return;
    }

    client.send({
      type: "req",
      id: crypto.randomUUID(),
      method: "orchestrator.session.input",
      sessionId: selectedSessionId,
      params: {
        text: trimmed,
        inputIntent: awaitingInput ? "reply" : "instruction",
      },
    });
    setSessions((current) => touchSessionToTop(current, selectedSessionId));
    setComposerValue("");
  };

  const requestExplain = () => {
    if (!selectedSessionId || !clientRef.current) {
      return;
    }
    clientRef.current.send({
      type: "req",
      id: crypto.randomUUID(),
      method: "orchestrator.session.input",
      sessionId: selectedSessionId,
      params: {
        text: "",
        inputIntent: "explain",
      },
    });
  };

  const requestSnapshot = () => {
    if (!selectedSessionId || !clientRef.current) {
      return;
    }
    requestSessionSnapshot(clientRef.current, selectedSessionId);
  };

  const applySettings = () => {
    const nextUrl = settingsUrl.trim();
    if (!nextUrl || nextUrl === serverUrl) {
      return;
    }
    setSettingsFeedback(null);
    setServerUrl(nextUrl);
  };

  const applyPlannerSettings = () => {
    if (!clientRef.current) {
      return;
    }
    setIsConfigSaving(true);
    setSettingsFeedback(null);
    clientRef.current.send({
      type: "req",
      id: crypto.randomUUID(),
      method: "orchestrator.config.set",
      params: {
        provider: plannerSettings.provider,
        model: plannerSettings.model,
        apiBase: plannerSettings.apiBase,
        apiKey: plannerSettings.apiKey,
        memoryEnabled: memorySettings.enabled,
        memoryAutoCompact: memorySettings.autoCompact,
        memoryCompactOnComplete: memorySettings.compactOnComplete,
        memoryCompactOnFailure: memorySettings.compactOnFailure,
        memoryRetrievalScope: memorySettings.retrievalScope,
        memoryRetrievalStrength: memorySettings.retrievalStrength,
        memoryCleanupEnabled: memorySettings.cleanupEnabled,
        memoryCleanupIntervalHours: memorySettings.cleanupIntervalHours,
        langsmithEnabled: langsmithSettings.enabled,
        langsmithProject: langsmithSettings.project,
        langsmithApiKey: langsmithSettings.apiKey,
        langsmithApiUrl: langsmithSettings.apiUrl,
      },
    });
  };

  const runMemoryCleanup = () => {
    if (!clientRef.current) {
      return;
    }
    setIsMemoryCleanupRunning(true);
    setSettingsFeedback(null);
    setMemoryFeedback(null);
    clientRef.current.send({
      type: "req",
      id: crypto.randomUUID(),
      method: "orchestrator.memory.cleanup",
      params: {},
    });
  };

  const applyMemoryReindex = () => {
    if (!clientRef.current || isMemoryReindexing) {
      return;
    }
    setIsMemoryReindexing(true);
    setSettingsFeedback(null);
    setMemoryFeedback(null);
    clientRef.current.send({
      type: "req",
      id: crypto.randomUUID(),
      method: "orchestrator.memory.reindex",
      params: {},
    });
  };

  const runMemorySearch = (query: string, limit: number, sessionId?: string) => {
    if (!clientRef.current) {
      return;
    }
    const text = query.trim();
    if (!text) {
      return;
    }
    setIsMemorySearching(true);
    setMemoryFeedback(null);
    setMemorySearchResult(null);
    clientRef.current.send({
      type: "req",
      id: crypto.randomUUID(),
      method: "orchestrator.memory.search",
      ...(sessionId?.trim() ? { sessionId: sessionId.trim() } : {}),
      params: {
        text,
        limit: Math.max(1, limit || 8),
      },
    });
  };

  const refreshKnowledgeCourses = () => {
    if (!clientRef.current) {
      return;
    }
    setIsKnowledgeLoadingCourses(true);
    requestKnowledgeCourseList(clientRef.current);
  };

  const createKnowledgeCourse = (name: string, description: string) => {
    if (!clientRef.current) {
      return;
    }
    const courseName = name.trim();
    if (!courseName) {
      return;
    }
    setIsKnowledgeCreatingCourse(true);
    setKnowledgeFeedback(null);
    clientRef.current.send({
      type: "req",
      id: crypto.randomUUID(),
      method: "orchestrator.knowledge.course.create",
      params: {
        courseName,
        courseDescription: description.trim(),
      },
    });
  };

  const deleteKnowledgeCourse = (courseId: string) => {
    if (!clientRef.current || !courseId.trim()) {
      return;
    }
    setIsKnowledgeDeletingCourse(true);
    setKnowledgeFeedback(null);
    clientRef.current.send({
      type: "req",
      id: crypto.randomUUID(),
      method: "orchestrator.knowledge.course.delete",
      params: {
        courseId: courseId.trim(),
      },
    });
  };

  const refreshKnowledgeCourseData = (courseId: string) => {
    if (!clientRef.current || !courseId.trim()) {
      return;
    }
    setIsKnowledgeLoadingCourseData(true);
    requestKnowledgeCourseData(clientRef.current, courseId.trim());
  };

  const ingestKnowledgeFile = (params: {
    courseId: string;
    filePath: string;
    fileName: string;
    chunkSize: number;
  }) => {
    if (!clientRef.current) {
      return;
    }
    const courseId = params.courseId.trim();
    const filePath = params.filePath.trim();
    if (!courseId || !filePath) {
      return;
    }
    setIsKnowledgeIngestingFile(true);
    setKnowledgeFeedback(null);
    clientRef.current.send({
      type: "req",
      id: crypto.randomUUID(),
      method: "orchestrator.knowledge.file.ingest",
      params: {
        courseId,
        filePath,
        fileName: params.fileName.trim(),
        chunkSize: Math.max(200, params.chunkSize || 900),
      },
    });
  };

  const deleteKnowledgeFile = (courseId: string, fileId: string) => {
    if (!clientRef.current || !courseId.trim() || !fileId.trim()) {
      return;
    }
    setKnowledgeFeedback(null);
    clientRef.current.send({
      type: "req",
      id: crypto.randomUUID(),
      method: "orchestrator.knowledge.file.delete",
      params: {
        courseId: courseId.trim(),
        target: fileId.trim(),
      },
    });
  };

  const runKnowledgeRagQuery = (courseId: string, text: string, limit: number) => {
    if (!clientRef.current) {
      return;
    }
    const normalizedCourse = courseId.trim();
    const queryText = text.trim();
    if (!normalizedCourse || !queryText) {
      return;
    }
    setIsKnowledgeQueryingRag(true);
    setKnowledgeFeedback(null);
    clientRef.current.send({
      type: "req",
      id: crypto.randomUUID(),
      method: "orchestrator.knowledge.rag.query",
      params: {
        courseId: normalizedCourse,
        text: queryText,
        limit: Math.max(1, limit || 8),
      },
    });
  };

  const reembedKnowledgeCourse = (courseId: string, batchSize: number) => {
    if (!clientRef.current || !courseId.trim()) {
      return;
    }
    setIsKnowledgeReembeddingCourse(true);
    setKnowledgeFeedback(null);
    clientRef.current.send({
      type: "req",
      id: crypto.randomUUID(),
      method: "orchestrator.knowledge.course.reembed",
      params: {
        courseId: courseId.trim(),
        batchSize: Math.max(1, batchSize || 32),
      },
    });
  };

  const reindexKnowledgeCourse = (courseId: string) => {
    if (!clientRef.current || !courseId.trim()) {
      return;
    }
    setIsKnowledgeReindexingCourse(true);
    setKnowledgeFeedback(null);
    clientRef.current.send({
      type: "req",
      id: crypto.randomUUID(),
      method: "orchestrator.knowledge.course.reindex",
      params: {
        courseId: courseId.trim(),
      },
    });
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ height: "100vh", display: "grid", gridTemplateRows: "auto minmax(0, 1fr)", bgcolor: "background.default" }}>
        <Box
          component="header"
          sx={{
            borderBottom: "1px solid",
            borderColor: "divider",
            px: 2,
            py: 1,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            bgcolor: "background.paper",
          }}
        >
          <Typography variant="subtitle2" letterSpacing={1.1}>
            PC ORCHESTRATOR
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            <Chip
              size="small"
              color={connectionState === "已连接" ? "success" : "default"}
              label={connectionState}
              variant={connectionState === "已连接" ? "filled" : "outlined"}
            />
            <Tabs
              value={view}
              onChange={(_, value: "workspace" | "knowledge" | "memory" | "settings") => setView(value)}
              sx={{ minHeight: 32, "& .MuiTab-root": { minHeight: 32 } }}
            >
              <Tab value="workspace" label="工作台" />
              <Tab value="knowledge" label="知识库/RAG" />
              <Tab value="memory" label="记忆" />
              <Tab value="settings" label="设置" />
            </Tabs>
          </Stack>
        </Box>

        {view === "workspace" ? (
          <Box sx={{ display: "grid", gridTemplateColumns: "260px minmax(0,1fr) 300px", minHeight: 0 }}>
            <SessionList
              sessions={sessions}
              selectedSessionId={selectedSessionId}
              onSelect={handleSelectSession}
              onPrepareNewTask={prepareNewTask}
              onRenameSession={handleRenameSession}
            />
            <Timeline
              session={selectedSession}
              events={selectedTimeline}
              liveEvent={selectedLiveEvent}
              inputValue={composerValue}
              onInputChange={setComposerValue}
              onSubmit={handleSubmit}
            onSnapshot={requestSnapshot}
            onExplain={requestExplain}
            isAwaitingInput={Boolean(selectedSnapshot?.awaitingInput)}
            isRunning={Boolean(selectedSessionId) && !terminalStatuses.has(selectedStatus)}
            />
            <StatePanel
              session={selectedSession}
              snapshot={selectedSnapshot}
              traceEntries={selectedTrace}
              errorItems={selectedErrors}
              artifactData={selectedArtifacts}
            />
          </Box>
        ) : view === "knowledge" ? (
          <KnowledgeWorkbench
            courses={knowledgeCourses}
            selectedCourseId={selectedCourseId}
            files={knowledgeFiles}
            chunks={knowledgeChunks}
            jobs={knowledgeJobs}
            ragResult={ragResult}
            notice={knowledgeFeedback}
            busy={{
              loadingCourses: isKnowledgeLoadingCourses,
              creatingCourse: isKnowledgeCreatingCourse,
              deletingCourse: isKnowledgeDeletingCourse,
              ingestingFile: isKnowledgeIngestingFile,
              loadingCourseData: isKnowledgeLoadingCourseData,
              queryingRag: isKnowledgeQueryingRag,
              reembeddingCourse: isKnowledgeReembeddingCourse,
              reindexingCourse: isKnowledgeReindexingCourse,
            }}
            onSelectCourse={setSelectedCourseId}
            onRefreshCourses={refreshKnowledgeCourses}
            onCreateCourse={createKnowledgeCourse}
            onDeleteCourse={deleteKnowledgeCourse}
            onRefreshCourseData={refreshKnowledgeCourseData}
            onIngestFile={ingestKnowledgeFile}
            onDeleteFile={deleteKnowledgeFile}
            onRagQuery={runKnowledgeRagQuery}
            onReembedCourse={reembedKnowledgeCourse}
            onReindexCourse={reindexKnowledgeCourse}
          />
        ) : view === "memory" ? (
          <MemoryWorkbench
            notice={memoryFeedback}
            busy={{
              searching: isMemorySearching,
              cleaning: isMemoryCleanupRunning,
              reindexing: isMemoryReindexing,
            }}
            result={memorySearchResult}
            onSearch={runMemorySearch}
            onCleanup={runMemoryCleanup}
            onReindex={applyMemoryReindex}
          />
        ) : (
          <Box sx={{ p: 2.5, overflow: "auto" }}>
            <Stack spacing={2} sx={{ maxWidth: 860 }}>
              <Paper variant="outlined" sx={{ overflow: "hidden" }}>
                {isConfigLoading || isConfigSaving || isMemoryCleanupRunning || isMemoryReindexing ? (
                  <LinearProgress />
                ) : null}
                <Box sx={{ p: 2.5 }}>
                  <Typography variant="h6">设置</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    连接、模型和记忆策略统一在这里配置。
                  </Typography>
                  {settingsFeedback ? (
                    <Alert severity={settingsFeedback.severity} sx={{ mt: 2 }}>
                      {settingsFeedback.message}
                    </Alert>
                  ) : null}
                </Box>
                <Divider />
                <Box sx={{ p: 2.5, display: "grid", gap: 3 }}>
                  <Box>
                    <Typography variant="subtitle1">连接</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
                      桌面端会连接这里的 WebSocket 服务地址。
                    </Typography>
                    <Stack spacing={2}>
                      <TextField
                        fullWidth
                        label="WebSocket 地址"
                        value={settingsUrl}
                        onChange={(event) => setSettingsUrl(event.target.value)}
                      />
                      <Stack direction="row" justifyContent="flex-end" spacing={1}>
                        <Button variant="outlined" onClick={() => setSettingsUrl(serverUrl)}>
                          还原
                        </Button>
                        <Button variant="contained" onClick={applySettings}>
                          应用连接
                        </Button>
                      </Stack>
                    </Stack>
                  </Box>

                  <Divider />

                  <Box>
                    <Typography variant="subtitle1">模型与 API</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
                      这里控制后端 planner 的 provider、模型和 API 连接信息。
                    </Typography>
                    <Stack spacing={2}>
                      <TextField
                        fullWidth
                        label="Provider"
                        value={plannerSettings.provider}
                        onChange={(event) =>
                          setPlannerSettings((current) => ({
                            ...current,
                            provider: event.target.value,
                          }))
                        }
                      />
                      <TextField
                        fullWidth
                        label="Model"
                        value={plannerSettings.model}
                        onChange={(event) =>
                          setPlannerSettings((current) => ({
                            ...current,
                            model: event.target.value,
                          }))
                        }
                      />
                      <TextField
                        fullWidth
                        label="API Base"
                        value={plannerSettings.apiBase}
                        onChange={(event) =>
                          setPlannerSettings((current) => ({
                            ...current,
                            apiBase: event.target.value,
                          }))
                        }
                      />
                      <TextField
                        fullWidth
                        label="API Key"
                        type="password"
                        value={plannerSettings.apiKey}
                        onChange={(event) =>
                          setPlannerSettings((current) => ({
                            ...current,
                            apiKey: event.target.value,
                          }))
                        }
                      />
                    </Stack>
                  </Box>

                  <Divider />

                  <Box>
                    <Typography variant="subtitle1">LangSmith</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
                      配置 LangSmith tracing（用于 RAG/Memory/Workflow 调试追踪）。
                    </Typography>
                    <Stack spacing={2}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={langsmithSettings.enabled}
                            onChange={(event) =>
                              setLangsmithSettings((current) => ({
                                ...current,
                                enabled: event.target.checked,
                              }))
                            }
                          />
                        }
                        label="启用 LangSmith Tracing"
                      />
                      <TextField
                        fullWidth
                        label="LangSmith Project"
                        value={langsmithSettings.project}
                        onChange={(event) =>
                          setLangsmithSettings((current) => ({
                            ...current,
                            project: event.target.value,
                          }))
                        }
                      />
                      <TextField
                        fullWidth
                        label="LangSmith API Key"
                        type="password"
                        value={langsmithSettings.apiKey}
                        onChange={(event) =>
                          setLangsmithSettings((current) => ({
                            ...current,
                            apiKey: event.target.value,
                          }))
                        }
                      />
                      <TextField
                        fullWidth
                        label="LangSmith API URL (optional)"
                        value={langsmithSettings.apiUrl}
                        onChange={(event) =>
                          setLangsmithSettings((current) => ({
                            ...current,
                            apiUrl: event.target.value,
                          }))
                        }
                      />
                    </Stack>
                  </Box>

                  <Divider />

                  <Box>
                    <Typography variant="subtitle1">记忆</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
                      控制是否读取历史记忆、何时自动整理，以及召回范围与强度。
                    </Typography>
                    <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        手动执行一次记忆清理，用于去重和移除空文档。
                      </Typography>
                      <Button
                        variant="outlined"
                        onClick={runMemoryCleanup}
                        disabled={isMemoryCleanupRunning}
                      >
                        立即整理记忆
                      </Button>
                    </Stack>
                    <Stack spacing={2}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={memorySettings.enabled}
                            onChange={(event) =>
                              setMemorySettings((current) => ({
                                ...current,
                                enabled: event.target.checked,
                              }))
                            }
                          />
                        }
                        label="启用记忆召回"
                      />
                      <FormControlLabel
                        control={
                          <Switch
                            checked={memorySettings.autoCompact}
                            onChange={(event) =>
                              setMemorySettings((current) => ({
                                ...current,
                                autoCompact: event.target.checked,
                              }))
                            }
                          />
                        }
                        label="启用自动记忆整理"
                      />
                      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                        <FormControlLabel
                          control={
                            <Switch
                              checked={memorySettings.compactOnComplete}
                              onChange={(event) =>
                                setMemorySettings((current) => ({
                                  ...current,
                                  compactOnComplete: event.target.checked,
                                }))
                              }
                            />
                          }
                          label="会话完成后整理"
                        />
                        <FormControlLabel
                          control={
                            <Switch
                              checked={memorySettings.compactOnFailure}
                              onChange={(event) =>
                                setMemorySettings((current) => ({
                                  ...current,
                                  compactOnFailure: event.target.checked,
                                }))
                              }
                            />
                          }
                          label="会话失败后整理"
                        />
                      </Stack>
                      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                        <FormControl fullWidth>
                          <InputLabel id="memory-scope-label">记忆召回范围</InputLabel>
                          <Select
                            labelId="memory-scope-label"
                            label="记忆召回范围"
                            value={memorySettings.retrievalScope}
                            onChange={(event) =>
                              setMemorySettings((current) => ({
                                ...current,
                                retrievalScope: String(event.target.value),
                              }))
                            }
                          >
                            <MenuItem value="session">当前会话</MenuItem>
                            <MenuItem value="global">全局记忆</MenuItem>
                          </Select>
                        </FormControl>
                        <FormControl fullWidth>
                          <InputLabel id="memory-strength-label">记忆召回强度</InputLabel>
                          <Select
                            labelId="memory-strength-label"
                            label="记忆召回强度"
                            value={memorySettings.retrievalStrength}
                            onChange={(event) =>
                              setMemorySettings((current) => ({
                                ...current,
                                retrievalStrength: String(event.target.value),
                              }))
                            }
                          >
                            <MenuItem value="conservative">保守</MenuItem>
                            <MenuItem value="standard">标准</MenuItem>
                            <MenuItem value="aggressive">激进</MenuItem>
                          </Select>
                        </FormControl>
                      </Stack>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={memorySettings.cleanupEnabled}
                            onChange={(event) =>
                              setMemorySettings((current) => ({
                                ...current,
                                cleanupEnabled: event.target.checked,
                              }))
                            }
                          />
                        }
                        label="启用周期性记忆整理"
                      />
                      <TextField
                        fullWidth
                        type="number"
                        label="记忆整理周期（小时）"
                        value={memorySettings.cleanupIntervalHours}
                        onChange={(event) =>
                          setMemorySettings((current) => ({
                            ...current,
                            cleanupIntervalHours: Math.max(1, Number(event.target.value) || 24),
                          }))
                        }
                        helperText="当前用于后端记忆整理策略，后续可扩展为后台定时任务。"
                      />
                    </Stack>
                  </Box>
                </Box>
                <Divider />
                <Box sx={{ p: 2, display: "flex", justifyContent: "flex-end" }}>
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
                    <Button
                      variant="outlined"
                      onClick={runMemoryCleanup}
                      disabled={isMemoryCleanupRunning || isConfigSaving || isConfigLoading}
                    >
                      {isMemoryCleanupRunning ? "整理中..." : "整理记忆"}
                    </Button>
                    <Button
                      variant="outlined"
                      onClick={applyMemoryReindex}
                      disabled={isMemoryReindexing || isConfigSaving || isConfigLoading}
                    >
                      {isMemoryReindexing ? "重建中..." : "重建记忆索引"}
                    </Button>
                    <Button
                      variant="contained"
                      color="primary"
                      onClick={applyPlannerSettings}
                      disabled={isConfigSaving || isMemoryCleanupRunning || isMemoryReindexing}
                    >
                      保存运行时设置
                    </Button>
                  </Stack>
                </Box>
              </Paper>
            </Stack>
          </Box>
        )}
      </Box>
    </ThemeProvider>
  );
}

function requestSessionList(client: ClientHandle) {
  client.send({
    type: "req",
    id: crypto.randomUUID(),
    method: "orchestrator.session.list",
    params: { limit: 50 },
  });
}

function requestConfig(client: ClientHandle) {
  client.send({
    type: "req",
    id: crypto.randomUUID(),
    method: "orchestrator.config.get",
    params: {},
  });
}

function requestSessionHistory(client: ClientHandle, sessionId: string) {
  client.send({
    type: "req",
    id: crypto.randomUUID(),
    method: "orchestrator.session.history",
    sessionId,
    params: { limit: 200 },
  });
}

function requestSessionSnapshot(client: ClientHandle, sessionId: string) {
  client.send({
    type: "req",
    id: crypto.randomUUID(),
    method: "orchestrator.session.snapshot",
    sessionId,
    params: {},
  });
}

function requestSessionTrace(client: ClientHandle, sessionId: string) {
  client.send({
    type: "req",
    id: crypto.randomUUID(),
    method: "orchestrator.session.trace",
    sessionId,
    params: { limit: 100 },
  });
}

function requestSessionErrors(client: ClientHandle, sessionId: string) {
  client.send({
    type: "req",
    id: crypto.randomUUID(),
    method: "orchestrator.session.errors",
    sessionId,
    params: { limit: 50 },
  });
}

function requestSessionArtifacts(client: ClientHandle, sessionId: string) {
  client.send({
    type: "req",
    id: crypto.randomUUID(),
    method: "orchestrator.session.artifacts",
    sessionId,
    params: { limit: 50 },
  });
}

function requestKnowledgeCourseList(client: ClientHandle) {
  client.send({
    type: "req",
    id: crypto.randomUUID(),
    method: "orchestrator.knowledge.course.list",
    params: { limit: 200 },
  });
}

function requestKnowledgeFileList(client: ClientHandle, courseId: string) {
  client.send({
    type: "req",
    id: crypto.randomUUID(),
    method: "orchestrator.knowledge.file.list",
    params: {
      courseId,
      limit: 200,
    },
  });
}

function requestKnowledgeChunkList(client: ClientHandle, courseId: string) {
  client.send({
    type: "req",
    id: crypto.randomUUID(),
    method: "orchestrator.knowledge.chunk.list",
    params: {
      courseId,
      limit: 200,
    },
  });
}

function requestKnowledgeJobList(client: ClientHandle, courseId: string) {
  client.send({
    type: "req",
    id: crypto.randomUUID(),
    method: "orchestrator.knowledge.job.list",
    params: {
      courseId,
      limit: 200,
    },
  });
}

function requestKnowledgeCourseData(client: ClientHandle, courseId: string) {
  requestKnowledgeFileList(client, courseId);
  requestKnowledgeChunkList(client, courseId);
  requestKnowledgeJobList(client, courseId);
}

function mapMemorySearchResult(payload: Record<string, unknown>): MemorySearchResult | null {
  const query = getString(payload.query);
  if (!query) {
    return null;
  }
  const itemsRaw = Array.isArray(payload.items) ? payload.items : [];
  const items = itemsRaw
    .map((item) => mapMemorySearchItem(item as Record<string, unknown>))
    .filter((item): item is NonNullable<MemorySearchResult["items"][number]> => item !== null);
  return {
    query,
    items,
  };
}

function mapMemorySearchItem(item: Record<string, unknown>): MemorySearchResult["items"][number] | null {
  const documentId = getString(item.documentId);
  const updatedAt = getString(item.updatedAt);
  if (!documentId || !updatedAt) {
    return null;
  }
  return {
    documentId,
    sessionId: getString(item.sessionId) ?? "",
    documentType: getString(item.documentType) ?? "",
    title: getString(item.title) ?? "",
    content: getString(item.content) ?? "",
    metadata: isRecord(item.metadata) ? item.metadata : {},
    score: Number(item.score ?? 0) || 0,
    updatedAt,
  };
}

function mergeSessionLists(current: UiSession[], incoming: UiSession[]) {
  const byId = new Map<string, UiSession>(current.map((item) => [item.sessionId, item]));
  for (const item of incoming) {
    byId.set(item.sessionId, {
      ...(byId.get(item.sessionId) ?? {}),
      ...item,
    });
  }
  return [...byId.values()].sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
}

function touchSessionToTop(current: UiSession[], sessionId: string) {
  const next = [...current];
  const index = next.findIndex((item) => item.sessionId === sessionId);
  if (index < 0) {
    return current;
  }
  const updated = {
    ...next[index],
    updatedAt: new Date().toISOString(),
  };
  next.splice(index, 1);
  next.unshift(updated);
  return next;
}

function upsertSession(
  current: UiSession[],
  sessionId: string,
  payload: Record<string, unknown>,
  snapshot: SessionSnapshot | null,
  promote: boolean,
) {
  const next = [...current];
  const existingIndex = next.findIndex((item) => item.sessionId === sessionId);
  const previous = existingIndex >= 0 ? next[existingIndex] : null;
  const updated: UiSession = {
    sessionId,
    task:
      getString(payload.task) ??
      snapshot?.task ??
      previous?.task ??
      sessionId,
    runner:
      getString(payload.runner) ??
      snapshot?.runner ??
      previous?.runner ??
      "",
    status:
      snapshot?.status ??
      previous?.status ??
      "UNKNOWN",
    phase:
      snapshot?.phase ??
      previous?.phase ??
      "",
    latestSummary:
      snapshot?.latestSummary ??
      getString(payload.message) ??
      previous?.latestSummary ??
      "",
    activeWorker:
      snapshot?.activeWorker ??
      previous?.activeWorker ??
      "",
    updatedAt:
      snapshot?.updatedAt ??
      new Date().toISOString(),
    displayTitle: previous?.displayTitle,
    snapshot: {
      ...(previous?.snapshot ?? {}),
      ...(snapshot ?? {}),
    },
  };
  if (existingIndex >= 0) {
    next[existingIndex] = updated;
    if (promote) {
      const [item] = next.splice(existingIndex, 1);
      next.unshift(item);
    }
  } else {
    next.unshift(updated);
  }
  return next;
}

function mapHistoryItem(item: Record<string, unknown>, index: number): TimelineEvent | null {
  const createdAt = getString(item.createdAt);
  const detail = getString(item.detail);
  const title = getString(item.title);
  if (!createdAt || !detail || !title) {
    return null;
  }
  return {
    id: `history-${String(item.seq ?? index + 1)}-${createdAt}`,
    seq: typeof item.seq === "number" ? item.seq : undefined,
    kind: normalizeEventKind(getString(item.kind) ?? "event"),
    title,
    event: getString(item.event) ?? undefined,
    status: getString(item.status) ?? "completed",
    detail,
    createdAt,
  };
}

function mapTraceItem(item: Record<string, unknown>): TraceEntry | null {
  const seq = Number(item.seq ?? 0);
  const timestamp = getString(item.timestamp);
  const event = getString(item.event);
  if (!timestamp || !event || !seq) {
    return null;
  }
  return {
    seq,
    timestamp,
    event,
    runner: getString(item.runner),
    payload: isRecord(item.payload) ? item.payload : {},
  };
}

function mapErrorItem(item: Record<string, unknown>): SessionErrorItem | null {
  const message = getString(item.message);
  const createdAt = getString(item.createdAt);
  if (!message || !createdAt) {
    return null;
  }
  return {
    seq: Number(item.seq ?? 0),
    errorLayer: getString(item.errorLayer) ?? "",
    errorCode: getString(item.errorCode) ?? "",
    message,
    details: isRecord(item.details) ? item.details : {},
    retryable: Boolean(item.retryable),
    phase: getString(item.phase) ?? "",
    worker: getString(item.worker) ?? "",
    createdAt,
  };
}

function mapArtifactItem(item: Record<string, unknown>): SessionArtifactItem | null {
  const path = getString(item.path);
  const createdAt = getString(item.createdAt);
  if (!path || !createdAt) {
    return null;
  }
  return {
    path,
    changeType: getString(item.changeType) ?? "unknown",
    size: typeof item.size === "number" ? item.size : null,
    summary: getString(item.summary) ?? "",
    createdAt,
  };
}

function mapArtifactTile(item: Record<string, unknown>): ArtifactTile | null {
  const path = getString(item.path);
  if (!path) {
    return null;
  }
  return {
    path,
    changeType: getString(item.changeType) ?? "unknown",
    summary: getString(item.summary) ?? "",
    size: typeof item.size === "number" ? item.size : null,
  };
}

function mapKnowledgeCourse(item: Record<string, unknown>): KnowledgeCourse | null {
  const courseId = getString(item.courseId);
  const name = getString(item.name);
  const createdAt = getString(item.createdAt);
  const updatedAt = getString(item.updatedAt);
  if (!courseId || !name || !createdAt || !updatedAt) {
    return null;
  }
  return {
    courseId,
    name,
    description: getString(item.description) ?? "",
    createdAt,
    updatedAt,
  };
}

function mapKnowledgeFile(item: Record<string, unknown>): KnowledgeFile | null {
  const fileId = getString(item.fileId);
  const courseId = getString(item.courseId);
  const originalName = getString(item.originalName);
  const storedPath = getString(item.storedPath);
  const fileExt = getString(item.fileExt);
  const createdAt = getString(item.createdAt);
  const updatedAt = getString(item.updatedAt);
  if (!fileId || !courseId || !originalName || !storedPath || !fileExt || !createdAt || !updatedAt) {
    return null;
  }
  return {
    fileId,
    courseId,
    originalName,
    storedPath,
    fileExt,
    parseStatus: getString(item.parseStatus) ?? "",
    parseError: getString(item.parseError) ?? "",
    sourceType: getString(item.sourceType) ?? "",
    createdAt,
    updatedAt,
  };
}

function mapKnowledgeChunk(item: Record<string, unknown>): KnowledgeChunk | null {
  const chunkId = getString(item.chunkId);
  const courseId = getString(item.courseId);
  const fileId = getString(item.fileId);
  const content = getString(item.content);
  const createdAt = getString(item.createdAt);
  const updatedAt = getString(item.updatedAt);
  if (!chunkId || !courseId || !fileId || !content || !createdAt || !updatedAt) {
    return null;
  }
  return {
    chunkId,
    courseId,
    fileId,
    chunkIndex: Number(item.chunkIndex ?? 0) || 0,
    sourcePage: Number(item.sourcePage ?? 0) || 0,
    sourceSection: getString(item.sourceSection) ?? "",
    content,
    tokenEstimate: Number(item.tokenEstimate ?? 0) || 0,
    metadata: isRecord(item.metadata) ? item.metadata : {},
    createdAt,
    updatedAt,
  };
}

function mapKnowledgeJob(item: Record<string, unknown>): KnowledgeJob | null {
  const jobId = getString(item.jobId);
  const courseId = getString(item.courseId);
  const fileId = getString(item.fileId);
  const status = getString(item.status);
  const createdAt = getString(item.createdAt);
  const updatedAt = getString(item.updatedAt);
  if (!jobId || !courseId || !fileId || !status || !createdAt || !updatedAt) {
    return null;
  }
  return {
    jobId,
    courseId,
    fileId,
    status,
    progress: Number(item.progress ?? 0) || 0,
    message: getString(item.message) ?? "",
    createdAt,
    updatedAt,
  };
}

function mapRagQueryResult(payload: Record<string, unknown>): RagQueryResult | null {
  const courseId = getString(payload.courseId);
  const query = getString(payload.query);
  if (!courseId || !query) {
    return null;
  }
  const itemsRaw = Array.isArray(payload.items) ? payload.items : [];
  const items = itemsRaw
    .map((item) => mapRagQueryItem(item as Record<string, unknown>))
    .filter((item): item is NonNullable<RagQueryResult["items"][number]> => item !== null);
  return {
    courseId,
    query,
    answer: getString(payload.answer) ?? "",
    items,
    debug: isRecord(payload.debug) ? payload.debug : {},
  };
}

function mapRagQueryItem(item: Record<string, unknown>): RagQueryResult["items"][number] | null {
  const chunkId = getString(item.chunkId);
  const fileId = getString(item.fileId);
  const content = getString(item.content);
  if (!chunkId || !fileId || !content) {
    return null;
  }
  return {
    chunkId,
    fileId,
    content,
    sourcePage: Number(item.sourcePage ?? 0) || 0,
    sourceSection: getString(item.sourceSection) ?? "",
    score: Number(item.score ?? 0) || 0,
    denseScore: Number(item.denseScore ?? 0) || 0,
    lexicalScore: Number(item.lexicalScore ?? 0) || 0,
    rerankScore: Number(item.rerankScore ?? 0) || 0,
    metadata: isRecord(item.metadata) ? item.metadata : {},
  };
}

function mapRealtimeEvent(eventName: string, payload: Record<string, unknown>): TimelineEvent | null {
  if (eventName === "orchestrator.session.followup.accepted" && !getString(payload.text)) {
    return null;
  }
  if (eventName.includes(".subnode.")) {
    const kind = getString(payload.kind) ?? "";
    const status = getString(payload.status) ?? "";
    const summary = summarizeSubstep(kind, status);
    return {
      id: `${eventName}-${crypto.randomUUID()}`,
      kind: "event",
      title: summary.title,
      event: eventName,
      status: summary.status,
      detail: summary.detail,
      createdAt: new Date().toISOString(),
    };
  }
  return {
    id: `${eventName}-${crypto.randomUUID()}`,
    kind: normalizeEventKind(eventName),
    title: buildTimelineTitle(eventName, payload),
    event: eventName,
    status: buildTimelineStatus(eventName, payload),
    detail: formatPayloadDetail(payload),
    createdAt: new Date().toISOString(),
  };
}

function isPersistentTimelineEvent(eventName: string, kind: TimelineEvent["kind"]) {
  if (kind === "summary" || kind === "error") {
    return true;
  }
  return (
    eventName.endsWith(".completed") ||
    eventName.endsWith(".failed") ||
    eventName.endsWith(".followup.accepted") ||
    eventName.endsWith(".await_user")
  );
}

function buildTimelineTitle(eventName: string, payload: Record<string, unknown>) {
  if (eventName.includes(".subnode.")) {
    return getString(payload.title) ?? getString(payload.kind) ?? "substep";
  }
  if (eventName.includes(".phase")) {
    return getString((payload.snapshot as Record<string, unknown> | undefined)?.phase) ?? "phase";
  }
  if (eventName.includes(".worker")) {
    return getString(payload.worker) ?? "worker";
  }
  return eventName;
}

function buildTimelineStatus(eventName: string, payload: Record<string, unknown>) {
  if (typeof payload.status === "string" && payload.status) {
    return payload.status;
  }
  if (eventName.endsWith(".failed")) {
    return "failed";
  }
  if (eventName.includes(".subnode.")) {
    return getString(payload.status) ?? "completed";
  }
  return "completed";
}

function formatPayloadDetail(payload: Record<string, unknown>): string {
  if (typeof payload.detail === "string" && payload.detail.trim()) {
    return payload.detail;
  }
  if (typeof payload.message === "string" && payload.message.trim()) {
    return payload.message;
  }
  if (typeof payload.error === "string" && payload.error.trim()) {
    return payload.error;
  }
  return JSON.stringify(payload, null, 2);
}

function summarizeSubstep(kind: string, status: string) {
  const normalizedKind = kind.trim().toLowerCase();
  const normalizedStatus = status.trim().toLowerCase();
  if (normalizedKind === "tool") {
    return {
      title: normalizedStatus === "completed" ? "当前步骤已完成" : "正在处理当前步骤",
      status: normalizedStatus || "running",
      detail: normalizedStatus === "completed" ? "已完成一次中间处理。" : "正在执行必要的中间处理。",
    };
  }
  if (normalizedKind === "worker") {
    return {
      title: "正在调用执行端",
      status: normalizedStatus || "running",
      detail: "正在协调执行端完成当前任务。",
    };
  }
  return {
    title: "正在处理中",
    status: normalizedStatus || "running",
    detail: "系统正在推进当前会话。",
  };
}

function normalizeEventKind(kind: string): TimelineEvent["kind"] {
  if (kind === "phase" || kind === "substep" || kind === "summary" || kind === "worker" || kind === "snapshot" || kind === "error" || kind === "event") {
    return kind;
  }
  if (kind.includes(".phase")) {
    return "phase";
  }
  if (kind.includes(".summary")) {
    return "summary";
  }
  if (kind.includes(".worker")) {
    return "worker";
  }
  if (kind.includes(".snapshot")) {
    return "snapshot";
  }
  if (kind.includes(".failed")) {
    return "error";
  }
  if (kind.includes(".subnode.")) {
    return "substep";
  }
  return "event";
}

function getString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
