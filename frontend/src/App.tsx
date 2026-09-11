import { useEffect, useState } from "react";
import { Alert, Button, Form, Input, Spin } from "antd";
import {
  BarChartOutlined,
  ArrowRightOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import { api, post } from "./api";
import Workbench from "./Workbench";
export default function App() {
  const [user, setUser] = useState<any>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    api("/auth/me")
      .then(setUser)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  if (loading)
    return (
      <div className="screen-center">
        <Spin size="large" />
      </div>
    );
  if (user)
    return (
      <Workbench
        user={user}
        onLogout={() => post("/auth/logout").then(() => setUser(null))}
      />
    );
  return (
    <div className="login-page">
      <div className="login-story">
        <div className="brand">
          <span className="brand-icon">
            <BarChartOutlined />
          </span>
          经管之星
        </div>
        <div className="login-copy">
          <span className="eyebrow">BUSINESS INTELLIGENCE</span>
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
          <div className="sample-chart">
            <div className="chart-heading">
              经营分析<span>收入 · 趋势 · 目标</span>
            </div>
            <div className="bars">
              {[32, 47, 42, 61, 54, 77, 69, 91].map((h, i) => (
                <div key={i} style={{ height: h + "%" }} />
              ))}
            </div>
            <div className="chart-caption">提问 → 查询 → 核对 → 洞察</div>
          </div>
        </div>
        <div className="login-foot">企业经营智能问数工作台 · v0.1</div>
      </div>
      <div className="login-form">
        <div className="form-inner">
          <span className="eyebrow">欢迎回来</span>
          <h2>{user ? "工作台正在准备中" : "登录你的工作台"}</h2>
          <p>使用本地账号，开始探索经营数据。</p>
          {error && <Alert type="error" message={error} showIcon />}
          <Form
            layout="vertical"
            initialValues={{ username: "admin" }}
            onFinish={async (values) => {
              setBusy(true);
              setError("");
              try {
                setUser(await post("/auth/login", values));
              } catch (e) {
                setError((e as Error).message);
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
            <Button
              htmlType="submit"
              type="primary"
              size="large"
              block
              loading={busy}
            >
              进入工作台 <ArrowRightOutlined />
            </Button>
          </Form>
          <div className="login-note">
            <SafetyCertificateOutlined /> 本地部署 · 业务数据为模拟生成
          </div>
        </div>
      </div>
    </div>
  );
}
