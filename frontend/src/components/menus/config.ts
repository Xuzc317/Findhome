/**
 * 侧边导航。图标用 emoji，不再依赖上游项目的 png 图标资源。
 *
 * 顺序即使用顺序：先采集 → 再看收藏 → 然后才是查库与配置。
 */
export interface MenuItem {
  title: string;
  key: string;
  path: string;
  icon: string;
}

export const MENUS_LIST: MenuItem[] = [
  { title: "实时采集", key: "collect", path: "/", icon: "🔍" },
  { title: "收藏与记录", key: "favorites", path: "/favorites", icon: "⭐" },
  { title: "快速查询", key: "search", path: "/search", icon: "⚡" },
  { title: "保存的搜索", key: "saved", path: "/saved", icon: "💾" },
  { title: "配置", key: "settings", path: "/settings", icon: "⚙️" },
];
