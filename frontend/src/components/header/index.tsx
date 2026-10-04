import { Link, useSearchParams } from "react-router-dom";
import styles from "./styles.module.css";
import classNames from "classnames";
import { useEffect, useState } from "react";
import { CitiesModal } from "../cities";

export default function Header(props: {
  headerLeft?: React.ReactNode;
  style?: React.CSSProperties;
  hiddenCity?: boolean;
  hiddenPlaceholder?: boolean;
}) {
  const [cityModalVisible, setCityModalVisible] = useState(false);
  const [searchParams] = useSearchParams();

  useEffect(() => {
    // 通过事件 触发显示城市选择弹窗
    const showCityModal = () => {
      setCityModalVisible(true);
    };
    window.addEventListener("showCityModal", showCityModal);
    return () => {
      window.removeEventListener("showCityModal", showCityModal);
    };
  }, []);

  return (
    <>
      <header className={styles.container} style={props.style}>
        <div className={styles.content}>
          <Link to={"/"}>
            <div className={styles.titleContainer}>
              <img className={classNames(styles.logo, styles.mobileHidden)} src="/logo.png" />
              <h1 className="ml-4">地图搜租房</h1>
            </div>
          </Link>
          {props.headerLeft && <div className={styles.left}>{props.headerLeft}</div>}
          {!props.hiddenCity && (
            <div
              className={styles.cityContainer}
              onClick={() => {
                setCityModalVisible(true);
              }}
            >
              <img src="/images/positioning.png" className={styles.positioningIcon} />
              {searchParams.get("city") || "上海"}
            </div>
          )}

        </div>
      </header>
      {!props.hiddenPlaceholder && <div className={styles.placeholder} />}
      <CitiesModal
        visible={cityModalVisible}
        onClose={() => {
          setCityModalVisible(false);
        }}
      />
    </>
  );
}

export function showCityModal() {
  window.dispatchEvent(new Event("showCityModal"));
}
