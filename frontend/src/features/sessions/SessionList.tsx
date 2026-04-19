import type { UiSession } from "../../lib/ws-client";

interface SessionListProps {
  sessions: UiSession[];
  selectedSessionId: string;
  onSelect: (sessionId: string) => void;
  onCreateSession: () => void;
}

export function SessionList({ sessions, selectedSessionId, onSelect, onCreateSession }: SessionListProps) {
  return (
    <aside className="sidebar-shell">
      <div className="sidebar-brand">
        <div className="sidebar-brand-mark">O</div>
        <div>
          <div className="sidebar-brand-title">Orchestrator</div>
          <div className="sidebar-brand-subtitle">Session Console</div>
        </div>
      </div>

      <button type="button" className="new-session-button" onClick={onCreateSession}>
        新建会话
      </button>

      <div className="sidebar-section-title">最近会话</div>
      <div className="session-list">
        {sessions.map((session) => (
          <button
            type="button"
            key={session.sessionId}
            className={`session-card ${session.sessionId === selectedSessionId ? "selected" : ""}`}
            onClick={() => onSelect(session.sessionId)}
          >
            <div className="session-card-title-row">
              <div className="session-card-title">{session.task}</div>
              <span className="session-card-badge">{session.phase || "idle"}</span>
            </div>
            <div className="session-card-meta">
              <div>{session.runner || "unknown runner"}</div>
              <div>
                {session.status} / {session.phase}
              </div>
              <div>{session.latestSummary || "暂无摘要"}</div>
            </div>
          </button>
        ))}
      </div>

      <div className="sidebar-footer">
        <div className="sidebar-footer-title">当前模式</div>
        <div className="sidebar-footer-value">GUI first · Tauri shell ready</div>
      </div>
    </aside>
  );
}
