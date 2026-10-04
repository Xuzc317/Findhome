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

> 详细证据、失败原因与边界说明见 **[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)**。
> 判断标准是"真实请求 + 真实解析"，不是 HTTP 200。

| 平台 | 状态 | 需要登录 | 实测结果 |
|------|------|---------|---------|
| **豆瓣租房** | ✅ 可用（有风控） | 否 | 单页实采 **59 条**北京房源并入库；触发风控时如实上报 `blocked`，不静默返回 0 |
| **贝壳找房** | ✅ 可用（有验证码风控） | 否（列表页） | 深圳列表页实采 **14 条**并入库（标题/价格/行政区/商圈/小区/标签/房源编号）；详情页验证码保护，**不抓取** |
| 闲鱼 | 🔐 需登录 | 是 | 未登录返回 `RGV587_ERROR` 并跳转 passport 登录页；旧接口已下线 |
| 小红书 | 🔐 需登录 | 是 | 搜索接口返回 `code=-101 无登录信息`；页面为客户端渲染且需签名头 |

登录类平台**不要求密码**、不做验证码/签名逆向：只使用用户本人浏览器登录后的 Cookie（写入 `.env`，已被 git 忽略）。

## 筛选能力（前端 ↔ 后端闭环）

| 维度 | 前端 | API 参数 |
|------|------|---------|
| 城市 / 数据源 | 筛选栏 | `city` / `source` |
| 出租类型 | 筛选栏 | `rentType` |
| 价格区间 | 筛选栏（最低-最高） | `fromPrice` / `toPrice` |
| 发布时间 | 筛选栏（1/3/7/30 天） | `intervalDay` |
| 关键词包含 | 顶部搜索框 | `keyword`（空格分隔多词，AND） |
| 关键词排除 | 筛选栏 | `keywordExclude`（空格分隔多词） |
| 风险 | 筛选栏（低中介嫌疑 / 可信度≥70） | `maxAgentScore` / `minConfidenceScore` |
| 隐藏重复 | 默认开启 | `hide_duplicates` |

**时间语义**：`publish_time` 是平台发布时间；贝壳列表页只展示"X天前维护"，
因此单独存入 `last_active_time`，API 返回 `timeText` 明确区分（如 `2026-10-03(维护)`）。
两者都没有时，前端显示"采集 + 日期"，不把采集时间冒充发布时间。
时间筛选使用 `COALESCE(publish_time, last_active_time)`，两者皆空的房源不参与时间筛选。

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
# 真实探针：确认每个平台当前的真实状态与失败原因（被拦截 / 需登录 / 不可用）
python crawl.py health

# 豆瓣（无需登录，但平台有频率风控；触发后需等待冷却或配置 DOUBAN_COOKIE）
python crawl.py douban --city 北京 --pages 1
python crawl.py douban --city 北京 --pages 1 --with-detail 5   # 额外抓前 5 条正文/图片
python crawl.py douban --city 上海 --group <小组ID>            # 覆盖内置小组映射

# 贝壳（列表页公开，无需 Cookie；连续快速请求会触发验证码）
python crawl.py beike --city 深圳              # 默认整租
python crawl.py beike --city 深圳 --rent-type 1  # 1 合租 / 3 整租

# 需要登录 Cookie 的平台（先在 .env 配置，见 docs/DATA_SOURCES.md）
python crawl.py xianyu --city 上海
python crawl.py xiaohongshu --city 上海
```

- 豆瓣支持城市：北京（已验证）、上海、深圳、广州、杭州、成都（待验证小组 ID）
- 贝壳支持城市：北京、上海、深圳、广州、杭州、成都、南京、武汉、西安、重庆、苏州、天津、长沙
- **风控提示**：触发验证码/中间页时应停止请求等待冷却，不要加大频率；
  各 Adapter 已内置最小请求间隔（豆瓣 5s、贝壳 8s）

### 5. 验收与自检

```bash
# 离线解析测试（71 项，无需联网、不触发平台风控）
python tests/test_parsers.py

# 验收记录：各来源最近的房源（标题/价格/发布时间/source_url/抓取时间/风险分）
python verify_sources.py
python verify_sources.py --write docs/acceptance.md

# 线上一致性校验：与平台当前页面逐条比对（贝壳按房源编号比对标题+价格）
python verify_consistency.py --limit 5

