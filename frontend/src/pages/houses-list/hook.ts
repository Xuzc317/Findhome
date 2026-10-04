import { housesService } from "@/services";
import React from "react";

export function useBreakpointCols() {
  // 创建一个state来存储当前的屏幕宽度
  const [breakpointCols, setBreakpointCols] = React.useState(3);

  React.useEffect(() => {
    const handleResize = () => {
      // 左侧有 300px 筛选栏，列数按剩余宽度估算
      const available = window.innerWidth - 380;
      if (available < 700) return setBreakpointCols(1);
      return setBreakpointCols(Math.min(Math.max(Math.floor(available / 300), 1), 3));
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return { breakpointCols };
}

export const useHouseState = () => {
  const [houses, setHouses] = React.useState<HouseListItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [refreshLoading, setRefreshLoading] = React.useState(false);
  const [error, setError] = React.useState<string>("");
  const [hasMore, setHasMore] = React.useState(true);
  const pageRef = React.useRef(0);
  const loadingRef = React.useRef(false);
  const housesRef = React.useRef(houses);
  housesRef.current = houses;

  const PAGE_SIZE = 60;

  const loadData = React.useCallback((params?: any) => {
    loadingRef.current = true;
    setError("");
    return housesService
      .searchHouses({
        ...params,
        page: pageRef.current,
        pageSize: PAGE_SIZE,
      })
      .then((res) => {
        setTotal(res.total);
        setHasMore(res.hasMore);
        if (pageRef.current > 0) {
          setHouses(housesRef.current.concat(res.list));
        } else {
          setHouses(res.list);
        }
      })
      .catch((err) => {
        // 错误要显式暴露给用户，而不是只在控制台里悄悄失败
        setError(err?.message || "查询失败，请确认后端已启动");
        setHasMore(false);
      })
      .finally(() => {
        loadingRef.current = false;
      });
  }, []);

  const refreshData = React.useCallback((params: any) => {
    if (loadingRef.current) return;
    pageRef.current = 0;
    setHasMore(true);
    setRefreshLoading(true);
    setHouses([]);
    loadData(params).finally(() => setRefreshLoading(false));
  }, [loadData]);

  const loadMore = React.useCallback((params: any) => {
    if (loadingRef.current || !hasMore) return;
    pageRef.current += 1;
    loadData(params);
  }, [loadData, hasMore]);

  return {
    houses,
    total,
    hasMore,
    error,
    refreshLoading,
    loadMore,
    refreshData,
  };
};
