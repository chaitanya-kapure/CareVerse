/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL for the CAREVERSE API. Defaults to the dev proxy, "/api". */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
