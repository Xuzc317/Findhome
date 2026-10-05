import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Col,
  Divider,
  Empty,
  InputNumber,
  Row,
  Segmented,
  Select,
  Skeleton,
  Slider,
  Space,
  Tag,
  Tooltip,
  message,
} from "antd";
import { Helmet } from "react-helmet";
import Masonry from "react-masonry-css";
import BaseLayout from "@/components/layout";
import { HouseCard } from "@/components/house-card";
import {
  DEFAULT_CRITERIA,
  SearchCriteria,
  SearchResult,
  searchService,
} from "@/services/search";
import { MetroService } from "@/services/metro";

const metroService = new MetroService();

const LAYOUT_OPTIONS = [
  { label: "单间", value: "studio" },
  { label: "1房1厅", value: "1b1l" },
  { label: "2房1厅", value: "2b1l" },
  { label: "3房1厅", value: "3b1l" },
  { label: "4房及以上", value: "4b+" },
];

function useColumns() {
  const [cols, setCols] = useState(4);
  useEffect(() => {
    const calc = () => {
      const w = window.innerWidth;
      if (w < 700) return setCols(1);
      if (w < 1000) return setCols(2);
      if (w < 1360) return setCols(3);
      return setCols(4);
    };
    calc();
    window.addEventListener("resize", calc);
    return () => window.removeEventListener("resize", calc);
  }, []);
  return cols;
}

