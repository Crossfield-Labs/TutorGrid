export {};

declare global {
  interface Window {
    metaAgent?: {
      app: {
        getInfo: () => Promise<{
          name: string;
          version: string;
          userDataPath: string;
          isDevelopment: boolean;
        }>;
      };
      workspace: {
        pickFolder: () => Promise<string | null>;
        getRoot: () => Promise<string>;
        setRoot: (newRoot: string) => Promise<string>;
        loadTiles: () => Promise<unknown | null>;
        saveTiles: (data: unknown) => Promise<void>;
        importFile: (payload: {
          buffer: Uint8Array;
          originalName: string;
        }) => Promise<{ relPath: string }>;
        listRootFiles: () => Promise<
          Array<{ name: string; size: number; mtime: number }>
        >;
        fileExists: (relPath: string) => Promise<boolean>;
        readFileBuffer: (relPath: string) => Promise<Uint8Array>;
        readText: (relPath: string) => Promise<string>;
        writeText: (payload: {
          relPath: string;
          content: string;
        }) => Promise<void>;
        createHyperdoc: (
          initialContent?: string
        ) => Promise<{ relPath: string }>;
        deleteFile: (relPath: string) => Promise<void>;
        openExternal: (relPath: string) => Promise<void>;
        openPath: (filePath: string) => Promise<void>;
        exportPdf: (payload: {
          title: string;
        }) => Promise<{ canceled: boolean; filePath?: string }>;
      };
    };
  }
}
