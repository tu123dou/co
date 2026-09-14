import { useState } from "react";
import { Alert, Button, Form, Input } from "antd";
import { ArrowRightOutlined, BarChartOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { login, type CurrentUser } from "../../api/auth";
import styles from "./LoginPage.module.scss";

export default function LoginPage({ onLogin }: { onLogin: (user: CurrentUser) => void }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className={styles.loginPage}>
      <div className={styles.loginStory}>
        <div className={styles.brand}>
          <span className={styles.brandIcon}>
            <BarChartOutlined />
          </span>
          经管之星
        </div>
        <div className={styles.loginCopy}>
          <span className={styles.eyebrow}>BUSINESS INTELLIGENCE</span>
          <h1>
            让每一个经营问题
            <br />
            都有数据可循。
          </h1>
          <p>
            从一句提问开始，连接指标、趋势与洞察。
            <br />
            在同一个工作台，读懂你的业务。
          </p>
          <div className={styles.sampleChart}>
            <div className={styles.chartHeading}>
              经营分析<span>收入 · 趋势 · 目标</span>
            </div>
            <div className={styles.bars}>
              {[32, 47, 42, 61, 54, 77, 69, 91].map((height, index) => (
                <div key={index} style={{ height: `${height}%` }} />
              ))}
            </div>
            <div className={styles.chartCaption}>提问 → 查询 → 核对 → 洞察</div>
          </div>
        </div>
        <div className={styles.loginFoot}>企业经营智能问数工作台 · v0.1</div>
      </div>
      <div className={styles.loginForm}>
        <div className={styles.formInner}>
          <span className={styles.eyebrow}>欢迎回来</span>
          <h2>登录你的工作台</h2>
          <p>使用本地账号，开始探索经营数据。</p>
          {error && <Alert type="error" message={error} showIcon />}
          <Form
            layout="vertical"
            initialValues={{ username: "admin" }}
            onFinish={async (values) => {
              setBusy(true);
              setError("");
              try {
                onLogin(await login(values));
              } catch (exception) {
                setError((exception as Error).message);
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
            <Form.Item
              label="密码"
              name="password"
              rules={[{ required: true, message: "请输入密码" }]}
            >
              <Input.Password
                size="large"
                autoComplete="current-password"
                placeholder="输入账号密码"
              />
            </Form.Item>
            <Button htmlType="submit" type="primary" size="large" block loading={busy}>
              进入工作台 <ArrowRightOutlined />
            </Button>
          </Form>
          <div className={styles.loginNote}>
            <SafetyCertificateOutlined /> 本地部署 · 数据安全可控
          </div>
        </div>
      </div>
    </div>
  );
}