export default function SearchPage() {
  const columns = useColumns();
  const [criteria, setCriteria] = useState<SearchCriteria>({
    ...DEFAULT_CRITERIA,
    stations: ["上芬", "上塘", "元芬", "红山", "龙胜", "龙华", "清湖", "上屋",
               "长圳", "官田", "阳台山东", "长岭陂"],
  });

  const [cities, setCities] = useState<{ name: string; houseCount: number }[]>([]);
  const [lines, setLines] = useState<{ name: string; color?: string }[]>([]);
  const [stations, setStations] = useState<string[]>([]);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"precise" | "pending">("precise");

  const patch = (p: Partial<SearchCriteria>) => setCriteria((c) => ({ ...c, ...p }));

  // ① 城市：优先选
  useEffect(() => {
    searchService.cities().then((list) => {
      setCities(list);
      if (list.length && !list.some((c) => c.name === criteria.city)) {
        patch({ city: list[0].name, stations: [], line_names: [] });
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ② 换城市 → 重新加载该城市的线路与站点
  useEffect(() => {
    if (!criteria.city) return;
    setLines([]);
    setStations([]);
    metroService.getLines(criteria.city).then((res: any) => {
      setLines(res?.data || []);
    });
    metroService.getStations(criteria.city).then((res: any) => {
      const list = (res?.data || []).map((s: any) => s.name);
      setStations(Array.from(new Set(list)) as string[]);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [criteria.city]);

  const runSearch = async () => {
    if (!criteria.stations.length && !criteria.line_names.length) {
      message.warning("请至少选择一个地铁站，或选择一条线路");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await searchService.run(criteria);
      const ids = [...(res.data || []), ...(res.pendingLocation || [])].map(
        (m) => m.house_id
      );
      const pics = await searchService.fetchPictures(ids);
      const fill = (list: any[]) =>
        list.map((m) => ({ ...m, picture: pics[m.house_id] }));
      setResult({
        ...res,
        data: fill(res.data || []),
        pendingLocation: fill(res.pendingLocation || []),
      });
      setTab("precise");
      message.success(`找到 ${res.total} 套符合条件`);
    } catch (e: any) {
      setError(e?.message || "搜索失败");
    } finally {
      setLoading(false);
    }
  };

  const list = tab === "precise" ? result?.data || [] : result?.pendingLocation || [];
  const stats = result?.stats;

  const cityOptions = useMemo(
    () =>
      cities.map((c) => ({
        label: `${c.name}（${c.houseCount} 套在租）`,
        value: c.name,
      })),
    [cities]
  );

  return (
    <BaseLayout>
      <Helmet>
        <title>搜索房源 · Findhome</title>
      </Helmet>

      <div style={{ maxWidth: 1360, margin: "0 auto", padding: "16px 16px 60px" }}>
        {/* ============ 搜索条件 ============ */}
        <Card
          title="搜索房源"
          styles={{ body: { paddingTop: 16 } }}
          extra={
            <Space>
              <Button
                onClick={() =>
                  patch({
                    stations: [],
                    line_names: [],
                    price_min: null,
                    price_max: null,
                    layouts: [],
                    listing_kinds: [],
                    poster_types: [],
                    sources: [],
                  })
                }
              >
                清空条件
              </Button>
              <Button type="primary" loading={loading} onClick={runSearch}>
                搜索
              </Button>
            </Space>
          }
        >
          {/* ① 城市优先 */}
          <Row gutter={[16, 12]} align="middle">
            <Col xs={24} md={8}>
              <div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 4 }}>
                ① 选择城市
              </div>
              <Select
                style={{ width: "100%" }}
                size="large"
                value={criteria.city}
                onChange={(v) => patch({ city: v, stations: [], line_names: [] })}
                options={cityOptions}
                placeholder="先选城市"
              />
            </Col>
            <Col xs={24} md={16}>
              <div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 4 }}>
                ② 按地铁线路快速选站（可多选；也可直接在下一行挑站）
              </div>
              <Select
                mode="multiple"
                allowClear
                style={{ width: "100%" }}
                size="large"
                placeholder={lines.length ? `可选 ${lines.length} 条线路` : "该城市暂无线路数据"}
                value={criteria.line_names}
                onChange={(v) => patch({ line_names: v })}
                options={lines.map((l) => ({ label: l.name, value: l.name }))}
                maxTagCount="responsive"
              />
            </Col>
          </Row>

          <Divider style={{ margin: "16px 0 12px" }} />

          {/* ② 站点 */}
          <div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 4 }}>
            地铁站（{criteria.stations.length} 个已选，留空则用线路包含的全部站点）
          </div>
          <Select
            mode="multiple"
            allowClear
            style={{ width: "100%" }}
            placeholder={stations.length ? `搜索 ${stations.length} 个站点` : "该城市暂无站点数据"}
            value={criteria.stations}
            onChange={(v) => patch({ stations: v })}
            options={stations.map((s) => ({ label: s, value: s }))}
            maxTagCount="responsive"
            showSearch
            optionFilterProp="label"
          />

          <Divider style={{ margin: "16px 0 12px" }} />

          {/* ③ 预算与房型 */}
          <Row gutter={[16, 12]}>
            <Col xs={24} md={10}>
              <div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 4 }}>预算（元/月）</div>
              <Space>
                <InputNumber
                  placeholder="最低"
                  min={0}
                  value={criteria.price_min ?? undefined}
                  onChange={(v) => patch({ price_min: (v as number) ?? null })}
                  style={{ width: 110 }}
                />
                <span>—</span>
                <InputNumber
                  placeholder="最高"
                  min={0}
                  value={criteria.price_max ?? undefined}
                  onChange={(v) => patch({ price_max: (v as number) ?? null })}
                  style={{ width: 110 }}
                />
              </Space>
              <div style={{ marginTop: 8 }}>
                <Space size={4} wrap>
                  {[[0, 1500], [1200, 2500], [1500, 3000], [2500, 4000], [4000, 8000]].map(
                    ([a, b]) => (
                      <Tag
                        key={`${a}-${b}`}
                        style={{ cursor: "pointer", margin: 0 }}
                        color={
                          criteria.price_min === a && criteria.price_max === b
                            ? "blue"
                            : undefined
                        }
                        onClick={() => patch({ price_min: a || null, price_max: b })}
                      >
                        {a === 0 ? `${b} 以下` : `${a}-${b}`}
                      </Tag>
                    )
                  )}
                </Space>
              </div>
            </Col>
            <Col xs={24} md={14}>
              <div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 4 }}>房型</div>
              <Checkbox.Group
                options={LAYOUT_OPTIONS}
                value={criteria.layouts}
                onChange={(v) => patch({ layouts: v as string[] })}
              />
            </Col>
          </Row>

          <Divider style={{ margin: "16px 0 12px" }} />

          {/* ④ 通勤与房源性质 */}
          <Row gutter={[16, 12]}>
            <Col xs={24} md={10}>
              <div style={{ fontSize: 13, color: "#8c8c8c" }}>
                真实步行时间上限：
                <b style={{ color: "#00a3ca" }}>{criteria.max_walk_minutes} 分钟</b>
              </div>
              <Slider
                min={5}
                max={40}
                step={5}
                value={criteria.max_walk_minutes}
                onChange={(v) => patch({ max_walk_minutes: v as number })}
                marks={{ 5: "5", 20: "20", 40: "40" }}
              />
            </Col>
            <Col xs={24} md={14}>
              <div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 6 }}>
                房源性质
                <Tooltip title="勾选后搜索会调用高德逐条计算真实步行路径，首次约需 1 分钟（结果会缓存，之后很快）。不勾选则先按直线距离预筛，秒出结果，之后可在结果区一键精算。">
                  <Checkbox
                    style={{ marginLeft: 12 }}
                    checked={criteria.compute_walk}
                    onChange={(e) => patch({ compute_walk: e.target.checked })}
                  >
                    精算真实步行距离（较慢）
                  </Checkbox>
                </Tooltip>
              </div>
              <Space wrap>
                <Checkbox
                  checked={criteria.listing_kinds.includes("sublet")}
                  onChange={(e) =>
                    patch({
                      listing_kinds: e.target.checked
                        ? [...criteria.listing_kinds, "sublet"]
                        : criteria.listing_kinds.filter((k) => k !== "sublet"),
                    })
                  }
                >
                  🔑 只看转租
                </Checkbox>
                <Checkbox
                  checked={criteria.poster_types.includes("individual")}
                  onChange={(e) =>
                    patch({
                      poster_types: e.target.checked
                        ? [...criteria.poster_types, "individual"]
                        : criteria.poster_types.filter((k) => k !== "individual"),
                    })
                  }
                >
                  👤 只看个人房东
                </Checkbox>
                <Checkbox
                  checked={criteria.exclude_agency}
                  onChange={(e) => patch({ exclude_agency: e.target.checked })}
                >
                  排除疑似中介
                </Checkbox>
                <Tooltip title="平台大多不写电梯，硬筛可能一条不剩；不勾选时每条会标明电梯状态">
                  <Checkbox
                    checked={criteria.require_elevator}
                    onChange={(e) => patch({ require_elevator: e.target.checked })}
                  >
                    必须有电梯
                  </Checkbox>
                </Tooltip>
              </Space>
            </Col>
          </Row>

          <Divider style={{ margin: "16px 0 12px" }} />

          {/* ⑤ 数据源与排序 */}
          <Row gutter={[16, 12]} align="middle">
            <Col xs={24} md={14}>
              <div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 4 }}>
                数据源（不选=全部启用中的来源）
              </div>
              <Checkbox.Group
                value={criteria.sources}
                onChange={(v) => patch({ sources: v as string[] })}
                options={[
                  { label: "闲鱼", value: "xianyu" },
                  { label: "小红书", value: "xiaohongshu" },
                  { label: "豆瓣", value: "douban" },
                ]}
              />
            </Col>
            <Col xs={24} md={10}>
              <div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 4 }}>排序</div>
              <Segmented
                value={criteria.sort_by}
                onChange={(v) => patch({ sort_by: v as any })}
                options={[
                  { label: "步行最短", value: "walk" },
                  { label: "价格最低", value: "price" },
                  { label: "房况较新", value: "newness" },
                ]}
              />
            </Col>
          </Row>
        </Card>

        {/* ============ 结果 ============ */}
        {error && <Alert type="error" showIcon style={{ marginTop: 16 }} message={error} />}

        {loading && (
          <div style={{ display: "flex", gap: 16, marginTop: 24 }}>
            {[1, 2, 3, 4].map((i) => (
              <div key={i} style={{ flex: 1 }}>
                <Skeleton.Image active style={{ width: "100%", height: 180 }} />
                <Skeleton active paragraph={{ rows: 3 }} style={{ marginTop: 12 }} />
              </div>
            ))}
          </div>
        )}

        {!loading && result && (
          <>
            <div
              style={{
                marginTop: 20,
                display: "flex",
                gap: 20,
                flexWrap: "wrap",
                fontSize: 13,
                color: "#8c8c8c",
              }}
            >
              <span>候选 {stats?.priceLayoutCandidates}</span>
              <span>排除合租 {stats?.droppedShared}</span>
              <span>排除求租帖 {stats?.droppedWanted}</span>
              <span>直线达标 {stats?.withinStraight}</span>
              <span style={{ color: "#fa541c", fontWeight: 600 }}>
                精确符合 {stats?.matched}
              </span>
              <span>位置待确认 {stats?.pendingLocation}</span>
              {stats?.amapKeyMissing && (
                <span style={{ color: "#fa8c16" }}>⚠️ 未配置高德 Web 服务 Key</span>
              )}
            </div>

            {!criteria.compute_walk &&
              (stats?.walkUnknown ?? 0) > 0 &&
              criteria.max_walk_minutes > 0 && (
                <Alert
                  type="info"
                  showIcon
                  style={{ marginTop: 12 }}
                  message={`有 ${stats?.walkUnknown} 套尚未计算真实步行距离`}
                  description="当前按直线距离预筛（秒出结果）。若要按「步行 ≤ N 分钟」严格筛选，需要调用高德逐条计算，首次约 1 分钟。"
                  action={
                    <Button
                      size="small"
                      type="primary"
                      loading={loading}
                      onClick={() => {
                        const next = { ...criteria, compute_walk: true };
                        setCriteria(next);
                        // 用新条件立即重跑一次
                        setLoading(true);
                        searchService
                          .run(next)
                          .then(async (res) => {
                            const ids = [
                              ...(res.data || []),
                              ...(res.pendingLocation || []),
                            ].map((m) => m.house_id);
                            const pics = await searchService.fetchPictures(ids);
                            const fill = (l: any[]) =>
                              l.map((m) => ({ ...m, picture: pics[m.house_id] }));
                            setResult({
                              ...res,
                              data: fill(res.data || []),
                              pendingLocation: fill(res.pendingLocation || []),
                            });
                            message.success(
                              `精算完成：符合 ${res.stats?.matched ?? 0} 套`
                            );
                          })
                          .catch((e) => setError(e?.message || "精算失败"))
                          .finally(() => setLoading(false));
                      }}
                    >
                      精算步行距离
                    </Button>
                  }
                />
              )}

            <div style={{ marginTop: 12 }}>
              <Segmented
                value={tab}
                onChange={(v) => setTab(v as "precise" | "pending")}
                options={[
                  {
                    label: (
                      <span>
                        精确符合{" "}
                        <Badge count={stats?.matched ?? 0} overflowCount={999}
                               style={{ backgroundColor: "#00a3ca" }} />
                      </span>
                    ),
                    value: "precise",
                  },
                  {
                    label: (
                      <span>
                        位置待确认{" "}
                        <Badge count={stats?.pendingLocation ?? 0} overflowCount={999}
                               style={{ backgroundColor: "#bfbfbf" }} />
                      </span>
                    ),
                    value: "pending",
                  },
                ]}
              />
            </div>

            {tab === "pending" && (
              <Alert
                type="info"
                showIcon
                style={{ marginTop: 12 }}
                message="这些房源只写了「某地铁站附近」，没有小区名"
                description="不能用站点坐标冒充房源坐标（那会把距离算成 0 米）。价格房型符合，距离需你点开原帖确认。"
              />
            )}

            <Alert
              type="warning"
              showIcon
              style={{ marginTop: 12 }}
              message="房源图由发布者上传，可能是宣传图，不等于实际房间"
              description="批量发布者（🏢 疑似中介）尤其如此。建议先要实拍视频，或到现场核对。"
            />

            <div style={{ marginTop: 16 }}>
              {list.length === 0 ? (
                <Empty description="没有符合条件的房源" style={{ padding: "60px 0" }} />
              ) : (
                <Masonry
                  breakpointCols={columns}
                  className="my-masonry-grid"
                  columnClassName="my-masonry-grid_column"
                >
                  {list.map((item) => (
                    <HouseCard key={`${item.house_id}-${item.nearest_station}`} item={item} />
                  ))}
                </Masonry>
              )}
            </div>
          </>
        )}

        {!loading && !result && (
          <Empty
            style={{ padding: "80px 0" }}
            description="选好城市与地铁站后点「搜索」"
          />
        )}
      </div>
    </BaseLayout>
  );
}
