import { HomeFilterOptions } from "@/constant";
import { useCities } from "@/hook/cities";
import { useUserInfo } from "@/hook/user";
import { housesService } from "@/services";
import {
  AimOutlined,
  EnvironmentOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from "@ant-design/icons";
import {
  Button,
  Input,
  message,
  Select,
  Slider,
} from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Helmet } from "react-helmet";
import { useSearchParams } from "react-router-dom";
import styles from "./styles.module.css";

// 高德地图 Key 通过 frontend/.env 的 VITE_AMAP_KEY 注入；
// 默认值仅为兼容原项目，强烈建议换成自己在 https://lbs.amap.com 申请的 Key。
const AMAP_KEY = import.meta.env.VITE_AMAP_KEY || "REMOVED_UPSTREAM_EXAMPLE_KEY";
const AMAP_SCRIPT_ID = "house-search-amap";
const AMAP_UI_SCRIPT_ID = "house-search-amap-ui";

const MARKER_STYLES = [
  { type: "Blue", url: "/images/Blue.png" },
  { type: "PaleGreen", url: "/images/PaleGreen.png" },
  { type: "LightGreen", url: "/images/LightGreen.png" },
  { type: "PaleYellow", url: "/images/PaleYellow.png" },
  { type: "OrangeYellow", url: "/images/OrangeYellow.png" },
  { type: "PaleRed", url: "/images/PaleRed.png" },
  { type: "Red", url: "/images/Red.png" },
  { type: "Pink", url: "/images/Pink.png" },
  { type: "Violet", url: "/images/Violet.png" },
  { type: "Black", url: "/images/Black.png" },
];

type LngLatTuple = [number, number];

interface MarkerPayload {
  lnglat: LngLatTuple;
  style: number;
  name: string;
  house: HouseListItem;
  title: string;
  displayMoney: string;
  sourceContent: string;
}

interface FilterDraft {
  city: string;
  source: string;
  rentType: number;
  keyword: string;
  intervalDay: number;
}

const scriptPromises = new Map<string, Promise<void>>();

function loadScript(id: string, src: string) {
  if (scriptPromises.has(id)) return scriptPromises.get(id)!;
  const promise = new Promise<void>((resolve, reject) => {
    const existing = document.getElementById(id) as HTMLScriptElement | null;
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("脚本加载失败")), {
        once: true,
      });
      if (existing.dataset.loaded === "true") resolve();
      return;
    }
    const script = document.createElement("script");
    script.id = id;
    script.charset = "utf-8";
    script.src = src;
    script.onload = () => {
      script.dataset.loaded = "true";
      resolve();
    };
    script.onerror = () => reject(new Error("地图脚本加载失败"));
    document.head.appendChild(script);
  });
  scriptPromises.set(id, promise);
  return promise;
}

async function loadAmap() {
  if (typeof AMap !== "undefined") return;
  const plugins = [
    "AMap.Scale",
    "AMap.Geocoder",
    "AMap.Transfer",
    "AMap.AutoComplete",
    "AMap.PlaceSearch",
    "AMap.CitySearch",
    "AMap.ArrivalRange",
    "AMap.ToolBar",
  ];
  await loadScript(
    AMAP_SCRIPT_ID,
    `https://webapi.amap.com/maps?v=2.0&key=${AMAP_KEY}&plugin=${plugins.join()}`,
  );
  await loadScript(
    AMAP_UI_SCRIPT_ID,
    "//webapi.amap.com/ui/1.1/main.js?v=1.1.1",
  ).catch(() => undefined);
}

