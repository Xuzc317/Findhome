"use client";

import { LockOutlined, MailOutlined } from "@ant-design/icons";
import React, { useState } from "react";
import styles from "./styles.module.css";
import { Button, Checkbox, Input, message, Tabs } from "antd";
import { userService } from "@/services";
import { setBrowserToken } from "@/utils/user";
import { setLocalStorageObject } from "@/utils/storage";
import { StorageKey } from "@/constant";
import { Link, useNavigate } from "react-router-dom";
import { getPageTitle } from "@/utils";
import { Helmet } from "react-helmet";
import Header from "@/components/header";

type PageType = "login" | "register" | "check_code";

const Page: React.FC = () => {
  const [type, setType] = useState<PageType>("login");
  return (
    <>
      <Header hiddenCity hiddenPlaceholder style={{ background: "transparent" }} />
      <div className={styles.container}>
        <Helmet>
          <title>{getPageTitle("登录")}</title>
        </Helmet>
        <SwitchTab
          value={type}
          onChange={(key) => {
            setType(key);
          }}
        />
        {type === "login" && <Login />}
        {type === "register" && (
          <Register
            onSuccess={() => {
              setType("check_code");
            }}
          />
        )}
        {type === "check_code" && (
          <CheckCode
            onSuccess={() => {
              setType("login");
            }}
          />
        )}
      </div>
    </>
  );
};

export default Page;

const items: {
  key: PageType;
  label: string;
}[] = [
  { key: "login", label: "登录" },
  { key: "register", label: "注册" },
  { key: "check_code", label: "激活" },
];

function SwitchTab(props: { value: string; onChange?: (key: PageType) => void }) {
  return (
    <Tabs
      defaultActiveKey="1"
      activeKey={props.value}
      items={items}
      onChange={(key) => props.onChange?.(key as PageType)}
    />
  );
}

function Login() {
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async () => {
    try {
      setLoading(true);
      const res = await userService.login({
        userName: email,
        password: password,
      });
      setBrowserToken(res.data.token);
      setLocalStorageObject(StorageKey.USER_INFO, res.data.user);
      navigate("/");
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className={styles.content}>
      <Input
        value={email}
        placeholder="邮箱"
        prefix={<MailOutlined />}
        size="large"
        onChange={(e) => {
          setEmail(e.target.value);
        }}
      />
      <Input.Password
        value={password}
        placeholder="密码"
        prefix={<LockOutlined />}
        className="mt-4"
        size="large"
        onChange={(e) => setPassword(e.target.value)}
      />
      <div className="flex justify-between mt-4 w-full">
        <Checkbox style={{ alignItems: "center" }} checked>
          自动登录
        </Checkbox>
        <Link to="/user/find-password">忘记密码</Link>
      </div>
      <Button
        disabled={!email || password.length < 6}
        type="primary"
        className="mt-4"
        block
        size="large"
        loading={loading}
        onClick={handleLogin}
      >
        登录
      </Button>
    </div>
  );
}

/**
 * 注册
 */
function Register(props: { onSuccess?: () => void }) {
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
    try {
      setLoading(true);
      await userService.register({
        email,
        password: password,
      });
      props.onSuccess?.();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className={styles.content}>
      <Input
        value={email}
        placeholder="邮箱"
        prefix={<MailOutlined />}
        type="email"
        size="large"
        onChange={(e) => {
          setEmail(e.target.value);
        }}
      />{" "}
      <Input.Password
        value={password}
        placeholder="密码"
        prefix={<LockOutlined />}
        className="mt-4"
        size="large"
        onChange={(e) => setPassword(e.target.value)}
      />{" "}
      <Button
        disabled={!email || password.length < 6}
        type="primary"
        className="mt-4"
        block
        size="large"
        loading={loading}
        onClick={handleRegister}
      >
        注册
      </Button>
    </div>
  );
}

function CheckCode(props: { onSuccess?: () => void }) {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);

  const handleCode = () => {
    setLoading(true);
    userService
      .activate({ activationCode: code })
      .then(() => {
        props.onSuccess?.();
      })
      .catch((error) => {
        message.error(error.message);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  return (
    <div className={styles.content}>
      <Input
        placeholder="请输入注册邮箱中的激活码~"
        prefix={<MailOutlined />}
        size="large"
        value={code}
        onChange={(e) => setCode(e.target.value)}
      />
      <Button
        disabled={!code}
        type="primary"
        className="mt-4"
        block
        size="large"
        onClick={handleCode}
        loading={loading}
      >
        提交
      </Button>
    </div>
  );
}
