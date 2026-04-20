import { useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Button,
  Chip,
  CssBaseline,
  Stack,
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

  const clientRef = useRef<ClientHandle | null>(null);
  const selectedSessionIdRef = useRef(selectedSessionId);

  useEffect(() => {
    selectedSessionIdRef.current = selectedSessionId;
  }, [selectedSessionId]);

  const selectedSession = useMemo(
    () => sessions.find((session) => session.sessionId === selectedSessionId) ?? null,
    [selectedSessionId, sessions],
  );
  const selectedSnapshot = selectedSessionId ? snapshotsBySession[selectedSessionId] ?? selectedSession?.snapshot ?? null : null;
  const selectedTimeline = selectedSessionId ? timelinesBySession[selectedSessionId] ?? [] : [];
  const selectedLiveEvent = selectedSessionId ? liveEventsBySession[selectedSessionId] ?? null : null;

  useEffect(() => {
    setSettingsUrl(serverUrl);
  }, [serverUrl]);

  useEffect(() => {
    const client = createClient({
      url: serverUrl,
      onOpen: () => {
        setConnectionState("已连接");
        requestSessionList(client);
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
    const hasActiveSession = Boolean(selectedSessionId);
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
    setServerUrl(nextUrl);
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
            />
            <StatePanel session={selectedSession} snapshot={selectedSnapshot} />
          </Box>
        ) : (
          <Box sx={{ p: 2.5, overflow: "auto" }}>
            <Box sx={{ maxWidth: 760, p: 2.5, border: "1px solid", borderColor: "divider", bgcolor: "background.paper", borderRadius: 2 }}>
              <Typography variant="h6">连接设置</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                在这里配置桌面端连接的 WebSocket 地址。
              </Typography>
              <TextField
                fullWidth
                label="WebSocket"
                value={settingsUrl}
                onChange={(event) => setSettingsUrl(event.target.value)}
                sx={{ mt: 2 }}
              />
              <Stack direction="row" justifyContent="flex-end" spacing={1} sx={{ mt: 2 }}>
                <Button variant="outlined" onClick={() => setSettingsUrl(serverUrl)}>
                  还原
                </Button>
                <Button variant="contained" onClick={applySettings}>
                  应用
                </Button>
              </Stack>
            </Box>
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
