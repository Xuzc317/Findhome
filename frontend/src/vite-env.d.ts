/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 高德地图 JS API Key（前端地图页使用） */
  readonly VITE_AMAP_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
