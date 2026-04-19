import type { UiSession } from "../../lib/ws-client";

interface StatePanelProps {
  session: UiSession | null;
}

export function StatePanel({ session }: StatePanelProps) {
  return (
    <aside className="inspector-shell">
      <div className="inspector-header">
        <h3>Inspector</h3>
        <div className="inspector-header-copy">对齐 snapshot 与 worker runtime</div>
      </div>

      <div className="state-grid">
        <StateRow label="Session ID" value={session?.sessionId ?? "-"} />
        <StateRow label="Runner" value={session?.runner ?? "-"} />
        <StateRow label="Status" value={session?.status ?? "-"} />
        <StateRow label="Phase" value={session?.phase ?? "-"} />
        <StateRow label="Active Worker" value={session?.activeWorker ?? "-"} />
        <StateRow label="Latest Summary" value={session?.latestSummary ?? "-"} />
        <StateRow label="Updated At" value={session?.updatedAt ?? "-"} />
      </div>

      <div className="inspector-section">
        <div className="inspector-section-title">后续接入</div>
        <ul className="inspector-list">
          <li>错误详情</li>
          <li>artifact 预览</li>
          <li>trace 调试视图</li>
          <li>历史 snapshot 浏览</li>
        </ul>
      </div>
    </aside>
  );
}

function StateRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="state-row">
      <div className="state-row-label">{label}</div>
      <div className="state-row-value">{value}</div>
    </div>
  );
}
