/**
 * 服务聚合出口。
 *
 * 已移除上游的 CitiesService / UserService（本地工具无城市弹窗与登录体系）。
 */
import HousesService from "./houses";

export const housesService = new HousesService();
