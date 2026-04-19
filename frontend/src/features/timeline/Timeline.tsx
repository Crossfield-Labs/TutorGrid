import type { TimelineEvent, UiSession } from "../../lib/ws-client";

interface TimelineProps {
  session: UiSession | null;
  events: TimelineEvent[];
  inputValue: string;
  onInputChange: (value: string) => void;
  onSendReply: () => void;
  onExplain: () => void;
  onSnapshot: () => void;
}

export function Timeline({
  session,
  events,
  inputValue,
  onInputChange,
  onSendReply,
  onExplain,
  onSnapshot,
}: TimelineProps) {
  return (
    <section className="chat-shell">
      <div className="chat-header">
        <div>
          <div className="chat-title">{session ? session.task : "会话时间线"}</div>
          <div className="chat-subtitle">
            {session
              ? `${session.runner} · ${session.status} · ${session.activeWorker || "no worker"}`
              : "等待选择会话"}
          </div>
        </div>
        <div className="chat-actions">
          <button type="button" className="ghost-button" onClick={onSnapshot}>
            Snapshot
          </button>
          <button type="button" className="ghost-button" onClick={onExplain}>
            Explain
          </button>
        </div>
      </div>

      <div className="chat-stage">
        <div className="chat-stage-pill">实时编排流</div>
        <div className="chat-stage-copy">
          这里展示 LangGraph 驱动的阶段变化、工具执行、worker 运行和摘要收口过程。
        </div>
      </div>

      <div className="timeline">
        {events.map((event) => (
          <article key={event.id} className="timeline-item">
            <div className="timeline-item-header">
              <div>
                <div className="timeline-kind">{event.kind}</div>
                <strong>{event.title}</strong>
              </div>
              <span>{new Date(event.createdAt).toLocaleTimeString()}</span>
            </div>
            <p className="timeline-detail">{event.detail}</p>
          </article>
        ))}
      </div>

      <div className="composer-shell">
        <textarea
          className="composer-input"
          placeholder="输入回复、redirect 或 explain 请求。下一步会接到真实 session.input 协议。"
          rows={3}
          value={inputValue}
          onChange={(event) => onInputChange(event.target.value)}
        />
        <div className="composer-actions">
          <span className="composer-hint">Enter 发送 · Shift+Enter 换行</span>
          <button type="button" className="composer-send" onClick={onSendReply}>
            发送
          </button>
        </div>
      </div>
    </section>
  );
}
