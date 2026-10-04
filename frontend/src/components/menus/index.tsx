import { Button } from "antd";
import { MENUS_LIST } from "./config";
import styles from "./styles.module.css";
import classNames from "classnames";
import { UNSAFE_useRouteId, useNavigate } from "react-router-dom";
import { useUserInfo } from "@/hook/user";
export default function Menus() {
  const id = UNSAFE_useRouteId();
  const navigate = useNavigate();
  const { userInfo, loading } = useUserInfo(false);
  const menus = MENUS_LIST.filter((menu) => {
    if (menu.auth) {
      return !!userInfo;
    }
    return true
  });

  return (
    <>
      <div style={{ width: 250, flexShrink: 0 }}></div>
      <div className={styles.container}>
        {menus.map((menu) => (
          <div
            key={menu.key}
            className={classNames(styles.item, {
              [styles.itemSel]: id === menu.key,
            })}
            onClick={() => {
              if (menu.outside) {
                window.open(menu.path, "_blank");
              } else {
                navigate(menu.path);
              }
            }}
          >
            <img src={menu.icon} />
            <span>{menu.title}</span>
          </div>
        ))}

        {!userInfo && !loading && (
          <Button
            type="primary"
            className={styles.loginBtn}
            size="large"
            onClick={() => {
              navigate("/user/login");
            }}
          >
            登录
          </Button>
        )}
      </div>
    </>
  );
}
