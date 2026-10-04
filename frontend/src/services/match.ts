import BaseService from "./base";

/** 匹配结果里的一条房源 */
export interface MatchedHouse {
  house_id: string;
  title: string;
  price: number | null;
  layout_label: string;
  source: string;
  source_url: string;
  district: string | null;
  community: string | null;
  nearest_station: string;
  nearest_station_lines: string[];
  straight_m: number;
  walk_m: number | null;
  walk_minutes: number | null;
  walk_status: string;
  elevator: boolean | null;
  elevator_evidence: string | null;
  elevator_hint: string | null;
  newness_score: number;
  newness_signals: string[];
  old_small: boolean;
  geo_source: string | null;
  geo_precision: string | null;
  listing_kind: "sublet" | "direct" | "normal";
  seller_id: string | null;
  seller_listings: number;
  poster_type: "individual" | "agency" | "unknown";
  reasons: string[];
  caveats: string[];
  /** 前端补充：卡片图（由 /v3/houses 里取，匹配接口不返回图片） */
  picture?: string;
}

export interface MatchStats {
  priceLayoutCandidates: number;
  stationsUsed: number;
  stationsMissing: string[];
  withoutCoord: number;
  locatedNow: number;
  withinStraight: number;
  droppedByWalkTime: number;
  droppedShared: number;
  droppedWanted: number;
  walkUnknown: number;
  matched: number;
  pendingLocation: number;
  agencyListings: number;
  individualListings: number;
  walkApiCalls: number;
  amapKeyMissing: boolean;
}

export interface MatchResult {
  success: boolean;
  message?: string;
  profile: {
    name: string;
    city: string;
    stations: string[];
    price_min: number | null;
    price_max: number | null;
    layouts: string[];
    max_straight_m: number;
    max_walk_minutes: number;
  };
  stats: MatchStats;
  total: number;
  data: MatchedHouse[];
  pendingLocation: MatchedHouse[];
  report: string;
}

export interface ProfileSummary {
  name: string;
  profile: {
    name: string;
    city: string;
    stations: string[];
    price_min: number | null;
    price_max: number | null;
    layouts: string[];
    max_straight_m: number;
    max_walk_minutes: number;
  };
}

/** 匹配接口返回结构（后端直接返回对象，没有包 code/data 信封） */
export class MatchService extends BaseService {
  async listProfiles(): Promise<ProfileSummary[]> {
    const res = await this.get<any>("/match/profiles");
    return res?.data || [];
  }

  async run(profileName: string, walk = true): Promise<MatchResult> {
    // 后端 /match 直接返回结果对象（含 code/数据/统计），不是标准信封，
    // 所以这里按 any 接收后断言，避免 BaseService 的 ApiResponse 泛型不匹配。
    const res = await this.get<any>("/match", { profile: profileName, walk });
    return res as unknown as MatchResult;
  }

  /** 取一批房源的图片（匹配接口不返回图片，这里补上） */
  async fetchPictures(ids: string[]): Promise<Record<string, string>> {
    if (!ids.length) return {};
    const map: Record<string, string> = {};
    // 分批查询，避免 URL 过长
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
        // 图片是锦上添花，取不到不影响主流程
      }
    }
    return map;
  }
}

export const matchService = new MatchService();
