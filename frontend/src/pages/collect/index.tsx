import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Col,
  Descriptions,
  Empty,
  InputNumber,
  Progress,
  Row,
  Segmented,
  Select,
  Slider,
  Space,
  Steps,
  Tag,
  Typography,
  message,
} from "antd";
import { Helmet } from "react-helmet";
import Masonry from "react-masonry-css";
import axios from "axios";
import BaseLayout from "@/components/layout";
import { HouseCard } from "@/components/house-card";
import { API_BASE_URL } from "@/constant";
import { MetroService } from "@/services/metro";
import { DEFAULT_COLLECT, CollectCriteria, TaskLog, taskService } from "@/services/task";

const metroService = new MetroService();
const { Text } = Typography;

const LAYOUT_OPTIONS = [
  { label: "单间", value: "studio" },
  { label: "1房1厅", value: "1b1l" },
  { label: "2房1厅", value: "2b1l" },
  { label: "3房1厅", value: "3b1l" },
];

const SOURCE_OPTIONS = [
  { label: "闲鱼", value: "xianyu" },
  { label: "小红书", value: "xiaohongshu" },
  { label: "豆瓣", value: "douban" },
];

interface CityInfo {
  name: string;
  houseCount: number;
  stationCount: number;
  lineCount: number;
}

interface IntegrationStatus {
  amap: { available: boolean; webServiceConfigured: boolean };
  sources: {
    key: string;
    name: string;
    access: string;
    note: string;
    enabled: boolean;
    cookieConfigured: boolean;
  }[];
}

function useColumns() {
  const [cols, setCols] = useState(4);
  useEffect(() => {
    const calc = () => {
      const w = window.innerWidth;
      setCols(w < 700 ? 1 : w < 1000 ? 2 : w < 1360 ? 3 : 4);
    };
    calc();
    window.addEventListener("resize", calc);
    return () => window.removeEventListener("resize", calc);
  }, []);
  return cols;
}

