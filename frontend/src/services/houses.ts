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

  async getHouses(props: GetHousesParams): Promise<HouseListItem[]> {
    const params = { page: props.page, pageSize: props.pageSize || 20 } as any;
    if (props.city) params.city = props.city;
    if (props.source && props.source !== "all") params.source = props.source;
    if (!!props.fromPrice) params.fromPrice = props.fromPrice;
    if (!!props.toPrice) params.toPrice = props.toPrice;
    if (props.district && props.district != "全部") {
      params.district = props.district;
    }
    if (!!props.keyword) params.keyword = props.keyword;
    if (
      props.rentType !== undefined && props.rentType !== null &&
      props.rentType != -1
    ) {
      params.rentType = props.rentType;
    }
    if (props.intervalDay && props.intervalDay != -1) {
      params.intervalDay = props.intervalDay;
    }

    return this.get<HouseListItem[]>(`/v3/houses`, params).then((res) => {
      const list = res.data;
      return list.map((item: HouseListItem) => this.normalizeHouse(item));
    });
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
