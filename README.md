# HouseSearch Local v1

本地租房信息聚合、搜索、筛选系统。基于开源项目 [liguobao/HouseSearch](https://github.com/liguobao/HouseSearch) 改造，专为个人本地使用设计。

## 项目定位

**不是**完美的开源产品，**而是**真正能用来找房的本地工具。

核心目标：从多个租房平台采集近期真实房源，汇总到本地数据库，提供统一的搜索、筛选、排序和地图展示能力。

## 技术架构

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 前端 | React 18 + TypeScript + Vite + Ant Design | 复用原项目 newUI |
| 后端 | Python + FastAPI | 轻量、现代、易维护 |
| 数据库 | SQLite | 单文件、零配置、足够第一版使用 |
| 爬虫 | Python + httpx + BeautifulSoup | 各平台独立 Adapter |

## 当前验证状态（2026-10-04 实测）

| 平台 | 状态 | 需要登录 | 实测结果 |
|------|------|---------|---------|
| **豆瓣租房** | ✅ **已跑通** | 否 | 单页实测采集 **59 条**北京真实房源，标题/作者/发布时间/租金解析正常 |
| 贝壳找房 | ⚠️ 框架就绪 | 是 | 健康检查可访问（HTTP 200）；未配 Cookie 时返回空，待配 Cookie 验证 |
| 闲鱼 | ⚠️ 框架就绪 | 是 | 健康检查可访问；`search()` 为占位实现，需按当前页面结构补全解析 |
| 小红书 | ⚠️ 框架就绪 | 是 | 健康检查可访问；搜索 API 需真实 Cookie + 签名参数，待验证 |

后端全部 API 已实测通过（见「API 一览」）。

## 快速开始

### 1. 环境准备

需要 Python 3.10+ 和 Node.js 18+

```bash
cd HouseSearch-local-v1

# 建议使用独立虚拟环境
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# 前端依赖
cd frontend && npm install && cd ..
```

### 2. 配置

```bash
cp .env.example .env                # 后端配置（Cookie / 通勤目的地）
cp frontend/.env.example frontend/.env   # 前端配置（高德 Key）
```

- `.env`：高德 Web Key、各平台 Cookie、通勤目的地
- `frontend/.env`：`VITE_AMAP_KEY`（高德 JS API Key，地图页必需，不填则回退到内置的旧 Key，很可能因域名限制而无法加载）

### 3. 启动

```bash
# 后端（http://localhost:8000，接口文档 /docs）
python start.py backend

# 前端（新终端，http://localhost:5173）
python start.py frontend
```

> ⚠️ **必须在项目根目录运行**。所有后端模块都使用 `backend.xxx` 绝对导入，
> 因此 `cd backend && uvicorn main:app` 会直接报 `ModuleNotFoundError`。
> 正确写法：`uvicorn backend.main:app`（工作目录为项目根）。

### 4. 采集数据

```bash
# 检查各平台健康状态
python crawl.py health

# 采集豆瓣租房（无需登录，当前唯一可直接使用的数据源）
python crawl.py douban --city 北京 --pages 3
python crawl.py douban --city 上海 --pages 3
python crawl.py douban --city 深圳 --pages 3

# 需要登录 Cookie 的平台
python crawl.py beike --city 深圳
python crawl.py xiaohongshu --city 上海
```

豆瓣支持的城市：北京、上海、深圳、广州、杭州、成都。

### 5. 只想先看界面？（可选）

没有真实数据时，可写入带 `[示例]` 前缀的演示数据来验证前后端链路：

```bash
python start.py seed            # 写入 15 条演示房源（幂等）
python seed_demo.py --clear     # 用完清理，避免与真实数据混淆
```

### 6. 打开浏览器

访问 http://localhost:5173

### 7. 自检（可选但推荐）

```bash
# 逐项校验接口契约与前端预期是否一致（21 项检查，退出码 0 即全部通过）
python verify_api.py
```

> 该脚本使用 `trust_env=False` 直连 localhost；若手动用 curl 验证中文参数，
> 请使用 `-G --data-urlencode`，把中文直接写进 URL 会被 uvicorn 判为非法请求。

### 单端口模式（可选）

执行过 `npm run build` 后，后端会自动托管前端产物，
此时只需启动后端、直接访问 http://localhost:8000 即可（深链接已做 index.html 回退）。

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/v3/houses` | 房源搜索（分页/筛选/排序） |
| POST | `/api/v2/houses` | 地图批量取点（前端地图页使用） |
| GET | `/api/v2/houses/{id}` | 房源详情 |
| PUT | `/api/v2/houses-lat-lng` | 批量回填经纬度 |
| POST | `/api/v3/houses/{id}/report` | 举报房源（本地仅登记） |
| DELETE | `/api/v3/houses/{id}` | 软删除房源（status=1） |
| GET | `/api/v2/cities` | 城市列表 + 各城市数据源 |
| GET | `/api/v2/cities/{city}/districts` | 城市行政区列表 |
| GET | `/api/houses/{id}/risk` | 风险评分明细 |
| GET | `/api/houses/sources/count` | 各数据源房源数 |
| GET | `/api/sources` | 数据源状态（只读） |
| POST | `/api/sources/{source}/enable|disable` | 启停数据源 |
| POST | `/api/crawl` | 手动触发采集（记录日志） |
| GET | `/api/crawl/logs` | 采集日志 |
| GET | `/api/config` | 前端公开配置 |

### 接口契约说明（重要）

原前端 `src/services/base.ts` 对 axios 响应会**再取一次 `.data`**，因此：

- `/v3/houses`、`/v2/cities` 等必须返回 `{"code": 0, "data": [...]}`
- `/v3/houses` 同时兼容 `pageSize/fromPrice/toPrice/intervalDay/sortBy` 与
  `page_size/from_price/...` 两种参数写法
- 分页从 `page=0` 开始，`pageSize` 上限 500

```bash
# 实测示例
curl 'http://localhost:8000/api/v3/houses?city=北京&pageSize=5'
curl -G 'http://localhost:8000/api/v3/houses' --data-urlencode 'keyword=合租' \
     --data-urlencode 'keyword_exclude=中介' -d 'sortBy=price' -d 'sortOrder=asc'
curl 'http://localhost:8000/api/v2/cities'
```

> curl 传中文参数请用 `-G --data-urlencode`，直接把中文写进 URL 会被 uvicorn 判为非法请求。

## 项目结构

```
HouseSearch-local-v1/
├── backend/
│   ├── main.py            # FastAPI 入口（lifespan 初始化数据库）
│   ├── config.py          # 配置（路径全部以项目根为基准）
│   ├── constants.py       # 数据源元信息 / 默认城市
│   ├── models.py          # SQLAlchemy 模型（houses / crawl_logs / source_configs）
│   ├── database.py        # SQLite 连接（相对路径自动解析到项目根）
│   ├── schemas.py         # Pydantic 模型
│   ├── routers/
│   │   ├── houses.py      # 房源搜索/详情/风险/上报/删除
│   │   ├── cities.py      # 城市与行政区
│   │   ├── sources.py     # 数据源状态与采集日志
│   │   └── config.py      # 公开配置
│   ├── services/
│   │   ├── search.py      # 搜索/筛选/排序
│   │   ├── risk.py        # 中介/广告/异常三维评分
│   │   └── dedup.py       # 链接/标题+价格+城市/小区+相似标题去重
│   └── crawlers/
│       ├── base.py        # 爬虫基类 + 租金提取工具
│       ├── manager.py     # 采集编排（标准化/去重/评分/入库）
│       ├── douban.py      # 豆瓣小组（✅ 已跑通）
│       ├── beike.py       # 贝壳找房
│       ├── xianyu.py      # 闲鱼
│       └── xiaohongshu.py # 小红书
├── frontend/              # React 前端（已适配本地 API）
│   └── .env.example       # VITE_AMAP_KEY 模板
├── data/houses.db         # SQLite 单文件（git 忽略）
├── seed_demo.py           # 演示数据（幂等写入/清理）
├── verify_api.py          # 后端 API 契约自检（21 项）
├── start.py               # 启动脚本（backend/frontend/setup/seed）
├── crawl.py               # 爬虫 CLI
└── requirements.txt
```

## 如何添加新的数据源

1. 在 `backend/crawlers/` 下创建爬虫文件，继承 `BaseCrawler`
2. 实现 `search()`（`fetch_detail()` 可选，基类已提供默认实现）
3. 在 `backend/crawlers/manager.py` 的 `CRAWLERS` 中注册
4. 在 `backend/constants.py` 的 `SOURCE_CONFIGS` 中添加元信息

## 已知限制

1. **爬虫依赖平台页面结构**：各平台改版会导致爬虫失效；豆瓣已按当前 4 列表结构（标题/作者/回应数/时间）适配
2. **租金解析保守**：只认带「元/月/月租/租金/k」语境的数字（裸数字兜底且排除年份），因此抓到的房源里约 1/3 拿不到价格，显示为未知，好过把手机号当租金
3. **需要登录的平台**：贝壳、闲鱼、小红书需有效 Cookie；闲鱼的列表解析目前是占位实现
4. **坐标缺失**：豆瓣小组列表没有经纬度，地图页只能展示已有坐标的房源（贝壳详情页可解析坐标）
5. **SQLite 并发**：适合个人单机使用，不适合高并发写入
6. **无账号体系**：本地版未实现 `/v1/user/*` 登录注册，前端登录页不可用（不影响搜索/筛选/地图）

## 数据来源与致谢

本项目基于开源项目 [liguobao/HouseSearch](https://github.com/liguobao/HouseSearch) 改造，保留原项目的前端 UI 设计。

原项目技术栈：.NET Core + Vue.js + MySQL + Redis + MongoDB + Elasticsearch

## License

与原项目保持一致：LGPL v3
