import { Link } from "react-router-dom";
import styles from "./styles.module.css";

/**
 * 顶栏：只保留品牌与导航。
 *
 * 已移除上游项目的「城市选择弹窗」——城市现在由主入口向导的第一步决定，
 * 顶栏再放一个城市开关会出现两处状态、互相打架。
 */
export default function Header(props: {
  headerLeft?: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <>
      <header className={styles.container} style={props.style}>
        <div className={styles.content}>
          <Link to={"/"} style={{ textDecoration: "none" }}>
            <div className={styles.titleContainer}>
              <span className={styles.logoMark}>🏠</span>
              <h1 style={{ fontSize: 20, margin: "0 0 0 10px" }}>
                Findhome
              </h1>
              <span
                style={{
                  marginLeft: 10,
                  fontSize: 12,
                  color: "#8c8c8c",
                  fontWeight: 400,
                }}
              >
                本地租房聚合与通勤筛选
              </span>
            </div>
          </Link>
          {props.headerLeft && <div className={styles.left}>{props.headerLeft}</div>}
        </div>
      </header>
      <div className={styles.placeholder} />
    </>
  );
}
