import { useState } from "react";
import { Alert, Button, Form, Input } from "antd";
import { ArrowRightOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { register, type CurrentUser, type RegisterInput } from "../../api/auth";
import { AUTH_ROUTES } from "../../router/paths";
import AuthLayout from "../Auth/AuthLayout";
import styles from "../Auth/AuthLayout.module.scss";

type RegisterForm = RegisterInput & { confirmPassword: string };

export default function RegisterPage({ onRegister }: { onRegister: (user: CurrentUser) => void }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <AuthLayout>
      <span className={styles.eyebrow}>创建账号</span>
      <h2>注册你的工作台</h2>
      <p>注册普通用户账号，开始使用经营数据问答。</p>
      {error && <Alert type="error" message={error} showIcon />}
      <Form
        layout="vertical"
        onFinish={async ({ confirmPassword: _, ...values }: RegisterForm) => {
          setBusy(true);
          setError("");
          try {
            onRegister(await register(values));
          } catch (exception) {
            setError(exception instanceof Error ? exception.message : "注册失败，请重试");
          } finally {
            setBusy(false);
          }
        }}
      >
        <Form.Item
          label="用户名"
          name="username"
          extra="3–32 位，可使用字母、数字、点、下划线和连字符。"
          rules={[
            { required: true, message: "请输入用户名" },
            { min: 3, max: 32, message: "用户名长度为 3–32 位" },
            { pattern: /^[A-Za-z0-9][A-Za-z0-9_.-]*$/, message: "用户名格式不正确" },
          ]}
        >
          <Input size="large" autoComplete="username" placeholder="输入登录用户名" />
        </Form.Item>
        <Form.Item
          label="显示名称"
          name="display_name"
          rules={[
            { required: true, whitespace: true, message: "请输入显示名称" },
            { max: 80, message: "显示名称不能超过 80 个字符" },
          ]}
        >
          <Input size="large" autoComplete="name" placeholder="例如：张三" />
        </Form.Item>
        <Form.Item
          label="密码"
          name="password"
          extra="至少 8 位，包含字母和数字，不能包含空格。"
          rules={[
            { required: true, message: "请输入密码" },
            { min: 8, max: 200, message: "密码长度为 8–200 位" },
            {
              validator: (_, value: unknown) =>
                typeof value === "string" &&
                /\p{L}/u.test(value) &&
                /\p{N}/u.test(value) &&
                !/\s/u.test(value)
                  ? Promise.resolve()
                  : Promise.reject(new Error("密码至少包含一个字母和一个数字，且不能包含空格")),
            },
          ]}
        >
          <Input.Password size="large" autoComplete="new-password" placeholder="设置登录密码" />
        </Form.Item>
        <Form.Item
          label="确认密码"
          name="confirmPassword"
          dependencies={["password"]}
          rules={[
            { required: true, message: "请再次输入密码" },
            ({ getFieldValue }) => ({
              validator(_, value) {
                return !value || getFieldValue("password") === value
                  ? Promise.resolve()
                  : Promise.reject(new Error("两次输入的密码不一致"));
              },
            }),
          ]}
        >
          <Input.Password size="large" autoComplete="new-password" placeholder="再次输入密码" />
        </Form.Item>
        <Button htmlType="submit" type="primary" size="large" block loading={busy}>
          创建账号 <ArrowRightOutlined />
        </Button>
      </Form>
      <div className={styles.authSwitch}>
        已有账号？<Link to={AUTH_ROUTES.login}>返回登录</Link>
      </div>
      <div className={styles.loginNote}>
        <SafetyCertificateOutlined /> 注册账号不会获得系统管理权限
      </div>
    </AuthLayout>
  );
}
