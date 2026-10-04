import { userService } from "@/services";
import { getLocalStorageObject } from "@/utils/storage";
import { isLogin } from "@/utils/user";
import { useEffect, useState } from "react";
import { StorageKey } from "@/constant";
import { useNavigate } from "react-router-dom";

export function useUserInfo(isGoLogin?: boolean) {
  const [loading, setLoading] = useState(true);
  const [userInfo, setUserInfo] = useState<UserInfo | null>(
    getLocalStorageObject(StorageKey.USER_INFO) as UserInfo,
  );
  const navigate = useNavigate();
  useEffect(() => {
    if (!isLogin()) {
      if (isGoLogin) navigate("/user/login/");
      setUserInfo(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    userService.getUserInfo(!isGoLogin).then((res) => {
      setUserInfo(res.data);
    }).finally(() => {
      setLoading(false);
    });
  }, [navigate, isGoLogin]);

  return {
    loading,
    userInfo,
  };
}