export default function CollectWizard() {
  const columns = useColumns();
  const [step, setStep] = useState(0);

  const [cities, setCities] = useState<CityInfo[]>([]);
  const [integration, setIntegration] = useState<IntegrationStatus | null>(null);
  const [checkingLogin, setCheckingLogin] = useState(false);

  const [lines, setLines] = useState<{ name: string }[]>([]);
  const [stations, setStations] = useState<string[]>([]);
  const [criteria, setCriteria] = useState<CollectCriteria>({ ...DEFAULT_COLLECT });

  const [task, setTask] = useState<TaskLog | null>(null);
  const [running, setRunning] = useState(false);
  const pollRef = useRef<number | null>(null);
  const [pictures, setPictures] = useState<Record<string, string>>({});
  const [tab, setTab] = useState<"precise" | "pending">("precise");

  const patch = (p: Partial<CollectCriteria>) => setCriteria((c) => ({ ...c, ...p }));

  // 城市
  useEffect(() => {
    axios
      .get(`${API_BASE_URL}/search/cities`)
      .then((res) => setCities(res.data?.data || []))
      .catch(() => undefined);
  }, []);

  // 授权状态
  const checkLogin = () => {
    setCheckingLogin(true);
    axios
      .get(`${API_BASE_URL}/settings`)
      .then((res) => setIntegration(res.data?.data))
      .catch(() => message.error("读取平台状态失败"))
      .finally(() => setCheckingLogin(false));
  };
  useEffect(checkLogin, []);

  // 线路随城市
  useEffect(() => {
    if (!criteria.city) return;
    setLines([]);
    setStations([]);
    metroService.getLines(criteria.city).then((res: any) => setLines(res?.data || []));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [criteria.city]);

  // 站点随线路联动（选了线路只列该线路上的站）
  useEffect(() => {
    if (!criteria.city) return;
    const selected = criteria.line_names;
    let cancelled = false;
    const load = async () => {
      if (!selected.length) {
        const res: any = await metroService.getStations(criteria.city);
        if (!cancelled)
          setStations(Array.from(new Set((res?.data || []).map((s: any) => s.name))) as string[]);
        return;
      }
      const results = await Promise.all(
        selected.map((line) => metroService.getStations(criteria.city, line))
      );
      if (cancelled) return;
      const names = new Set<string>();
      results.forEach((res: any) => (res?.data || []).forEach((s: any) => names.add(s.name)));
      setStations(Array.from(names));
      setCriteria((c) => {
        const kept = c.stations.filter((s) => names.has(s));
        return kept.length === c.stations.length ? c : { ...c, stations: kept };
      });
    };
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [criteria.city, criteria.line_names.join(",")]);

  // 轮询任务
  const poll = async (taskId: string) => {
    try {
      const data = await taskService.getTask(taskId, true);
      setTask(data);
      if (data.status === "done" || data.status === "failed") {
        setRunning(false);
        if (pollRef.current) {
          window.clearInterval(pollRef.current);
          pollRef.current = null;
        }
        const result = data.result;
        if (result?.data) {
          const ids = [...(result.data || []), ...(result.pendingLocation || [])].map(
            (m: any) => m.house_id
          );
          const pics: Record<string, string> = {};
          for (let i = 0; i < ids.length; i += 40) {
            try {
              const r = await axios.get(`${API_BASE_URL}/v3/houses/by-ids`, {
                params: { ids: ids.slice(i, i + 40).join(",") },
              });
              (r.data?.data || []).forEach((h: any) => {
                if (h?.id && h.pictures?.[0]) pics[h.id] = h.pictures[0];
              });
            } catch {
              break;
            }
          }
          setPictures(pics);
          message.success(`完成：符合 ${result.total ?? 0} 套`);
        }
      }
    } catch {
      /* 轮询失败下次再试 */
    }
  };

  const startCollect = async () => {
    if (!criteria.stations.length && !criteria.line_names.length) {
      message.warning("请至少选择一个地铁站或一条线路");
      return;
    }
    setRunning(true);
    setTask(null);
    try {
      const { taskId } = await taskService.startCollect(criteria);
      await poll(taskId);
      pollRef.current = window.setInterval(() => poll(taskId), 3000);
    } catch (e: any) {
      setRunning(false);
      message.error(e?.message || "启动失败");
    }
  };

  useEffect(() => () => {
    if (pollRef.current) window.clearInterval(pollRef.current);
  }, []);

  const result = task?.result;
  const list = tab === "precise" ? result?.data || [] : result?.pendingLocation || [];
  const withPic = (m: any) => ({ ...m, picture: pictures[m.house_id] });

  const currentCity = useMemo(
    () => cities.find((c) => c.name === criteria.city),
    [cities, criteria.city]
  );

  const canNext = useMemo(() => {
    // 城市没有地铁数据时挡在这一步，避免用户走到下一步却什么都选不了
    if (step === 0) return !!criteria.city && (currentCity?.stationCount ?? 0) > 0;
    if (step === 1) return true;
    if (step === 2) return criteria.stations.length > 0 || criteria.line_names.length > 0;
    return true;
  }, [step, criteria, currentCity]);

  const sourceBlock = integration?.sources?.filter((s) => s.enabled) || [];

  return (
    <BaseLayout>
      <Helmet>
        <title>搜索房源 · Findhome</title>
      </Helmet>

      <div style={{ maxWidth: 1360, margin: "0 auto", padding: "16px 16px 60px" }}>
        <Steps
          current={step}
          onChange={setStep}
          style={{ marginBottom: 20 }}
          items={[
            { title: "选择城市" },
            { title: "平台授权" },
            { title: "筛选条件" },
            { title: "采集结果" },
          ]}
        />

        {/* ============ ① 城市 ============ */}
        {step === 0 && (
          <Card title="先选择城市">
            <Row gutter={[16, 16]}>
              {cities.map((c) => (
                <Col xs={24} md={8} key={c.name}>
                  <Card
                    hoverable
                    onClick={() => patch({ city: c.name, stations: [], line_names: [] })}
                    style={{
                      borderColor: criteria.city === c.name ? "#00a3ca" : undefined,
                      borderWidth: criteria.city === c.name ? 2 : 1,
                    }}
                  >
                    <div style={{ fontSize: 20, fontWeight: 600 }}>{c.name}</div>
                    <div style={{ color: "#8c8c8c", fontSize: 13, marginTop: 6 }}>
                      已采集 {c.houseCount} 套房源 · {c.lineCount} 条线路 · {c.stationCount} 个站点
                    </div>
                    {c.stationCount === 0 && (
                      <Tag color="orange" style={{ marginTop: 8 }}>
                        暂无地铁数据，无法按站点搜索
                      </Tag>
                    )}
                  </Card>
                </Col>
              ))}
              {!cities.length && <Col span={24}><Empty description="暂无可用城市" /></Col>}
            </Row>
            {currentCity && currentCity.stationCount === 0 && (
              <Alert
                style={{ marginTop: 12 }}
                type="warning"
                showIcon
                message={`${currentCity.name} 暂无地铁线路数据`}
                description={`该城市已采集到 ${currentCity.houseCount} 套房源，但还没有地铁站点数据，无法按"地铁站 + 步行距离"筛选。如需支持请先导入该城市的地铁数据。`}
              />
            )}
            <div style={{ marginTop: 16 }}>
              <Button type="primary" disabled={!canNext} onClick={() => setStep(1)}>
                下一步：平台授权
              </Button>
            </div>
          </Card>
        )}

        {/* ============ ② 授权 ============ */}
        {step === 1 && (
          <Card
            title="平台授权状态"
            extra={
              <Button size="small" loading={checkingLogin} onClick={checkLogin}>
                重新检测
              </Button>
            }
          >
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message="采集前请确认各平台已登录"
              description={
                <>
                  闲鱼与小红书需要登录态（搜索接口要求页面签名，必须走真实浏览器）；
                  豆瓣登录后更稳定。未登录时仍会尝试，但大概率拿不到数据。
                  <br />
                  <Text code style={{ fontSize: 12 }}>
                    终端运行：python browser_daemon.py
                  </Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {" "}
                    打开浏览器扫码登录并保持窗口不关
                  </Text>
                </>
              }
            />
            <Descriptions column={1} bordered size="small">
              {sourceBlock.map((s) => (
                <Descriptions.Item key={s.key} label={s.name}>
                  <Space wrap>
                    <Tag color={s.cookieConfigured ? "green" : "orange"}>
                      {s.cookieConfigured ? "✅ 已登录" : "⚠️ 未检测到登录态"}
                    </Tag>
                    <Tag color={s.access === "browser" ? "purple" : "blue"}>
                      {s.access === "browser" ? "浏览器采集" : "直连接口"}
                    </Tag>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {s.note}
                    </Text>
                  </Space>
                </Descriptions.Item>
              ))}
            </Descriptions>
            {integration?.amap && (
              <Alert
                style={{ marginTop: 12 }}
                type={integration.amap.available ? "success" : "warning"}
                showIcon
                message={
                  integration.amap.available
                    ? "高德 Web 服务 Key 已配置，可计算真实步行距离"
                    : "未配置高德 Web 服务 Key，只能按直线距离筛选"
                }
              />
            )}
            <div style={{ marginTop: 16 }}>
              <Space>
                <Button onClick={() => setStep(0)}>上一步</Button>
                <Button type="primary" disabled={!canNext} onClick={() => setStep(2)}>
                  下一步：筛选条件
                </Button>
              </Space>
            </div>
          </Card>
        )}

        {/* ============ ③ 条件 ============ */}
        {step === 2 && (
          <Card title={`筛选条件（${criteria.city}）`}>
            <Row gutter={[16, 12]}>
              <Col xs={24} md={10}>
                <div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 4 }}>
                  地铁线路（选了线路，站点列表只保留该线路上的站）
                </div>
                <Select
                  mode="multiple"
                  allowClear
                  style={{ width: "100%" }}
                  placeholder={lines.length ? `可选 ${lines.length} 条线路` : "该城市暂无线路数据"}
                  value={criteria.line_names}
                  onChange={(v) => patch({ line_names: v })}
                  options={lines.map((l) => ({ label: l.name, value: l.name }))}
                  maxTagCount="responsive"
                />
              </Col>
              <Col xs={24} md={14}>
                <div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 4 }}>
                  地铁站（已选 {criteria.stations.length} 个
                  {criteria.line_names.length
                    ? `；当前只列 ${criteria.line_names.join("、")} 上的 ${stations.length} 个站`
                    : `；共 ${stations.length} 个站`}）
                </div>
                <Select
                  mode="multiple"
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  style={{ width: "100%" }}
                  placeholder="搜索并选择站点"
                  value={criteria.stations}
                  onChange={(v) => patch({ stations: v })}
                  options={stations.map((s) => ({ label: s, value: s }))}
                  maxTagCount="responsive"
                />
              </Col>
            </Row>

            <Alert
              style={{ marginTop: 12 }}
              type="warning"
              showIcon
              message={`实时采集较慢：每个站要搜 2 个关键词 × 所选平台。当前最多采集 ${criteria.max_stations} 个站，约需 ${Math.ceil(criteria.max_stations * criteria.sources.length * 2 * 0.25)} 分钟。`}
              description={
                <Space>
                  <span style={{ fontSize: 13 }}>每轮最多采集站点数：</span>
                  <InputNumber
                    min={1}
                    max={12}
                    value={criteria.max_stations}
                    onChange={(v) => patch({ max_stations: (v as number) || 6 })}
                    size="small"
                  />
                </Space>
              }
            />

            <Row gutter={[16, 12]} style={{ marginTop: 16 }}>
              <Col xs={24} md={10}>
                <div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 4 }}>预算（元/月）</div>
                <Space>
                  <InputNumber
                    placeholder="最低"
                    value={criteria.price_min ?? undefined}
                    onChange={(v) => patch({ price_min: (v as number) ?? null })}
                    style={{ width: 110 }}
                  />
                  <span>—</span>
                  <InputNumber
                    placeholder="最高"
                    value={criteria.price_max ?? undefined}
                    onChange={(v) => patch({ price_max: (v as number) ?? null })}
                    style={{ width: 110 }}
                  />
                </Space>
                <div style={{ marginTop: 8 }}>
                  <Space size={4} wrap>
                    {[[0, 1500], [1200, 2500], [1500, 3000], [2500, 4000]].map(([a, b]) => (
                      <Tag
                        key={`${a}-${b}`}
                        style={{ cursor: "pointer", margin: 0 }}
                        color={criteria.price_min === a && criteria.price_max === b ? "blue" : undefined}
                        onClick={() => patch({ price_min: a || null, price_max: b })}
                      >
                        {a === 0 ? `${b} 以下` : `${a}-${b}`}
                      </Tag>
                    ))}
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
                <div style={{ fontSize: 13, color: "#8c8c8c", margin: "10px 0 4px" }}>数据源</div>
                <Checkbox.Group
                  options={SOURCE_OPTIONS}
                  value={criteria.sources}
                  onChange={(v) => patch({ sources: v as string[] })}
                />
              </Col>
            </Row>

            <Row gutter={[16, 12]} style={{ marginTop: 16 }}>
              <Col xs={24} md={10}>
                <div style={{ fontSize: 13, color: "#8c8c8c" }}>
                  真实步行时间上限：<b style={{ color: "#00a3ca" }}>{criteria.max_walk_minutes} 分钟</b>
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
                <div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 6 }}>房源性质</div>
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
                    checked={criteria.listing_kinds.includes("direct")}
                    onChange={(e) =>
                      patch({
                        listing_kinds: e.target.checked
                          ? [...criteria.listing_kinds, "direct"]
                          : criteria.listing_kinds.filter((k) => k !== "direct"),
                      })
                    }
                  >
                    只看直接房东
                  </Checkbox>
                  <Checkbox
                    checked={criteria.poster_types.includes("individual")}
                    onChange={(e) =>
                      patch({
                        poster_types: e.target.checked ? ["individual"] : [],
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
                </Space>
              </Col>
            </Row>

            <div style={{ marginTop: 20 }}>
              <Space>
                <Button onClick={() => setStep(1)}>上一步</Button>
                <Button
                  type="primary"
                  size="large"
                  disabled={!canNext || running}
                  loading={running}
                  onClick={() => {
                    setStep(3);
                    startCollect();
                  }}
                >
                  开始采集并筛选
                </Button>
              </Space>
            </div>
          </Card>
        )}

        {/* ============ ④ 进度 / 结果 ============ */}
        {step === 3 && (
          <>
            <Card
              title="采集进度"
              extra={
                running ? (
                  <Button
                    size="small"
                    danger
                    onClick={async () => {
                      if (task?.taskId) {
                        await taskService.cancelTask(task.taskId);
                        message.info("已请求取消");
                      }
                    }}
                  >
                    取消
                  </Button>
                ) : (
                  <Button size="small" onClick={() => setStep(2)}>
                    改条件重来
                  </Button>
                )
              }
            >
              {!task && running && <Progress percent={0} status="active" />}
              {task && (
                <>
                  <Progress
                    percent={task.progress}
                    status={
                      task.status === "failed"
                        ? "exception"
                        : task.status === "done"
                          ? "success"
                          : "active"
                    }
                  />
                  <div style={{ marginTop: 8, color: "#595959" }}>
                    {task.status === "running" && `正在：${task.stageText}`}
                    {task.status === "done" && `完成，用时 ${task.elapsed} 秒`}
                    {task.status === "failed" && `失败：${task.error}`}
                  </div>
                  <div
                    style={{
                      marginTop: 12,
                      maxHeight: 180,
                      overflow: "auto",
                      background: "#fafafa",
                      borderRadius: 8,
                      padding: "10px 12px",
                      fontFamily: "monospace",
                      fontSize: 12,
                      lineHeight: "20px",
                      color: "#595959",
                    }}
                  >
                    {task.logs.map((l, i) => (
                      <div key={i}>{l}</div>
                    ))}
                  </div>
                </>
              )}
            </Card>

            {result && (
              <div style={{ marginTop: 16 }}>
                <Space size={20} wrap style={{ fontSize: 13, color: "#8c8c8c" }}>
                  <span>候选 {result.stats?.priceLayoutCandidates}</span>
                  <span>排除合租 {result.stats?.droppedShared}</span>
                  <span>排除求租帖 {result.stats?.droppedWanted}</span>
                  <span>直线达标 {result.stats?.withinStraight}</span>
                  <span style={{ color: "#fa541c", fontWeight: 600 }}>
                    精确符合 {result.stats?.matched}
                  </span>
                  <span>位置待确认 {result.stats?.pendingLocation}</span>
                </Space>

                <div style={{ marginTop: 12 }}>
                  <Segmented
                    value={tab}
                    onChange={(v) => setTab(v as "precise" | "pending")}
                    options={[
                      {
                        label: (
                          <span>
                            精确符合{" "}
                            <Badge count={result.stats?.matched ?? 0} overflowCount={999}
                                   style={{ backgroundColor: "#00a3ca" }} />
                          </span>
                        ),
                        value: "precise",
                      },
                      {
                        label: (
                          <span>
                            位置待确认{" "}
                            <Badge count={result.stats?.pendingLocation ?? 0} overflowCount={999}
                                   style={{ backgroundColor: "#bfbfbf" }} />
                          </span>
                        ),
                        value: "pending",
                      },
                    ]}
                  />
                </div>

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
                      {list.map((m: any) => (
                        <HouseCard key={`${m.house_id}-${m.nearest_station}`} item={withPic(m)} />
                      ))}
                    </Masonry>
                  )}
                </div>
              </div>
            )}

            {!task && !running && (
              <Empty style={{ padding: "60px 0" }} description="尚未开始采集" />
            )}
          </>
        )}
      </div>
    </BaseLayout>
  );
}
