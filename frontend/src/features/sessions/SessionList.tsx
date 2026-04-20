import { useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import {
  Box,
  Button,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  TextField,
  Typography,
} from "@mui/material";
import type { UiSession } from "../../lib/ws-client";

interface SessionListProps {
  sessions: UiSession[];
  selectedSessionId: string;
  onSelect: (sessionId: string) => void;
  onPrepareNewTask: () => void;
  onRenameSession: (sessionId: string, title: string) => void;
}

export function SessionList({
  sessions,
  selectedSessionId,
  onSelect,
  onPrepareNewTask,
  onRenameSession,
}: SessionListProps) {
  const [editingSessionId, setEditingSessionId] = useState<string>("");
  const [editingValue, setEditingValue] = useState("");

  const beginRename = (session: UiSession) => {
    setEditingSessionId(session.sessionId);
    setEditingValue(session.displayTitle ?? session.task);
  };

  const commitRename = () => {
    if (!editingSessionId) {
      return;
    }
    onRenameSession(editingSessionId, editingValue);
    setEditingSessionId("");
    setEditingValue("");
  };

  return (
    <Box
      component="aside"
      sx={{
        borderRight: "1px solid",
        borderColor: "divider",
        bgcolor: "grey.50",
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
        p: 1.5,
      }}
    >
      <Box sx={{ mb: 1.5 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Orchestrator
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Session Console
        </Typography>
      </Box>

      <Button
        startIcon={<AddIcon />}
        variant="contained"
        size="small"
        onClick={onPrepareNewTask}
        sx={{ mb: 1.5, justifyContent: "flex-start" }}
      >
        新任务
      </Button>

      <Typography variant="caption" color="text.secondary" sx={{ px: 1, mb: 1 }}>
        最近会话
      </Typography>

      <List dense disablePadding sx={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        {sessions.map((session) => {
          const title = session.displayTitle ?? session.task;
          const isSelected = session.sessionId === selectedSessionId;
          const isEditing = session.sessionId === editingSessionId;
          return (
            <ListItem
              key={session.sessionId}
              disablePadding
              secondaryAction={
                !isEditing ? (
                  <IconButton
                    size="small"
                    edge="end"
                    aria-label="重命名会话"
                    onClick={(event) => {
                      event.stopPropagation();
                      beginRename(session);
                    }}
                  >
                    <EditIcon fontSize="inherit" />
                  </IconButton>
                ) : undefined
              }
            >
              {isEditing ? (
                <TextField
                  size="small"
                  fullWidth
                  value={editingValue}
                  autoFocus
                  onClick={(event) => event.stopPropagation()}
                  onChange={(event) => setEditingValue(event.target.value)}
                  onBlur={commitRename}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      commitRename();
                    }
                    if (event.key === "Escape") {
                      setEditingSessionId("");
                      setEditingValue("");
                    }
                  }}
                  sx={{ ml: 1, mr: 1 }}
                />
              ) : (
                <ListItemButton selected={isSelected} onClick={() => onSelect(session.sessionId)} sx={{ pr: 5 }}>
                  <ListItemText
                    primary={title}
                    primaryTypographyProps={{ noWrap: true, title }}
                  />
                </ListItemButton>
              )}
            </ListItem>
          );
        })}
      </List>

      <Typography variant="caption" color="text.secondary" sx={{ mt: 1.5, px: 1 }}>
        Desktop GUI · Electron shell
      </Typography>
    </Box>
  );
}
