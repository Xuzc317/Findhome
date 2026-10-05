import BaseService from "./base";
import type { MatchedHouse, MatchStats } from "./match";

export interface CityInfo {
  name: string;
  houseCount: number;
  stationCount: number;
  lineCount: number;
}

export interface SearchCriteria {
  city: string;
  stations: string[];
  line_names: string[];
  max_straight_m: number;
  max_walk_minutes: number;
  price_min: number | null;
  price_max: number | null;
  layouts: string[];
  rent_types: number[];
  exclude_shared: boolean;
  require_elevator: boolean;
  require_precise_location: boolean;
  min_newness_score: number | null;
  avoid_old_small: boolean;
  sources: string[];
  listing_kinds: string[];
  poster_types: string[];
  exclude_agency: boolean;
  sort_by: "walk" | "price" | "newness";
  compute_walk: boolean;
  max_walk_calls: number;
  locate_missing: boolean;
}

export interface SearchResult {
  success: boolean;
  message?: string;
  criteria: SearchCriteria;
  stats: MatchStats;
  total: number;
  data: MatchedHouse[];
  pendingLocation: MatchedHouse[];
}

export const DEFAULT_CRITERIA: SearchCriteria = {
  city: "深圳",
  stations: [],
  line_names: [],
  max_straight_m: 1000,
  max_walk_minutes: 20,
  price_min: 1200,
  price_max: 2500,
  layouts: ["studio", "1b1l", "2b1l"],
  rent_types: [3, 4],
  exclude_shared: true,
  require_elevator: false,
  require_precise_location: true,
  min_newness_score: null,
  avoid_old_small: true,
  sources: [],
  listing_kinds: [],
  poster_types: [],
  exclude_agency: false,
  sort_by: "walk",
  compute_walk: false,
  max_walk_calls: 150,
  locate_missing: false,
};

export class SearchService extends BaseService {
  async cities(): Promise<CityInfo[]> {
    const res = await this.get<any>("/search/cities");
    return res?.data || [];
  }

  async run(criteria: SearchCriteria): Promise<SearchResult> {
    const res = await this.post<any>("/search", criteria as unknown as Record<string, unknown>);
    return res as unknown as SearchResult;
  }

  /** 批量取卡片图（搜索结果不含图片，单独取） */
  async fetchPictures(ids: string[]): Promise<Record<string, string>> {
    const map: Record<string, string> = {};
    for (let i = 0; i < ids.length; i += 40) {
      const chunk = ids.slice(i, i + 40);
      try {
        const res = await this.get<any>("/v3/houses/by-ids", {
          ids: chunk.join(","),
        });
        (res?.data || []).forEach((h: any) => {
          if (h?.id && h.pictures?.[0]) map[h.id] = h.pictures[0];
        });
      } catch {
        // 图是锦上添花
      }
    }
    return map;
  }
}

export const searchService = new SearchService();