function getNumber(value?: string | number) {
  if (value === undefined || value === null || value === "") return undefined;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function getHouseLngLat(house: HouseListItem): LngLatTuple | undefined {
  const lng = getNumber(house.longitude);
  const lat = getNumber(house.latitude);
  if (lng === undefined || lat === undefined) return undefined;
  return [lng, lat];
}

function getStyleIndex(house: HouseListItem) {
  if (house.icon) {
    const iconIndex = MARKER_STYLES.findIndex((style) =>
      house.icon?.includes(style.type)
    );
    if (iconIndex >= 0) return iconIndex;
  }
  if (!house.price || house.price < 0) return 0;
  return Math.min(Math.floor(house.price / 1000), MARKER_STYLES.length - 1);
}

function getSearchFilter(searchParams: URLSearchParams): FilterDraft {
  return {
    city: searchParams.get("city") || "上海",
    source: searchParams.get("source") || "all",
    rentType: Number(searchParams.get("rentType") || -1),
    keyword: searchParams.get("keyword") || "",
    intervalDay: Number(searchParams.get("intervalDay") || 30),
  };
}

export default function MapPage() {
  const cities = useCities();
  const { userInfo } = useUserInfo(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const routeFilter = useMemo(() => getSearchFilter(searchParams), [searchParams]);
  const [draft, setDraft] = useState<FilterDraft>(routeFilter);
  const [loading, setLoading] = useState(true);
  const [mapReady, setMapReady] = useState(false);
  const [workAddress, setWorkAddress] = useState("");
  const [commuteMinutes, setCommuteMinutes] = useState(45);
  const [commuteMode, setCommuteMode] = useState("");
  const [routePanelOpen, setRoutePanelOpen] = useState(false);
  const [routeSidebarOpen, setRouteSidebarOpen] = useState(false);
  const [commutePosition, setCommutePosition] = useState<LngLatTuple>();

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const routePanelRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>();
  const geocoderRef = useRef<any>();
  const massMarksRef = useRef<any>();
  const markersRef = useRef<any[]>([]);
  const infoWindowRef = useRef<any>();
  const transferRef = useRef<any>();
  const polygonsRef = useRef<any[]>([]);
  const markerPayloadsRef = useRef(new Map<string, MarkerPayload>());
  const commutePositionRef = useRef<LngLatTuple>();
  commutePositionRef.current = commutePosition;

  useEffect(() => {
    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  }, []);

  useEffect(() => {
    setDraft(routeFilter);
  }, [routeFilter]);

  const selectedCity = useMemo(
    () => cities.find((item) => item.city === routeFilter.city),
    [cities, routeFilter.city],
  );

  const sourceOptions = useMemo(() => {
    const sources = selectedCity?.sources || [];
    return [
      { label: "全部", value: "all" },
      ...sources.map((source) => ({
        label: source.displaySource,
        value: source.source,
      })),
    ];
  }, [selectedCity]);

  const clearMapOverlays = useCallback(() => {
    if (massMarksRef.current) {
      massMarksRef.current.clear();
      massMarksRef.current.setMap(null);
      massMarksRef.current = undefined;
    }
    markersRef.current.forEach((marker) => marker.setMap(null));
    markersRef.current = [];
    if (infoWindowRef.current) {
      infoWindowRef.current.close();
    }
  }, []);

  const collectHouse = useCallback(async (house: HouseListItem) => {
    if (!userInfo) {
      message.warning("请先登录");
      return;
    }
    try {
      await housesService.addCollection(userInfo.id, house.id);
      message.success("收藏成功");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "收藏失败");
    }
  }, [userInfo]);

  const resolveAddress = useCallback((address: string) => {
    return new Promise<LngLatTuple | undefined>((resolve) => {
      const geocoder = geocoderRef.current;
      if (!geocoder || !address.trim()) {
        resolve(undefined);
        return;
      }
      geocoder.getLocation(address.trim(), (status: string, result: any) => {
        const location = result?.geocodes?.[0]?.location;
        if (status === "complete" && location) {
          resolve([location.lng, location.lat]);
          return;
        }
        resolve(undefined);
      });
    });
  }, []);

  const ensureCommutePosition = useCallback(async () => {
    if (commutePositionRef.current) return commutePositionRef.current;
    const position = await resolveAddress(workAddress || routeFilter.city);
    if (position) {
      setCommutePosition(position);
      return position;
    }
    message.warning("没有找到出发位置");
    return undefined;
  }, [resolveAddress, routeFilter.city, workAddress]);

  const startTransfer = useCallback(async (destination: LngLatTuple) => {
    const map = mapRef.current;
    const start = await ensureCommutePosition();
    if (!map || !start) return;
    if (transferRef.current) transferRef.current.clear();
    if (routePanelRef.current) routePanelRef.current.innerHTML = "";
    setRoutePanelOpen(true);
    setRouteSidebarOpen(true);
    const transfer = new AMap.Transfer({
      city: routeFilter.city,
      map,
      panel: routePanelRef.current,
      extensions: "all",
      policy: AMap.TransferPolicy.LEAST_DISTANCE,
    });
    transferRef.current = transfer;
    transfer.search(
      new AMap.LngLat(start[0], start[1]),
      new AMap.LngLat(destination[0], destination[1]),
      (status: string) => {
        if (status !== "complete") message.warning("没有找到合适路线");
      },
    );
  }, [ensureCommutePosition, routeFilter.city]);

  const openInfoWindow = useCallback((payload: MarkerPayload) => {
    const map = mapRef.current;
    if (!map) return;
    const content = document.createElement("div");
    content.className = styles.infoWindow;

    const title = document.createElement("a");
    title.className = styles.infoTitle;
    title.href = `/houses/${payload.house.id}`;
    title.target = "_blank";
    title.textContent = payload.title;
    content.appendChild(title);

    const meta = document.createElement("div");
    meta.className = styles.infoMeta;
    meta.textContent = `${payload.displayMoney || "价格未知"} · ${payload.sourceContent}`;
    content.appendChild(meta);

    const address = document.createElement("div");
    address.className = styles.infoAddress;
    address.textContent = payload.house.location || payload.house.district || "";
    content.appendChild(address);

    const actions = document.createElement("div");
    actions.className = styles.infoActions;

    const collect = document.createElement("button");
    collect.type = "button";
    collect.textContent = "收藏";
    collect.addEventListener("click", () => collectHouse(payload.house));
    actions.appendChild(collect);

    const route = document.createElement("button");
    route.type = "button";
    route.textContent = "导航";
    route.addEventListener("click", () => startTransfer(payload.lnglat));
    actions.appendChild(route);

    content.appendChild(actions);

    if (!infoWindowRef.current) {
      infoWindowRef.current = new AMap.InfoWindow({
        offset: new AMap.Pixel(8, 0),
      });
    }
    infoWindowRef.current.setContent(content);
    infoWindowRef.current.open(map, payload.lnglat);
  }, [collectHouse, startTransfer]);

  const renderMarkers = useCallback((data: HouseListItem[]) => {
    const map = mapRef.current;
    if (!map) return;
    clearMapOverlays();
    const payloads = data
      .map((house) => {
        const lnglat = getHouseLngLat(house);
        if (!lnglat) return undefined;
        const title = house.title || house.location;
        return {
          lnglat,
          style: getStyleIndex(house),
          name: title,
          house,
          title,
          displayMoney: house.price > 0 ? `￥${house.price}/月` : "",
          sourceContent: house.displaySource || house.source,
        };
      })
      .filter(Boolean) as MarkerPayload[];

    markerPayloadsRef.current = new Map(
      payloads.map((payload) => [payload.house.id, payload]),
    );

    if (!payloads.length) return;

    const style = MARKER_STYLES.map((item) => ({
      url: item.url,
      anchor: new AMap.Pixel(3, 3),
      size: new AMap.Size(19, 30),
    }));

    if (AMap.MassMarks) {
      const massMarks = new AMap.MassMarks([], {
        zIndex: 120,
        zooms: [3, 19],
        style,
      });
      massMarks.on("click", (event: any) => {
        openInfoWindow(event.data as MarkerPayload);
      });
      massMarks.setMap(map);
      massMarks.setData(payloads);
      massMarksRef.current = massMarks;
    } else {
      markersRef.current = payloads.map((payload) => {
        const marker = new AMap.Marker({
          map,
          position: payload.lnglat,
          title: payload.title,
        });
        marker.on("click", () => openInfoWindow(payload));
        return marker;
      });
    }

    const center = payloads.reduce<LngLatTuple>(
      (acc, payload) => [acc[0] + payload.lnglat[0], acc[1] + payload.lnglat[1]],
      [0, 0] as LngLatTuple,
    );
    map.setZoomAndCenter(payloads.length === 1 ? 16 : 12, [
      center[0] / payloads.length,
      center[1] / payloads.length,
    ]);
  }, [clearMapOverlays, openInfoWindow]);

  const loadHouses = useCallback(async () => {
    if (!mapReady) return;
    setLoading(true);
    try {
      const list = await housesService.getMapHouses({
          city: routeFilter.city,
          source: routeFilter.source,
          rentType: routeFilter.rentType,
          keyword: routeFilter.keyword,
          size: 1200,
        });
      renderMarkers(list);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "加载房源失败");
    } finally {
      setLoading(false);
    }
  }, [mapReady, renderMarkers, routeFilter]);

  useEffect(() => {
    let disposed = false;
    loadAmap()
      .then(() => {
        if (disposed || !mapContainerRef.current) return;
        const map = new AMap.Map(mapContainerRef.current, {
          zoom: 12,
          resizeEnable: true,
          viewMode: "2D",
        });
        map.addControl(new AMap.ToolBar());
        map.addControl(new AMap.Scale());
        mapRef.current = map;
        geocoderRef.current = new AMap.Geocoder({
          city: routeFilter.city,
          radius: 1000,
        });
        setMapReady(true);
      })
      .catch((error) => {
        message.error(error instanceof Error ? error.message : "地图初始化失败");
        setLoading(false);
      });
    return () => {
      disposed = true;
      clearMapOverlays();
      transferRef.current?.clear?.();
      if (mapRef.current) {
        mapRef.current.destroy();
        mapRef.current = undefined;
      }
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const geocoder = geocoderRef.current;
    if (!mapReady || !map || !geocoder) return;
    geocoder.setCity(routeFilter.city);
    map.setCity(routeFilter.city);
    resolveAddress(routeFilter.city).then((position) => {
      if (position) map.setZoomAndCenter(12, position);
    });
  }, [mapReady, resolveAddress, routeFilter.city]);

  useEffect(() => {
    loadHouses();
  }, [loadHouses]);

  useEffect(() => {
    if (!mapReady || typeof AMap === "undefined") return;
    const autocomplete = new AMap.AutoComplete({
      input: "map-work-address",
      city: routeFilter.city,
    });
    autocomplete.on("select", (event: any) => {
      const location = event?.poi?.location;
      if (location) {
        setWorkAddress(event.poi.name || event.poi.address || "");
        setCommutePosition([location.lng, location.lat]);
        mapRef.current?.setZoomAndCenter(14, [location.lng, location.lat]);
      }
    });
  }, [mapReady, routeFilter.city]);

  const applyFilter = () => {
    const next = new URLSearchParams();
    next.set("city", draft.city || "上海");
    if (draft.source && draft.source !== "all") next.set("source", draft.source);
    if (draft.rentType !== -1) next.set("rentType", String(draft.rentType));
    if (draft.keyword.trim()) next.set("keyword", draft.keyword.trim());
    setSearchParams(next);
  };

  const resetFilter = () => {
    setDraft({
      city: routeFilter.city,
      source: "all",
      rentType: -1,
      keyword: "",
      intervalDay: 30,
    });
    setSearchParams({ city: routeFilter.city });
  };

  const runArrivalRange = async () => {
    const map = mapRef.current;
    if (!map || !AMap.ArrivalRange) {
      message.warning("当前地图 SDK 不支持到达圈");
      return;
    }
    const position = await ensureCommutePosition();
    if (!position) return;
    if (polygonsRef.current.length) {
      map.remove(polygonsRef.current);
      polygonsRef.current = [];
    }
    const arrivalRange = new AMap.ArrivalRange();
    arrivalRange.search(
      new AMap.LngLat(position[0], position[1]),
      commuteMinutes,
      (status: string, result: any) => {
        if (status !== "complete" || !result?.bounds?.length) {
          message.warning("没有找到可达范围");
          return;
        }
        const polygons = result.bounds.map((bound: any) => {
          const polygon = new AMap.Polygon({
            fillColor: "#00a3ca",
            fillOpacity: 0.22,
            strokeColor: "#00a3ca",
            strokeOpacity: 0.72,
            strokeWeight: 1,
          });
          polygon.setPath(bound);
          return polygon;
        });
        polygonsRef.current = polygons;
        map.add(polygons);
        map.setFitView(polygons);
      },
      { policy: commuteMode },
    );
  };

  return (
    <div className={styles.mapPage}>
      <Helmet>
        <title>{`地图搜租房-${routeFilter.city}`}</title>
      </Helmet>

      <a
        className={styles.noticeBar}
        href="https://wj.qq.com/s/2953926/aabe"
        target="_blank"
        rel="noreferrer"
      >
        特此声明:房源信息来自网络，请自行鉴别。合租需谨慎，群租有风险，长租公寓多当心。
      </a>

      <header className={styles.topBar}>
        <div className={styles.headerTitle}>
          <a href="/" className={styles.topBrand}>
            <img src="/logo.png" alt="地图搜租房" />
            <span>地图搜租房</span>
          </a>
          <div className={styles.topCity}>
            <EnvironmentOutlined />
            <Select
              value={draft.city}
              variant="borderless"
              options={cities.map((city) => ({ label: city.city, value: city.city }))}
              onChange={(city) =>
                setDraft((value) => ({ ...value, city, source: "all" }))}
            />
          </div>
        </div>
        <div className={styles.headerSearch}>
          <Button className={styles.addKeywordButton}>
            + 关键词
          </Button>
          <Button type="primary" onClick={applyFilter} loading={loading}>
            搜索
          </Button>
        </div>
      </header>

      <div className={styles.filterBar}>
        <span className={styles.filterLabel}>房源类型:</span>
        <Select
          className={styles.typeSelect}
          value={draft.rentType}
          options={HomeFilterOptions.types.map((item) => ({
            label: item.label,
            value: item.value,
          }))}
          onChange={(rentType) => setDraft((value) => ({ ...value, rentType }))}
        />
        <span className={styles.filterLabel}>房源:</span>
        <div className={styles.sourceTabs}>
          {sourceOptions.map((source) => (
            <button
              key={source.value}
              className={draft.source === source.value ? styles.sourceTabActive : ""}
              type="button"
              onClick={() => setDraft((value) => ({ ...value, source: source.value }))}
            >
              {source.label}
            </button>
          ))}
        </div>
        <Button className={styles.resetButton} onClick={resetFilter}>
          重置
        </Button>
      </div>

      <div
        className={`${styles.mapBody} ${
          routeSidebarOpen ? "" : styles.mapBodyCollapsed
        }`}
      >
        <aside className={styles.navigationPanel}>
          <div className={styles.routePanel}>
            <div className={styles.routeHeader}>
              <span>路线</span>
              <Button type="text" onClick={() => setRouteSidebarOpen(false)}>
                收起
              </Button>
            </div>
            <div
              ref={routePanelRef}
              className={`${styles.routeContent} ${
                routePanelOpen ? "" : styles.routeContentCollapsed
              }`}
            />
            {!routePanelOpen && (
              <div className={styles.routePlaceholder}>
                点击房源标记里的“导航”，路线会显示在这里。
              </div>
            )}
          </div>
        </aside>

        <Button
          className={styles.sidebarToggle}
          type="primary"
          icon={routeSidebarOpen ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
          onClick={() => setRouteSidebarOpen((open) => !open)}
          aria-label={routeSidebarOpen ? "收起路线" : "展开路线"}
        />

        <main className={styles.mapArea}>
          <div className={styles.mapToolbar}>
            <div className={styles.workInput}>
              <Input
                id="map-work-address"
                value={workAddress}
                prefix={<EnvironmentOutlined />}
                placeholder="上班地点"
                onChange={(event) => {
                  setWorkAddress(event.target.value);
                  setCommutePosition(undefined);
                }}
                onPressEnter={runArrivalRange}
              />
            </div>
            <div className={styles.minutes}>
              <Slider
                min={1}
                max={60}
                value={commuteMinutes}
                onChange={setCommuteMinutes}
              />
              <span>{commuteMinutes} 分钟</span>
            </div>
            <Select
              className={styles.modeSelect}
              value={commuteMode}
              options={[
                { label: "地铁+公交", value: "" },
                { label: "地铁", value: "SUBWAY" },
                { label: "公交", value: "BUS" },
              ]}
              onChange={setCommuteMode}
            />
            <Button type="primary" icon={<AimOutlined />} onClick={runArrivalRange}>
              到达圈
            </Button>
          </div>

          <div ref={mapContainerRef} className={styles.mapCanvas} />

          <Button
            className={styles.locateButton}
            icon={<EnvironmentOutlined />}
            onClick={async () => {
              const position = await ensureCommutePosition();
              if (position) mapRef.current?.setZoomAndCenter(15, position);
            }}
          >
            我在哪
          </Button>
        </main>
      </div>
    </div>
  );
}
