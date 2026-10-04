

interface GetHousesParams {
  city?: string;
  source?: string;
  fromPrice?: string;
  toPrice?: string;
  district?: string;
  keyword?: string;
  keywordExclude?: string;
  rentType?: number;
  /** 出租类型多选，逗号分隔："3"=整租，"1"=合租，"3,4"=整租+公寓；空=不限 */
  rentTypes?: string;
  /** 房型档位多选：studio,1b1l,2b1l,3b1l,4b+ */
  layouts?: string;
  intervalDay?: number;
  maxAgentScore?: number;
  minConfidenceScore?: number;
  /** 地铁站 ID */
  stationId?: string;
  /** 步行距离上限（米） */
  walkMaxM?: number;
  sortBy?: string;
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
  /** 平台时间展示文本：发布时间，或“日期(维护)”，缺失则为空 */
  timeText?: string;
  lastActiveDate?: string;
  rentType: number;
  reportNum?: string;
  source: string;
  status: number;
  tags?: string;
  timestamp: number;
  title: string;
  updateTime: string;

  // ---- 房型（由平台原文解析，解析不出为 null）----
  bedrooms?: number | null;
  livingRooms?: number | null;
  layoutKey?: string | null;
  layoutLabel?: string | null;
  layoutConfidence?: number | null;
  layoutEvidence?: string | null;

  // ---- 位置溯源 ----
  geoSource?: string | null;
  geoPrecision?: string | null;
  geoConfidence?: number | null;
  geoNote?: string | null;
  hasCoord?: boolean;

  // ---- 到所选地铁站的真实步行距离 ----
  walkMeters?: number | null;
  walkMinutes?: number | null;
  straightMeters?: number | null;
  walkStatus?: string | null;
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
  /** 平台时间展示文本：发布时间，或“日期(维护)”，缺失则为空 */
  timeText?: string;
  lastActiveDate?: string;
  rentType: number;
  reportNum?: string;
  source: string;
  tags?: string;
  text: string;
  title: string;
  collected?: boolean;
}
