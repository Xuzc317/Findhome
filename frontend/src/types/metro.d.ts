/** 地铁 / 地理定位相关类型 */

interface MetroLine {
  id: string;
  name: string;
  alias?: string | null;
  color?: string | null;
  sortOrder: number;
  stationCount: number;
  stationWithCoord: number;
  source?: string | null;
}

interface MetroStationLineRef {
  name: string;
  color?: string | null;
  seq: number;
}

interface MetroStation {
  id: string;
  name: string;
  city: string;
  lng?: number | null;
  lat?: number | null;
  coordSource?: string | null;
  lines: MetroStationLineRef[];
}

interface StationCoverage {
  cached: number;
  ok: number;
  noRoute: number;
}

interface MetroStats {
  lines: number;
  stations: number;
  stationsWithCoord: number;
}

interface GeoConfig {
  amap: { available: boolean };
  llm: {
    requested: string;
    active: string | null;
    deepseekConfigured: boolean;
    doubaoConfigured: boolean;
    doubaoModelSet: boolean;
    visionAvailable: boolean;
  };
  layoutOptions: { key: string; label: string }[];
}

interface GeoStats {
  city: string;
  total: number;
  withCoord: number;
  withoutCoord: number;
  bySource: Record<string, number>;
  byPrecision: Record<string, number>;
  byLayout: Record<string, number>;
  stationDistancesCached: number;
  coveragePercent: number;
}

interface LocateBatchResult {
  total: number;
  located: number;
  failed: number;
  skipped: number;
  amapCalls: number;
  cacheHits: number;
  details: { id: string; title?: string; result: string; precision?: string }[];
}

interface ComputeDistanceResult {
  success: boolean;
  message: string;
  computed?: number;
  noRoute?: number;
  errors?: number;
  skipped?: number;
  queued?: number;
  amapCalls?: number;
  coverage?: StationCoverage;
}
