import classNames from "classnames";
import { useEffect, useState } from "react";
import styles from "./styles.module.css";
import { HomeFilterOptions } from "@/constant";
import { useSearchParams } from "react-router-dom";
import { useCities } from "@/hook/cities";

export interface FilterInfo {
  city: string;
  source?: string;
  fromPrice?: number;
  toPrice?: number;
  district?: string;
  keyword?: string;
  keywordExclude?: string;
  rentType?: number;
  intervalDay?: number;
  maxAgentScore?: number;
  minConfidenceScore?: number;
}

/** 风险筛选：与后端 maxAgentScore / minConfidenceScore 一一对应，规则可解释 */
const RiskOptions = [
  { label: "全部", maxAgentScore: undefined, minConfidenceScore: undefined },
  { label: "低中介嫌疑", maxAgentScore: 30, minConfidenceScore: undefined },
  { label: "可信度≥70", maxAgentScore: undefined, minConfidenceScore: 70 },
];

export function HouseFilter(props: { onSearch: (info: FilterInfo) => void }) {
  const cities = useCities();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectCityItem = cities.find((item) =>
    item.city === (searchParams.get("city") || "上海")
  );

  // 价格与排除词是输入型条件，先用本地态收集，点击/回车后再写回 URL
  const [fromPrice, setFromPrice] = useState(searchParams.get("fromPrice") || "");
  const [toPrice, setToPrice] = useState(searchParams.get("toPrice") || "");
  const [excludeKeyword, setExcludeKeyword] = useState(
    searchParams.get("keywordExclude") || "",
  );

  useEffect(() => {
    const newParams: any = Object.fromEntries(searchParams.entries());
    if (newParams.fromPrice) newParams.fromPrice = parseInt(newParams.fromPrice);
    if (newParams.toPrice) newParams.toPrice = parseInt(newParams.toPrice);
    if (newParams.rentType) newParams.rentType = parseInt(newParams.rentType);
    if (newParams.intervalDay) {
      newParams.intervalDay = parseInt(newParams.intervalDay);
    }
    if (newParams.maxAgentScore) {
      newParams.maxAgentScore = parseInt(newParams.maxAgentScore);
    }
    if (newParams.minConfidenceScore) {
      newParams.minConfidenceScore = parseInt(newParams.minConfidenceScore);
    }
    if (!newParams.city) newParams.city = "上海";

    props.onSearch(newParams);
  }, [searchParams]);

  /** 只改动指定字段，保留其余条件 */
  const applyParams = (patch: Record<string, string | undefined>) => {
    const params: Record<string, string> = Object.fromEntries(
      searchParams.entries(),
    );
    Object.entries(patch).forEach(([key, value]) => {
      if (value === undefined || value === "" || value === "all_clear") {
        delete params[key];
      } else {
        params[key] = value;
      }
    });
    setSearchParams(params);
  };

  const applyPrice = () => {
    applyParams({
      fromPrice: fromPrice || undefined,
      toPrice: toPrice || undefined,
    });
  };

  const clearAll = () => {
    setFromPrice("");
    setToPrice("");
    setExcludeKeyword("");
    setSearchParams(
      searchParams.get("city") ? { city: searchParams.get("city")! } : {},
    );
  };

  const activeInterval = searchParams.get("intervalDay");
  const activeAgentScore = searchParams.get("maxAgentScore");
  const activeConfidence = searchParams.get("minConfidenceScore");

  return (
    <>
      <div className={styles.container}>
        {/* 数据源 */}
        <div className={styles.sourceContainer}>
          {selectCityItem?.sources.map((item) => {
            return (
              <div
                key={item.source}
                className={classNames(styles.sourceItem, {
                  [styles.sourceItemSel]: item.source ==
                    (searchParams.get("source") || "all"),
                })}
                onClick={() => applyParams({ source: item.source })}
              >
                {item.displaySource}
              </div>
            );
          })}
        </div>

        {/* 出租类型 */}
        <div className={styles.sourceContainer}>
          {HomeFilterOptions.types.map((item) => {
            return (
              <div
                key={item.value}
                className={classNames(styles.sourceItem, {
                  [styles.sourceItemSel]: item.value ==
                    parseInt(searchParams.get("rentType") || "-1"),
                })}
                onClick={() =>
                  applyParams({
                    rentType: item.value === -1 ? undefined : `${item.value}`,
                  })}
              >
                {item.label}
              </div>
            );
          })}
        </div>

        {/* 发布时间 */}
        <div className={styles.sourceContainer}>
          <span className={styles.filterLabel}>发布时间</span>
          {HomeFilterOptions.times.map((item) => {
            const selected = item.value === -1
              ? !activeInterval
              : activeInterval === `${item.value}`;
            return (
              <div
                key={item.value}
                className={classNames(styles.sourceItem, {
                  [styles.sourceItemSel]: selected,
                })}
                onClick={() =>
                  applyParams({
                    intervalDay: item.value === -1 ? undefined : `${item.value}`,
                  })}
              >
                {item.label}
              </div>
            );
          })}
        </div>

        {/* 风险 */}
        <div className={styles.sourceContainer}>
          <span className={styles.filterLabel}>风险</span>
          {RiskOptions.map((item) => {
            const selected = item.maxAgentScore !== undefined
              ? activeAgentScore === `${item.maxAgentScore}`
              : item.minConfidenceScore !== undefined
              ? activeConfidence === `${item.minConfidenceScore}`
              : !activeAgentScore && !activeConfidence;
            return (
              <div
                key={item.label}
                className={classNames(styles.sourceItem, {
                  [styles.sourceItemSel]: selected,
                })}
                onClick={() =>
                  applyParams({
                    maxAgentScore: item.maxAgentScore
                      ? `${item.maxAgentScore}`
                      : undefined,
                    minConfidenceScore: item.minConfidenceScore
                      ? `${item.minConfidenceScore}`
                      : undefined,
                  })}
              >
                {item.label}
              </div>
            );
          })}
        </div>

        {/* 价格区间 + 排除关键词 */}
        <div className={styles.sourceContainer}>
          <span className={styles.filterLabel}>价格</span>
          <input
            className={styles.filterInput}
            style={{ width: 76 }}
            type="number"
            placeholder="最低"
            value={fromPrice}
            onChange={(e) => setFromPrice(e.target.value)}
            onKeyUp={(e) => e.key === "Enter" && applyPrice()}
          />
          <span className={styles.filterDash}>-</span>
          <input
            className={styles.filterInput}
            style={{ width: 76 }}
            type="number"
            placeholder="最高"
            value={toPrice}
            onChange={(e) => setToPrice(e.target.value)}
            onKeyUp={(e) => e.key === "Enter" && applyPrice()}
          />
          <div className={styles.applyBtn} onClick={applyPrice}>确定</div>

          <span className={styles.filterLabel} style={{ marginLeft: 16 }}>
            排除词
          </span>
          <input
            className={styles.filterInput}
            style={{ width: 150 }}
            type="text"
            placeholder="如：中介 公寓"
            value={excludeKeyword}
            onChange={(e) => setExcludeKeyword(e.target.value)}
            onKeyUp={(e) =>
              e.key === "Enter" &&
              applyParams({ keywordExclude: excludeKeyword || undefined })}
          />
          <div
            className={styles.applyBtn}
            onClick={() =>
              applyParams({ keywordExclude: excludeKeyword || undefined })}
          >
            确定
          </div>

          <div className={styles.clearBtn} onClick={clearAll}>清空条件</div>
        </div>
      </div>
      <div style={{ height: 216 }}></div>
    </>
  );
}
