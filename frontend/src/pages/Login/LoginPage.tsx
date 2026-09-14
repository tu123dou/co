import { useState } from "react";
import { Alert, Button, Form, Input } from "antd";
import { ArrowRightOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { login, type CurrentUser } from "../../api/auth";
import { AUTH_ROUTES } from "../../router/paths";
import AuthLayout from "../Auth/AuthLayout";
import styles from "../Auth/AuthLayout.module.scss";

export default function LoginPage({ onLogin }: { onLogin: (user: CurrentUser) => void }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <AuthLayout>
      <span className={styles.eyebrow}>欢迎回来</span>
      <h2>登录你的工作台</h2>
      <p>使用本地账号，开始探索经营数据。</p>
      {error && <Alert type="error" message={error} showIcon />}
      <Form
        layout="vertical"
        initialValues={{ username: "admin" }}
        onFinish={async (values: { username: string; password: string }) => {
          setBusy(true);
          setError("");
          try {
            onLogin(await login(values));
          } catch (exception) {
            setError(exception instanceof Error ? exception.message : "登录失败，请重试");
          } finally {
            setBusy(false);
          }
        }}
      >
        <Form.Item
          label="用户名"
          name="username"
          rules={[{ required: true, message: "请输入用户名" }]}
        >
          <Input size="large" autoComplete="username" />
        </Form.Item>
        <Form.Item label="密码" name="password" rules={[{ required: true, message: "请输入密码" }]}>
          <Input.Password size="large" autoComplete="current-password" placeholder="输入账号密码" />
        </Form.Item>
        <Button htmlType="submit" type="primary" size="large" block loading={busy}>
          进入工作台 <ArrowRightOutlined />
        </Button>
      </Form>
      <div className={styles.authSwitch}>
        还没有账号？<Link to={AUTH_ROUTES.register}>创建账号</Link>
      </div>
    </AuthLayout>
  );
}
