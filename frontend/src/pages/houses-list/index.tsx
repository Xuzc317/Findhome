import { HouseFilter } from "@/components/house-filter";
import { Alert, Empty, Spin, Tag, Tooltip } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import Masonry from "react-masonry-css";
import { useBreakpointCols, useHouseState } from "./hook";
import styles from "./styles.module.css";
import BaseLayout from "@/components/layout";
import { Helmet } from "react-helmet";
import { useSearchParams } from "react-router-dom";

/** 坐标来源的中文说明：让用户一眼看出"这个位置是平台给的还是推断的" */
const GEO_SOURCE_LABEL: Record<
  string,
  { text: string; color: string; tip: string }
> = {
  platform: { text: "平台坐标", color: "green", tip: "平台页面直接提供的坐标" },
  amap_poi: {
    text: "高德POI",
    color: "blue",
    tip: "按小区/站点名在高德 POI 中匹配得到",
  },
  amap_geocode: {
    text: "高德编码",
    color: "blue",
    tip: "按地址文本做地理编码得到",
  },
  llm_text: {
    text: "模型抽取",
    color: "purple",
    tip: "由大模型从文字中抽取后定位",
  },
  llm_image: {
    text: "图片抽取",
    color: "purple",
    tip: "由大模型从图片中抽取后定位",
  },
  manual: { text: "手动标注", color: "gold", tip: "人工确认过" },
};

const PRECISION_LABEL: Record<string, string> = {
  building: "楼栋级",
  community: "小区级",
  street: "街道级",
  station: "站点附近",
  district: "区级(不展示)",
  unknown: "精度未知",
};

export default function HousesList() {
  const [searchParams] = useSearchParams();
  const { houses, total, hasMore, error, refreshLoading, loadMore, refreshData } =
    useHouseState();
  const { breakpointCols } = useBreakpointCols();
  const filterRef = useRef<any>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const stateRef = useRef({ refreshLoading, hasMore });
  stateRef.current = { refreshLoading, hasMore };

  const cityName = useMemo(
    () => searchParams.get("city") || "深圳",
    [searchParams],
  );
  const stationName = searchParams.get("stationName") || "";

  // 用 IntersectionObserver 替代滚动事件：更省资源，也不会漏触发
  useEffect(() => {
    const node = sentinelRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          const { refreshLoading: loading, hasMore: more } = stateRef.current;
          if (!loading && more) loadMore(filterRef.current);
        }
      },
      { rootMargin: "400px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [loadMore]);

  return (
    <BaseLayout
      headerLeft={
        <SearchBar
          onSearch={(keyword) => {
            filterRef.current = { ...filterRef.current, keyword };
            refreshData(filterRef.current);
          }}
        />
      }
    >
      <Helmet>
        <title>{`地图搜租房-${cityName}`}</title>
      </Helmet>

      <div className={styles.pageBody}>
        <HouseFilter
          resultCount={total}
          loading={refreshLoading}
          onSearch={(filter) => {
            filterRef.current = filter;
            refreshData(filter);
          }}
        />

        <main className={styles.results}>
          <div className={styles.resultsHeader}>
            <span className={styles.resultsTitle}>
              {cityName}
              {stationName ? ` · ${stationName}站附近` : ""}
            </span>
            <span className={styles.resultsTotal}>共 {total} 套</span>
          </div>

          {error && (
            <Alert
              type="error"
              showIcon
              className="mb-4"
              message="查询失败"
              description={error}
            />
          )}

          {!refreshLoading && !error && houses.length === 0 && (
            <Empty
              className="mt-16"
              description={
                stationName
                  ? "该条件下没有房源。可放宽步行距离，或先在左侧「更多筛选 → 数据准备」计算步行距离"
                  : "没有符合条件的房源，试试放宽预算或把出租类型改成「不限」"
              }
            />
          )}

          <Masonry
            breakpointCols={breakpointCols}
            className={styles.content}
            columnClassName={styles.gridColumn}
          >
            {houses.map((item) => (
              <ItemCard item={item} key={item.id} />
            ))}
          </Masonry>

          <div ref={sentinelRef} className={styles.loadingContainer}>
            {hasMore && houses.length > 0 && <Spin spinning={true} />}
          </div>
        </main>
      </div>
    </BaseLayout>
  );
}

function ItemCard(props: { item: HouseListItem }) {
  const { item } = props;
  const geo = GEO_SOURCE_LABEL[item.geoSource || ""] || null;

  return (
    <div
      className={styles.itemCard}
      onClick={() => {
        window.open(`/houses/${item.id}`);
      }}
    >
      <div className={styles.imageWrap}>
        <img
          className={styles.itemImage}
          src={item.pictures?.[0]}
          loading="lazy"
          onError={(e) => {
            (e.target as HTMLImageElement).style.visibility = "hidden";
          }}
        />
        {item.walkMeters != null && (
          <div className={styles.walkBadge}>
            🚇 步行 {item.walkMinutes ?? Math.round(item.walkMeters / 80)} 分钟 ·{" "}
            {item.walkMeters}m
          </div>
        )}
        {item.walkMeters == null && item.walkStatus === "no_route" && (
          <div className={styles.walkBadgeMuted}>该站无法步行到达</div>
        )}
      </div>

      <div className={styles.title}>{item.title}</div>

      <div className={styles.metaRow}>
        {item.layoutLabel && (
          <Tag color="blue" className={styles.metaTag}>
            {item.layoutLabel}
          </Tag>
        )}
        {item.district && (
          <span className={styles.metaText}>{item.district}</span>
        )}
        {geo && (
          <Tooltip
            title={`${geo.tip}${
              item.geoPrecision
                ? ` · ${PRECISION_LABEL[item.geoPrecision] || item.geoPrecision}`
                : ""
            }${item.geoNote ? ` · ${item.geoNote}` : ""}`}
          >
            <Tag color={geo.color} className={styles.metaTag}>
              {geo.text}
            </Tag>
          </Tooltip>
        )}
      </div>

      <div className={styles.bottom}>
        <div className={styles.price}>
          {item.price ? `￥${item.price}` : "价格未知"}
        </div>
        <Tag color="magenta" className="ml-2">
          {item.displaySource}
        </Tag>
        <div style={{ flex: 1 }}></div>
        <div className={styles.time}>{item.timeText || "时间未知"}</div>
      </div>
    </div>
  );
}

function SearchBar(props: { onSearch: (keyword: string) => void }) {
  const [keyword, setKeyword] = useState(
    () => new URLSearchParams(window.location.search).get("keyword") || "",
  );

  return (
    <div className={styles.searchBar}>
      <input
        type="text"
        placeholder="搜索小区 / 地铁站 / 关键词"
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        onKeyUp={(e) => {
          if (e.key === "Enter") props.onSearch(keyword);
        }}
      />
      <div className={styles.searchIcon} onClick={() => props.onSearch(keyword)}>
        <img src="/images/search.svg" />
      </div>
    </div>
  );
}
