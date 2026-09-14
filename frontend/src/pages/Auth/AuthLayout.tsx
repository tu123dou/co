import type { ReactNode } from "react";
import { BarChartOutlined } from "@ant-design/icons";
import styles from "./AuthLayout.module.scss";

export default function AuthLayout({ children }: { children: ReactNode }) {
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
        <div className={styles.formInner}>{children}</div>
      </div>
    </div>
  );
}
