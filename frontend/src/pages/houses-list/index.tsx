import { HouseFilter } from "@/components/house-filter";
import { Spin, Tag } from "antd";
import dayjs from "dayjs";
import { useEffect, useMemo, useRef, useState } from "react";
import Masonry from "react-masonry-css";
import { useBreakpointCols, useHouseState } from "./hook";
import styles from "./styles.module.css";
import BaseLayout from "@/components/layout";
import { Helmet } from "react-helmet";
import { useSearchParams } from "react-router-dom";

export default function HomePage() {
  const [searchParams] = useSearchParams();
  const { houses, hasMore, refreshLoading, loadMore, refreshData } =
    useHouseState();
  const { breakpointCols } = useBreakpointCols();
  const filterRef = useRef<any>(null);
  const refreshLoadingRef = useRef(refreshLoading);
  refreshLoadingRef.current = refreshLoading;
  const hasMoreRef = useRef(hasMore);
  hasMoreRef.current = hasMore;

  useEffect(() => {
    // 监听是否滚动到底部，加载更多
    function handleScroll() {
      const scrollTop = document.documentElement.scrollTop ||
        document.body.scrollTop;
      const scrollHeight = document.documentElement.scrollHeight ||
        document.body.scrollHeight;
      const clientHeight = document.documentElement.clientHeight ||
        document.body.clientHeight;
      if (scrollTop + clientHeight >= scrollHeight - 300) {
        if (!refreshLoadingRef.current && hasMoreRef.current) {
          loadMore(filterRef.current);
        }
      }
    }
    window.addEventListener("scroll", handleScroll);
    return () => {
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  const cityName = useMemo(() => {
    return searchParams.get("city") || "上海";
  }, [searchParams]);

  return (
    <BaseLayout
      headerLeft={
        <SearchBar
          onSearch={(keyword) => {
            filterRef.current = {
              ...filterRef.current,
              keyword,
            };
            refreshData(filterRef.current);
          }}
        />
      }
    >
      <Helmet>
        <title>{`地图搜租房-${cityName}`}</title>
      </Helmet>
      <HouseFilter
        onSearch={(filter) => {
          filterRef.current = filter;
          refreshData(filter);
        }}
      />
      <Masonry
        breakpointCols={breakpointCols}
        className={styles.content}
        columnClassName={styles.gridColumn}
      >
        {houses.map((item) => <ItemCard item={item} key={item.id} />)}
      </Masonry>
      {hasMore && (
        <div className={styles.loadingContainer}>
          <Spin spinning={true} />
        </div>
      )}
    </BaseLayout>
  );
}

function ItemCard(props: { item: HouseListItem }) {
  const { item } = props;
  return (
    <div
      className={styles.itemCard}
      onClick={() => {
        window.open(`/houses/${item.id}`);
      }}
    >
      <img
        className={styles.itemImage}
        src={item.pictures[0]}
        onError={() => {}}
      />
      <div className={styles.title}>{item.title}</div>
      <div className={styles.bottom}>
        <div className={styles.price}>
          ￥{item.price === -1 ? "暂无价格" : item.price}
        </div>
        <Tag color="magenta" className="ml-2">{item.displaySource}</Tag>
        <div style={{ flex: 1 }}></div>
        <div className={styles.time}>
          {dayjs(item.createTime).format("YYYY-MM-DD")}
        </div>
      </div>
    </div>
  );
}

function SearchBar(props: { onSearch: (keyword: string) => void }) {
  const [keyword, setKeyword] = useState(() => {
    const searchParams = new URLSearchParams(window.location.search);
    return searchParams.get("keyword") || "";
  });

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    searchParams.set("title", keyword);
    window.history.pushState(null, "", `?${searchParams.toString()}`);
  }, [keyword]);

  return (
    <div className={styles.searchBar}>
      <input
        type="text"
        placeholder="搜索房源"
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        onKeyUp={(e) => {
          if (e.key === "Enter") {
            props.onSearch(keyword);
          }
        }}
      />
      <div
        className={styles.searchIcon}
        onClick={() => props.onSearch(keyword)}
      >
        <img src="/images/search.svg" />
      </div>
    </div>
  );
}
