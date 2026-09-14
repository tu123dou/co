import {
  ApartmentOutlined,
  ArrowRightOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  LineChartOutlined,
  MessageOutlined,
  PieChartOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useMemo, useState } from "react";
import type { AskSettings, Catalog } from "../../../api/workbench";
import styles from "../AskPage.module.scss";

const ICONS = [
  BarChartOutlined,
  PieChartOutlined,
  LineChartOutlined,
  ApartmentOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
];

export default function WelcomePanel({
  catalog,
  settings,
  questions,
  busy,
  onAsk,
  onCatalog,
}: {
  catalog: Catalog | null;
  settings: AskSettings;
  questions: string[];
  busy: boolean;
  onAsk: (question: string) => void;
  onCatalog: () => void;
}) {
  const [offset, setOffset] = useState(0);
  const visible = useMemo(
    () =>
      Array.from(
        { length: Math.min(6, questions.length) },
        (_, index) => questions[(offset + index) % questions.length],
      ),
    [offset, questions],
  );
  const contractCount = catalog?.dataset.counts.contracts;
  const orgCount = catalog?.values.org_unit?.length;

  return (
    <div className={styles["ask-welcome"]}>
      {settings.welcome_enabled && (
        <>
          <div className={styles["ask-welcome__mark"]}>
            <BarChartOutlined />
          </div>
          <span className={styles["ask-welcome__eyebrow"]}>你的经营分析伙伴</span>
          <h1>{settings.welcome_title}</h1>
          <p>{settings.welcome_message}</p>
          <div className={styles["ask-welcome__capabilities"]}>
            <span>
              <CheckCircleOutlined /> 真实 SQL 取数
            </span>
            <span>
              <LineChartOutlined /> 图表自动呈现
            </span>
            <span>
              <MessageOutlined /> 支持连续追问
            </span>
          </div>
          {!!visible.length && (
            <>
              <div className={styles["ask-welcome__suggestion-heading"]}>
                <span>从一个问题开始</span>
                <button
                  disabled={questions.length <= 6}
                  onClick={() => setOffset((current) => (current + 6) % questions.length)}
                >
                  <ReloadOutlined /> 换一批
                </button>
              </div>
              <div className={styles["ask-welcome__questions"]}>
                {visible.map((question, index) => {
                  const Icon = ICONS[index % ICONS.length];
                  return (
                    <button
                      key={question}
                      disabled={busy || !catalog}
                      onClick={() => onAsk(question)}
                    >
                      <span>
                        <Icon />
                      </span>
                      <b>{question}</b>
                      <ArrowRightOutlined />
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}
      <div className={styles["ask-welcome__context"]}>
        <DatabaseOutlined />
        <span>
          企业软件与服务 · {contractCount?.toLocaleString("zh-CN") ?? "—"} 份合同 ·{" "}
          {orgCount ?? "—"} 个经营单元
        </span>
        <button onClick={onCatalog}>查看数据范围</button>
      </div>
    </div>
  );
}
