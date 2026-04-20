import type { ReactNode } from "react";
import { Box, List, ListItem, ListItemText, Typography } from "@mui/material";
import type { SessionSnapshot, UiSession } from "../../lib/ws-client";

interface StatePanelProps {
  session: UiSession | null;
  snapshot: SessionSnapshot | null;
}

export function StatePanel({ session, snapshot }: StatePanelProps) {
  return (
    <Box
      component="aside"
      sx={{
        borderLeft: "1px solid",
        borderColor: "divider",
        bgcolor: "grey.50",
        minHeight: 0,
        overflow: "auto",
      }}
    >
      <Box sx={{ p: 2, borderBottom: "1px solid", borderColor: "divider" }}>
        <Typography variant="subtitle1">Context</Typography>
        <Typography variant="caption" color="text.secondary">
          会话状态、worker 信息与等待输入信号
        </Typography>
      </Box>

      <Box sx={{ p: 2, display: "grid", gap: 2 }}>
        <StateGroup title="会话">
          <StateRow label="Session ID" value={session?.sessionId ?? snapshot?.sessionId ?? "-"} />
          <StateRow label="Task" value={snapshot?.task ?? session?.task ?? "-"} />
          <StateRow label="Runner" value={snapshot?.runner ?? session?.runner ?? "-"} />
          <StateRow label="Status" value={snapshot?.status ?? session?.status ?? "-"} />
          <StateRow label="Phase" value={snapshot?.phase ?? session?.phase ?? "-"} />
          <StateRow label="Stop Reason" value={snapshot?.stopReason ?? "-"} />
          <StateRow label="Updated At" value={snapshot?.updatedAt ?? session?.updatedAt ?? "-"} />
        </StateGroup>

        <StateGroup title="执行">
          <StateRow label="Active Worker" value={snapshot?.activeWorker ?? session?.activeWorker ?? "-"} />
          <StateRow label="Worker Profile" value={snapshot?.activeWorkerProfile ?? "-"} />
          <StateRow label="Session Mode" value={snapshot?.activeSessionMode ?? "-"} />
          <StateRow label="Progress" value={snapshot?.lastProgressMessage ?? "-"} />
          <StateRow label="Artifact Summary" value={snapshot?.latestArtifactSummary ?? "-"} />
        </StateGroup>

        <StateGroup title="交互">
          <StateRow label="Awaiting Input" value={snapshot?.awaitingInput ? "true" : "false"} />
          <StateRow label="Pending Prompt" value={snapshot?.pendingUserPrompt ?? "-"} />
          <StateRow label="Summary" value={snapshot?.latestSummary ?? session?.latestSummary ?? "-"} />
          <StateRow label="Error" value={snapshot?.error ?? "-"} />
        </StateGroup>

        <StateGroup title="运行时">
          <StateRow label="Permission" value={snapshot?.permissionSummary ?? "-"} />
          <StateRow label="Runtime Info" value={snapshot?.sessionInfoSummary ?? "-"} />
          <StateRow label="MCP" value={snapshot?.mcpStatusSummary ?? "-"} />
        </StateGroup>
      </Box>

      <Box sx={{ p: 2, borderTop: "1px solid", borderColor: "divider" }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          最近 hook
        </Typography>
        {snapshot?.recentHookEvents && snapshot.recentHookEvents.length > 0 ? (
          <List dense disablePadding>
            {snapshot.recentHookEvents.slice(-5).map((item, index) => (
              <ListItem key={`${index}-${String(item.name ?? item.message ?? "hook")}`} disableGutters>
                <ListItemText
                  primaryTypographyProps={{ variant: "body2" }}
                  primary={`${String(item.name ?? "hook")} · ${String(item.message ?? "")}`}
                />
              </ListItem>
            ))}
          </List>
        ) : (
          <Typography variant="body2" color="text.secondary">
            暂无 hook 事件。
          </Typography>
        )}
      </Box>
    </Box>
  );
}

function StateGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Box component="section">
      <Typography variant="overline" color="text.secondary">
        {title}
      </Typography>
      <Box>{children}</Box>
    </Box>
  );
}

function StateRow({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ py: 0.75, borderBottom: "1px solid", borderColor: "divider" }}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
        {value || "-"}
      </Typography>
    </Box>
  );
}
