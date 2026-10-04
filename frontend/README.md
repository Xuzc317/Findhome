# House-Map.newUI

地图搜租房新版前端，基于 React 18、TypeScript、Vite 和 Ant Design。当前目录是同步后的主要前端实现，旧版 Vue 前端仍保留在 `House-Map.UI`。

## 功能范围

- 首页：项目介绍、城市入口、数据源入口和反馈链接。
- 房源列表：瀑布流展示房源，支持城市、来源、租房类型和关键字筛选，滚动到底自动加载更多。
- 地图找房：高德地图点位展示、房源弹窗、收藏、公交/地铁路线规划、通勤可达范围。
- 房源详情：图片轮播、价格、来源、城市、发布时间、正文和来源链接。
- 用户功能：登录、注册、找回密码、个人信息、收藏房源。

## 技术栈

- React 18
- React Router 6
- TypeScript 5
- Vite 5
- Ant Design 5
- Axios
- Tailwind CSS / CSS Modules / SCSS Modules
- React Helmet
- React Masonry CSS

## 本地开发

建议使用 Node.js 18 或更新版本。

```shell
npm install
npm run dev
```

开发服务默认由 Vite 启动，`dev` 脚本会监听 `0.0.0.0`，便于局域网或容器环境访问。

## 常用脚本

```shell
npm run start     # 启动 Vite 开发服务
npm run dev       # 以 0.0.0.0 启动 Vite 开发服务
npm run build     # TypeScript 构建检查并生成生产包
npm run lint      # ESLint 检查
npm run preview   # 本地预览生产包
```

## 接口配置

接口基础地址在 `src/constant.ts`：

```ts
export const API_BASE_URL = "https://web.house2048.cn/api";
```

本地联调后端时，将它改为本地 API 地址即可。请求封装在 `src/services/base.ts`，登录态 token 会从浏览器存储读取并写入请求头 `token`。

## 目录说明

```text
src/
  components/       通用组件，包含头部、布局、城市选择、房源筛选、菜单和移动端弹窗
  hook/             城市数据、用户信息等 React hooks
  pages/            页面路由：首页、列表、地图、详情、登录、找回密码、个人信息
  services/         API 请求封装
  types/            房源、城市、接口和高德地图类型声明
  utils/            浏览器存储、用户 token 等工具函数
public/
  images/           当前前端使用的图片资源
  house-map/        历史静态站点资源，构建时会随 Vite public 目录原样复制
```

## 路由

| 路由 | 页面 |
| --- | --- |
| `/` | 首页 |
| `/houses-list` | 房源列表 |
| `/map` | 地图找房 |
| `/houses/:id` | 房源详情 |
| `/user/login` | 登录/注册 |
| `/user/info` | 个人信息 |
| `/user/find-password` | 找回密码 |

## 构建

```shell
npm run build
```

构建产物输出到 `dist`，可通过 `npm run preview` 本地预览。
