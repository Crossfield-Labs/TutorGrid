import { useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import type {
  KnowledgeChunk,
  KnowledgeCourse,
  KnowledgeFile,
  KnowledgeJob,
  RagQueryResult,
} from "../../lib/ws-client";

type Notice = {
  severity: "success" | "info" | "warning" | "error";
  message: string;
};

type BusyState = {
  loadingCourses: boolean;
  creatingCourse: boolean;
  deletingCourse: boolean;
  ingestingFile: boolean;
  loadingCourseData: boolean;
  queryingRag: boolean;
  reembeddingCourse: boolean;
  reindexingCourse: boolean;
};

interface KnowledgeWorkbenchProps {
  courses: KnowledgeCourse[];
  selectedCourseId: string;
  files: KnowledgeFile[];
  chunks: KnowledgeChunk[];
  jobs: KnowledgeJob[];
  ragResult: RagQueryResult | null;
  notice: Notice | null;
  busy: BusyState;
  onSelectCourse: (courseId: string) => void;
  onRefreshCourses: () => void;
  onCreateCourse: (name: string, description: string) => void;
  onDeleteCourse: (courseId: string) => void;
  onRefreshCourseData: (courseId: string) => void;
  onIngestFile: (params: {
    courseId: string;
    filePath: string;
    fileName: string;
    chunkSize: number;
  }) => void;
  onDeleteFile: (courseId: string, fileId: string) => void;
  onRagQuery: (courseId: string, text: string, limit: number) => void;
  onReembedCourse: (courseId: string, batchSize: number) => void;
  onReindexCourse: (courseId: string) => void;
}

export function KnowledgeWorkbench({
  courses,
  selectedCourseId,
  files,
  chunks,
  jobs,
  ragResult,
  notice,
  busy,
  onSelectCourse,
  onRefreshCourses,
  onCreateCourse,
  onDeleteCourse,
  onRefreshCourseData,
  onIngestFile,
  onDeleteFile,
  onRagQuery,
  onReembedCourse,
  onReindexCourse,
}: KnowledgeWorkbenchProps) {
  const [localNotice, setLocalNotice] = useState<Notice | null>(null);
  const [courseName, setCourseName] = useState("");
  const [courseDescription, setCourseDescription] = useState("");
  const [filePath, setFilePath] = useState("");
  const [fileName, setFileName] = useState("");
  const [chunkSizeText, setChunkSizeText] = useState("900");
  const [ragQuery, setRagQuery] = useState("");
  const [ragLimitText, setRagLimitText] = useState("8");
  const [batchSizeText, setBatchSizeText] = useState("32");

  const selectedCourse = useMemo(
    () => courses.find((item) => item.courseId === selectedCourseId) ?? null,
    [courses, selectedCourseId],
  );
  const ragDebug = ragResult?.debug ?? {};
  const ragAnswer = ragResult?.answer?.trim() ?? "";
  const hydeText = typeof ragDebug.hyde === "string" ? ragDebug.hyde.trim() : "";
  const answerSource = typeof ragDebug.answerSource === "string" ? ragDebug.answerSource : "";
  const answerError = typeof ragDebug.answerError === "string" ? ragDebug.answerError : "";
  const hydeSource = typeof ragDebug.hydeSource === "string" ? ragDebug.hydeSource : "";
  const hydeError = typeof ragDebug.hydeError === "string" ? ragDebug.hydeError : "";

  const submitCreateCourse = () => {
    const trimmedName = courseName.trim();
    if (!trimmedName) {
      return;
    }
    onCreateCourse(trimmedName, courseDescription.trim());
    setCourseName("");
    setCourseDescription("");
  };

  const submitIngest = () => {
    if (!selectedCourseId) {
      return;
    }
    const trimmedPath = filePath.trim();
    if (!trimmedPath) {
      return;
    }
    const parsedChunkSize = Math.max(200, Number(chunkSizeText) || 900);
    onIngestFile({
      courseId: selectedCourseId,
      filePath: trimmedPath,
      fileName: fileName.trim(),
      chunkSize: parsedChunkSize,
    });
  };

  const submitRagQuery = () => {
    if (!selectedCourseId) {
      return;
    }
    const question = ragQuery.trim();
    if (!question) {
      return;
    }
    const limit = Math.max(1, Number(ragLimitText) || 8);
    onRagQuery(selectedCourseId, question, limit);
  };

  const runReembed = () => {
    if (!selectedCourseId) {
      return;
    }
    const batchSize = Math.max(1, Number(batchSizeText) || 32);
    onReembedCourse(selectedCourseId, batchSize);
  };

  const pickFileFromDesktop = async () => {
    setLocalNotice(null);
    const picker = window.desktopShell?.pickFiles;
    if (!picker) {
      setLocalNotice({
        severity: "warning",
        message: "当前环境未注入桌面文件选择器，请使用桌面端启动（npm run dev）或手动填写文件绝对路径。",
      });
      return;
    }
    try {
      const paths = await picker({ multiple: false, title: "选择要入库的文件" });
      const selected = paths[0] ?? "";
      if (!selected) {
        return;
      }
      setFilePath(selected);
      if (!fileName.trim()) {
        const segments = selected.split(/[\\/]/g);
        setFileName(segments[segments.length - 1] ?? "");
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : "unknown error";
      setLocalNotice({
        severity: "error",
        message: `文件选择失败：${detail}`,
      });
    }
  };

  return (
    <Box sx={{ p: 2.5, overflow: "auto" }}>
      <Stack spacing={2}>
        {notice ? <Alert severity={notice.severity}>{notice.message}</Alert> : null}
        {localNotice ? <Alert severity={localNotice.severity}>{localNotice.message}</Alert> : null}

        <Box sx={{ display: "grid", gridTemplateColumns: "320px minmax(0, 1fr)", gap: 2 }}>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack spacing={2}>
              <Box>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="h6">课程知识库</Typography>
                  <Button size="small" onClick={onRefreshCourses} disabled={busy.loadingCourses}>
                    刷新
                  </Button>
                </Stack>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  创建课程并切换当前课程，后续入库/RAG都基于当前课程。
                </Typography>
              </Box>

              <Divider />

              <Stack spacing={1.25}>
                <TextField
                  size="small"
                  label="课程名称"
                  value={courseName}
                  onChange={(event) => setCourseName(event.target.value)}
                />
                <TextField
                  size="small"
                  label="课程描述"
                  value={courseDescription}
                  onChange={(event) => setCourseDescription(event.target.value)}
                />
                <Button
                  variant="contained"
                  onClick={submitCreateCourse}
                  disabled={busy.creatingCourse || !courseName.trim()}
                >
                  创建课程
                </Button>
              </Stack>

              <Divider />

              <Stack spacing={1}>
                {courses.map((course) => {
                  const selected = course.courseId === selectedCourseId;
                  return (
                    <Box
                      key={course.courseId}
                      sx={{
                        p: 1.2,
                        border: "1px solid",
                        borderColor: selected ? "primary.main" : "divider",
                        borderRadius: 1.2,
                        bgcolor: selected ? "primary.50" : "background.paper",
                      }}
                    >
                      <Stack direction="row" justifyContent="space-between" spacing={1}>
                        <Box sx={{ minWidth: 0 }}>
                          <Typography variant="subtitle2" noWrap title={course.name}>
                            {course.name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary" noWrap title={course.courseId}>
                            {course.courseId}
                          </Typography>
                        </Box>
                        <Stack direction="row" spacing={0.5}>
                          <Button size="small" onClick={() => onSelectCourse(course.courseId)}>
                            选择
                          </Button>
                          <Button
                            size="small"
                            color="error"
                            onClick={() => onDeleteCourse(course.courseId)}
                            disabled={busy.deletingCourse}
                          >
                            删除
                          </Button>
                        </Stack>
                      </Stack>
                    </Box>
                  );
                })}
                {courses.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    暂无课程，先创建一个课程。
                  </Typography>
                ) : null}
              </Stack>
            </Stack>
          </Paper>

          <Stack spacing={2}>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Stack spacing={1.5}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="h6">入库与索引操作</Typography>
                  <Chip
                    size="small"
                    color={selectedCourse ? "primary" : "default"}
                    label={selectedCourse ? `当前课程：${selectedCourse.name}` : "未选择课程"}
                  />
                </Stack>

                <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                  <Button
                    variant="outlined"
                    onClick={() => selectedCourseId && onRefreshCourseData(selectedCourseId)}
                    disabled={!selectedCourseId || busy.loadingCourseData}
                  >
                    刷新文件/分块/任务
                  </Button>
                  <Button
                    variant="outlined"
                    onClick={() => selectedCourseId && onReindexCourse(selectedCourseId)}
                    disabled={!selectedCourseId || busy.reindexingCourse}
                  >
                    重建课程索引
                  </Button>
                </Stack>

                <Divider />

                <Stack spacing={1.2}>
                  <Typography variant="subtitle2">文件入库</Typography>
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                    <TextField
                      size="small"
                      fullWidth
                      label="文件路径"
                      value={filePath}
                      onChange={(event) => setFilePath(event.target.value)}
                    />
                    <Button variant="outlined" onClick={pickFileFromDesktop}>
                      浏览
                    </Button>
                  </Stack>
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                    <TextField
                      size="small"
                      fullWidth
                      label="文件名（可选）"
                      value={fileName}
                      onChange={(event) => setFileName(event.target.value)}
                    />
                    <TextField
                      size="small"
                      sx={{ width: 150 }}
                      label="Chunk Size"
                      value={chunkSizeText}
                      onChange={(event) => setChunkSizeText(event.target.value)}
                    />
                    <Button
                      variant="contained"
                      onClick={submitIngest}
                      disabled={!selectedCourseId || !filePath.trim() || busy.ingestingFile}
                    >
                      开始入库
                    </Button>
                  </Stack>
                </Stack>

                <Divider />

                <Stack spacing={1.2}>
                  <Typography variant="subtitle2">课程重嵌入</Typography>
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                    <TextField
                      size="small"
                      label="Batch Size"
                      value={batchSizeText}
                      onChange={(event) => setBatchSizeText(event.target.value)}
                      sx={{ width: 150 }}
                    />
                    <Button
                      variant="outlined"
                      onClick={runReembed}
                      disabled={!selectedCourseId || busy.reembeddingCourse}
                    >
                      执行重嵌入
                    </Button>
                  </Stack>
                </Stack>
              </Stack>
            </Paper>

            <Paper variant="outlined" sx={{ p: 2 }}>
              <Stack spacing={1.5}>
                <Typography variant="h6">RAG 查询</Typography>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                  <TextField
                    size="small"
                    fullWidth
                    label="问题"
                    value={ragQuery}
                    onChange={(event) => setRagQuery(event.target.value)}
                  />
                  <TextField
                    size="small"
                    label="Limit"
                    value={ragLimitText}
                    onChange={(event) => setRagLimitText(event.target.value)}
                    sx={{ width: 120 }}
                  />
                  <Button
                    variant="contained"
                    onClick={submitRagQuery}
                    disabled={!selectedCourseId || !ragQuery.trim() || busy.queryingRag}
                  >
                    查询
                  </Button>
                </Stack>
                <Divider />
                <Typography variant="subtitle2">答案</Typography>
                <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                  {ragAnswer || "暂无答案（仅返回了检索片段）"}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  answerSource: {answerSource || "-"}
                </Typography>
                {answerError ? (
                  <Typography variant="caption" color="error.main">
                    answerError: {answerError}
                  </Typography>
                ) : null}
                <Divider />
                <Typography variant="subtitle2">HyDE</Typography>
                <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                  {hydeText || "HyDE 未产出（可能未启用或生成失败）"}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  hydeSource: {hydeSource || "-"}
                </Typography>
                {hydeError ? (
                  <Typography variant="caption" color="error.main">
                    hydeError: {hydeError}
                  </Typography>
                ) : null}
                <Typography variant="subtitle2">调试信息</Typography>
                <Typography variant="caption" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                  {ragResult ? JSON.stringify(ragResult.debug ?? {}, null, 2) : "{}"}
                </Typography>
              </Stack>
            </Paper>
          </Stack>
        </Box>

        <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 2 }}>
          <Paper variant="outlined" sx={{ p: 2, minHeight: 220 }}>
            <Typography variant="subtitle1">文件列表</Typography>
            <Stack spacing={1} sx={{ mt: 1.2 }}>
              {files.map((file) => (
                <Box key={file.fileId} sx={{ p: 1, border: "1px solid", borderColor: "divider", borderRadius: 1 }}>
                  <Stack direction="row" justifyContent="space-between" spacing={1}>
                    <Typography variant="body2" noWrap title={file.originalName}>
                      {file.originalName}
                    </Typography>
                    <Chip size="small" label={file.parseStatus || "unknown"} />
                  </Stack>
                  <Typography variant="caption" color="text.secondary">
                    {file.fileId}
                  </Typography>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 0.6 }}>
                    <Typography variant="caption" color="text.secondary" noWrap title={file.fileExt}>
                      {file.fileExt}
                    </Typography>
                    <Button
                      size="small"
                      color="error"
                      onClick={() => selectedCourseId && onDeleteFile(selectedCourseId, file.fileId)}
                      disabled={!selectedCourseId}
                    >
                      删除
                    </Button>
                  </Stack>
                </Box>
              ))}
              {files.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  当前课程暂无文件。
                </Typography>
              ) : null}
            </Stack>
          </Paper>

          <Paper variant="outlined" sx={{ p: 2, minHeight: 220 }}>
            <Typography variant="subtitle1">入库任务</Typography>
            <Stack spacing={1} sx={{ mt: 1.2 }}>
              {jobs.map((job) => (
                <Box key={job.jobId} sx={{ p: 1, border: "1px solid", borderColor: "divider", borderRadius: 1 }}>
                  <Stack direction="row" justifyContent="space-between" spacing={1}>
                    <Typography variant="body2">{job.status}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {(job.progress * 100).toFixed(0)}%
                    </Typography>
                  </Stack>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.4 }}>
                    {job.message || "-"}
                  </Typography>
                </Box>
              ))}
              {jobs.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  当前课程暂无任务记录。
                </Typography>
              ) : null}
            </Stack>
          </Paper>

          <Paper variant="outlined" sx={{ p: 2, minHeight: 220 }}>
            <Typography variant="subtitle1">分块与解析器</Typography>
            <Stack spacing={1} sx={{ mt: 1.2 }}>
              {chunks.map((chunk) => {
                const parser = String(chunk.metadata?.parser ?? "unknown");
                return (
                  <Box key={chunk.chunkId} sx={{ p: 1, border: "1px solid", borderColor: "divider", borderRadius: 1 }}>
                    <Stack direction="row" justifyContent="space-between" spacing={1}>
                      <Chip size="small" label={parser} />
                      <Typography variant="caption" color="text.secondary">
                        {chunk.sourceSection || `page-${chunk.sourcePage}`}
                      </Typography>
                    </Stack>
                    <Typography variant="body2" sx={{ mt: 0.6, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                      {chunk.content}
                    </Typography>
                  </Box>
                );
              })}
              {chunks.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  当前课程暂无分块数据。
                </Typography>
              ) : null}
            </Stack>
          </Paper>
        </Box>

        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle1">RAG 命中文档片段</Typography>
          <Stack spacing={1} sx={{ mt: 1.2 }}>
            {(ragResult?.items ?? []).map((item) => (
              <Box key={item.chunkId} sx={{ p: 1, border: "1px solid", borderColor: "divider", borderRadius: 1 }}>
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="caption" color="text.secondary">
                    chunk={item.chunkId}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    score={Number(item.score ?? 0).toFixed(4)}
                  </Typography>
                </Stack>
                <Typography variant="body2" sx={{ mt: 0.5, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                  {item.content}
                </Typography>
              </Box>
            ))}
            {(ragResult?.items?.length ?? 0) === 0 ? (
              <Typography variant="body2" color="text.secondary">
                暂无命中片段，先执行一次 RAG 查询。
              </Typography>
            ) : null}
          </Stack>
        </Paper>
      </Stack>
    </Box>
  );
}
