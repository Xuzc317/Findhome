import { useEffect, useMemo, useState } from "react";
import { Alert, Badge, Empty, Segmented, Skeleton, Spin, Tag, Tooltip } from "antd";
import { Helmet } from "react-helmet";
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

/** 电梯状态的展示：事实与推断分开展示，未标注 ≠ 没有 */
function ElevatorTag({ item }: { item: MatchedHouse }) {
  if (item.elevator === true) {
    return (
      <Tooltip title={`原文依据：${item.elevator_evidence || "—"}`}>
        <Tag color="green" style={{ margin: 0, fontSize: 11 }}>
          ✅ 电梯
        </Tag>
      </Tooltip>
    );
  }
  if (item.elevator === false) {
    return (
      <Tooltip title={`原文依据：${item.elevator_evidence || "—"}`}>
        <Tag color="red" style={{ margin: 0, fontSize: 11 }}>
          ❌ 无电梯
        </Tag>
      </Tooltip>
    );
  }
  return (
    <Tooltip title={item.elevator_hint || "平台没写电梯，需自行确认（未标注不等于没有）"}>
      <Tag style={{ margin: 0, fontSize: 11 }}>❓ 电梯未标注</Tag>
    </Tooltip>
  );
}

function MatchCard({ item }: { item: MatchedHouse }) {
  const walkText =
    item.walk_minutes != null
      ? `🚇 步行 ${item.walk_minutes} 分钟 · ${item.walk_m}m`
      : item.walk_status === "位置待确认"
        ? "📍 仅知在站附近"
        : "步行未计算";

  return (
    <div
      style={{
        marginBottom: 20,
        borderRadius: 12,
        border: "1px solid #f0f0f0",
        overflow: "hidden",
        cursor: "pointer",
        background: "#fff",
        transition: "all .18s",
      }}
      onClick={() => window.open(`/houses/${item.house_id}`)}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = "0 6px 20px rgba(0,0,0,.08)";
        e.currentTarget.style.transform = "translateY(-2px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "none";
        e.currentTarget.style.transform = "none";
      }}
    >
      <div style={{ position: "relative", background: "#f5f5f5", height: 180 }}>
        {item.picture ? (
          <img
            src={item.picture}
            alt={item.title}
            loading="lazy"
            referrerPolicy="no-referrer"
            style={{ width: "100%", height: 180, objectFit: "cover", display: "block" }}
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <div
            style={{
              height: 180,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#bfbfbf",
              fontSize: 13,
            }}
          >
            该房源未提供图片
          </div>
        )}
        <div
          style={{
            position: "absolute",
            left: 8,
            bottom: 8,
            padding: "3px 9px",
            fontSize: 12,
            fontWeight: 600,
            color: "#fff",
            background: "rgba(0,163,202,.92)",
            borderRadius: 10,
          }}
        >
          {walkText}
        </div>
        {item.price != null && (
          <div
            style={{
              position: "absolute",
              right: 8,
              top: 8,
              padding: "3px 10px",
              fontSize: 15,
              fontWeight: 700,
              color: "#fff",
              background: "rgba(250,84,28,.92)",
              borderRadius: 10,
            }}
          >
            ￥{item.price}
          </div>
        )}
      </div>

      <div style={{ padding: "10px 12px 12px" }}>
        <div
          style={{
            fontWeight: 600,
            fontSize: 14,
            lineHeight: "20px",
            color: "#262626",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {item.title}
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
          <Tag color="blue" style={{ margin: 0, fontSize: 11 }}>
            {item.layout_label}
          </Tag>
          <ElevatorTag item={item} />
          <Tooltip title={item.newness_signals?.join("、") || "无明显新旧信号"}>
            <Tag
              color={item.newness_score >= 70 ? "cyan" : "default"}
              style={{ margin: 0, fontSize: 11 }}
            >
              新旧 {item.newness_score}
            </Tag>
          </Tooltip>
        </div>

        <div style={{ marginTop: 8, fontSize: 12, color: "#595959" }}>
          🚉 {item.nearest_station}（{item.nearest_station_lines?.join("/")}）
          {item.straight_m ? ` · 直线 ${item.straight_m}m` : ""}
        </div>
        {(item.community || item.district) && (
          <div style={{ marginTop: 4, fontSize: 12, color: "#8c8c8c" }}>
            📍 {item.district || ""} {item.community || ""}
          </div>
        )}

        {item.caveats?.length > 0 && (
          <div style={{ marginTop: 6, fontSize: 11, color: "#fa8c16" }}>
            ⚠️ {item.caveats[0]}
          </div>
        )}

        <div
          style={{
            marginTop: 10,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Tag color="magenta" style={{ margin: 0, fontSize: 11 }}>
            {SOURCE_LABEL[item.source] || item.source}
          </Tag>
          <a
            href={item.source_url}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={{ fontSize: 12 }}
          >
            查看原帖 ↗
          </a>
        </div>
      </div>
    </div>
  );
}

export default function MatchPage() {
  const columns = useColumns();
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [profile, setProfile] = useState("longhua");
  const [result, setResult] = useState<MatchResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"precise" | "pending">("precise");

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
  const list = tab === "precise" ? result?.data || [] : result?.pendingLocation || [];

  return (
    <BaseLayout>
      <Helmet>
        <title>我的通勤需求 · 匹配结果</title>
      </Helmet>

      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "16px 16px 60px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h2 style={{ margin: 0, fontSize: 20 }}>我的通勤需求</h2>
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
                <MatchCard key={`${item.house_id}-${item.nearest_station}`} item={item} />
              ))}
            </Masonry>
          )}
        </div>
      </div>
    </BaseLayout>
  );
}
