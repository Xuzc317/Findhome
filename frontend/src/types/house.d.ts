

interface GetHousesParams {
  city?: string;
  source?: string;
  fromPrice?: string;
  toPrice?: string;
  district?: string;
  keyword?: string;
  rentType?: number;
  intervalDay?: number;
  page: number;
  pageSize: number;
}

interface GetMapHousesParams {
  city: string;
  source?: string;
  keyword?: string;
  rentType?: number;
  intervalDay?: number;
  page?: number;
  size?: number;
}

interface HouseListItem {
  city: string;
  createTime: string;
  displayRentType?: string;
  displaySource: string;
  district: string;
  icon?: string;
  id: string;
  labels?: string;
  latitude?: string | number;
  location: string;
  longitude?: string | number;
  onlineURL: string;
  picURLs?: string;
  pictures: string[];
  price: number;
  pubTime: string;
  publishDate: string;
  rentType: number;
  reportNum?: string;
  source: string;
  status: number;
  tags?: string;
  timestamp: number;
  title: string;
  updateTime: string;
}

interface HousesLatLng {
  id: string;
  city: string;
  longitude: string;
  latitude: string;
  source: string;
  onlineURL: string;
}

interface HouseDetail {
  city: string;
  displayRentType: string;
  displaySource: string;
  district?: string;
  icon: string;
  id: string;
  labels?: string;
  latitude?: string | number;
  location: string;
  longitude?: string | number;
  onlineURL: string;
  picURLs?: string;
  pictures: string[];
  price: number;
  pubTime: string;
  publishDate: string;
  rentType: number;
  reportNum?: string;
  source: string;
  tags?: string;
  text: string;
  title: string;
  collected?: boolean;
}
