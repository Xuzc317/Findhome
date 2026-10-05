import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import "./index.css";
import { ConfigProvider } from "antd";

import CollectWizard from "./pages/collect/index";
import FavoritesPage from "./pages/favorites/index";
import SearchPage from "./pages/search/index";
import MatchPage from "./pages/match/index";
import SettingsPage from "./pages/settings/index";
import HouseDetail from "./pages/house-detail";

const router = createBrowserRouter([
  // 主入口：实时采集向导（城市 → 授权 → 条件 → 结果）
  {
    path: "/",
    id: "collect",
    element: <CollectWizard />,
  },
  {
    path: "/collect",
    id: "collect-alias",
    element: <CollectWizard />,
  },
  {
    path: "/favorites",
    id: "favorites",
    element: <FavoritesPage />,
  },
  {
    path: "/search",
    id: "search",
    element: <SearchPage />,
  },
  {
    path: "/saved",
    id: "saved",
    element: <MatchPage />,
  },
  {
    path: "/settings",
    id: "settings",
    element: <SettingsPage />,
  },
  {
    path: "/houses/:id",
    element: <HouseDetail />,
  },
  // 旧路径兜底：上游项目的入口一律指回主入口，避免收藏的旧链接 404
  {
    path: "*",
    element: <Navigate to="/" replace />,
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#00a3ca",
        },
      }}
    >
      <RouterProvider router={router} />
    </ConfigProvider>
  </StrictMode>,
);
