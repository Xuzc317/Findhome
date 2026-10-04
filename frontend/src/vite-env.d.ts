/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 高德地图 JS API Key（前端地图页使用） */
  readonly VITE_AMAP_KEY?: string;
  /** 高德 JS API v2.0 安全密钥（与 VITE_AMAP_KEY 配套） */
  readonly VITE_AMAP_SECURITY_CODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
