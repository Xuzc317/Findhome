import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Collapse, InputNumber, message, Select, Tag, Tooltip } from "antd";
import classNames from "classnames";
import { useSearchParams } from "react-router-dom";
import styles from "./styles.module.css";
import { HomeFilterOptions } from "@/constant";
import { useCities } from "@/hook/cities";
import { geoService, metroService } from "@/services/metro";

export interface FilterInfo {
  city: string;
  source?: string;
  fromPrice?: number;
  toPrice?: number;
  district?: string;
  keyword?: string;
  keywordExclude?: string;
  rentType?: number;
  rentTypes?: string;
  intervalDay?: number;
  maxAgentScore?: number;
  minConfidenceScore?: number;
  layouts?: string;
  stationId?: string;
  walkMaxM?: number;
}

/** 预算快捷档 */
const BUDGET_PRESETS = [
  { label: "≤3000", from: undefined, to: 3000 },
  { label: "3000-5000", from: 3000, to: 5000 },
  { label: "5000-8000", from: 5000, to: 8000 },
  { label: "8000-12000", from: 8000, to: 12000 },
  { label: "≥12000", from: 12000, to: undefined },
];

/** 步行距离档位 */
const WALK_PRESETS = [
  { label: "300m 内", value: 300 },
  { label: "500m 内", value: 500 },
  { label: "800m 内", value: 800 },
  { label: "1.2km 内", value: 1200 },
  { label: "不限", value: undefined },
];

/** 房型（与后端 layout_key 对应；口径：按卧室数） */
const LAYOUT_OPTIONS = [
  { key: "studio", label: "单间" },
  { key: "1b1l", label: "1房1厅" },
  { key: "2b1l", label: "2房1厅" },
  { key: "3b1l", label: "3房1厅" },
  { key: "4b+", label: "4房及以上" },
];

const RENT_TYPE_OPTIONS = [
  { key: "3", label: "整租" },
  { key: "1", label: "合租" },
  { key: "4", label: "公寓" },
];

const RISK_OPTIONS = [
  { label: "不限", maxAgentScore: undefined, minConfidenceScore: undefined },
  { label: "低中介嫌疑", maxAgentScore: 30, minConfidenceScore: undefined },
  { label: "可信度≥70", maxAgentScore: undefined, minConfidenceScore: 70 },
];

