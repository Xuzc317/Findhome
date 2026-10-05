import { MENUS_LIST } from "./config";
import styles from "./styles.module.css";
import classNames from "classnames";
import { UNSAFE_useRouteId, useNavigate } from "react-router-dom";

/**
 * 侧边导航。已移除上游的用户体系（本地个人工具不需要登录）。
 */
export default function Menus() {
  const id = UNSAFE_useRouteId();
  const navigate = useNavigate();

  return (
    <>
      <div style={{ width: 250, flexShrink: 0 }}></div>
      <div className={styles.container}>
        {MENUS_LIST.map((menu) => (
          <div
            key={menu.key}
            className={classNames(styles.item, {
              [styles.itemSel]: id === menu.key,
            })}
            onClick={() => navigate(menu.path)}
          >
            <span style={{ fontSize: 16, width: 20, textAlign: "center" }}>
              {menu.icon}
            </span>
            <span>{menu.title}</span>
          </div>
        ))}
      </div>
    </>
  );
}
