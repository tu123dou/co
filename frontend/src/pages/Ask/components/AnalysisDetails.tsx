import { Collapse } from "antd";
import type { AnalysisStep } from "../../../models/ask";
import styles from "../AskPage.module.scss";

export default function AnalysisDetails({
  steps,
  live = false,
}: {
  steps: AnalysisStep[];
  live?: boolean;
}) {
  if (!steps.length) return null;
  return (
    <Collapse
      className={styles["ask-analysis"]}
      defaultActiveKey={live ? ["analysis"] : []}
      items={[
        {
          key: "analysis",
          label: live ? "实时分析过程" : "查看分析过程",
          children: (
            <div>
              {steps.map((step, index) => (
                <div className={styles["ask-analysis__step"]} key={step.key}>
                  <div className={styles["ask-analysis__index"]}>{index + 1}</div>
                  <div>
                    <h4>
                      {step.title}
                      <span data-status={step.status ?? "complete"}>
                        {step.status === "running" ? "进行中" : "已完成"}
                      </span>
                    </h4>
                    {step.items?.map((item, itemIndex) => (
                      <p key={`${step.key}-${itemIndex}`}>{item}</p>
                    ))}
                    {step.executions?.map((execution, executionIndex) => (
                      <div
                        className={styles["ask-analysis__sql"]}
                        key={`${step.key}-sql-${executionIndex}`}
                      >
                        <details>
                          <summary>{execution.name ?? "可执行 SQL"}</summary>
                          <pre>{execution.executable_sql}</pre>
                        </details>
                        <details>
                          <summary>取数逻辑</summary>
                          <pre>{execution.business_sql}</pre>
                        </details>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ),
        },
      ]}
    />
  );
}
