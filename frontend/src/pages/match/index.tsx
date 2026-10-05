import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Empty,
  Segmented,
  Select,
  Skeleton,
  Spin,
  Tooltip,
} from "antd";
import { Helmet } from "react-helmet";
import { HouseCard } from "@/components/house-card";
import { HouseMark } from "@/services/mark";
import Masonry from "react-masonry-css";
import BaseLayout from "@/components/layout";
import {
  MatchService,
  MatchedHouse,
  MatchResult,
  ProfileSummary,
} from "@/services/match";
import { useEffect as useEffectCols, useState as useStateCols } from "react";

/** 本页没有左侧筛选栏，所以列数按整屏宽度算（不能用列表页那个扣掉 380px 的 hook） */
function useColumns() {
  const [cols, setCols] = useStateCols(4);
  useEffectCols(() => {
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

const service = new MatchService();

const SOURCE_LABEL: Record<string, string> = {
  xianyu: "闲鱼",
  xiaohongshu: "小红书",
  douban: "豆瓣",
  beike: "贝壳",
};

/** 房源性质：转租是租客自己要走了，图片/价格通常真实，中介基本不做这类 */
export default function MatchPage() {
  const columns = useColumns();
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [profile, setProfile] = useState("longhua");
  const [result, setResult] = useState<MatchResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"precise" | "pending">("precise");
  const [marks, setMarks] = useState<Record<string, HouseMark>>({});
  const [stationFilter, setStationFilter] = useState<string[]>([]);
  const [sourceFilter, setSourceFilter] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState<"walk" | "price" | "newness">("walk");
  const [posterFilter, setPosterFilter] = useState<"all" | "individual" | "agency">(
    "all"
  );
  const [kindFilter, setKindFilter] = useState<"all" | "sublet" | "direct">("all");

  useEffect(() => {
    service
      .listProfiles()
      .then((list) => {
        setProfiles(list);
        if (list.length && !list.some((p) => p.name === profile)) {
          setProfile(list[0].name);
        }
      })
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    service
      .run(profile, true)
      .then(async (res) => {
        if (cancelled) return;
        const ids = [...(res.data || []), ...(res.pendingLocation || [])].map(
          (m) => m.house_id
        );
        const pics = await service.fetchPictures(ids);
        if (cancelled) return;
        const fill = (list: MatchedHouse[]) =>
          list.map((m) => ({ ...m, picture: pics[m.house_id] }));
        setResult({
          ...res,
          data: fill(res.data || []),
          pendingLocation: fill(res.pendingLocation || []),
        });
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "匹配失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [profile]);

  const currentProfile = useMemo(
    () => profiles.find((p) => p.name === profile)?.profile,
    [profiles, profile]
  );
  const rawList =
    tab === "precise" ? result?.data || [] : result?.pendingLocation || [];

  /** 可选的地铁站 / 平台（按当前 Tab 里实际出现的选项生成，避免选了没结果） */
  const stationOptions = useMemo(() => {
    const counter = new Map<string, number>();
    rawList.forEach((m) =>
      counter.set(m.nearest_station, (counter.get(m.nearest_station) || 0) + 1)
    );
    return [...counter.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({ label: `${name}（${count}）`, value: name }));
  }, [rawList]);

  const sourceOptions = useMemo(() => {
    const counter = new Map<string, number>();
    rawList.forEach((m) => counter.set(m.source, (counter.get(m.source) || 0) + 1));
    return [...counter.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([src, count]) => ({
        label: `${SOURCE_LABEL[src] || src}（${count}）`,
        value: src,
      }));
  }, [rawList]);

  const list = useMemo(() => {
    const filtered = rawList.filter(
      (m) =>
        (stationFilter.length === 0 || stationFilter.includes(m.nearest_station)) &&
        (sourceFilter.length === 0 || sourceFilter.includes(m.source)) &&
        (posterFilter === "all" || m.poster_type === posterFilter) &&
        (kindFilter === "all" || m.listing_kind === kindFilter)
    );
    const sorted = [...filtered];
    if (sortBy === "walk") {
      sorted.sort(
        (a, b) =>
          (a.walk_minutes ?? 999) - (b.walk_minutes ?? 999) ||
          a.straight_m - b.straight_m
      );
    } else if (sortBy === "price") {
      sorted.sort((a, b) => (a.price ?? 99999) - (b.price ?? 99999));
    } else {
      sorted.sort((a, b) => b.newness_score - a.newness_score);
    }
    return sorted;
  }, [rawList, stationFilter, sourceFilter, sortBy, posterFilter, kindFilter]);

  return (
    <BaseLayout>
      <Helmet>
        <title>保存的搜索 · Findhome</title>
      </Helmet>

      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "16px 16px 60px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h2 style={{ margin: 0, fontSize: 20 }}>保存的搜索</h2>
          {profiles.length > 1 && (
            <Segmented
              options={profiles.map((p) => ({ label: p.name, value: p.name }))}
              value={profile}
              onChange={(v) => setProfile(String(v))}
            />
          )}
          {loading && <Spin size="small" />}
        </div>

        {currentProfile && (
          <div
            style={{
              marginTop: 12,
              padding: "12px 16px",
              background: "#f6fbfd",
              border: "1px solid #e6f4f8",
              borderRadius: 10,
              fontSize: 13,
              lineHeight: "22px",
              color: "#595959",
            }}
          >
            <b>{currentProfile.city}</b> ·{" "}
            {currentProfile.stations.join("、")}
            <br />
            预算 <b>{currentProfile.price_min}–{currentProfile.price_max}</b> 元/月 ·
            直线 ≤ {currentProfile.max_straight_m}m 且真实步行 ≤{" "}
            {currentProfile.max_walk_minutes} 分钟 · 只要整租 · 已排除合租与求租帖
          </div>
        )}

        <Alert
          type="warning"
          showIcon
          style={{ marginTop: 12 }}
          message="房源图由发布者上传，可能是宣传图，不等于实际房间"
          description="用户实测：联系中介后被告知图片是宣传图。批量发布者（🏢 疑似中介）尤其如此——这类账号一次挂几十上百套，常用统一装修图。建议先要实拍视频，或到现场核对。"
        />

        {error && (
          <Alert type="error" showIcon style={{ marginTop: 16 }} message={error} />
        )}

        {result?.stats && (
          <div
            style={{
              marginTop: 16,
              display: "flex",
              gap: 24,
              flexWrap: "wrap",
              fontSize: 13,
              color: "#8c8c8c",
            }}
          >
            <span>价格房型候选 {result.stats.priceLayoutCandidates}</span>
            <span>排除合租 {result.stats.droppedShared}</span>
            <span>排除求租帖 {result.stats.droppedWanted}</span>
            <span>直线达标 {result.stats.withinStraight}</span>
            <span style={{ color: "#fa541c", fontWeight: 600 }}>
              精确符合 {result.stats.matched}
            </span>
            <span>位置待确认 {result.stats.pendingLocation}</span>
          </div>
        )}

        {result?.stats?.amapKeyMissing && (
          <Alert
            type="warning"
            showIcon
            style={{ marginTop: 12 }}
            message="未配置高德 Web 服务 Key，无法计算真实步行距离"
          />
        )}

        <div style={{ marginTop: 16 }}>
          <Segmented
            value={tab}
            onChange={(v) => setTab(v as "precise" | "pending")}
            options={[
              {
                label: (
                  <span>
                    精确符合{" "}
                    <Badge
                      count={result?.stats?.matched ?? 0}
                      overflowCount={999}
                      style={{ backgroundColor: "#00a3ca" }}
                    />
                  </span>
                ),
                value: "precise",
              },
              {
                label: (
                  <span>
                    位置待确认{" "}
                    <Badge
                      count={result?.stats?.pendingLocation ?? 0}
                      overflowCount={999}
                      style={{ backgroundColor: "#bfbfbf" }}
                    />
                  </span>
                ),
                value: "pending",
              },
            ]}
          />
        </div>

        <div
          style={{
            marginTop: 12,
            display: "flex",
            gap: 12,
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          <Select
            mode="multiple"
            allowClear
            placeholder="按地铁站筛选"
            style={{ minWidth: 260, maxWidth: 520, flex: "1 1 260px" }}
            value={stationFilter}
            onChange={setStationFilter}
            options={stationOptions}
            maxTagCount="responsive"
          />
          <Select
            mode="multiple"
            allowClear
            placeholder="按平台筛选"
            style={{ minWidth: 180, maxWidth: 320, flex: "0 1 200px" }}
            value={sourceFilter}
            onChange={setSourceFilter}
            options={sourceOptions}
            maxTagCount="responsive"
          />
          <Segmented
            value={kindFilter}
            onChange={(v) => setKindFilter(v as "all" | "sublet" | "direct")}
            options={[
              { label: "全部类型", value: "all" },
              { label: "🔑 转租", value: "sublet" },
              { label: "直接房东", value: "direct" },
            ]}
          />
          <Segmented
            value={posterFilter}
            onChange={(v) => setPosterFilter(v as "all" | "individual" | "agency")}
            options={[
              { label: "全部发布者", value: "all" },
              { label: "👤 个人房东", value: "individual" },
              { label: "🏢 疑似中介", value: "agency" },
            ]}
          />
          <Tooltip title="平台搜索结果不提供发布时间，所以这里按「房况新旧分」排序（装修/新上/首次出租等信号），不是发布时间。想按发布时间需要逐条打开详情页抓取。">
            <Segmented
            value={sortBy}
            onChange={(v) => setSortBy(v as "walk" | "price" | "newness")}
            options={[
              { label: "步行最短", value: "walk" },
              { label: "价格最低", value: "price" },
              { label: "房况较新", value: "newness" },
            ]}
            />
          </Tooltip>
          {(stationFilter.length > 0 ||
            sourceFilter.length > 0 ||
            kindFilter !== "all" ||
            posterFilter !== "all") && (
            <Button
              type="link"
              size="small"
              onClick={() => {
                setStationFilter([]);
                setSourceFilter([]);
                setKindFilter("all");
                setPosterFilter("all");
              }}
            >
              清除筛选
            </Button>
          )}
          <span style={{ fontSize: 13, color: "#8c8c8c" }}>
            显示 {list.length} / {rawList.length} 条
          </span>
        </div>

        {tab === "pending" && (
          <Alert
            type="info"
            showIcon
            style={{ marginTop: 12 }}
            message="这些房源只写了「某地铁站附近」，没有小区名"
            description="不能用站点坐标冒充房源坐标（那会把距离算成 0 米）。价格和房型都符合，距离需要你点开原帖自行确认。"
          />
        )}

        <div style={{ marginTop: 16 }}>
          {loading ? (
            <div style={{ display: "flex", gap: 16 }}>
              {[1, 2, 3].map((i) => (
                <div key={i} style={{ flex: 1 }}>
                  <Skeleton.Image active style={{ width: "100%", height: 180 }} />
                  <Skeleton active paragraph={{ rows: 3 }} style={{ marginTop: 12 }} />
                </div>
              ))}
            </div>
          ) : list.length === 0 ? (
            <Empty description="没有符合条件的房源" style={{ padding: "60px 0" }} />
          ) : (
            <Masonry
              breakpointCols={columns}
              className="my-masonry-grid"
              columnClassName="my-masonry-grid_column"
            >
              {list.map((item) => (
                <HouseCard
                  key={`${item.house_id}-${item.nearest_station}`}
                  item={item}
                  mark={marks[item.house_id]}
                  onMarkChange={(next) =>
                    setMarks((prev) => {
                      const copy = { ...prev };
                      if (next) copy[item.house_id] = next;
                      else delete copy[item.house_id];
                      return copy;
                    })
                  }
                />
              ))}
            </Masonry>
          )}
        </div>
      </div>
    </BaseLayout>
  );
}
