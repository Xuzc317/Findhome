import classNames from "classnames";
import { useEffect } from "react";
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
  rentType?: number;
  intervalDay?: number;
}

export function HouseFilter(props: { onSearch: (info: FilterInfo) => void }) {
  const cities = useCities();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectCityItem = cities.find((item) => item.city === (searchParams.get("city") || "上海"));

  useEffect(() => {
    const newParams: any = Object.fromEntries(searchParams.entries());
    if (newParams.fromPrice) {
      newParams.fromPrice = parseInt(newParams.fromPrice);
    }
    if (newParams.toPrice) {
      newParams.toPrice = parseInt(newParams.toPrice);
    }
    if (newParams.rentType) {
      newParams.rentType = parseInt(newParams.rentType);
    }
    if (newParams.intervalDay) {
      newParams.intervalDay = parseInt(newParams.intervalDay);
    }
    if (!newParams.city) {
      newParams.city = "上海";
    }

    props.onSearch(newParams);
  }, [searchParams]);

  if (!cities.length) return <div></div>;
  return (
    <>
      <div className={styles.container}>
        <div className="flex">
          {selectCityItem?.sources.map((item) => {
            return (
              <div
                key={item.source}
                className={classNames(styles.sourceItem, {
                  [styles.sourceItemSel]: item.source == (searchParams.get("source") || "all"),
                })}
                onClick={() => {
                  const params: any = Object.fromEntries(searchParams.entries());
                  setSearchParams({ ...params, source: item.source });
                }}
              >
                {item.displaySource}
              </div>
            );
          })}
        </div>

        <div className="flex">
          {HomeFilterOptions.types.map((item) => {
            return (
              <div
                key={item.value}
                className={classNames(styles.sourceItem, {
                  [styles.sourceItemSel]: item.value == parseInt(searchParams.get("rentType") || "-1"),
                })}
                onClick={() => {
                  const params: any = Object.fromEntries(searchParams.entries());
                  setSearchParams({ ...params, rentType: `${item.value}` });
                }}
              >
                {item.label}
              </div>
            );
          })}
        </div>
      </div>
      <div style={{ height: 120 }}></div>
    </>
  );
}
