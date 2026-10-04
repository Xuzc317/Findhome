import BaseService from "./base";

export default class HousesService extends BaseService {
  private normalizeHouse(item: HouseListItem): HouseListItem {
    if (item.pictures?.length) return item;
    try {
      if (item.picURLs) item.pictures = JSON.parse(item.picURLs);
      else item.pictures = [""];
    } catch (error) {
      item.pictures = [""];
    }
    return item;
  }

  /**
   * 搜索房源（带总数），用于分页与"共 N 套"展示
   */
  async searchHouses(props: GetHousesParams): Promise<{
    list: HouseListItem[];
    total: number;
    hasMore: boolean;
  }> {
    const params = this.buildParams(props);
    return this.get<any>(`/v3/houses`, params).then((res: any) => ({
      list: (res?.data || []).map((item: HouseListItem) =>
        this.normalizeHouse(item)
      ),
      total: res?.total ?? 0,
      hasMore: res?.hasMore ?? false,
    }));
  }

  async getHouses(props: GetHousesParams): Promise<HouseListItem[]> {
    const result = await this.searchHouses(props);
    return result.list;
  }

  private buildParams(props: GetHousesParams) {
    const params = { page: props.page, pageSize: props.pageSize || 20 } as any;
    if (props.city) params.city = props.city;
    if (props.source && props.source !== "all") params.source = props.source;
    if (!!props.fromPrice) params.fromPrice = props.fromPrice;
    if (!!props.toPrice) params.toPrice = props.toPrice;
    if (props.district && props.district != "全部") {
      params.district = props.district;
    }
    if (!!props.keyword) params.keyword = props.keyword;
    if (props.keywordExclude) params.keywordExclude = props.keywordExclude;
    if (props.maxAgentScore) params.maxAgentScore = props.maxAgentScore;
    if (props.minConfidenceScore) {
      params.minConfidenceScore = props.minConfidenceScore;
    }
    // 出租类型多选（"3"=只看整租；空字符串=不限）
    if (props.rentTypes !== undefined && props.rentTypes !== "") {
      params.rentTypes = props.rentTypes;
    }
    // 房型档位多选
    if (props.layouts) params.layouts = props.layouts;
    // 地铁站 + 步行距离
    if (props.stationId) params.stationId = props.stationId;
    if (props.walkMaxM) params.walkMaxM = props.walkMaxM;
    if (
      props.rentType !== undefined && props.rentType !== null &&
      props.rentType != -1
    ) {
      params.rentType = props.rentType;
    }
    if (props.intervalDay && props.intervalDay != -1) {
      params.intervalDay = props.intervalDay;
    }
    if (props.sortBy) params.sortBy = props.sortBy;

    return params;
  }

  async getMapHouses(props: GetMapHousesParams): Promise<HouseListItem[]> {
    const params: Record<string, unknown> = {
      city: props.city,
      page: props.page || 0,
      size: props.size || 1200,
      intervalDay: props.intervalDay ?? 30,
    };
    if (props.source && props.source !== "all") params.source = props.source;
    if (props.keyword) params.keyword = props.keyword;
    if (
      props.rentType !== undefined && props.rentType !== null &&
      props.rentType !== -1
    ) {
      params.rentType = props.rentType;
    }

    return this.post<HouseListItem[]>(`/v2/houses`, params).then((res) => {
      return res.data.map((item: HouseListItem) => this.normalizeHouse(item));
    });
  }

  async getHouseDetail(id: string): Promise<HouseDetail> {
    return this.get<HouseDetail>(`/v2/houses/${id}`).then((res) => {
      res.data.collected = (res as any).collected;
      return res.data;
    });
  }

  async reportHouse(id: string, city: string, source: string) {
    return this.post(`/v3/houses/${id}/report?city=${city}&source=${source}`)
      .then((res) => res.data);
  }

  async deleteHouse(id: string, city: string, source: string) {
    return this.delete(`/v3/houses/${id}?city=${city}&source=${source}`).then(
      (res) => res.data,
    );
  }

  async updateHousesLatLng(list: HousesLatLng[]) {
    return this.put(`/v2/houses-lat-lng`, list).then((res) => res.data);
  }

  async getCollections(userId: number): Promise<HouseListItem[]> {
    return this.get<HouseListItem[]>(`/v2/users/${userId}/collections/`).then((
      res,
    ) => res.data.map((item: HouseListItem) => this.normalizeHouse(item)));
  }

  async addCollection(userId: number, houseId: string) {
    return this.post(`/v2/users/${userId}/collections/`, { houseID: houseId })
      .then((res) => res.data);
  }
}
