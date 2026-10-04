import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./index.css";
import { ConfigProvider } from "antd";

import HomePage from "./pages/home";
import Login from "./pages/user/login/index";
import FindPassword from "./pages/user/find-password/index";
import UserInfo from "./pages/user/info/index";
import HousesList from "./pages/houses-list/index";
import { CitiesProvider } from "./hook/cities";
import HouseDetail from "./pages/house-detail";
import MobileModal from "./components/mobile-modal/index.";
import MapPage from "./pages/map";

const router = createBrowserRouter([
  {
    path: "/",
    element: <HomePage />,
  },
  {
    path: "/houses-list",
    id: "houses-list",
    element: <HousesList />,
  },
  {
    path: "/map",
    id: "map",
    element: <MapPage />,
  },
  {
    path: "/houses/:id",
    element: <HouseDetail />,
  },
  {
    path: "/user/login",
    element: <Login />,
  },
  {
    path: "/user/info",
    id: "user-info",
    element: <UserInfo />,
  },
  {
    path: "/user/find-password",
    element: <FindPassword />,
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <CitiesProvider>
      <ConfigProvider
        theme={{
          token: {
            colorPrimary: "#00a3ca",
          },
        }}
      >
        <RouterProvider router={router} />
        <MobileModal />
      </ConfigProvider>
    </CitiesProvider>
  </StrictMode>,
);
