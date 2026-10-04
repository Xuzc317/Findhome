/**
 1. 创建 Provider 在main.tsx中引入
  2. 创建 Context 在其他地方公用，防止重复请求
*/
import { citiesService } from "@/services";
import React, { createContext, useContext } from "react";

export const CitiesContext = createContext<CityEntity[]>([]);

export const useCities = () => {
  const values = useContext(CitiesContext)
  return values;
};

export function CitiesProvider(props: { children: React.ReactNode }) {
  const [cities, setCities] = React.useState<CityEntity[]>([]);

  React.useEffect(() => {
    citiesService.getCities().then((res) => {
      res.map((item: any) => {
        item.sources.unshift({ displaySource: "全部", source: "all" });
      });
      setCities(res as any);
    });
  }, []);
  return <CitiesContext.Provider value={cities}>{props.children}</CitiesContext.Provider>;
}
