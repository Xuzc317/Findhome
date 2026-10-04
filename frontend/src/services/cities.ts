import BaseService from "./base";

export default class CitiesService extends BaseService {
  async getCities(): Promise<CityEntity[]> {
    return this.get<CityEntity[]>(`/v2/cities?fields=id,city,sources`).then((
      res,
    ) => res.data);
  }

  async getCityDistricts(city: string): Promise<string[]> {
    return this.get<string[]>(`/v2/cities/${city}/districts`).then((res) =>
      res.data
    );
  }
}
