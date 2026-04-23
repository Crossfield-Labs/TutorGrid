import { type ReactNode, useState } from "react";
import {
  Box,
  Chip,
  Divider,
  List,
  ListItem,
  Stack,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";

import type {
  ArtifactTile,
  SessionArtifactItem,
  SessionErrorItem,
  SessionSnapshot,
  TraceEntry,
  UiSession,
} from "../../lib/ws-client";

interface ArtifactPanelData {
  items: SessionArtifactItem[];
  tiles: ArtifactTile[];
}

interface StatePanelProps {
  session: UiSession | null;
  snapshot: SessionSnapshot | null;
  traceEntries: TraceEntry[];
  errorItems: SessionErrorItem[];
  artifactData: ArtifactPanelData;
}

type InspectorTab = "overview" | "trace" | "errors" | "artifacts";

export function StatePanel({
  session,
  snapshot,
  traceEntries,
  errorItems,
  artifactData,
}: StatePanelProps) {
  const [tab, setTab] = useState<InspectorTab>("overview");

  return (
    <Box
      component="aside"
      sx={{
        borderLeft: "1px solid",
        borderColor: "divider",
        bgcolor: "grey.50",
        minHeight: 0,
        display: "grid",
        gridTemplateRows: "auto auto minmax(0, 1fr)",
      }}
    >
      <Box sx={{ p: 2, borderBottom: "1px solid", borderColor: "divider", bgcolor: "background.paper" }}>
        <Typography variant="subtitle1">Inspector</Typography>
        <Typography variant="caption" color="text.secondary">
          概览当前会话，并查看 trace、错误和产物。
        </Typography>
      </Box>

      <Tabs
        value={tab}
        onChange={(_, next: InspectorTab) => setTab(next)}
        variant="fullWidth"
        sx={{
          minHeight: 40,
          bgcolor: "background.paper",
          borderBottom: "1px solid",
          borderColor: "divider",
          "& .MuiTab-root": { minHeight: 40, fontSize: 12 },
        }}
      >
        <Tab value="overview" label="概览" />
        <Tab value="trace" label="Trace" />
        <Tab value="errors" label="Errors" />
        <Tab value="artifacts" label="Artifacts" />
      </Tabs>

      <Box sx={{ minHeight: 0, overflowY: "auto" }}>
        {tab === "overview" ? (
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

            <Box sx={{ pt: 1 }}>
              <Typography variant="overline" color="text.secondary">
                最近 hook
              </Typography>
              {snapshot?.recentHookEvents && snapshot.recentHookEvents.length > 0 ? (
                <List dense disablePadding sx={{ mt: 0.5 }}>
                  {snapshot.recentHookEvents.slice(-5).map((item, index) => (
                    <ListItem key={`${index}-${String(item.name ?? item.message ?? "hook")}`} disableGutters sx={{ py: 0.5 }}>
                      <Typography variant="body2" sx={{ overflowWrap: "anywhere" }}>
                        {`${String(item.name ?? "hook")} · ${String(item.message ?? "")}`}
                      </Typography>
                    </ListItem>
                  ))}
                </List>
              ) : (
                <EmptyState text="暂无 hook 事件。" />
              )}
            </Box>
          </Box>
        ) : null}

        {tab === "trace" ? (
          <Box sx={{ p: 2 }}>
            {traceEntries.length > 0 ? (
              <Stack spacing={1.25}>
                {traceEntries.map((entry) => (
                  <Box key={`${entry.seq}-${entry.timestamp}`} sx={{ pb: 1.25 }}>
                    <Stack direction="row" justifyContent="space-between" spacing={1}>
                      <Typography variant="caption" sx={{ color: "primary.main", fontWeight: 600 }}>
                        {entry.event}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {formatTimestamp(entry.timestamp)}
                      </Typography>
                    </Stack>
                    <Typography variant="body2" sx={{ mt: 0.5, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                      {formatRecord(entry.payload)}
                    </Typography>
                    <Divider sx={{ mt: 1.25 }} />
                  </Box>
                ))}
              </Stack>
            ) : (
              <EmptyState text="这个会话还没有 trace 记录。" />
            )}
          </Box>
        ) : null}

        {tab === "errors" ? (
          <Box sx={{ p: 2 }}>
            {errorItems.length > 0 ? (
              <Stack spacing={1.5}>
                {errorItems.map((item) => (
                  <Box key={`${item.seq}-${item.createdAt}-${item.errorCode}`} sx={{ pb: 1 }}>
                    <Stack direction="row" justifyContent="space-between" spacing={1} alignItems="flex-start">
                      <Box>
                        <Typography variant="subtitle2">{item.message}</Typography>
                        <Stack direction="row" spacing={0.75} sx={{ mt: 0.5, flexWrap: "wrap" }}>
                          <Chip size="small" label={item.errorLayer || "error"} />
                          <Chip size="small" variant="outlined" label={item.errorCode || "unknown"} />
                          {item.retryable ? <Chip size="small" color="warning" label="可重试" /> : null}
                        </Stack>
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {formatTimestamp(item.createdAt)}
                      </Typography>
                    </Stack>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
                      {`phase=${item.phase || "-"} · worker=${item.worker || "-"}`}
                    </Typography>
                    {Object.keys(item.details ?? {}).length > 0 ? (
                      <Typography variant="body2" sx={{ mt: 0.75, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                        {formatRecord(item.details)}
                      </Typography>
                    ) : null}
                    <Divider sx={{ mt: 1.25 }} />
                  </Box>
                ))}
              </Stack>
            ) : (
              <EmptyState text="这个会话目前没有错误记录。" />
            )}
          </Box>
        ) : null}

        {tab === "artifacts" ? (
          <Box sx={{ p: 2, display: "grid", gap: 2 }}>
            {artifactData.tiles.length > 0 ? (
              <Box>
                <Typography variant="overline" color="text.secondary">
                  磁贴
                </Typography>
                <Stack spacing={1} sx={{ mt: 0.75 }}>
                  {artifactData.tiles.map((tile) => (
                    <Box
                      key={`${tile.path}-${tile.changeType}`}
                      sx={{
                        p: 1.25,
                        border: "1px solid",
                        borderColor: "divider",
                        borderRadius: 1.5,
                        bgcolor: "background.paper",
                      }}
                    >
                      <Stack direction="row" justifyContent="space-between" spacing={1}>
                        <Typography variant="body2" fontWeight={600} sx={{ overflowWrap: "anywhere" }}>
                          {tile.path}
                        </Typography>
                        <Chip size="small" label={tile.changeType} />
                      </Stack>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                        {tile.summary}
                      </Typography>
                    </Box>
                  ))}
                </Stack>
              </Box>
            ) : null}

            <Box>
              <Typography variant="overline" color="text.secondary">
                产物列表
              </Typography>
              {artifactData.items.length > 0 ? (
                <Stack spacing={1} sx={{ mt: 0.75 }}>
                  {artifactData.items.map((item) => (
                    <Box key={`${item.path}-${item.createdAt}`} sx={{ pb: 1 }}>
                      <Stack direction="row" justifyContent="space-between" spacing={1}>
                        <Typography variant="body2" fontWeight={600} sx={{ overflowWrap: "anywhere" }}>
                          {item.path}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {formatTimestamp(item.createdAt)}
                        </Typography>
                      </Stack>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
                        {`${item.changeType}${typeof item.size === "number" ? ` · ${item.size} B` : ""}`}
                      </Typography>
                      <Typography variant="body2" sx={{ mt: 0.5, overflowWrap: "anywhere" }}>
                        {item.summary || "-"}
                      </Typography>
                      <Divider sx={{ mt: 1.25 }} />
                    </Box>
                  ))}
                </Stack>
              ) : (
                <EmptyState text="这个会话还没有产物记录。" />
              )}
            </Box>
          </Box>
        ) : null}
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

function EmptyState({ text }: { text: string }) {
  return (
    <Typography variant="body2" color="text.secondary">
      {text}
    </Typography>
  );
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatRecord(value: Record<string, unknown>) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
