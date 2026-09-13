import { lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Collapse,
  Empty,
  Segmented,
  Spin,
  Table,
  Tag,
  Tooltip,
  message,
} from "antd";
import {
  BarChartOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
  DownloadOutlined,
  CopyOutlined,
  FlagOutlined,
  ReloadOutlined,
  LineChartOutlined,
  PieChartOutlined,
  TableOutlined,
  SafetyCertificateOutlined,
  SoundOutlined,
  PauseCircleOutlined,
  LoadingOutlined,
} from "@ant-design/icons";
// 只有结果选择图表展示时才加载 ECharts 及绘图组件。
const Chart = lazy(() => import("./QueryChart"));
import { format, type Row, type Msg } from "./types";

export function AnalysisSteps({ process }: { process: any[] }) {
  return (
    <div className="analysis-steps">
      {process.map((step: any, index: number) => (
        <div className="analysis-step" key={step.key}>
          <div className="analysis-step-index">{index + 1}</div>
          <div className="analysis-step-body">
            <h4>
              {step.title}
              <span className={"analysis-step-status " + (step.status || "complete")}>
                {step.status === "running" ? "进行中" : "已完成"}
              </span>
            </h4>
            {(step.items || []).map((item: string, itemIndex: number) => (
              <p key={itemIndex}>{item}</p>
            ))}
            {(step.executions || []).map((execution: any, sqlIndex: number) => (
              <div className="analysis-sql" key={sqlIndex}>
                <details className="analysis-sql-details">
                  <summary>{execution.name}</summary>
                  <pre>{execution.executable_sql}</pre>
                </details>
                <details className="analysis-sql-details">
                  <summary>取数逻辑</summary>
                  <pre>{execution.business_sql}</pre>
                </details>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Answer({
  msg,
  onAsk,
  onFeedback,
}: {
  msg: Msg;
  onAsk: (s: string) => void;
  onFeedback: (id: string) => void;
}) {
  const r = msg.result;
  const [tab, setTab] = useState(r?.plan?.chart || "bar");
  const [speechLoading, setSpeechLoading] = useState(false);
  const [speechPlaying, setSpeechPlaying] = useState(false);
  const speech = useRef<HTMLAudioElement | null>(null);
  const speechUrl = useRef<string | null>(null);
  useEffect(
    () => () => {
      speech.current?.pause();
      if (speechUrl.current) URL.revokeObjectURL(speechUrl.current);
    },
    [],
  );

  async function toggleSpeech() {
    if (speech.current && speechPlaying) {
      speech.current.pause();
      setSpeechPlaying(false);
      return;
    }
    if (speech.current) {
      await speech.current.play();
      setSpeechPlaying(true);
      return;
    }
    setSpeechLoading(true);
    try {
      const response = await fetch("/api/audio/speech", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: msg.content.slice(0, 3000) }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "语音合成失败");
      }
      const url = URL.createObjectURL(await response.blob());
      const audio = new Audio(url);
      speechUrl.current = url;
      speech.current = audio;
      audio.onended = () => setSpeechPlaying(false);
      audio.onerror = () => {
        setSpeechPlaying(false);
        message.error("语音播放失败");
      };
      await audio.play();
      setSpeechPlaying(true);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSpeechLoading(false);
    }
  }
  const ok = r?.status === "success";
  if (!ok)
    return (
      <div className="assistant-row">
        <div className="assistant-icon">
          <BarChartOutlined />
        </div>
        <div className="answer-message">
          <strong>
            经管之星 <span>AI 问数助手</span>
          </strong>
          <Alert
            type={r?.status === "error" ? "error" : "info"}
            message={msg.content}
            showIcon
          />
          {r?.status !== "error" && (
            <Button
              size="small"
              icon={speechLoading ? <LoadingOutlined spin /> : speechPlaying ? <PauseCircleOutlined /> : <SoundOutlined />}
              disabled={speechLoading}
              onClick={toggleSpeech}
            >
              {speechPlaying ? "暂停播放" : "播放回答"}
            </Button>
          )}
          {r?.status === "error" && (
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => onAsk("__retry__")}
            >
              重新尝试
            </Button>
          )}
        </div>
      </div>
    );
  const masterData = r.plan.query_kind === "master_data";
  const comparison = !masterData && r.plan.comparison !== "none";
  const unit = r.metric.unit;
  const process = r.analysis_process || [];
  const responseTime = r.completed_at || msg.created_at;
  const pieAllowed =
    unit !== "%" &&
    !comparison &&
    r.rows.every((row: Row) => (row.value ?? 0) >= 0) &&
    r.rows.length > 1;
  const columns: any[] = masterData
    ? r.record_columns.map((column: any) => ({
        title: column.title,
        dataIndex: column.key,
        key: column.key,
      }))
    : [
    {
      title: "分组",
      dataIndex: "label",
      key: "label",
      fixed: "left",
      width: 180,
    },
    {
      title: r.metric.name + "（" + unit + "）",
      dataIndex: "value",
      key: "value",
      align: "right",
      render: (v: number | null) =>
        v === null
          ? "—"
          : v.toLocaleString("zh-CN", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            }),
      sorter: (a: Row, b: Row) => (a.value ?? 0) - (b.value ?? 0),
    },
  ];
  if (comparison)
    columns.push(
      {
        title: "对比期",
        dataIndex: "previous",
        align: "right",
        render: (v: number | null) => format(v, unit),
      },
      {
        title: unit === "%" ? "变化（百分点）" : "变化率",
        dataIndex: unit === "%" ? "difference" : "change",
        align: "right",
        render: (v: number | null) =>
          v === null ? (
            "—"
          ) : (
            <span className={v >= 0 ? "positive" : "negative"}>
              {v > 0 ? "+" : ""}
              {v.toFixed(2)}
              {unit === "%" ? "" : "%"}
            </span>
          ),
      },
    );
  return (
    <div className="assistant-row">
      <div className="assistant-icon">
        <BarChartOutlined />
      </div>
      <div className="answer-message">
        <div className="answer-byline">
          <strong>经管之星</strong>
          <span>AI 问数助手</span>
          <span className="verified">
            <CheckCircleOutlined /> 已核对取数
          </span>
        </div>
        {process.length > 0 && (
          <Collapse
            className="analysis-process"
            items={[
              {
                key: "process",
                label: "查看分析过程",
                children: <AnalysisSteps process={process} />,
              },
            ]}
          />
        )}
        <p className="answer-text">{msg.content}</p>
        <div className="result-card">
          <div className="result-heading">
            <div>
              <span className="card-eyebrow">
                {masterData ? "当前基础资料快照" : `${r.plan.start_date} — ${r.plan.end_date}`}
              </span>
              <h3>
                {r.metric.name}
                {!masterData && r.plan.dimensions.length
                  ? " · " +
                    r.plan.dimensions
                      .map(
                        (d: string) =>
                          ({
                            region: "区域",
                            city: "城市",
                            org_unit: "经营单元",
                            industry: "行业",
                            customer: "客户",
                            product_line: "产品线",
                            salesperson: "销售人员",
                            contract: "合同",
                            receivable_plan: "应收计划",
                            month: "月份",
                          })[d],
                      )
                      .join(" / ")
                  : ""}
              </h3>
            </div>
            <Tag bordered={false}>经营数据</Tag>
          </div>
          <div className="result-kpis">
            <div>
              <span>{r.metric.name} · 全部符合条件数据</span>
              <b>
                {masterData ? r.total_count.toLocaleString("zh-CN") : format(r.total, unit)}
                <small>{masterData ? "个" : unit === "元" ? "元" : ""}</small>
              </b>
            </div>
            {comparison && (
              <>
                <div>
                  <span>对比期</span>
                  <b>
                    {format(r.previous_total, unit)}
                    <small>{unit === "元" ? "元" : ""}</small>
                  </b>
                </div>
                <div>
                  <span>
                    {unit === "%"
                      ? "变化（百分点）"
                      : r.plan.comparison === "yoy"
                        ? "同比变化"
                        : "环比变化"}
                  </span>
                  <b
                    className={
                      (unit === "%" ? r.difference : r.change) >= 0
                        ? "positive"
                        : "negative"
                    }
                  >
                    {(unit === "%" ? r.difference : r.change) == null
                      ? "—"
                      : ((unit === "%" ? r.difference : r.change) > 0
                          ? "+"
                          : "") +
                        (unit === "%" ? r.difference : r.change).toFixed(2) +
                        (unit === "%" ? "" : "%")}
                  </b>
                </div>
              </>
            )}
          </div>
          {!masterData && <div className="chart-toolbar">
            <Segmented
              value={tab}
              onChange={(v) => setTab(String(v))}
              options={[
                { value: "bar", label: "柱状图", icon: <BarChartOutlined /> },
                { value: "line", label: "折线图", icon: <LineChartOutlined /> },
                ...(pieAllowed
                  ? [
                      {
                        value: "pie",
                        label: "占比图",
                        icon: <PieChartOutlined />,
                      },
                    ]
                  : []),
                { value: "table", label: "数据表", icon: <TableOutlined /> },
              ]}
            />
            <Tooltip title="导出当前展示结果">
              <Button
                type="text"
                icon={<DownloadOutlined />}
                href={"/api/messages/" + msg.id + "/export"}
                aria-label="导出 CSV"
              />
            </Tooltip>
          </div>}
          {r.empty ? (
            <Empty description="当前范围没有业务记录" />
          ) : masterData ? (
            r.records.length ? (
              <Table
                rowKey={(record: any) => record.code || record.name}
                size="small"
                dataSource={r.records}
                columns={columns}
                pagination={r.records.length > 10 ? { pageSize: 10, showSizeChanger: false } : false}
                scroll={{ x: 650 }}
              />
            ) : null
          ) : tab === "table" ? (
            <Table
              rowKey="label"
              size="small"
              dataSource={r.rows}
              columns={columns}
              pagination={
                r.rows.length > 10
                  ? { pageSize: 10, showSizeChanger: false }
                  : false
              }
              scroll={{ x: 550 }}
            />
          ) : (
            <Suspense fallback={<Spin size="large" />}>
              <Chart
                rows={r.rows}
                type={tab === "pie" && !pieAllowed ? "bar" : tab}
                unit={unit}
                comparison={comparison}
              />
            </Suspense>
          )}
          <div className="result-foot">
            <SafetyCertificateOutlined /> {masterData ? "基础资料实时查询" : `数据截止 ${r.cutoff_date}`}
            {r.truncated && (
              <span>
                {" "}
                · 展示 {masterData ? r.records.length : r.rows.length} / {r.group_count} {masterData ? "条" : "组"}
              </span>
            )}
          </div>
        </div>
        <div className="answer-actions">
          <div>
            <Tooltip title="复制结论">
              <Button
                type="text"
                icon={<CopyOutlined />}
                aria-label="复制结论"
                onClick={() =>
                  navigator.clipboard
                    .writeText(msg.content)
                    .then(() => message.success("已复制"))
                }
              />
            </Tooltip>
            <Tooltip title="反馈问题">
              <Button
                type="text"
                icon={<FlagOutlined />}
                aria-label="反馈问题"
                onClick={() => onFeedback(msg.id)}
              />
            </Tooltip>
            <Tooltip title={speechPlaying ? "暂停播放" : "播放回答"}>
              <Button
                type="text"
                icon={speechLoading ? <LoadingOutlined spin /> : speechPlaying ? <PauseCircleOutlined /> : <SoundOutlined />}
                aria-label={speechPlaying ? "暂停播放" : "播放回答"}
                disabled={speechLoading}
                onClick={toggleSpeech}
              />
            </Tooltip>
          </div>
          <span className="answer-meta">
            耗时 {(r.duration_ms / 1000).toFixed(1)}s
            {r.usage?.total_tokens != null && ` · Token ${r.usage.total_tokens}`}
            {responseTime &&
              ` · ${new Date(responseTime).toLocaleTimeString("zh-CN", {
                hour12: false,
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}`}
          </span>
        </div>
        <div className="followups">
          {(r.suggestions || []).map((q: string) => (
            <button key={q} onClick={() => onAsk(q)}>
              {q}
              <ArrowRightOutlined />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
