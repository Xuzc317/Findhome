import BaseService from "./base";

export interface TaskLog {
  taskId: string;
  status: "pending" | "running" | "done" | "failed";
  stage: string;
  stageText: string;
  progress: number;
  logs: string[];
  detail: {
    sources?: { usable: string[]; missingLogin: string[]; amapAvailable: boolean };
    collect?: { cards: number; new: number; updated: number; bySource: Record<string, number> };
    locate?: { total: number; located: number; failed: number };
  };
  error: string | null;
  elapsed: number;
  result?: any;
}

export interface CollectCriteria {
  city: string;
  stations: string[];
  line_names: string[];
  sources: string[];
  price_min: number | null;
  price_max: number | null;
  layouts: string[];
  rent_types: number[];
  exclude_shared: boolean;
  max_straight_m: number;
  max_walk_minutes: number;
  require_elevator: boolean;
  require_precise_location: boolean;
  avoid_old_small: boolean;
  listing_kinds: string[];
  poster_types: string[];
  exclude_agency: boolean;
  sort_by: string;
  compute_walk: boolean;
  max_stations: number;
}

export const DEFAULT_COLLECT: CollectCriteria = {
  city: "",
  stations: [],
  line_names: [],
  sources: ["xianyu", "xiaohongshu", "douban"],
  price_min: 1200,
  price_max: 2500,
  layouts: ["studio", "1b1l", "2b1l"],
  rent_types: [3, 4],
  exclude_shared: true,
  max_straight_m: 1000,
  max_walk_minutes: 20,
  require_elevator: false,
  require_precise_location: true,
  avoid_old_small: true,
  listing_kinds: [],
  poster_types: [],
  exclude_agency: false,
  sort_by: "walk",
  compute_walk: true,
  max_stations: 6,
};

export class TaskService extends BaseService {
  /** 启动一次实时采集 + 筛选任务 */
  async startCollect(criteria: CollectCriteria): Promise<{ taskId: string }> {
    const res = await this.post<any>(
      "/tasks/collect",
      criteria as unknown as Record<string, unknown>
    );
    return res?.data;
  }

  /** 查询任务进度（完成后同一响应里带 result） */
  async getTask(taskId: string, includeResult = true): Promise<TaskLog> {
    const res = await this.get<any>(`/tasks/${taskId}`, {
      include_result: includeResult,
    });
    return res?.data;
  }

  async cancelTask(taskId: string): Promise<void> {
    await this.post<any>(`/tasks/${taskId}/cancel`, {});
  }
}

export const taskService = new TaskService();
