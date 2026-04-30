import { defineStore } from "pinia";
import { useOrchestratorStore } from "@/stores/orchestratorStore";

const COURSE_STORAGE_KEY = "metaagent.defaultCourseId";
const DEFAULT_COURSE_NAME = "MetaAgent 默认课程";
const DEFAULT_COURSE_DESC = "演示用：所有入库文件归档于此";

export interface KnowledgeFile {
  fileId: string;
  fileName: string;
  filePath?: string;
  chunkCount?: number;
  parseStatus?: string;
  parseError?: string;
  fileExt?: string;
  createdAt?: string;
}

export const useKnowledgeStore = defineStore("knowledge", {
  state: () => ({
    courseId: "" as string,
    courseName: "" as string,
    files: [] as KnowledgeFile[],
    loading: false,
    initializing: false,
  }),

  getters: {
    isReady: (state) => Boolean(state.courseId),
  },

  actions: {
    async ensureDefaultCourse(): Promise<string> {
      if (this.courseId) return this.courseId;
      if (this.initializing) {
        return new Promise<string>((resolve) => {
          const tick = () => {
            if (!this.initializing && this.courseId) resolve(this.courseId);
            else setTimeout(tick, 80);
          };
          tick();
        });
      }
      this.initializing = true;
      try {
        const cached = localStorage.getItem(COURSE_STORAGE_KEY) || "";
        const orchestrator = useOrchestratorStore();

        if (cached) {
          try {
            const list = await orchestrator.knowledgeCourseList({ limit: 200 });
            const items: any[] = list?.items || list?.courses || [];
            const found = items.find((c) => c.courseId === cached);
            if (found) {
              this.courseId = cached;
              this.courseName = found.name || DEFAULT_COURSE_NAME;
              return this.courseId;
            }
          } catch {
            /* fall through to create */
          }
        }

        const created = await orchestrator.knowledgeCourseCreate({
          courseName: DEFAULT_COURSE_NAME,
          courseDescription: DEFAULT_COURSE_DESC,
        });
        const cid =
          created?.courseId || created?.id || created?.course?.courseId || "";
        if (!cid) throw new Error("course.create 未返回 courseId");
        this.courseId = cid;
        this.courseName = created?.name || DEFAULT_COURSE_NAME;
        localStorage.setItem(COURSE_STORAGE_KEY, cid);
        return cid;
      } finally {
        this.initializing = false;
      }
    },

    async refreshFiles() {
      if (!this.courseId) return;
      this.loading = true;
      try {
        const orchestrator = useOrchestratorStore();
        const res = await orchestrator.knowledgeFileList({
          courseId: this.courseId,
          limit: 500,
        });
        const items: any[] = res?.items || res?.files || [];
        // preserve previously-known chunkCount across reloads (list_files doesn't return it)
        const prevChunks = new Map<string, number>(
          this.files.map((f) => [f.fileId, f.chunkCount || 0])
        );
        this.files = items.map((it) => ({
          fileId: it.fileId || it.id || "",
          fileName:
            it.originalName ||
            it.fileName ||
            it.name ||
            it.storedPath ||
            it.filePath ||
            "未命名",
          filePath: it.storedPath || it.filePath || "",
          chunkCount: prevChunks.get(it.fileId) || 0,
          parseStatus: it.parseStatus || it.status || "",
          parseError: it.parseError || "",
          fileExt: it.fileExt || "",
          createdAt: it.createdAt || "",
        }));
      } finally {
        this.loading = false;
      }
    },

    async ingestFile(opts: { absolutePath: string; fileName: string }) {
      const courseId = await this.ensureDefaultCourse();
      const orchestrator = useOrchestratorStore();
      const res = await orchestrator.knowledgeFileIngest({
        courseId,
        filePath: opts.absolutePath,
        fileName: opts.fileName,
      });
      await this.refreshFiles();
      // patch chunkCount from ingest response (file.list doesn't expose it)
      const fid = res?.fileId || "";
      const chunks = res?.chunkCount || res?.chunks || 0;
      if (fid && chunks) {
        const f = this.files.find((x) => x.fileId === fid);
        if (f) f.chunkCount = chunks;
      }
      return res;
    },

    reset() {
      localStorage.removeItem(COURSE_STORAGE_KEY);
      this.courseId = "";
      this.courseName = "";
      this.files = [];
    },
  },
});
