import { useEffect, useMemo, useState } from "react";

import { SessionList } from "../features/sessions/SessionList";
import { StatePanel } from "../features/state-panel/StatePanel";
import { Timeline } from "../features/timeline/Timeline";
import { buildWsUrl, createClient, type TimelineEvent, type UiSession } from "../lib/ws-client";
import "./app.css";

const demoSessions: UiSession[] = [];

const demoTimeline: TimelineEvent[] = [
  {
    id: "evt-1",
    kind: "phase",
    title: "进入 planning",
    status: "completed",
    detail: "Planning iteration 1 scheduled 1 tool call(s).",
    createdAt: new Date().toISOString(),
  },
  {
    id: "evt-2",
    kind: "substep",
    title: "list_files",
    status: "completed",
    detail: "列出了当前工作区结构。",
    createdAt: new Date().toISOString(),
  },
  {
    id: "evt-3",
    kind: "summary",
    title: "项目摘要",
    status: "completed",
    detail: "这是一个基于 LangGraph + LangChain 的 PC 端编排器。",
    createdAt: new Date().toISOString(),
  },
];

export function App() {
  const [sessions, setSessions] = useState<UiSession[]>(demoSessions);
  const [selectedSessionId, setSelectedSessionId] = useState<string>("");
  const [timeline, setTimeline] = useState<TimelineEvent[]>(demoTimeline);
  const [connectionState, setConnectionState] = useState("未连接");
  const [serverUrl, setServerUrl] = useState(buildWsUrl());
  const [composerValue, setComposerValue] = useState("");
  const selectedSession = useMemo(
    () => sessions.find((session) => session.sessionId === selectedSessionId) ?? sessions[0] ?? null,
    [selectedSessionId, sessions],
  );

  useEffect(() => {
    const client = createClient({
      url: serverUrl,
      onOpen: () => setConnectionState("已连接"),
      onClose: () => setConnectionState("已断开"),
      onError: () => setConnectionState("连接异常"),
      onEvent: (message) => {
        if (message.type === "event" && message.event === "orchestrator.session.list") {
          const items = Array.isArray(message.payload?.items) ? (message.payload.items as UiSession[]) : [];
          setSessions(items);
          setSelectedSessionId((current) => current || items[0]?.sessionId || "");
          return;
        }

        if (message.type !== "event" || !message.sessionId) {
          return;
        }

        const sessionId = message.sessionId;
        const payload = message.payload ?? {};
        const snapshot = ((payload.snapshot as Record<string, unknown> | undefined) ?? {});

        setSessions((current) => {
          const next = [...current];
          const existingIndex = next.findIndex((item) => item.sessionId === sessionId);
          const updated: UiSession = {
            sessionId,
            task:
              typeof payload.task === "string"
                ? payload.task
                : existingIndex >= 0
                  ? next[existingIndex].task
                  : sessionId,
            runner:
              typeof payload.runner === "string"
                ? payload.runner
                : existingIndex >= 0
                  ? next[existingIndex].runner
                  : "",
            status:
              typeof snapshot.status === "string"
                ? snapshot.status
                : existingIndex >= 0
                  ? next[existingIndex].status
                  : "UNKNOWN",
            phase:
              typeof snapshot.phase === "string"
                ? snapshot.phase
                : existingIndex >= 0
                  ? next[existingIndex].phase
                  : "",
            latestSummary:
              typeof snapshot.latestSummary === "string"
                ? snapshot.latestSummary
                : typeof payload.message === "string"
                  ? payload.message
                  : existingIndex >= 0
                    ? next[existingIndex].latestSummary
                    : "",
            activeWorker:
              typeof snapshot.activeWorker === "string"
                ? snapshot.activeWorker
                : existingIndex >= 0
                  ? next[existingIndex].activeWorker
                  : "",
            updatedAt: new Date().toISOString(),
          };
          if (existingIndex >= 0) {
            next[existingIndex] = updated;
          } else {
            next.unshift(updated);
          }
          return next;
        });
        setSelectedSessionId((current) => current || sessionId);

        if (sessionId !== selectedSessionId) {
          return;
        }

        setTimeline((current) => [
          ...current,
          {
            id: `${message.event}-${current.length + 1}`,
            kind: normalizeEventKind(message.event),
            title: message.event,
            status: "completed",
            detail: formatPayloadDetail(payload),
            createdAt: new Date().toISOString(),
          },
        ]);
      },
    });

    client.connect();
    const requestSessionList = () => {
      client.send({
        type: "req",
        id: crypto.randomUUID(),
        method: "orchestrator.session.list",
        params: {},
      });
    };
    setTimeout(requestSessionList, 150);

    const startSession = () => {
      const task = window.prompt("输入新会话任务", "先了解一下这个项目");
      if (!task) {
        return;
      }
      const requestId = crypto.randomUUID();
      client.send({
        type: "req",
        id: requestId,
        method: "orchestrator.session.start",
        taskId: requestId,
        nodeId: "gui-node",
        params: {
          runner: "pc_subagent",
          workspace: ".",
          task,
          goal: task,
        },
      });
    };

    const sendReply = () => {
      if (!selectedSessionId || !composerValue.trim()) {
        return;
      }
      client.send({
        type: "req",
        id: crypto.randomUUID(),
        method: "orchestrator.session.input",
        sessionId: selectedSessionId,
        params: {
          text: composerValue.trim(),
          inputIntent: "reply",
        },
      });
      setComposerValue("");
    };

    const sendExplain = () => {
      if (!selectedSessionId) {
        return;
      }
      client.send({
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
      if (!selectedSessionId) {
        return;
      }
      client.send({
        type: "req",
        id: crypto.randomUUID(),
        method: "orchestrator.session.snapshot",
        sessionId: selectedSessionId,
        params: {},
      });
    };

    (window as Window & typeof globalThis & {
      __orchestratorGui?: {
        startSession: () => void;
        sendReply: () => void;
        sendExplain: () => void;
        requestSnapshot: () => void;
      };
    }).__orchestratorGui = {
      startSession,
      sendReply,
      sendExplain,
      requestSnapshot,
    };

    return () => client.close();
  }, [composerValue, selectedSessionId, serverUrl]);

  const guiActions = (window as Window & typeof globalThis & {
    __orchestratorGui?: {
      startSession: () => void;
      sendReply: () => void;
      sendExplain: () => void;
      requestSnapshot: () => void;
    };
  }).__orchestratorGui;

  return (
    <div className="app-shell">
      <div className="app-backdrop" />
      <header className="floating-topbar">
        <div className="eyebrow">PC ORCHESTRATOR</div>
        <div className="floating-topbar-right">
          <div className={`status-dot ${connectionState === "已连接" ? "online" : ""}`} />
          <span>{connectionState}</span>
          <code>{serverUrl}</code>
        </div>
      </header>

      <main className="workspace-layout">
        <SessionList
          sessions={sessions}
          selectedSessionId={selectedSessionId}
          onSelect={setSelectedSessionId}
          onCreateSession={() => guiActions?.startSession()}
        />
        <Timeline
          session={selectedSession}
          events={timeline}
          inputValue={composerValue}
          onInputChange={setComposerValue}
          onSendReply={() => guiActions?.sendReply()}
          onExplain={() => guiActions?.sendExplain()}
          onSnapshot={() => guiActions?.requestSnapshot()}
        />
        <StatePanel session={selectedSession} />
      </main>

      <footer className="connection-strip">
        <label className="connection-field">
          <span>WebSocket</span>
          <input value={serverUrl} onChange={(event) => setServerUrl(event.target.value)} />
        </label>
      </footer>
    </div>
  );
}

function formatPayloadDetail(payload: Record<string, unknown>): string {
  if (typeof payload.message === "string" && payload.message.trim()) {
    return payload.message;
  }
  return JSON.stringify(payload, null, 2);
}

function normalizeEventKind(eventName: string): TimelineEvent["kind"] {
  if (eventName.includes(".phase")) {
    return "phase";
  }
  if (eventName.includes(".summary")) {
    return "summary";
  }
  if (eventName.includes(".worker")) {
    return "worker";
  }
  if (eventName.includes(".snapshot")) {
    return "snapshot";
  }
  if (eventName.includes(".failed")) {
    return "error";
  }
  if (eventName.includes(".subnode.")) {
    return "substep";
  }
  return "event";
}
