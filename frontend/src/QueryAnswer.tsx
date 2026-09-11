import { useState } from "react";
import {
  Alert,
  Button,
  Collapse,
  Empty,
  Segmented,
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
} from "@ant-design/icons";
import Chart from "./QueryChart";
import { format, type Row, type Msg } from "./types";
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
  const comparison = r.plan.comparison !== "none";
  const unit = r.metric.unit;
  const pieAllowed =
    unit !== "%" &&
    !comparison &&
    r.rows.every((row: Row) => (row.value ?? 0) >= 0) &&
    r.rows.length > 1;
  const columns: any[] = [
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
        <p className="answer-text">{msg.content}</p>
        <div className="result-card">
          <div className="result-heading">
            <div>
              <span className="card-eyebrow">
                {r.plan.start_date} — {r.plan.end_date}
              </span>
              <h3>
                {r.metric.name}
                {r.plan.dimensions.length
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
                            month: "月份",
                          })[d],
                      )
                      .join(" / ")
                  : ""}
              </h3>
            </div>
            <Tag bordered={false}>模拟数据</Tag>
          </div>
          <div className="result-kpis">
            <div>
              <span>{r.metric.name} · 全部符合条件数据</span>
              <b>
                {format(r.total, unit)}
                <small>{unit === "元" ? "元" : ""}</small>
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
          <div className="chart-toolbar">
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
          </div>
          {r.empty ? (
            <Empty description="当前范围没有业务记录" />
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
            <Chart
              rows={r.rows}
              type={tab === "pie" && !pieAllowed ? "bar" : tab}
              unit={unit}
              comparison={comparison}
            />
          )}
          <div className="result-foot">
            <SafetyCertificateOutlined /> 数据截止 {r.cutoff_date}
            {r.truncated && (
              <span>
                {" "}
                · 展示 {r.rows.length} / {r.group_count} 组
              </span>
            )}
            <span>{(r.duration_ms / 1000).toFixed(1)}s</span>
          </div>
        </div>
        <Collapse
          ghost
          size="small"
          items={[
            {
              key: "trace",
              label: "查看指标口径与取数依据",
              children: (
                <div className="trace">
                  <p>
                    <b>指标口径：</b>
                    {r.metric.definition}
                  </p>
                  <p>
                    <b>数据版本：</b>
                    {r.dataset_version} · 指标版本 v1
                  </p>
                  <p>
                    <b>模型：</b>
                    {r.model}
                  </p>
                  {r.comparison_range && (
                    <p>
                      <b>对比期间：</b>
                      {r.comparison_range.start} — {r.comparison_range.end}
                    </p>
                  )}
                  <p>
                    <b>筛选条件：</b>
                    {r.plan.filters.length
                      ? r.plan.filters
                          .map((f: any) => f.values.join("、"))
                          .join("；")
                      : "全部"}
                  </p>
                  {r.executions.map((e: any, i: number) => (
                    <div key={i}>
                      <b>{i ? "对比期 SQL" : "本期 SQL"}</b>
                      <pre>{e.sql}</pre>
                      <pre>{JSON.stringify(e.parameters, null, 2)}</pre>
                    </div>
                  ))}
                </div>
              ),
            },
          ]}
        />
        <div className="answer-actions">
          <Tooltip title="复制结论">
            <Button
              type="text"
              size="small"
              icon={<CopyOutlined />}
              onClick={() =>
                navigator.clipboard
                  .writeText(msg.content)
                  .then(() => message.success("已复制"))
              }
            />
          </Tooltip>
          <Button
            type="text"
            size="small"
            icon={<FlagOutlined />}
            onClick={() => onFeedback(msg.id)}
          >
            反馈
          </Button>
        </div>
        <div className="followups">
          {r.suggestions.map((q: string) => (
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
