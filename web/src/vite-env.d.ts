/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_BASEMAP_STYLE: string;
  readonly VITE_DEFAULT_LANG: 'id' | 'en';
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
