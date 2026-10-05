export const API_BASE_URL = "http://localhost:8000/api";

export const StorageKey = {
  USER_TOKEN: "USER_TOKEN",
  SEARCH_HISTORY: "SEARCH_HISTORY",
  USER_INFO: "USER_INFO",
};

export const SITE_NAME = "House2048";

export const HomeFilterOptions = {
  types: [
    { value: -1, label: "全部" },
    { value: 0, label: "未知" },
    { value: 1, label: "合租" },
    { value: 2, label: "单间" },
    { value: 3, label: "整租" },
    { value: 4, label: "公寓" },
  ],
  times: [
    { value: -1, label: "不限制" },
    { value: 1, label: "1天内" },
    { value: 3, label: "3天内" },
    { value: 7, label: "7天内" },
    { value: 30, label: "30天内" },
  ],
};

export const HouseRentTypeMap = HomeFilterOptions.types.reduce((acc, cur) => {
  acc[cur.value] = cur.label;
  return acc;
}, {} as Record<number, string>);