# 接口契约 + 筛选闭环自检（31 项，退出码 0 即全部通过）
python verify_api.py

# 前端端到端冒烟（可选，需 playwright，验证列表渲染 + 原始链接可打开）
pip install playwright && python -m playwright install chromium
python tests/test_ui_smoke.py --city 深圳
```

少于 5 条真实房源的来源会被标记为未达标；演示数据（`demo.local`）会被标记为不可打开且不计入。
平台风控期间一致性校验会如实报告"无法比对"，不会假装通过。

### 6. 只想先看界面？（可选）

没有真实数据时，可写入带 `[示例]` 前缀的演示数据来验证前后端链路：

```bash
python start.py seed            # 写入 15 条演示房源（幂等）
python seed_demo.py --clear     # 用完清理，避免与真实数据混淆
```

> 演示数据的链接是 `demo.local`，**不可打开**，因此不计入验收。

### 7. 打开浏览器

访问 http://localhost:5173

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
| GET | `/api/sources/health` | 数据源能力声明；`?probe=true` 执行真实网络探针（含失败原因） |
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
│       ├── base.py        # 爬虫基类 + 状态机 + 租金/相对时间/拦截检测工具
│       ├── manager.py     # 采集编排（标准化/去重/评分/入库，含真实健康探针）
│       ├── douban.py      # 豆瓣小组（✅ 列表可用，有风控）
│       ├── beike.py       # 贝壳找房（✅ 列表可用，详情验证码不抓取）
│       ├── xianyu.py      # 闲鱼（🔐 需登录 Cookie）
│       └── xiaohongshu.py # 小红书（🔐 需登录 Cookie）
├── frontend/              # React 前端（已适配本地 API）
│   └── .env.example       # VITE_AMAP_KEY 模板
├── docs/
│   ├── DATA_SOURCES.md    # 各数据源验证证据、失败原因、边界说明
│   └── acceptance.md      # 验收记录（由 verify_sources.py 生成）
├── data/houses.db         # SQLite 单文件（git 忽略）
├── seed_demo.py           # 演示数据（幂等写入/清理）
├── verify_api.py          # 接口契约 + 筛选闭环自检（31 项）
├── verify_sources.py      # 各来源真实房源验收记录导出
├── verify_consistency.py  # 与平台当前页面的一致性校验
├── tests/test_parsers.py  # 解析器离线测试（71 项，无需联网）
├── tests/test_ui_smoke.py # 前端端到端冒烟（可选，需 playwright）
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

1. **平台风控是主要不确定性**：豆瓣会返回"请点击下方按钮继续浏览"中间页或 429，
   贝壳会返回验证码页。触发后需等待冷却（实测冷却后单次请求可成功），
   本项目不做验证码识别、签名逆向等绕过手段。
2. **租金解析保守**：只认带「元/月/月租/租金/k」语境的数字（裸数字兜底且排除年份），
   豆瓣标题里约 1/3 拿不到价格 → 显示为未知，好过把手机号当租金。
3. **时间字段不猜测**：贝壳列表页只有"X天前维护"，因此 `publish_time` 留空、
   `last_active_time` 承载该值，前端标注"(维护)"。
4. **贝壳详情页不抓取**（验证码保护），因此贝壳房源**没有经纬度**，
   地图页不展示它们；**不伪造坐标**。
5. **闲鱼 / 小红书需要用户本人登录 Cookie**；且两者接口还需签名头，
   即使配置 Cookie 也可能失败，Adapter 会如实上报平台返回的原文。
6. **豆瓣非北京城市的小组 ID 未验证**（北京 `26926`/`279962` 已验证）。
7. **通勤时间为估算**：地图页的高德路径规划结果标注为路线规划值，
   本地不对通勤时间做任何"真实路线时间"的推断。
8. **无账号体系**：本地版未实现 `/v1/user/*` 登录注册，前端登录页不可用
   （不影响搜索/筛选/地图）。
9. **SQLite 并发**：适合个人单机使用，不适合高并发写入。

## 数据来源与致谢

本项目基于开源项目 [liguobao/HouseSearch](https://github.com/liguobao/HouseSearch) 改造，保留原项目的前端 UI 设计。

原项目技术栈：.NET Core + Vue.js + MySQL + Redis + MongoDB + Elasticsearch

## License

与原项目保持一致：LGPL v3
