/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_AUTH_DISABLED: string | undefined;
  readonly VITE_DEMO_MODE: string | undefined;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
