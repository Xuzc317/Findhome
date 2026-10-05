# Findhome

**本地租房聚合与通勤筛选工具** — 按「城市 + 地铁站 + 预算 + 房型」到多平台按需采集房源，
计算**真实步行距离**，并识别转租、机构批量发布者与可能为宣传图的房源。

**A local rental aggregator with commute-based filtering** — pick a city, some metro
stations, a budget and a layout; it collects listings from multiple platforms on demand,
computes **real walking distances**, and flags sublets, bulk-posting agencies and likely
promotional photos.

[作者的话](#作者的话) · [与原项目对比](#与原项目-housesearch-的对比) · [中文文档](#中文) · [English](#english) · [Author's note](#authors-note)

> ⚠️ **仅供个人本地使用 / For personal, local use only.**
> 不绕过任何验证码、登录或访问控制，不逆向平台签名算法，不使用他人账号。
> This project does **not** bypass CAPTCHAs, logins or access controls, does **not**
> reverse-engineer platform signing algorithms, and never uses anyone else's account.

---

<a id="作者的话"></a>
## 作者的话 / A note from the author

> 这一节是我自己写的，不是模板。想先说清楚「为什么要有这个项目」。

### 为什么要基于原项目改，而不是直接用

市面上的租房工具要么是平台自带的（筛选维度由平台决定），要么是别人做好的成品
（条件写死、不能改）。我有几个很具体的顾虑，最终决定自己动手：

**1. 担心小程序要付费。**
原项目的形态是小程序 + 服务端。对我来说，一个只是帮自己筛房源的工具，
不应该先考虑「要不要为它付费」这件事——它应该跑在我自己的电脑上。

**2. 我有自己的住房要求，不想被笼统的条件框住。**
原项目的筛选是通用的租房条件（城市、价格、区域……）。但真实的找房逻辑是
**「我在这几个地铁站附近找，步行不超过 20 分钟，预算这么多，只要整租，
别太旧」**——这种「按通勤条件反查」的搜索，现成工具基本都不支持。
更重要的是，需求是会变的：今天想加一个筛选维度，明天想多接一个渠道，
**我必须能随时自己改**。

**3. 原项目是 24 小时不间断爬虫，特别容易被检测到并封号。**
这是最实际的问题。持续高频请求几乎必然触发风控。所以我把它改成了
**按需采集**：你点「开始」，它才去采一次，采完就停。
既降低被识别的概率，也更符合「我一天只看一次房」的真实使用节奏。

**顺带一句给后续开发者的建议**：动手之前，先让手上的 AI / agent 工具去核实
一遍相关 API 的**最新**接入要求（高德地图、小红书、闲鱼等），
确认有没有新增限制、字段变更或资质要求，再按新条件改。
这类平台规则变化很快，用旧资料写出来的代码往往跑不通。

**4. 部署到本地，就不用担心个人数据与授权问题。**
所有数据只落在你自己电脑上的 `data/houses.db`，不上传任何服务器。
登录态也只使用**你本人浏览器**的会话，不索取密码、不做验证码绕过。

**5. 把想法通过 AI 变成能用的项目，这件事本身很有意义。**
从「我想要一个能按地铁站筛房的工具」，到真的有一个能跑起来、
能服务自己、还能开源给别人用的东西——这个把想法落地的过程，
我觉得值得记录，也值得分享。

### 与原项目 HouseSearch 的对比

先把原项目的自我描述原样放在这里（摘自
[liguobao/HouseSearch](https://github.com/liguobao/HouseSearch) 的 README）：

> 爬虫全天不间断获取公开租房信息，汇总处理分析后落地到数据库中。
>
> 使用高德地图 API 直接在地图上展示房源位置，方便查看租房地理位置，
> 同时提供住址到公司的路线计算（公交 + 地铁 or 步行导航）以及预估耗时。
>
> 通过实时爬虫获取公开租房信息，直接在高德地图上直观展示房源位置 + 基础信息，
> 同时提供住址到公司的路线计算（公交 + 地图 or 步行导航）。
> 已实现【豆瓣租房小组】、【Zuber 合租】、【蘑菇租房】、【小红书】、
> 【贝壳租房】、【房天下】、【上海互助租房】等房源信息数据爬取，
> 部分房源价格支持筛选功能。
>
> 支持个人收藏房源信息，以便筛选自己合适的房子。

**本项目保留了它的核心思路**——多平台采集公开租房信息、高德地图能力、
收藏机制；**在形态与筛选方式上做了实质改动**：

| 维度 | 原项目 HouseSearch | 本项目 Findhome |
|---|---|---|
| 形态 | 小程序 + 服务端 | **纯本地单体应用**（浏览器打开 `localhost`） |
| 技术栈 | .NET Core + Vue + MySQL + Redis + MongoDB + ES | FastAPI + SQLAlchemy + **SQLite** + React + Ant Design |
| 采集节奏 | **24 小时不间断爬虫** | **按需采集**：你点「开始」才去采，采完即停 |
| 数据落地 | 服务端数据库，面向所有用户 | **只落本地** `data/houses.db`，不上传 |
| 核心筛选 | 通用租房条件（城市/价格/区域…），部分房源支持价格筛选 | **按通勤条件反查**：地铁站 + **真实步行距离** + 房型 + 租型 + 发布者身份 |
| 距离 | 高德地图展示 + 住址到公司路线计算 | 保留高德能力，重心是**房源到地铁站的真实步行路径** |
| 房源定位 | — | 位置推断 + **精度分级**（楼栋级/小区级/仅站点附近），不伪造坐标 |
| 收藏 | 支持个人收藏 | 收藏 / 已联系 / 不感兴趣 / **备注**，独立于采集数据持久化 |
| 账号 | 小程序账号体系 | **无账号体系**，只用你本人浏览器会话 |
| 数据源 | 豆瓣、Zuber 合租、蘑菇租房、小红书、贝壳、房天下、上海互助租房 | 闲鱼、小红书、豆瓣（**贝壳因风控放弃**，原因见下） |
| 使用成本 | 小程序可能涉及付费 | 完全免费，本地运行 |

**需要说明的两点差异**：

- 原项目列出的数据源里，蘑菇租房等平台已停止运营，贝壳目前对自动化访问的
  校验也过于严格。所以本项目实际可用的是**闲鱼、小红书、豆瓣**三个源，
  这一点在文档里如实标注，不假装支持。
- 原项目面向多用户服务，本项目面向**你自己的找房过程**——所以它更像一个
  「筛房工作台」：有进度反馈、有收藏备注、有保存的搜索。

---

<a id="中文"></a>
## 中文

### 它解决什么问题

找房时的真实流程不是「先翻房源再想通勤」，而是：

> 我在**这几个地铁站**附近找房，预算 **1200–2500**，要**单间 / 一房一厅**，
> **步行不超过 20 分钟**，希望**有电梯、别太旧**。

主流平台都不支持这种「按通勤条件反查」的搜索，而且各有各的坑：宣传图、
中介冒充房东、合租混在整租里、距离只给直线不给步行。

Findhome 把这条路走通：

**先定地铁站 → 实时去各平台采 → 定位并计算真实步行距离 → 按条件筛选归类 → 图文卡片呈现**，
并且把你自己的收藏与备注独立保存。

### 功能

| 功能 | 说明 |
|---|---|
| 🚇 **按地铁站选址** | 支持按线路选站（选「6号线」自动展开该线全部站点） |
| 🚶 **真实步行距离** | 高德步行路径规划，不是直线折算；同时给出直线距离与步行时间 |
| 🔑 **转租识别** | 区分「转租 / 直接房东 / 普通」。转租贴的图片与价格通常更真实 |
| 🏢 **机构发布者标注** | 从图片 URL 提取发布者 ID；一个账号挂几十上百套的标为「疑似中介」 |
| 🖼 **图片可信度提示** | 明确提示「房源图由发布者上传，可能是宣传图」，并对机构房源加注 |
| 🏠 **房型与租型** | 单间 / 1房1厅 / 2房1厅…；默认排除合租 |
| ⭐ **收藏与备注** | 收藏、已联系、不感兴趣、备注，**独立于采集数据长期保存** |
| 📍 **位置精度分级** | 区分楼栋级 / 小区级 / 仅站点附近；只写「某站附近」的单独列出，不拿站点坐标冒充 0 米 |
| 💾 **保存的搜索** | 把当前条件存成档案，下次一键调用 |

### 界面

**① 选择城市** → **② 平台授权** → **③ 筛选条件** → **④ 采集结果**

![选择城市](docs/screenshots/01-choose-city.png)

![平台授权](docs/screenshots/02-auth-status.png)

![筛选条件](docs/screenshots/03-conditions.png)

结果以图文卡片呈现，含价格、步行时间、房型、电梯状态、新旧分、发布者身份：

![采集结果](docs/screenshots/04-results-cards.png)

> 截图中的**房源图片已打码**，文字保持可读；截图不含浏览器边框，因此不携带本机设备信息。

收藏与备注独立保存，采集覆盖房源时不会丢失：

![收藏与记录](docs/screenshots/05-favorites.png)

所有集成（高德、大模型、各平台登录态）在一处可见，服务端密钥只显示掩码：

![配置与集成](docs/screenshots/06-settings.png)

### 技术结构

```
┌─────────────────────────────────────────────────────────────┐
│  前端  React 18 + TypeScript + Vite 5 + Ant Design 5        │
│  ├─ /            实时采集向导（城市→授权→条件→结果）          │
│  ├─ /favorites   收藏与记录（用户数据）                       │
│  ├─ /search      快速查询（查本地已采数据，秒出）              │
│  ├─ /saved       保存的搜索                                   │
│  └─ /settings    配置与集成状态                               │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST  /api/*
┌───────────────────────────▼─────────────────────────────────┐
│  后端  FastAPI + SQLAlchemy 2 + SQLite                       │
│                                                              │
│  routers/    search  tasks  marks  metro  geo  houses …      │
│  services/   match        匹配引擎（预筛→步行→条件→排序）      │
│              collect_task 任务化采集（不阻塞 HTTP 请求）       │
│              amap         高德客户端（3 QPS 节流 + 缓存）      │
│              geolocate    位置推断（小区/地址/站点 → 坐标）    │
│              condition    转租 / 中介 / 电梯 / 新旧 识别       │
│              integrations 统一配置与脱敏                      │
│  crawlers/   base         Adapter 基类 + 状态机               │
│              manager      入库 / 去重 / 风险评分 / 事务        │
│              douban beike                    HTTP 直连        │
│              browser_fetch xianyu xiaohongshu   真实浏览器    │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   高德 Web 服务        DeepSeek / 豆包       平台页面
   地理编码/POI/步行路径   文字与图片理解      （真实浏览器会话）
```

| 层级 | 选型 | 说明 |
|---|---|---|
| 前端 | React 18 + TypeScript + Vite 5 + Ant Design 5 | 五个自有页面，无账号体系 |
| 后端 | FastAPI + SQLAlchemy 2 | `backend.xxx` 绝对导入 |
| 数据库 | SQLite | 单文件零配置；`houses` 与 `house_marks` 分离 |
| 采集 | httpx + BeautifulSoup（直连）/ Playwright（浏览器） | Adapter 模式，各平台独立 |
| 地理 | 高德 Web 服务 + 静态地铁数据 | 坐标统一为 GCJ-02 |
| 大模型 | DeepSeek / 豆包（火山方舟） | `LLM_PROVIDER=auto` 时互为兜底 |

**几个关键设计取舍**

- **采集分两类**：豆瓣、贝壳走 HTTP 直连；闲鱼、小红书的搜索接口要求页面 JS 生成的
  签名参数，**不做签名逆向**，改用真实浏览器打开搜索页、只读渲染结果——这跟手工浏览没有区别。
- **长任务不阻塞请求**：一次采集是分钟级的，因此做成任务（`POST /tasks/collect` → 轮询进度）。
  任务跑在同一事件循环内，同步阻塞的定位与距离计算丢进线程池，否则连进度接口都会卡住。
- **用户数据与采集数据分表**：`houses` 是平台数据的镜像，每次采集会覆盖；
  `house_marks` 是你的收藏与备注，独立存放，不随采集或房源下架丢失。
- **不伪造数据**：只写「某站附近」的房源不拿站点坐标冒充房源坐标（那会把距离算成 0 米），
  单独列为「位置待确认」；电梯状态区分「原文明确写了」与「按楼层推断」；拿不到价格就留空，不猜。

### 部署到本地

**环境要求**：Python 3.11+、Node.js 18+、（可选）Chromium 用于浏览器采集。

```bash
# 1. 克隆
git clone https://github.com/Xuzc317/Findhome.git
cd Findhome

# 2. 后端
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. 前端
cd frontend && npm install && npm run build && cd ..

# 4. 配置
cp .env.example .env
#    编辑 .env，至少填高德 Web 服务 Key（见下）

# 5. 启动（在项目根目录执行，不要 cd 进 backend）
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 6. 打开 http://localhost:8000
```

> ⚠️ **必须在项目根目录运行**。所有后端模块使用 `backend.xxx` 绝对导入，
> 因此 `cd backend && uvicorn main:app` 会直接报 `ModuleNotFoundError`。

#### 配置说明

`.env` **不要提交到 Git**（已在 `.gitignore` 中）。

| 变量 | 用途 | 必需 |
|---|---|---|
| `AMAP_WEB_KEY` | 高德「**Web服务**」Key：地理编码、POI、步行路径 | ✅ 强烈建议 |
| `AMAP_KEY` / `AMAP_SECURITY_CODE` | 高德「**Web端(JS API)**」Key 与安全密钥：前端地图 | 可选 |
| `DEEPSEEK_API_KEY` / `DOUBAO_API_KEY` | 大模型，用于从文字/图片推断位置 | 可选 |
| `DOUBAN_COOKIE` 等 | 各平台登录态 | 见下 |

> ⚠️ **高德两类 Key 不通用**。把 JS Key 填到 `AMAP_WEB_KEY` 会返回
> `10009 请求 Key 与绑定平台不符`。申请地址：<https://console.amap.com/dev/key/app>
>
> 未配置 `AMAP_WEB_KEY` 时功能仍可用，但只能按直线距离筛选，无法计算真实步行时间。

`frontend/.env` **留空即可**：高德 JS Key 由后端 `/api/config` 运行时下发，
写进前端会被 Vite 内联进 `build/assets/*.js`，分享构建目录就会泄漏。

#### 平台登录（只接受你本人浏览器的登录态）

闲鱼与小红书需要登录态。工具提供扫码登录助手 —— **不索取密码，不处理验证码**：

```bash
python browser_daemon.py      # 打开浏览器，扫码登录后保持窗口不关
python export_cookies.py      # 把登录态导出到 .env（只显示掩码）
python import_cookie.py --check   # 校验 .env 里的登录态是否仍有效
```

也可以手工导入（粘贴 → 真实请求校验 → 写入 `.env`，校验失败不写入）：

```bash
python import_cookie.py douban
```

#### 首次使用

```bash
# 地铁数据（深圳 17 条线路 / 351 个站点，已随仓库提供）
python crawl.py metro --city 深圳

# 采集（也可直接在 Web 界面操作）
python collect_from_browser.py xianyu --profile longhua --suffix 转租 --suffix 直租
python crawl.py douban --city 深圳

# 定位 + 计算步行距离 + 匹配
python crawl.py locate --city 深圳
python crawl.py match  --profile longhua --write docs/matches.md
```

### 加入你自己的要求条件

四种方式，从简单到灵活：

**① 直接用界面（推荐）**

打开 <http://localhost:8000> → 选择城市 → 检查登录 → 填条件 → 开始采集。
支持按线路选站、预算、房型、步行时间、只看转租、只看个人房东、排除中介等。

**② 保存成「保存的搜索」**

界面里点「保存为常用搜索」，条件会完整存进 `data/profiles/<名字>.json`，
下次在「保存的搜索」页直接调用。

**③ 直接编辑需求档案**

```jsonc
// data/profiles/longhua.json
{
  "name": "longhua",
  "city": "深圳",
  "stations": ["长圳", "上屋", "官田", "阳台山东", "元芬", "龙胜",
               "上芬", "红山", "清湖", "龙华", "上塘", "长岭陂"],
  "max_straight_m": 1000,        // 直线距离上限（米）
  "max_walk_minutes": 20,        // 真实步行时间上限（分钟）
  "price_min": 1200,
  "price_max": 2500,
  "layouts": ["studio", "1b1l", "2b1l"],   // 单间 / 1房1厅 / 2房1厅
  "rent_types": [3, 4],          // 3整租 4公寓；空 = 不限
  "exclude_shared": true,        // 排除合租
  "avoid_old_small": true,       // 排除老破小 / 城中村 / 农民房
  "require_elevator": false,     // 是否要求「原文明确写了有电梯」
  "listing_kinds": ["sublet"],   // 只看转租：sublet / direct / normal
  "poster_types": ["individual"],// 只看个人房东：individual / agency / unknown
  "sort_by": "walk"              // walk 步行 / price 价格 / newness 房况
}
```

保存后运行 `python crawl.py match --profile longhua`。

**④ 调用 API**

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "city": "深圳",
    "line_names": ["6号线"],
    "price_min": 1200, "price_max": 2500,
    "layouts": ["studio", "1b1l"],
    "listing_kinds": ["sublet"],
    "max_walk_minutes": 20
  }'
```

交互式接口文档：<http://localhost:8000/docs>

### API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/search` | **按任意条件搜索**（本轮新增，不依赖预存档案） |
| GET | `/api/search/cities` | 城市列表 + 在租数 / 线路数 / 站点数 |
| POST | `/api/tasks/collect` | **启动实时采集任务**，返回 taskId |
| GET | `/api/tasks/{id}` | 任务进度（stage / progress / logs / result） |
| POST | `/api/tasks/{id}/cancel` | 取消任务 |
| POST | `/api/marks` | 收藏 / 已联系 / 不感兴趣 / 备注（增量更新） |
| POST | `/api/marks/batch` | 批量取标记 |
| GET | `/api/marks` | 按标记类型列出（连带房源信息） |
| GET | `/api/settings` | **统一配置与集成状态**（密钥脱敏） |
| GET | `/api/match` | 按保存的档案匹配 |
| GET/POST | `/api/match/profiles` | 需求档案列表 / 保存 |
| GET | `/api/metro/lines\|stations\|stats` | 地铁线路 / 站点 / 统计 |
| POST | `/api/metro/stations/{id}/coverage` | 计算房源到该站的真实步行距离 |
| GET | `/api/geo/stats`、`/api/geo/locate` | 定位覆盖率 / 批量定位 |
| GET | `/api/config` | 前端公开配置（含 JS Key） |
| GET | `/api/health` | 健康检查 |

### 自检与测试

```bash
# 离线测试（不联网、不触发平台风控）
python tests/test_parsers.py      # 解析器 71 项
python tests/test_dedup_risk.py   # 去重与风险 16 项
python tests/test_metro_geo.py    # 地铁/坐标/房型/定位 41 项
python tests/test_match.py        # 条件识别与匹配 25 项（内存库隔离）

# 需后端运行
python verify_api.py              # 接口契约与筛选闭环 46 项
python verify_search.py           # 搜索/任务/标记 + 密钥不泄漏断言 52 项

# 红线检查
python check_secrets.py           # 密钥 / Cookie / .env 不进 Git
python check_secrets.py --fast    # 跳过历史扫描，秒级
```

### 已知限制

1. **平台风控是主要不确定性**：豆瓣会返回中间页或 429，闲鱼/小红书会要求验证码或登录态。
   触发后需等待冷却。本项目**不做验证码识别、签名逆向等绕过手段**。
2. **租金解析保守**：只认带「元/月/月租/租金/k」语境的数字（裸数字兜底，并按上下文排除年份），
   拿不到价格时显示为未知，好过把手机号当租金。
3. **贝壳已放弃**：实测其登录/验证码对自动化过于严格（带 Cookie 的 HTTP 直连被判未登录，
   真实浏览器打开同样回到登录页），在「不绕过访问控制」的前提下无法稳定采集。
4. **小红书详情页被限制**：搜索页可用，但笔记详情页返回「当前笔记暂时无法浏览」，
   因此小红书房源多停在「位置待确认」——只有标题信息，拿不到正文里的具体地址。
5. **图片可能是宣传图**：房源图由发布者上传，本工具**无法判断图片真伪**，
   只能标注发布者身份（个人房东 / 疑似中介）供你判断。
6. **时间字段不猜测**：平台不给发布时间的房源 `publish_time` 留空，
   前端明确显示「时间未知」或「(维护)」，不把采集时间冒充发布时间。
7. **SQLite 并发**：适合个人单机使用，不适合高并发写入。

### 隐私

- 所有数据存在本地 `data/houses.db`，不上传任何服务器
- 密钥与 Cookie 只存 `.env`（已 gitignore），**服务端密钥不下发到浏览器**
- 不包含任何统计或埋点代码
- 采集前请确认你所在地区与平台条款允许此类个人用途的数据获取

### 数据来源与致谢

本项目**基于开源项目 [liguobao/HouseSearch](https://github.com/liguobao/HouseSearch)
修改而来**，在此向上游作者与贡献者致谢。原项目技术栈为
.NET Core + Vue.js + MySQL + Redis + MongoDB + Elasticsearch。

详细的「继承了什么 / 改动了什么」见前文
[与原项目 HouseSearch 的对比](#与原项目-housesearch-的对比)。
简要来说：

- **继承自上游**：项目骨架与部分前端结构、数据源 Adapter 的整体思路、LGPL v3 许可
- **本项目重写或新增**：匹配引擎（按通勤条件反查）、地铁数据与真实步行距离、
  位置推断与精度分级、条件识别（转租/中介/电梯/新旧）、**按需采集**、
  统一配置层、收藏与备注持久化，以及当前这套界面

如果这个项目对你有帮助，也请给[上游项目](https://github.com/liguobao/HouseSearch)
点一个 star —— 没有它就没有这个项目。

### License

与原项目保持一致：**LGPL v3**，详见 [LICENSE](LICENSE)。

版本变更见 [CHANGELOG.md](CHANGELOG.md)，协作约定见 [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md)。

---

<a id="english"></a>
## English

<a id="authors-note"></a>
### A note from the author

> This section is written by me, not from a template — it explains *why* this project exists.

**1. I was worried the mini-program would cost money.**
The upstream project is a mini-program plus a server. For a tool whose only job is to
help me filter listings, the first question shouldn't be "how much does it cost" —
it should run on my own machine.

**2. I have my own requirements, and I don't want to be boxed in by generic filters.**
The upstream filters are generic (city, price, district…). But real flat-hunting looks
like this: *"I'm looking near **these** metro stations, under 20 minutes on foot, this
budget, whole flat only, nothing too old."* Almost no existing tool supports searching
**by commute conditions**. And requirements change — I need to be able to add a filter
dimension today and plug in another source tomorrow, **by myself**.

**3. The upstream project runs a 24/7 crawler, which is very easy to detect and gets accounts banned.**
This was the most practical problem. Continuous high-frequency requests will almost
certainly trigger anti-bot measures. So I changed it to **on-demand collection**: it only
goes out when you press *Start*, and stops when done. Lower detection risk, and it fits
how people actually flat-hunt — once a day, not every second.

**A tip for future developers**: before you start, have your AI / agent tool verify the
**latest** integration requirements of the relevant APIs (AMap, Xiaohongshu, Xianyu,
etc.) — new restrictions, changed fields, new qualification rules — and adapt to them.
These platforms change quickly, and code written against stale documentation simply
won't run.

**4. Deploying locally removes any personal-data or authorisation concerns.**
Everything lands in `data/houses.db` on your own machine; nothing is uploaded.
Sessions use **your own browser login only** — no passwords are ever requested and no
CAPTCHA is ever bypassed.

**5. Turning an idea into a working project through AI is meaningful in itself.**
From "I want a tool that can filter flats by metro station" to something that actually
runs, serves me, and can be open-sourced for others — that process is worth recording
and worth sharing.

### Comparison with the upstream HouseSearch

Here is the upstream project's own description, quoted verbatim from
[liguobao/HouseSearch](https://github.com/liguobao/HouseSearch):

> A crawler continuously collects public rental listings around the clock, aggregates
> and analyses them, and stores the results in a database.
>
> The AMap API is used to show listings directly on a map, making their location easy to
> inspect, and to compute the route from home to the office (transit + metro, or walking)
> together with an estimated travel time.
>
> Listings from Douban rental groups, Zuber shared housing, Mogu, Xiaohongshu, Beike,
> Fang.com and Shanghai mutual-aid rental groups are already supported, with price
> filtering available for some of them. Personal favourites are supported so you can
> shortlist suitable places.

**This project keeps the core idea** — multi-platform collection of public listings,
AMap integration, and a favourites mechanism — **while changing the form factor and the
way filtering works**:

| Aspect | Upstream HouseSearch | This project (Findhome) |
|---|---|---|
| Form | Mini-program + server | **Purely local single app** (open `localhost` in a browser) |
| Stack | .NET Core + Vue + MySQL + Redis + MongoDB + ES | FastAPI + SQLAlchemy + **SQLite** + React + Ant Design |
| Collection cadence | **24/7 continuous crawler** | **On demand** — only when you press *Start*, then it stops |
| Data location | Server database, shared by all users | **Local only** — `data/houses.db`, never uploaded |
| Core filtering | Generic criteria (city / price / district…), price filtering for some listings | **Commute-first**: metro station + **real walking distance** + layout + rent type + poster identity |
| Distance | Map display + home-to-office routing | AMap kept, but the focus is the **real walking route from the listing to the station** |
| Geocoding | — | Location inference with **precision tiers** (building / community / station-only); coordinates are never faked |
| Favourites | Personal favourites | Favourite / contacted / not-interested / **notes**, persisted independently of collected data |
| Accounts | Mini-program account system | **No account system** — your own browser session only |
| Sources | Douban, Zuber, Mogu, Xiaohongshu, Beike, Fang.com, Shanghai mutual-aid | Xianyu, Xiaohongshu, Douban (**Beike dropped** for anti-bot reasons, see below) |
| Cost | Mini-program may involve payment | Completely free, runs locally |

**Two differences worth spelling out:**

- Some sources listed upstream (Mogu, for instance) no longer operate, and Beike's
  automated-access checks are currently too strict. So the working sources here are
  **Xianyu, Xiaohongshu and Douban** — stated plainly rather than pretending otherwise.
- Upstream serves many users; this project serves **your own flat-hunting process**. It
  is therefore closer to a "flat-filtering workbench": progress feedback, favourites and
  notes, saved searches.

---

### The problem

Finding a rental does not start with listings — it starts with a commute:

> I want a place near **these metro stations**, budget **¥1200–2500**,
> a **studio or 1-bedroom**, **under 20 minutes on foot**, with an **elevator**,
> and **not too old**.

No mainstream platform supports searching this way, and each has its own traps:
promotional photos, agencies posing as landlords, shared flats mixed into whole-flat
results, and straight-line distances presented as walking distance.

Findhome closes that gap:

**pick stations → collect live from each platform → geocode and compute real walking
routes → filter and categorise → show as image cards**, while keeping your favourites
and notes in a separate, permanent store.

### Features

| Feature | Description |
|---|---|
| 🚇 **Search by metro station** | Pick by line (choosing "Line 6" expands to all its stations) |
| 🚶 **Real walking distance** | AMap walking-route planning, not straight-line estimation; both are shown |
| 🔑 **Sublet detection** | Distinguishes *sublet / direct-from-owner / normal*. Sublet posts tend to have genuine photos and prices |
| 🏢 **Agency flagging** | Extracts the poster ID from image URLs; accounts listing dozens of units are flagged as suspected agencies |
| 🖼 **Image honesty notice** | Explicitly warns that listing photos are uploaded by the poster and may be promotional |
| 🏠 **Layout & rent type** | Studio / 1-bed / 2-bed…; shared flats excluded by default |
| ⭐ **Favourites & notes** | Favourite, contacted, not-interested, notes — stored **independently of collected data** |
| 📍 **Location precision tiers** | Building / community / station-only. Listings that only say "near X station" are listed separately — station coordinates are never passed off as a 0 m distance |
| 💾 **Saved searches** | Store the current criteria as a profile and reuse it in one click |

### Screenshots

**① Choose city → ② Platform auth → ③ Conditions → ④ Results**

![Choose city](docs/screenshots/01-choose-city.png)

![Platform auth](docs/screenshots/02-auth-status.png)

![Conditions](docs/screenshots/03-conditions.png)

Results are shown as image cards with price, walking time, layout, elevator status,
freshness score and poster type:

![Results](docs/screenshots/04-results-cards.png)

> Listing photos in these screenshots are **blurred**; text remains readable. No browser
> chrome is captured, so no local device information is exposed.

Favourites and notes survive re-collection:

![Favourites](docs/screenshots/05-favorites.png)

All integrations in one place; server-side secrets are shown masked only:

![Settings](docs/screenshots/06-settings.png)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend  React 18 + TypeScript + Vite 5 + Ant Design 5    │
│  ├─ /            Live collection wizard (city→auth→query→…) │
│  ├─ /favorites   Favourites & notes (user data)             │
│  ├─ /search      Quick query over locally collected data    │
│  ├─ /saved       Saved searches                             │
│  └─ /settings    Configuration & integration status         │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST  /api/*
┌───────────────────────────▼─────────────────────────────────┐
│  Backend  FastAPI + SQLAlchemy 2 + SQLite                   │
│                                                             │
│  routers/    search  tasks  marks  metro  geo  houses …     │
│  services/   match        engine (prefilter→walk→filter→sort)│
│              collect_task taskified collection              │
│              amap         client (3 QPS throttle + cache)   │
│              geolocate    location inference                │
│              condition    sublet / agency / elevator / new  │
│              integrations centralised config + redaction    │
│  crawlers/   base         adapter base + status machine     │
│              manager      ingest / dedupe / risk / tx       │
│              douban beike                   HTTP direct     │
│              browser_fetch xianyu xiaohongshu  real browser │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  AMap Web Service     DeepSeek / Doubao    Platform pages
  geocode/POI/walking  text & image parsing (real browser session)
```

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React 18 + TypeScript + Vite 5 + Ant Design 5 | Five own pages, no account system |
| Backend | FastAPI + SQLAlchemy 2 | Absolute `backend.xxx` imports |
| Database | SQLite | Single file, zero config; `houses` and `house_marks` kept separate |
| Collection | httpx + BeautifulSoup (direct) / Playwright (browser) | Adapter pattern, one per platform |
| Geo | AMap Web Service + static metro data | Coordinates normalised to GCJ-02 |
| LLM | DeepSeek / Doubao (Volcano Ark) | `LLM_PROVIDER=auto` makes them fall back to each other |

**Key design decisions**

- **Two collection modes.** Douban and Beike use plain HTTP. Xianyu and Xiaohongshu
  require request signatures generated by page JavaScript; rather than
  reverse-engineering them, the tool opens the search page in a real browser and reads
  the rendered result — exactly what a human visit does.
- **Long tasks never block requests.** A collection run takes minutes, so it is taskified
  (`POST /tasks/collect` → poll progress). The task runs on the same event loop; blocking
  geocoding and routing work is offloaded to a thread pool, otherwise even the progress
  endpoint would hang.
- **User data is a separate table.** `houses` mirrors platform data and is overwritten on
  every collection; `house_marks` holds your favourites and notes and is never touched.
- **No fabricated data.** Listings that only say "near X station" are not given the
  station's coordinates (which would fake a 0 m distance) — they are listed separately.
  Elevator status distinguishes *stated in the listing* from *inferred from floor count*.
  Missing prices stay empty.

### Local deployment

**Requirements**: Python 3.11+, Node.js 18+, (optional) Chromium for browser collection.

```bash
# 1. Clone
git clone https://github.com/Xuzc317/Findhome.git
cd Findhome

# 2. Backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Frontend
cd frontend && npm install && npm run build && cd ..

# 4. Configure
cp .env.example .env
#    Edit .env; at minimum set the AMap Web Service key

# 5. Run (from the project root — do NOT cd into backend)
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 6. Open http://localhost:8000
```

> ⚠️ **Must be run from the project root.** All backend modules use absolute
> `backend.xxx` imports, so `cd backend && uvicorn main:app` fails with
> `ModuleNotFoundError`.

#### Configuration

`.env` must **never** be committed (already in `.gitignore`).

| Variable | Purpose | Required |
|---|---|---|
| `AMAP_WEB_KEY` | AMap **Web Service** key: geocoding, POI, walking routes | ✅ Strongly recommended |
| `AMAP_KEY` / `AMAP_SECURITY_CODE` | AMap **JS API** key + security code (frontend map) | Optional |
| `DEEPSEEK_API_KEY` / `DOUBAO_API_KEY` | LLMs for location inference from text/images | Optional |
| `DOUBAN_COOKIE` etc. | Platform sessions | See below |

> ⚠️ The two AMap key types are **not interchangeable**. Using a JS key as
> `AMAP_WEB_KEY` returns `10009 (key/platform mismatch)`.
> Get keys at <https://console.amap.com/dev/key/app>.
>
> Without `AMAP_WEB_KEY` everything still works, but filtering falls back to
> straight-line distance only.

`frontend/.env` should stay **empty**: the JS key is delivered at runtime by the backend
via `/api/config`, because Vite would otherwise inline it into `build/assets/*.js`.

#### Platform login (your own browser session only)

Xianyu and Xiaohongshu need a session. A QR-login helper is provided —
**it never asks for your password and never handles CAPTCHAs**:

```bash
python browser_daemon.py          # opens a browser; scan the QR code, keep it open
python export_cookies.py          # exports the session to .env (masked output)
python import_cookie.py --check   # verify the stored sessions are still valid
```

Or import manually (paste → validated with a real request → written to `.env`):

```bash
python import_cookie.py douban
```

#### First run

```bash
# Metro data (Shenzhen: 17 lines / 351 stations, shipped with the repo)
python crawl.py metro --city 深圳

# Collect (or use the web UI)
python collect_from_browser.py xianyu --profile longhua --suffix 转租 --suffix 直租
python crawl.py douban --city 深圳

# Geocode + walking distances + match
python crawl.py locate --city 深圳
python crawl.py match  --profile longhua --write docs/matches.md
```

### Customising your own criteria

Four ways, from easiest to most flexible:

**① Use the UI (recommended)** — open <http://localhost:8000> and follow the wizard:
choose city → check logins → set conditions → collect.

**② Save as a "saved search"** — click *Save as saved search*; the full criteria set is
stored in `data/profiles/<name>.json`.

**③ Edit the profile file directly**

```jsonc
// data/profiles/longhua.json
{
  "name": "longhua",
  "city": "深圳",
  "stations": ["长圳", "上屋", "官田", "阳台山东", "元芬", "龙胜",
               "上芬", "红山", "清湖", "龙华", "上塘", "长岭陂"],
  "max_straight_m": 1000,        // straight-line limit (metres)
  "max_walk_minutes": 20,        // real walking-time limit (minutes)
  "price_min": 1200,
  "price_max": 2500,
  "layouts": ["studio", "1b1l", "2b1l"],
  "rent_types": [3, 4],          // 3 = whole flat, 4 = apartment; empty = any
  "exclude_shared": true,        // exclude shared flats
  "avoid_old_small": true,       // exclude old / urban-village units
  "require_elevator": false,     // require elevator to be explicitly stated
  "listing_kinds": ["sublet"],   // sublet / direct / normal
  "poster_types": ["individual"],// individual / agency / unknown
  "sort_by": "walk"              // walk / price / newness
}
```

Then run `python crawl.py match --profile longhua`.

**④ Call the API**

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "city": "深圳",
    "line_names": ["6号线"],
    "price_min": 1200, "price_max": 2500,
    "layouts": ["studio", "1b1l"],
    "listing_kinds": ["sublet"],
    "max_walk_minutes": 20
  }'
```

Interactive API docs: <http://localhost:8000/docs>

### Tests

```bash
# Offline (no network, no platform rate-limit risk)
python tests/test_parsers.py      # parsers              71 checks
python tests/test_dedup_risk.py   # dedupe & risk        16 checks
python tests/test_metro_geo.py    # metro/geo/layout     41 checks
python tests/test_match.py        # condition & matching 25 checks (isolated DB)

# Requires the backend running
python verify_api.py              # API contract & filter loop   46 checks
python verify_search.py           # search/tasks/marks + no-secret-leak  52 checks

# Red line
python check_secrets.py           # keys / cookies / .env must not enter Git
```

### Known limitations

1. **Platform anti-bot measures are the main uncertainty.** Douban may return an
   interstitial or HTTP 429; Xianyu/Xiaohongshu may require a session or CAPTCHA.
   When triggered, wait for the cooldown. This project performs **no CAPTCHA solving
   and no signature reverse-engineering**.
2. **Conservative rent parsing.** Only numbers with a price context (元/月/月租/租金/k)
   are accepted; bare numbers are a fallback with year patterns excluded by context.
   Unparseable prices are shown as unknown rather than guessed.
3. **Beike dropped.** Its login/CAPTCHA checks are too strict for automation: an HTTP
   request carrying a valid cookie is still treated as logged out, and a real browser
   lands on the login page too. It cannot be collected reliably without bypassing
   access controls.
4. **Xiaohongshu note pages are restricted.** Search works, but note detail pages return
   "this note is temporarily unavailable", so most Xiaohongshu listings stay in the
   "location unconfirmed" tier — title only, no street address from the body.
5. **Photos may be promotional.** Listing photos are uploaded by the poster and this tool
   **cannot verify them**. It only labels the poster type (individual / suspected agency)
   so you can judge.
6. **No guessed timestamps.** When a platform does not expose a publish time,
   `publish_time` stays empty and the UI says "time unknown" — collection time is never
   presented as publish time.
7. **SQLite concurrency.** Fine for single-user local use, not for concurrent writes.

### Privacy

- All data lives in your local `data/houses.db`; nothing is uploaded anywhere
- Keys and cookies live only in `.env` (gitignored); **server-side secrets are never
  sent to the browser**
- No analytics or telemetry of any kind
- Before collecting, make sure such personal use is permitted in your jurisdiction and
  by the platform's terms

### Credits & licence

This project is **based on the open-source project
[liguobao/HouseSearch](https://github.com/liguobao/HouseSearch)**. Thanks to the original
author and contributors. Original stack: .NET Core + Vue.js + MySQL + Redis + MongoDB +
Elasticsearch.

See [Comparison with the upstream HouseSearch](#comparison-with-the-upstream-housesearch)
above for the full "what was inherited vs. what changed" breakdown. In short:

- **Inherited**: project skeleton and parts of the frontend structure, the data-source
  adapter concept, and the LGPL v3 licence
- **Rewritten / added here**: the matching engine (commute-first search), metro data and
  real walking distances, location inference with precision tiers, condition detection
  (sublet / agency / elevator / freshness), **on-demand collection**, the centralised
  configuration layer, favourites & notes persistence, and the current UI

If this project is useful to you, please also star the
[upstream project](https://github.com/liguobao/HouseSearch) — this wouldn't exist
without it.

Released under **LGPL v3**, same as upstream. See [LICENSE](LICENSE).
