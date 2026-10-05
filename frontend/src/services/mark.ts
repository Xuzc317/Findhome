import BaseService from "./base";

export interface HouseMark {
  houseId: string;
  favorite: boolean;
  contacted: boolean;
  hidden: boolean;
  note: string;
  updatedAt?: string;
  house?: {
    id: string;
    title: string;
    price: number | null;
    source: string;
    sourceUrl: string;
    city: string | null;
    district: string | null;
    community: string | null;
    layoutKey: string | null;
    pictures: string[];
  };
}

export const EMPTY_MARK: Omit<HouseMark, "houseId"> = {
  favorite: false,
  contacted: false,
  hidden: false,
  note: "",
};

export class MarkService extends BaseService {
  async update(
    houseId: string,
    patch: Partial<Omit<HouseMark, "houseId" | "house">>
  ): Promise<HouseMark | null> {
    const res = await this.post<any>("/marks", { houseId, ...patch });
    return res?.data ?? null;
  }

  async batch(houseIds: string[]): Promise<Record<string, HouseMark>> {
    if (!houseIds.length) return {};
    const res = await this.post<any>("/marks/batch", { houseIds });
    return res?.data || {};
  }

  async list(filter: "all" | "favorite" | "contacted" | "hidden" | "noted") {
    const res = (await this.get<any>("/marks", {
      filter,
      with_house: true,
    })) as any;
    return {
      items: (res?.data || []) as HouseMark[],
      total: res?.total || (res?.data || []).length,
    };
  }

  async remove(houseId: string): Promise<void> {
    await this.delete<any>(`/marks/${houseId}`);
  }
}

export const markService = new MarkService();
