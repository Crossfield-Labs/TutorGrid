export {};

declare global {
  interface Window {
    desktopShell?: {
      platform: string;
      pickFiles?: (options?: {
        multiple?: boolean;
        title?: string;
      }) => Promise<string[]>;
    };
  }
}
