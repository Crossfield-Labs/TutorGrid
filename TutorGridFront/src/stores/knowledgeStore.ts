import { defineStore } from "pinia";

const COURSE_STORAGE_KEY = "metaagent.defaultCourseId";
const DEFAULT_COURSE_NAME = "MetaAgent 默认课程";
const DEFAULT_COURSE_DESC = "演示用：所有入库文件归档于此";
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

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

function apiUrl(path: string): string {
  return `${DEFAULT_API_BASE_URL}${path}`;
}

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(apiUrl(path));
  if (!res.ok) {
    throw new Error(`GET ${path} 失败: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`POST ${path} 失败: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
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

        if (cached) {
          try {
            const items = await apiGet<any[]>(`/api/knowledge/courses?limit=200`);
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

        const created = await apiPostJson<any>("/api/knowledge/courses", {
          name: DEFAULT_COURSE_NAME,
          description: DEFAULT_COURSE_DESC,
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
        const items = await apiGet<any[]>(
          `/api/knowledge/courses/${encodeURIComponent(this.courseId)}/files?limit=500`
        );
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
      const res = await apiPostJson<any>(
        `/api/knowledge/courses/${encodeURIComponent(courseId)}/files/import-local`,
        {
          file_path: opts.absolutePath,
          file_name: opts.fileName,
        }
      );
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

    async ragQuery(question: string, limit = 5) {
      const courseId = await this.ensureDefaultCourse();
      return apiPostJson<any>("/api/knowledge/rag/query", {
        course_id: courseId,
        question,
        limit,
      });
    },

    reset() {
      localStorage.removeItem(COURSE_STORAGE_KEY);
      this.courseId = "";
      this.courseName = "";
      this.files = [];
    },
  },
});
