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
import { buildWsUrl, createClient, type SessionSnapshot, type TimelineEvent, type UiSession } from "../lib/ws-client";

type ClientHandle = ReturnType<typeof createClient>;
type PlannerSettings = {
  provider: string;
  model: string;
  apiBase: string;
  apiKey: string;
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
  const [connectionState, setConnectionState] = useState("未连接");
  const [serverUrl, setServerUrl] = useState(defaultWsUrl);
  const [settingsUrl, setSettingsUrl] = useState(defaultWsUrl);
  const [view, setView] = useState<"workspace" | "settings">("workspace");
  const [composerValue, setComposerValue] = useState("");
  const [pendingTaskId, setPendingTaskId] = useState<string>("");
  const [plannerSettings, setPlannerSettings] = useState<PlannerSettings>({
    provider: "openai_compat",
    model: "",
    apiBase: "",
    apiKey: "",
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
  const [settingsFeedback, setSettingsFeedback] = useState<string>("");

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
        const currentSessionId = selectedSessionIdRef.current;
        if (currentSessionId) {
          requestSessionHistory(client, currentSessionId);
          requestSessionSnapshot(client, currentSessionId);
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
          if (planner && typeof planner === "object") {
            setPlannerSettings({
              provider: getString((planner as Record<string, unknown>).provider) ?? "openai_compat",
              model: getString((planner as Record<string, unknown>).model) ?? "",
              apiBase: getString((planner as Record<string, unknown>).apiBase) ?? "",
              apiKey: getString((planner as Record<string, unknown>).apiKey) ?? "",
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
            setSettingsFeedback("设置已保存。");
          }
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
  }, [selectedSessionId]);

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
    setSettingsFeedback("");
    setServerUrl(nextUrl);
  };

  const applyPlannerSettings = () => {
    if (!clientRef.current) {
      return;
    }
    setIsConfigSaving(true);
    setSettingsFeedback("");
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
              onChange={(_, value: "workspace" | "settings") => setView(value)}
              sx={{ minHeight: 32, "& .MuiTab-root": { minHeight: 32 } }}
            >
              <Tab value="workspace" label="工作台" />
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
            <StatePanel session={selectedSession} snapshot={selectedSnapshot} />
          </Box>
        ) : (
          <Box sx={{ p: 2.5, overflow: "auto" }}>
            <Stack spacing={2} sx={{ maxWidth: 860 }}>
              <Paper variant="outlined" sx={{ overflow: "hidden" }}>
                {isConfigLoading || isConfigSaving ? <LinearProgress /> : null}
                <Box sx={{ p: 2.5 }}>
                  <Typography variant="h6">设置</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    连接、模型和记忆策略统一在这里配置。
                  </Typography>
                  {settingsFeedback ? <Alert severity="success" sx={{ mt: 2 }}>{settingsFeedback}</Alert> : null}
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
                    <Typography variant="subtitle1">记忆</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
                      控制是否读取历史记忆、何时自动整理，以及召回范围与强度。
                    </Typography>
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
                  <Button variant="contained" color="primary" onClick={applyPlannerSettings} disabled={isConfigSaving}>
                    保存运行时设置
                  </Button>
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
