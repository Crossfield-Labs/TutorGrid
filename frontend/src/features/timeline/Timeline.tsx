import { useLayoutEffect, useRef } from "react";
import { Box, Button, Stack, TextField, Typography } from "@mui/material";

import type { TimelineEvent, UiSession } from "../../lib/ws-client";

interface TimelineProps {
  session: UiSession | null;
  events: TimelineEvent[];
  liveEvent: TimelineEvent | null;
  inputValue: string;
  onInputChange: (value: string) => void;
  onSubmit: () => void;
  onSnapshot: () => void;
  onExplain: () => void;
  isAwaitingInput: boolean;
}

const COMPOSER_MIN_HEIGHT = 60;
const COMPOSER_MAX_HEIGHT = 168;

export function Timeline({
  session,
  events,
  liveEvent,
  inputValue,
  onInputChange,
  onSubmit,
  onSnapshot,
  onExplain,
  isAwaitingInput,
}: TimelineProps) {
  const placeholder = buildPlaceholder(session, isAwaitingInput);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = `${COMPOSER_MIN_HEIGHT}px`;
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, COMPOSER_MIN_HEIGHT), COMPOSER_MAX_HEIGHT);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > COMPOSER_MAX_HEIGHT ? "auto" : "hidden";
  }, [inputValue]);

  return (
    <Box
      component="section"
      sx={{
        display: "grid",
        gridTemplateRows: "auto minmax(0, 1fr) auto",
        minHeight: 0,
        bgcolor: "background.paper",
      }}
    >
      <Box sx={{ px: 2.5, py: 1.75, borderBottom: "1px solid", borderColor: "divider" }}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1.5}>
          <Box>
            <Typography variant="h6">{session ? session.displayTitle ?? session.task : "新建任务或选择会话"}</Typography>
            <Typography variant="caption" color="text.secondary">
            {session
              ? `${session.runner} · ${session.status} · ${session.activeWorker || "no worker"}`
              : "未选中会话时，输入框会直接创建新的任务。"}
            </Typography>
          </Box>
          <Stack direction="row" spacing={1}>
            <Button variant="outlined" size="small" onClick={onSnapshot} disabled={!session}>
            Snapshot
            </Button>
            <Button variant="outlined" size="small" onClick={onExplain} disabled={!session}>
            Explain
            </Button>
          </Stack>
        </Stack>
      </Box>

      <Box sx={{ minHeight: 0, overflowY: "auto" }}>
        <Box sx={{ px: 2.5, pt: 1.5, pb: 1, borderBottom: "1px solid", borderColor: "divider" }}>
          <Typography variant="overline" color="text.secondary">
            当前步骤
          </Typography>
          {liveEvent ? (
            <Box sx={{ mt: 0.5 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="baseline" spacing={1}>
                <Typography variant="subtitle2">{liveEvent.title}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {new Date(liveEvent.createdAt).toLocaleTimeString()}
                </Typography>
              </Stack>
              <Typography variant="caption" sx={{ textTransform: "uppercase", color: "success.dark", letterSpacing: 0.8 }}>
                {liveEvent.kind}
              </Typography>
              <Typography variant="body2" sx={{ mt: 0.5, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                {liveEvent.detail}
              </Typography>
            </Box>
          ) : (
            <Typography variant="body2" color="text.secondary">
              等待新的运行步骤。
            </Typography>
          )}
        </Box>

        <Box>
          {events.length > 0 ? (
            events.map((event) => (
              <Box key={event.id} sx={{ px: 2.5, py: 1.75, borderBottom: "1px solid", borderColor: "divider" }}>
                <Stack direction="row" justifyContent="space-between" spacing={1} alignItems="baseline">
                  <Box>
                    <Typography variant="caption" sx={{ textTransform: "uppercase", color: "success.dark", letterSpacing: 0.8 }}>
                      {event.kind}
                    </Typography>
                    <Typography variant="subtitle2">{event.title}</Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(event.createdAt).toLocaleTimeString()}
                  </Typography>
                </Stack>
                <Typography variant="body2" sx={{ mt: 0.5, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                  {event.detail}
                </Typography>
              </Box>
            ))
          ) : (
            <Typography variant="body2" color="text.secondary" sx={{ px: 2.5, py: 4 }}>
              这个会话还没有历史记录。发送一个新任务，或者选择左侧已有会话。
            </Typography>
          )}
        </Box>
      </Box>

      <Box sx={{ px: 2.5, py: 1.5, borderTop: "1px solid", borderColor: "divider" }}>
        <TextField
          inputRef={textareaRef}
          multiline
          fullWidth
          minRows={2}
          placeholder={placeholder}
          value={inputValue}
          onChange={(event) => onInputChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              event.stopPropagation();
              onSubmit();
            }
          }}
          inputProps={{ style: { lineHeight: 1.6, overflowWrap: "anywhere" } }}
          sx={{
            "& .MuiOutlinedInput-root": { alignItems: "flex-start" },
            "& textarea": {
              minHeight: `${COMPOSER_MIN_HEIGHT}px`,
              maxHeight: `${COMPOSER_MAX_HEIGHT}px`,
              overflowY: "hidden",
            },
          }}
        />
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary">
            {isAwaitingInput ? "当前会话正在等待你的回复" : "Enter 发送 · Shift+Enter 换行"}
          </Typography>
          <Button variant="contained" onClick={onSubmit}>
            发送
          </Button>
        </Stack>
      </Box>
    </Box>
  );
}

function buildPlaceholder(session: UiSession | null, isAwaitingInput: boolean): string {
  if (!session) {
    return "直接输入新的任务目标，例如：先了解一下这个项目，并重点看 server 和 runtime。";
  }
  if (isAwaitingInput) {
    return "继续当前会话，例如：继续，或者补充你想让 agent 回答的信息。";
  }
  return "继续输入你的要求，系统会自动判断是继续执行、补充指令还是调整方向。";
}
