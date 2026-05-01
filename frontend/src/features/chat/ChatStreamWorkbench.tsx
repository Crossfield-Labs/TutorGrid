import { useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  Divider,
  FormControlLabel,
  LinearProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import type { KnowledgeCourse } from "../../lib/ws-client";
import { streamChat, type ChatCitation, type ChatSseEvent } from "../../lib/chat-sse";

type ChatEventRecord = {
  id: string;
  event: ChatSseEvent;
  createdAt: string;
};

interface ChatStreamWorkbenchProps {
  courses: KnowledgeCourse[];
  selectedCourseId: string;
}

export function ChatStreamWorkbench({ courses, selectedCourseId }: ChatStreamWorkbenchProps) {
  const [baseUrl, setBaseUrl] = useState("http://127.0.0.1:8000");
  const [sessionId, setSessionId] = useState(() => `sess_frontend_${crypto.randomUUID().slice(0, 8)}`);
  const [courseId, setCourseId] = useState(selectedCourseId);
  const [message, setMessage] = useState("请简单介绍监督学习");
  const [useRag, setUseRag] = useState(true);
  const [useTavily, setUseTavily] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [answer, setAnswer] = useState("");
  const [events, setEvents] = useState<ChatEventRecord[]>([]);
  const [citations, setCitations] = useState<ChatCitation[]>([]);
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  const selectedCourse = useMemo(
    () => courses.find((course) => course.courseId === courseId) ?? null,
    [courseId, courses],
  );
  const eventTypes = events.map((item) => item.event.type);
  const hasDone = eventTypes.includes("done");
  const hasDelta = eventTypes.includes("delta");
  const hasRagCall = events.some((item) => item.event.type === "tool_call" && item.event.tool === "rag");
  const canSubmit = Boolean(sessionId.trim() && message.trim() && !isStreaming);

  const submit = async () => {
    if (!canSubmit) {
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setIsStreaming(true);
    setAnswer("");
    setEvents([]);
    setCitations([]);
    setError("");

    const tools = [
      ...(useRag ? ["rag"] : []),
      ...(useTavily ? ["tavily"] : []),
    ];

    try {
      await streamChat(
        baseUrl,
        {
          session_id: sessionId.trim(),
          message: message.trim(),
          course_id: courseId.trim() || undefined,
          tools,
        },
        {
          signal: controller.signal,
          onEvent: (event) => {
            setEvents((current) => [
              ...current,
              {
                id: crypto.randomUUID(),
                event,
                createdAt: new Date().toLocaleTimeString(),
              },
            ]);
            if (event.type === "delta" && event.content) {
              setAnswer((current) => current + event.content);
            }
            if (event.type === "tool_result" && event.tool === "rag" && Array.isArray(event.citations)) {
              setCitations(event.citations);
            }
            if (event.type === "error") {
              setError(event.message || "Stream failed.");
            }
          },
        },
      );
    } catch (streamError) {
      if (!controller.signal.aborted) {
        setError(streamError instanceof Error ? streamError.message : "Stream failed.");
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    setIsStreaming(false);
  };

  return (
    <Box sx={{ p: 2.5, overflow: "auto" }}>
      <Stack spacing={2}>
        <Paper variant="outlined" sx={{ overflow: "hidden" }}>
          {isStreaming ? <LinearProgress /> : null}
          <Box sx={{ p: 2.5 }}>
            <Stack spacing={2}>
              <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                <TextField
                  size="small"
                  label="Backend URL"
                  value={baseUrl}
                  onChange={(event) => setBaseUrl(event.target.value)}
                  sx={{ minWidth: 260 }}
                />
                <TextField
                  size="small"
                  label="Session ID"
                  value={sessionId}
                  onChange={(event) => setSessionId(event.target.value)}
                  sx={{ minWidth: 240 }}
                />
                <TextField
                  size="small"
                  label="Course ID"
                  value={courseId}
                  onChange={(event) => setCourseId(event.target.value)}
                  sx={{ minWidth: 320 }}
                  helperText={selectedCourse ? selectedCourse.name : "Leave empty for plain LLM chat"}
                />
              </Stack>

              <TextField
                label="Message"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                multiline
                minRows={3}
                fullWidth
              />

              <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }}>
                <FormControlLabel
                  control={<Checkbox checked={useRag} onChange={(event) => setUseRag(event.target.checked)} />}
                  label="rag"
                />
                <FormControlLabel
                  control={<Checkbox checked={useTavily} onChange={(event) => setUseTavily(event.target.checked)} />}
                  label="tavily"
                />
                <Box sx={{ flex: 1 }} />
                {isStreaming ? (
                  <Button color="warning" variant="outlined" onClick={stop}>
                    Stop
                  </Button>
                ) : null}
                <Button variant="contained" onClick={submit} disabled={!canSubmit}>
                  Send
                </Button>
              </Stack>
            </Stack>
          </Box>
        </Paper>

        {error ? <Alert severity="error">{error}</Alert> : null}

        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1fr) 360px" }, gap: 2 }}>
          <Paper variant="outlined" sx={{ p: 2, minHeight: 360 }}>
            <Stack spacing={1.5}>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="h6">Answer</Typography>
                <Chip size="small" color={hasDelta ? "success" : "default"} label={hasDelta ? "delta" : "waiting"} />
                <Chip size="small" color={hasDone ? "success" : "default"} label={hasDone ? "done" : "open"} />
                {hasRagCall ? <Chip size="small" color="primary" label="rag" /> : null}
              </Stack>
              <Divider />
              <Typography variant="body1" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                {answer || "No streamed content yet."}
              </Typography>
            </Stack>
          </Paper>

          <Stack spacing={2}>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle1">Events</Typography>
              <Stack spacing={1} sx={{ mt: 1.2 }}>
                {events.map((item) => (
                  <Box key={item.id} sx={{ display: "flex", gap: 1, alignItems: "center" }}>
                    <Typography variant="caption" color="text.secondary" sx={{ width: 76 }}>
                      {item.createdAt}
                    </Typography>
                    <Chip size="small" label={item.event.type} />
                    {"tool" in item.event && item.event.tool ? (
                      <Typography variant="caption" color="text.secondary">
                        {String(item.event.tool)}
                      </Typography>
                    ) : null}
                  </Box>
                ))}
                {!events.length ? (
                  <Typography variant="body2" color="text.secondary">
                    No SSE events yet.
                  </Typography>
                ) : null}
              </Stack>
            </Paper>

            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle1">Citations</Typography>
              <Stack spacing={1} sx={{ mt: 1.2 }}>
                {citations.map((citation, index) => (
                  <Box key={`${citation.source ?? "source"}-${index}`} sx={{ p: 1, border: "1px solid", borderColor: "divider", borderRadius: 1 }}>
                    <Stack direction="row" justifyContent="space-between" spacing={1}>
                      <Typography variant="caption" color="text.secondary" noWrap title={citation.source}>
                        {citation.source || "unknown"}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {typeof citation.score === "number" ? citation.score.toFixed(4) : "-"}
                      </Typography>
                    </Stack>
                    <Typography variant="body2" sx={{ mt: 0.5, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                      {citation.chunk || ""}
                    </Typography>
                  </Box>
                ))}
                {!citations.length ? (
                  <Typography variant="body2" color="text.secondary">
                    RAG citations will appear here.
                  </Typography>
                ) : null}
              </Stack>
            </Paper>
          </Stack>
        </Box>
      </Stack>
    </Box>
  );
}