export function HouseFilter(props: {
  onSearch: (info: FilterInfo) => void;
  resultCount?: number;
  loading?: boolean;
}) {
  const cities = useCities();
  const [searchParams, setSearchParams] = useSearchParams();

  const city = searchParams.get("city") || "深圳";

  // ---- 地铁数据 ----
  const [lines, setLines] = useState<MetroLine[]>([]);
  const [stations, setStations] = useState<MetroStation[]>([]);
  const [activeLine, setActiveLine] = useState<string>("all");
  const [metroLoading, setMetroLoading] = useState(false);
  const [coverage, setCoverage] = useState<StationCoverage | null>(null);
  const [computing, setComputing] = useState(false);
  const [metroReady, setMetroReady] = useState(true);

  // ---- 预算本地态 ----
  const [fromPrice, setFromPrice] = useState<string>("");
  const [toPrice, setToPrice] = useState<string>("");
  const [excludeKeyword, setExcludeKeyword] = useState<string>("");

  const stationId = searchParams.get("stationId") || "";
  const walkMaxM = searchParams.get("walkMaxM") || "";
  const layouts = searchParams.get("layouts") || "";
  const rentTypes = searchParams.get("rentTypes") ?? "3"; // 默认只看整租
  const intervalDay = searchParams.get("intervalDay") || "";
  const maxAgentScore = searchParams.get("maxAgentScore") || "";
  const minConfidenceScore = searchParams.get("minConfidenceScore") || "";
  const source = searchParams.get("source") || "all";

  /** 只改动指定字段，其余条件保留 */
  const applyParams = useCallback(
    (patch: Record<string, string | number | undefined>) => {
      const params: Record<string, string> = Object.fromEntries(
        searchParams.entries(),
      );
      Object.entries(patch).forEach(([key, value]) => {
        if (value === undefined || value === "" || value === null) {
          delete params[key];
        } else {
          params[key] = String(value);
        }
      });
      setSearchParams(params);
    },
    [searchParams, setSearchParams],
  );

  // 同步输入态 ↔ URL
  useEffect(() => {
    setFromPrice(searchParams.get("fromPrice") || "");
    setToPrice(searchParams.get("toPrice") || "");
    setExcludeKeyword(searchParams.get("keywordExclude") || "");
  }, [searchParams]);

  // 通知父组件重新查询
  useEffect(() => {
    const raw: Record<string, any> = Object.fromEntries(searchParams.entries());
    const int = (v: any) => (v === undefined || v === "" ? undefined : parseInt(v));
    const info: FilterInfo = {
      city: raw.city || "深圳",
      source: raw.source,
      fromPrice: int(raw.fromPrice),
      toPrice: int(raw.toPrice),
      district: raw.district,
      keyword: raw.keyword,
      keywordExclude: raw.keywordExclude,
      rentType: int(raw.rentType),
      rentTypes: raw.rentTypes ?? "3",
      intervalDay: int(raw.intervalDay),
      maxAgentScore: int(raw.maxAgentScore),
      minConfidenceScore: int(raw.minConfidenceScore),
      layouts: raw.layouts,
      stationId: raw.stationId,
      walkMaxM: int(raw.walkMaxM),
    };
    props.onSearch(info);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // 加载线路
  useEffect(() => {
    let alive = true;
    setMetroLoading(true);
    metroService
      .getLines(city)
      .then((res: any) => {
        if (!alive) return;
        setLines(res.data || []);
        setMetroReady((res.data || []).length > 0);
      })
      .catch(() => {
        if (alive) setMetroReady(false);
      })
      .finally(() => alive && setMetroLoading(false));
    return () => {
      alive = false;
    };
  }, [city]);

  // 加载站点
  useEffect(() => {
    let alive = true;
    metroService
      .getStations(city, activeLine)
      .then((res: any) => {
        if (alive) setStations(res.data || []);
      })
      .catch(() => alive && setStations([]));
    return () => {
      alive = false;
    };
  }, [city, activeLine]);

  // 选中站点后查覆盖情况
  useEffect(() => {
    if (!stationId) {
      setCoverage(null);
      return;
    }
    let alive = true;
    metroService
      .getCoverage(stationId)
      .then((res) => alive && setCoverage(res))
      .catch(() => alive && setCoverage(null));
    return () => {
      alive = false;
    };
  }, [stationId]);

  const selectedStation = useMemo(
    () => stations.find((s) => s.id === stationId),
    [stations, stationId],
  );

  const stationOptions = useMemo(
    () =>
      stations.map((station) => ({
        value: station.id,
        label: station.name,
        station,
      })),
    [stations],
  );

  /** 线路颜色小圆点 */
  const lineDot = (color?: string | null) => (
    <span
      className={styles.lineDot}
      style={{ backgroundColor: color || "#999" }}
    />
  );

  const toggleLayout = (key: string) => {
    const current = layouts ? layouts.split(",").filter(Boolean) : [];
    const next = current.includes(key)
      ? current.filter((k) => k !== key)
      : [...current, key];
    applyParams({ layouts: next.join(",") || undefined });
  };

  const activeLayouts = layouts ? layouts.split(",").filter(Boolean) : [];
  const activeRentTypes = rentTypes ? rentTypes.split(",").filter(Boolean) : [];

  const applyBudget = (from?: number, to?: number) => {
    applyParams({ fromPrice: from ?? undefined, toPrice: to ?? undefined });
    setFromPrice(from ? String(from) : "");
    setToPrice(to ? String(to) : "");
  };

  const clearAll = () => {
    setSearchParams({ city, rentTypes: "3" });
    setActiveLine("all");
  };

  /** 计算步行距离（可反复点击，增量续算） */
  const computeDistances = async () => {
    if (!stationId) return;
    setComputing(true);
    try {
      const result = await metroService.computeDistances(stationId, {
        limit: 200,
        onlyMissing: true,
        maxCalls: 400,
      });
      const data = (result as any).data || result;
      if (data?.success === false) {
        message.warning(data.message || "无法计算步行距离");
      } else {
        message.success(
          `已计算 ${data?.computed ?? 0} 条步行距离` +
            (data?.noRoute ? `，${data.noRoute} 条无法步行到达` : ""),
        );
      }
      const cov = await metroService.getCoverage(stationId);
      setCoverage(cov);
      applyParams({ _refresh: Date.now() });
    } catch (error: any) {
      message.error(error?.message || "计算失败，请检查高德 Key 配置");
    } finally {
      setComputing(false);
    }
  };

  const cityItem = cities.find((item) => item.city === city);

  return (
    <aside className={styles.panel}>
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>筛选条件</span>
        <span className={styles.resultCount}>
          {props.loading ? "查询中…" : `${props.resultCount ?? 0} 套`}
        </span>
      </div>

      <div className={styles.scrollArea}>
        {/* ==================== 地铁选址 ==================== */}
        <section className={styles.section}>
          <div className={styles.sectionTitle}>
            <span>地铁选址</span>
            {selectedStation && (
              <Tag color="cyan" className="mr-0">
                {selectedStation.name}
                {walkMaxM ? ` · ${walkMaxM}m内` : ""}
              </Tag>
            )}
          </div>

          {!metroReady && !metroLoading ? (
            <div className={styles.hint}>
              暂无 {city} 的地铁数据。可执行
              <code> python crawl.py metro --city {city} </code>
              导入。
            </div>
          ) : (
            <>
              <div className={styles.chipRow}>
                <span
                  className={classNames(styles.chip, {
                    [styles.chipActive]: activeLine === "all",
                  })}
                  onClick={() => setActiveLine("all")}
                >
                  全部线路
                </span>
                {lines.map((line) => (
                  <span
                    key={line.id}
                    className={classNames(styles.chip, styles.chipWithDot, {
                      [styles.chipActive]: activeLine === line.name,
                    })}
                    onClick={() => setActiveLine(line.name)}
                    title={`${line.name}${
                      line.alias ? ` (${line.alias})` : ""
                    } · ${line.stationCount} 站`}
                  >
                    {lineDot(line.color)}
                    {line.name}
                  </span>
                ))}
              </div>

              <Select
                className={styles.stationSelect}
                placeholder="搜索并选择地铁站"
                showSearch
                allowClear
                loading={metroLoading}
                value={stationId || undefined}
                onChange={(value) => {
                  const st = stations.find((s) => s.id === value);
                  applyParams({
                    stationId: value || undefined,
                    stationName: st?.name,
                  });
                }}
                filterOption={(input, option: any) =>
                  (option?.label ?? "").includes(input)
                }
                options={stationOptions.map((opt) => ({
                  value: opt.value,
                  label: opt.label,
                }))}
                notFoundContent={metroLoading ? "加载中…" : "没有匹配的站点"}
              />

              {selectedStation && (
                <>
                  <div className={styles.subLabel}>步行距离（真实路径）</div>
                  <div className={styles.chipRow}>
                    {WALK_PRESETS.map((preset) => (
                      <span
                        key={preset.label}
                        className={classNames(styles.chip, {
                          [styles.chipActive]:
                            (preset.value === undefined && !walkMaxM) ||
                            String(preset.value) === walkMaxM,
                        })}
                        onClick={() =>
                          applyParams({ walkMaxM: preset.value })
                        }
                      >
                        {preset.label}
                      </span>
                    ))}
                  </div>

                  <div className={styles.coverageRow}>
                    <span className={styles.coverageText}>
                      {coverage
                        ? `已算 ${coverage.ok} 条${
                            coverage.noRoute ? `，${coverage.noRoute} 条不可步行` : ""
                          }`
                        : "尚未计算该站的步行距离"}
                    </span>
                    <Button
                      size="small"
                      type="primary"
                      ghost
                      loading={computing}
                      onClick={computeDistances}
                    >
                      计算
                    </Button>
                  </div>
                  {coverage && coverage.ok === 0 && (
                    <div className={styles.hint}>
                      点「计算」调用高德步行路径，算出房源到该站的真实步行距离。
                      线上房源若还没有坐标，需要先在「更多筛选 → 数据准备」里定位。
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </section>

        {/* ==================== 预算 ==================== */}
        <section className={styles.section}>
          <div className={styles.sectionTitle}>预算（元/月）</div>
          <div className={styles.priceRow}>
            <InputNumber
              className={styles.priceInput}
              placeholder="最低"
              min={0}
              value={fromPrice ? Number(fromPrice) : null}
              onChange={(v) => setFromPrice(v ? String(v) : "")}
              onPressEnter={() =>
                applyBudget(
                  fromPrice ? Number(fromPrice) : undefined,
                  toPrice ? Number(toPrice) : undefined,
                )
              }
            />
            <span className={styles.priceDash}>—</span>
            <InputNumber
              className={styles.priceInput}
              placeholder="最高"
              min={0}
              value={toPrice ? Number(toPrice) : null}
              onChange={(v) => setToPrice(v ? String(v) : "")}
              onPressEnter={() =>
                applyBudget(
                  fromPrice ? Number(fromPrice) : undefined,
                  toPrice ? Number(toPrice) : undefined,
                )
              }
            />
            <Button
              size="small"
              type="primary"
              onClick={() =>
                applyBudget(
                  fromPrice ? Number(fromPrice) : undefined,
                  toPrice ? Number(toPrice) : undefined,
                )
              }
            >
              确定
            </Button>
          </div>
          <div className={styles.chipRow}>
            {BUDGET_PRESETS.map((preset) => {
              const active =
                String(preset.from ?? "") === (searchParams.get("fromPrice") || "") &&
                String(preset.to ?? "") === (searchParams.get("toPrice") || "");
              return (
                <span
                  key={preset.label}
                  className={classNames(styles.chip, {
                    [styles.chipActive]: active,
                  })}
                  onClick={() => applyBudget(preset.from, preset.to)}
                >
                  {preset.label}
                </span>
              );
            })}
          </div>
        </section>

        {/* ==================== 房型 ==================== */}
        <section className={styles.section}>
          <div className={styles.sectionTitle}>房型</div>
          <div className={styles.chipRow}>
            {LAYOUT_OPTIONS.map((item) => (
              <span
                key={item.key}
                className={classNames(styles.chip, {
                  [styles.chipActive]: activeLayouts.includes(item.key),
                })}
                onClick={() => toggleLayout(item.key)}
              >
                {item.label}
              </span>
            ))}
          </div>
          <div className={styles.hint}>可多选；未标注房型的房源不会被选中</div>
        </section>

        {/* ==================== 出租类型 ==================== */}
        <section className={styles.section}>
          <div className={styles.sectionTitle}>出租类型</div>
          <div className={styles.chipRow}>
            <span
              className={classNames(styles.chip, {
                [styles.chipActive]: activeRentTypes.length === 0,
              })}
              onClick={() => applyParams({ rentTypes: undefined })}
            >
              不限
            </span>
            {RENT_TYPE_OPTIONS.map((item) => (
              <span
                key={item.key}
                className={classNames(styles.chip, {
                  [styles.chipActive]: activeRentTypes.includes(item.key),
                })}
                onClick={() => {
                  const next = activeRentTypes.includes(item.key)
                    ? activeRentTypes.filter((k) => k !== item.key)
                    : [...activeRentTypes, item.key];
                  applyParams({ rentTypes: next.join(",") || undefined });
                }}
              >
                {item.label}
              </span>
            ))}
          </div>
          <div className={styles.hint}>
            默认只看整租；勾选「合租」可一并查看
          </div>
        </section>

        {/* ==================== 更多筛选 ==================== */}
        <Collapse
          ghost
          size="small"
          items={[
            {
              key: "more",
              label: <span className={styles.sectionTitle}>更多筛选</span>,
              children: (
                <div className={styles.moreArea}>
                  <div className={styles.subLabel}>发布时间</div>
                  <div className={styles.chipRow}>
                    {HomeFilterOptions.times.map((item) => (
                      <span
                        key={item.value}
                        className={classNames(styles.chip, {
                          [styles.chipActive]:
                            item.value === -1
                              ? !intervalDay
                              : intervalDay === String(item.value),
                        })}
                        onClick={() =>
                          applyParams({
                            intervalDay:
                              item.value === -1 ? undefined : item.value,
                          })
                        }
                      >
                        {item.label}
                      </span>
                    ))}
                  </div>

                  <div className={styles.subLabel}>数据源</div>
                  <div className={styles.chipRow}>
                    <span
                      className={classNames(styles.chip, {
                        [styles.chipActive]: source === "all",
                      })}
                      onClick={() => applyParams({ source: undefined })}
                    >
                      全部
                    </span>
                    {cityItem?.sources
                      .filter((s) => s.source !== "all")
                      .map((s) => (
                        <span
                          key={s.source}
                          className={classNames(styles.chip, {
                            [styles.chipActive]: source === s.source,
                          })}
                          onClick={() => applyParams({ source: s.source })}
                        >
                          {s.displaySource}
                        </span>
                      ))}
                  </div>

                  <div className={styles.subLabel}>风险</div>
                  <div className={styles.chipRow}>
                    {RISK_OPTIONS.map((item) => {
                      const active = item.maxAgentScore
                        ? maxAgentScore === String(item.maxAgentScore)
                        : item.minConfidenceScore
                        ? minConfidenceScore === String(item.minConfidenceScore)
                        : !maxAgentScore && !minConfidenceScore;
                      return (
                        <span
                          key={item.label}
                          className={classNames(styles.chip, {
                            [styles.chipActive]: active,
                          })}
                          onClick={() =>
                            applyParams({
                              maxAgentScore: item.maxAgentScore,
                              minConfidenceScore: item.minConfidenceScore,
                            })
                          }
                        >
                          {item.label}
                        </span>
                      );
                    })}
                  </div>

                  <div className={styles.subLabel}>排除关键词</div>
                  <div className={styles.priceRow}>
                    <input
                      className={styles.textInput}
                      placeholder="如：中介 公寓"
                      value={excludeKeyword}
                      onChange={(e) => setExcludeKeyword(e.target.value)}
                      onKeyUp={(e) =>
                        e.key === "Enter" &&
                        applyParams({
                          keywordExclude: excludeKeyword || undefined,
                        })
                      }
                    />
                    <Button
                      size="small"
                      onClick={() =>
                        applyParams({
                          keywordExclude: excludeKeyword || undefined,
                        })
                      }
                    >
                      应用
                    </Button>
                  </div>

                  <DataPrep city={city} />
                </div>
              ),
            },
          ]}
        />

        <div className={styles.footer}>
          <Button block onClick={clearAll}>
            清空全部条件
          </Button>
        </div>
      </div>
    </aside>
  );
}

/** 数据准备：定位覆盖率 + 一键推断坐标 + 房型回填 */
function DataPrep(props: { city: string }) {
  const [stats, setStats] = useState<GeoStats | null>(null);
  const [geoConfig, setGeoConfig] = useState<GeoConfig | null>(null);
  const [busy, setBusy] = useState<"locate" | "layout" | null>(null);

  const refresh = useCallback(() => {
    geoService.getStats(props.city).then(setStats).catch(() => undefined);
    geoService.getConfig().then(setGeoConfig).catch(() => undefined);
  }, [props.city]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runLocate = async () => {
    setBusy("locate");
    try {
      const result: any = await geoService.locate({
        city: props.city,
        limit: 10,
        onlyMissing: true,
        useLlm: true,
      });
      if (result?.success === false) {
        message.warning(result.message || "无法推断位置");
      } else {
        const d = result.data || {};
        message.success(
          `本轮定位 ${d.located ?? 0} 条，失败 ${d.failed ?? 0} 条` +
            `（高德调用 ${d.amapCalls ?? 0} 次）`,
        );
      }
      refresh();
    } catch (error: any) {
      message.error(error?.message || "定位失败");
    } finally {
      setBusy(null);
    }
  };

  const runLayout = async () => {
    setBusy("layout");
    try {
      const result: any = await geoService.backfillLayout();
      message.success(`房型回填完成：${result?.data?.updated ?? 0} 条`);
      refresh();
    } catch (error: any) {
      message.error(error?.message || "回填失败");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={styles.dataPrep}>
      <div className={styles.subLabel}>数据准备</div>
      {!geoConfig?.amap.available && (
        <div className={styles.warnBox}>
          未配置高德「Web服务」Key：无法定位房源、无法算步行距离。
          请在 .env 填 <code>AMAP_WEB_KEY</code>。
        </div>
      )}
      {geoConfig?.amap.available && !geoConfig.llm.active && (
        <div className={styles.hint}>
          大模型未配置：仅用规则解析位置与房型（可填 DEEPSEEK_API_KEY 或
          DOUBAO_API_KEY 提升准确率）
        </div>
      )}

      {stats && (
        <div className={styles.statsBox}>
          <div>
            已定位 <b>{stats.withCoord}</b> / {stats.total} 条（
            {stats.coveragePercent}%）
          </div>
          <div className={styles.statsSub}>
            含坐标来源：
            {Object.entries(stats.bySource).length
              ? Object.entries(stats.bySource)
                  .map(([k, v]) => `${k} ${v}`)
                  .join(" / ")
              : "暂无"}
          </div>
          <div className={styles.statsSub}>
            已缓存步行距离 {stats.stationDistancesCached} 条
          </div>
        </div>
      )}

      <div className={styles.prepButtons}>
        <Tooltip title="每次 10 条，可反复点击增量推进">
          <Button
            size="small"
            loading={busy === "locate"}
            disabled={!geoConfig?.amap.available}
            onClick={runLocate}
          >
            推断房源坐标
          </Button>
        </Tooltip>
        <Button size="small" loading={busy === "layout"} onClick={runLayout}>
          回填房型
        </Button>
        <Button size="small" type="link" onClick={refresh}>
          刷新
        </Button>
      </div>
    </div>
  );
}
