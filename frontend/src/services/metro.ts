import BaseService from "./base";

/** 地铁线路 / 站点 / 步行距离 */
export class MetroService extends BaseService {
  async getLines(city = "深圳"): Promise<{ data: MetroLine[]; stats: MetroStats }> {
    return this.get<any>(`/metro/lines`, { city }).then((res: any) => res);
  }

  async getStations(city = "深圳", line?: string, keyword?: string) {
    const params: Record<string, unknown> = { city };
    if (line && line !== "all") params.line = line;
    if (keyword) params.keyword = keyword;
    return this.get<any>(`/metro/stations`, params).then((res: any) => res);
  }

  async getStats(city = "深圳"): Promise<MetroStats> {
    return this.get<any>(`/metro/stats`, { city }).then((res: any) => res.data);
  }

  /** 用高德补齐站点坐标 */
  async syncCoords(city = "深圳", overwrite = false) {
    return this.post<any>(`/metro/sync-coords`, { city, overwrite }).then(
      (res: any) => res,
    );
  }

  /** 计算房源到该站的真实步行距离（可反复调用增量续算） */
  async computeDistances(
    stationId: string,
    options: { limit?: number; onlyMissing?: boolean; maxCalls?: number } = {},
  ): Promise<ComputeDistanceResult> {
    return this.post<any>(`/metro/stations/${stationId}/distances`, {
      limit: options.limit ?? 200,
      only_missing: options.onlyMissing ?? true,
      max_calls: options.maxCalls ?? 400,
    }).then((res: any) => res);
  }

  async getCoverage(stationId: string): Promise<StationCoverage> {
    return this.get<any>(`/metro/stations/${stationId}/coverage`).then(
      (res: any) => res.data,
    );
  }
}

/** 地理定位与房型回填 */
export class GeoService extends BaseService {
  async getConfig(): Promise<GeoConfig> {
    return this.get<any>(`/geo/config`).then((res: any) => res.data);
  }

  async getStats(city = "深圳"): Promise<GeoStats> {
    return this.get<any>(`/geo/stats`, { city }).then((res: any) => res.data);
  }

  /** 批量推断坐标（小批量可反复调用） */
  async locate(options: {
    city?: string;
    limit?: number;
    onlyMissing?: boolean;
    useLlm?: boolean;
    maxCalls?: number;
  } = {}): Promise<{ success: boolean; message?: string; data?: LocateBatchResult }> {
    return this.post<any>(`/geo/locate`, {
      city: options.city ?? "深圳",
      limit: options.limit ?? 10,
      only_missing: options.onlyMissing ?? true,
      use_llm: options.useLlm ?? true,
      max_calls: options.maxCalls ?? 60,
    }).then((res: any) => res);
  }

  /** 历史房源房型回填 */
  async backfillLayout(city?: string) {
    return this.post<any>(`/geo/backfill-layout`, {
      city,
      only_missing: true,
      limit: 5000,
    }).then((res: any) => res);
  }
}

export const metroService = new MetroService();
export const geoService = new GeoService();
