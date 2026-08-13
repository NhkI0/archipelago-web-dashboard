/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Set for the static "try it" demo build (VITE_DEMO=1). */
  readonly VITE_DEMO?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
