import { useState } from "react";
import { Alert, Box, Button, Divider, Paper, Stack, TextField, Typography } from "@mui/material";
import type { MemorySearchResult } from "../../lib/ws-client";

type Notice = {
  severity: "success" | "info" | "warning" | "error";
  message: string;
};

type BusyState = {
  searching: boolean;
  cleaning: boolean;
  reindexing: boolean;
};

interface MemoryWorkbenchProps {
  notice: Notice | null;
  busy: BusyState;
  result: MemorySearchResult | null;
  onSearch: (query: string, limit: number, sessionId?: string) => void;
  onCleanup: () => void;
  onReindex: () => void;
}

export function MemoryWorkbench({
  notice,
  busy,
  result,
  onSearch,
  onCleanup,
  onReindex,
}: MemoryWorkbenchProps) {
  const [query, setQuery] = useState("");
  const [limitText, setLimitText] = useState("8");
  const [sessionId, setSessionId] = useState("");

  const submitSearch = () => {
    const text = query.trim();
    if (!text) {
      return;
    }
    const limit = Math.max(1, Number(limitText) || 8);
    const trimmedSessionId = sessionId.trim();
    onSearch(text, limit, trimmedSessionId || undefined);
  };

  return (
    <Box sx={{ p: 2.5, overflow: "auto" }}>
      <Stack spacing={2}>
        {notice ? <Alert severity={notice.severity}>{notice.message}</Alert> : null}

        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={1.5}>
            <Typography variant="h6">Memory Retrieval Workbench</Typography>
            <Typography variant="body2" color="text.secondary">
              Search memory index results, then run cleanup/reindex for maintenance.
            </Typography>
            <Divider />
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
              <TextField
                size="small"
                fullWidth
                label="Search query"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <TextField
                size="small"
                sx={{ width: 120 }}
                label="Limit"
                value={limitText}
                onChange={(event) => setLimitText(event.target.value)}
              />
              <Button variant="contained" onClick={submitSearch} disabled={busy.searching || !query.trim()}>
                {busy.searching ? "Searching..." : "Search"}
              </Button>
            </Stack>
            <TextField
              size="small"
              label="Session ID (optional)"
              value={sessionId}
              onChange={(event) => setSessionId(event.target.value)}
            />
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
              <Button variant="outlined" onClick={onCleanup} disabled={busy.cleaning}>
                {busy.cleaning ? "Cleaning..." : "Cleanup Memory"}
              </Button>
              <Button variant="outlined" onClick={onReindex} disabled={busy.reindexing}>
                {busy.reindexing ? "Reindexing..." : "Reindex Memory"}
              </Button>
            </Stack>
          </Stack>
        </Paper>

        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={1}>
            <Typography variant="subtitle1">Results</Typography>
            <Typography variant="caption" color="text.secondary">
              Query: {result?.query ?? "-"} | Hit count: {result?.items.length ?? 0}
            </Typography>
            <Divider />
            <Stack spacing={1}>
              {(result?.items ?? []).map((item) => (
                <Box key={item.documentId} sx={{ p: 1, border: "1px solid", borderColor: "divider", borderRadius: 1 }}>
                  <Stack direction="row" justifyContent="space-between" spacing={1}>
                    <Typography variant="body2" noWrap title={item.title || item.documentId}>
                      {item.title || item.documentId}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      score={Number(item.score ?? 0).toFixed(4)}
                    </Typography>
                  </Stack>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.4 }}>
                    type={item.documentType || "-"} | session={item.sessionId || "-"}
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 0.8, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                    {item.content}
                  </Typography>
                </Box>
              ))}
              {(result?.items.length ?? 0) === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No results yet. Run a memory search first.
                </Typography>
              ) : null}
            </Stack>
          </Stack>
        </Paper>
      </Stack>
    </Box>
  );
}
