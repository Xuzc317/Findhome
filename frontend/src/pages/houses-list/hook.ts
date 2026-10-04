import { housesService } from "@/services";
import React, { useEffect, useState } from "react";

export function useBreakpointCols() {
  // 创建一个state来存储当前的屏幕宽度
  const [breakpointCols, setBreakpointCols] = useState(4);

  useEffect(() => {
    // 编写一个调整大小时执行的函数
    const handleResize = () => {
      if (innerWidth < 700) return setBreakpointCols(2);
      return setBreakpointCols(
        Math.min(Math.floor(window.innerWidth / 320), 4),
      );
    };

    // 添加事件监听器
    window.addEventListener("resize", handleResize);

    // 清理函数：组件卸载时移除事件监听器
    return () => window.removeEventListener("resize", handleResize);
  }, []); // 空依赖数组表示此effect只在组件挂载时运行一次

  return {
    breakpointCols,
  };
}

export const useHouseState = () => {
  const [houses, setHouses] = React.useState<HouseListItem[]>([]);
  const [refreshLoading, setRefreshLoading] = React.useState(false);
  const [hasMore, setHasMore] = React.useState(true);
  const pageRef = React.useRef(0);
  const loadingRef = React.useRef(false);
  const housesRef = React.useRef(houses);
  housesRef.current = houses;

  const loadData = React.useCallback((params?: any) => {
    loadingRef.current = true;
    return housesService.getHouses({
      ...params,
      page: pageRef.current,
      pageSize: 100,
    })
      .then((res) => {
        if (res.length != 100) setHasMore(false);
        if (pageRef.current > 0) {
          setHouses(housesRef.current.concat(res));
        } else {
          setHouses(res);
        }
      })
      .catch((error) => {
        console.error(error);
      })
      .finally(() => {
        loadingRef.current = false;
      });
  }, [setHouses, pageRef, loadingRef, setHasMore]);

  const refreshData = React.useCallback((params: any) => {
    if (loadingRef.current) return;
    pageRef.current = 0;
    setHasMore(true);
    setRefreshLoading(true);
    setHouses([]);
    loadData(params).finally(() => setRefreshLoading(false));
  }, [loadData, loadingRef, setRefreshLoading]);

  const loadMore = React.useCallback((params: any) => {
    if (loadingRef.current) return;
    pageRef.current += 1;
    loadData(params);
  }, [loadData, loadingRef, pageRef]);

  return {
    houses,
    hasMore,
    refreshLoading,
    loadMore,
    refreshData,
  };
};
