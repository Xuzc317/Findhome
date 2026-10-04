import { LockOutlined, MailOutlined } from "@ant-design/icons";
import React, { useState } from "react";
import styles from "./styles.module.css";
import { Button, Input, message, Tabs } from "antd";
import { userService } from "@/services";
import { Link, useNavigate } from "react-router-dom";
import { Helmet } from "react-helmet";
import { getPageTitle } from "@/utils";
import Header from "@/components/header";

type PageType = "find_password" | "reset_password";

const Page: React.FC = () => {
  const [type, setType] = useState<PageType>("find_password");
  return (
    <>
      <Header hiddenCity hiddenPlaceholder style={{ background: "transparent" }} />
      <div className={styles.container}>
        <Helmet>
          <title>{getPageTitle("找回密码")}</title>
        </Helmet>
        <SwitchTab
          value={type}
          onChange={(key) => {
            setType(key);
          }}
        />
        {type === "find_password" && (
          <FindPassword
            onSuccess={() => {
              setType("reset_password");
            }}
          />
        )}
        {type === "reset_password" && <ResetPassword />}
      </div>
    </>
  );
};

export default Page;

const items: {
  key: PageType;
  label: string;
}[] = [
  { key: "find_password", label: "找回密码" },
  { key: "reset_password", label: "重置密码" },
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

function FindPassword(props: { onSuccess?: () => void }) {
  const [email, setEmail] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const handleLogin = async () => {
    try {
      setLoading(true);
      await userService.findPasswordCode({
        email: email,
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
        size="large"
        onChange={(e) => {
          setEmail(e.target.value);
        }}
      />
      <div className="flex justify-between mt-4 w-full">
        <span></span>
        <Link to="/user/login">直接登录</Link>
      </div>
      <Button
        disabled={!email}
        type="primary"
        className="mt-4"
        block
        size="large"
        loading={loading}
        onClick={handleLogin}
      >
        发送验证码
      </Button>
    </div>
  );
}

/**
 * 注册
 */
function ResetPassword() {
  const [resetCode, setResetCode] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const handleRegister = async () => {
    try {
      setLoading(true);
      await userService.resetPassword({
        resetCode,
        password: password,
      });
      navigate("/user/login");
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className={styles.content}>
      <Input
        value={resetCode}
        placeholder="验证码"
        prefix={<MailOutlined />}
        type="email"
        size="large"
        onChange={(e) => {
          setResetCode(e.target.value);
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
        disabled={!resetCode || password.length < 6}
        type="primary"
        className="mt-4"
        block
        size="large"
        loading={loading}
        onClick={handleRegister}
      >
        重置密码
      </Button>
    </div>
  );
}
