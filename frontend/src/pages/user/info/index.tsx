"use client";
import BaseLayout from "@/components/layout";
import styles from "./styles.module.css";
import { useUserInfo } from "@/hook/user";
import dayjs from "dayjs";
import { setBrowserToken } from "@/utils/user";
import { useNavigate } from "react-router-dom";
import { Helmet } from "react-helmet";
import { getPageTitle } from "@/utils";
import { removeLocalStorage } from "@/utils/storage";
import { StorageKey } from "@/constant";

export default function Page() {
  return (
    <BaseLayout>
      <Helmet>
        <title>{getPageTitle("用户中心")}</title>
      </Helmet>
      <div className={styles.container}>
        <UserInfo />
      </div>
    </BaseLayout>
  );
}

function UserInfo() {
  const { userInfo, loading } = useUserInfo(true);
  const navigate = useNavigate();
  if (!userInfo || loading) return null;
  return (
    <div className={styles.content}>
      <div
        className={styles.logout}
        onClick={() => {
          setBrowserToken("");
          removeLocalStorage(StorageKey.USER_INFO)
          navigate("/");
        }}
      >
        退出登录
      </div>
      <p>
        <span className={styles.label}>用户名：</span>
        {userInfo?.userName}
      </p>
      <p className="mt-4">
        <span className={styles.label}>邮箱：</span>
        {userInfo?.userEmail}
      </p>
      <p className="mt-4">
        <span className={styles.label}>注册时间：</span>
        {dayjs(userInfo?.createTime).format("YYYY-MM-DD")}
      </p>
    </div>
  );
}
