import { lazy, Suspense, useState } from "react";
import { Button, Empty, Segmented, Spin, Table, Tag, Tooltip } from "antd";
import { BarChartOutlined, DownloadOutlined, LineChartOutlined, PieChartOutlined, SafetyCertificateOutlined, TableOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { format, type QueryResult, type Row } from "../../../../models/query";

const Chart = lazy(() => import("./QueryChart"));
const DIMENSION_LABELS: Record<string, string> = {
  region: "区域", city: "城市", org_unit: "经营单元", industry: "行业",
  customer: "客户", product_line: "产品线", salesperson: "销售人员",
  contract: "合同", receivable_plan: "应收计划", month: "月份",
};

export default function ResultCard({ messageId, result }: { messageId: string; result: QueryResult }) {
  const [tab, setTab] = useState(result.plan.chart);
  const masterData = result.plan.query_kind === "master_data";
  const comparison = !masterData && result.plan.comparison !== "none";
  const unit = result.metric.unit;
  const comparisonValue = unit === "%" ? result.difference : result.change;
  const pieAllowed = unit !== "%" && !comparison && result.rows.every((row) => (row.value ?? 0) >= 0) && result.rows.length > 1;
  const columns: ColumnsType<Record<string, unknown> | Row> = masterData
    ? result.record_columns.map((column) => ({ title: column.title, dataIndex: column.key, key: column.key }))
    : [
        { title: "分组", dataIndex: "label", key: "label", fixed: "left", width: 180 },
        { title: `${result.metric.name}（${unit}）`, dataIndex: "value", key: "value", align: "right",
          render: (value: number | null) => value === null ? "—" : value.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
          sorter: (left, right) => ((left as Row).value ?? 0) - ((right as Row).value ?? 0) },
        ...(comparison ? [
          { title: "对比期", dataIndex: "previous", key: "previous", align: "right" as const, render: (value: number | null) => format(value, unit) },
          { title: unit === "%" ? "变化（百分点）" : "变化率", dataIndex: unit === "%" ? "difference" : "change", key: "change", align: "right" as const,
            render: (value: number | null) => value === null ? "—" : <span className={value >= 0 ? "positive" : "negative"}>{value > 0 ? "+" : ""}{value.toFixed(2)}{unit === "%" ? "" : "%"}</span> },
        ] : []),
      ];

  return <div className="result-card">
    <div className="result-heading"><div>
      <span className="card-eyebrow">{masterData ? "当前基础资料快照" : `${result.plan.start_date} — ${result.plan.end_date}`}</span>
      <h3>{result.metric.name}{!masterData && result.plan.dimensions.length
        ? ` · ${result.plan.dimensions.map((dimension) => DIMENSION_LABELS[dimension] || dimension).join(" / ")}` : ""}</h3>
    </div><Tag bordered={false}>经营数据</Tag></div>
    <div className="result-kpis">
      <div><span>{result.metric.name} · 全部符合条件数据</span><b>
        {masterData ? result.total_count.toLocaleString("zh-CN") : format(result.total, unit)}
        <small>{masterData ? "个" : unit === "元" ? "元" : ""}</small>
      </b></div>
      {comparison && <>
        <div><span>对比期</span><b>{format(result.previous_total, unit)}<small>{unit === "元" ? "元" : ""}</small></b></div>
        <div><span>{unit === "%" ? "变化（百分点）" : result.plan.comparison === "yoy" ? "同比变化" : "环比变化"}</span>
          <b className={comparisonValue != null && comparisonValue >= 0 ? "positive" : "negative"}>
            {comparisonValue == null ? "—" : `${comparisonValue > 0 ? "+" : ""}${comparisonValue.toFixed(2)}${unit === "%" ? "" : "%"}`}
          </b></div>
      </>}
    </div>
    {!masterData && <div className="chart-toolbar">
      <Segmented value={tab} onChange={(value) => setTab(value as typeof tab)} options={[
        { value: "bar", label: "柱状图", icon: <BarChartOutlined /> },
        { value: "line", label: "折线图", icon: <LineChartOutlined /> },
        ...(pieAllowed ? [{ value: "pie", label: "占比图", icon: <PieChartOutlined /> }] : []),
        { value: "table", label: "数据表", icon: <TableOutlined /> },
      ]} />
      <Tooltip title="导出当前展示结果"><Button type="text" icon={<DownloadOutlined />}
        href={`/api/messages/${messageId}/export`} aria-label="导出 CSV" /></Tooltip>
    </div>}
    {result.empty ? <Empty description="当前范围没有业务记录" /> : masterData ? (
      result.records.length ? <Table rowKey={(record) => String(record.code || record.name)} size="small"
        dataSource={result.records} columns={columns as ColumnsType<Record<string, unknown>>}
        pagination={result.records.length > 10 ? { pageSize: 10, showSizeChanger: false } : false} scroll={{ x: 650 }} /> : null
    ) : tab === "table" ? <Table rowKey="label" size="small" dataSource={result.rows}
      columns={columns as ColumnsType<Row>} pagination={result.rows.length > 10 ? { pageSize: 10, showSizeChanger: false } : false} scroll={{ x: 550 }} />
    : <Suspense fallback={<Spin size="large" />}><Chart rows={result.rows} type={tab === "pie" && !pieAllowed ? "bar" : tab}
        unit={unit} comparison={comparison} /></Suspense>}
    <div className="result-foot"><SafetyCertificateOutlined /> {masterData ? "基础资料实时查询" : `数据截止 ${result.cutoff_date}`}
      {result.truncated && <span> · 展示 {masterData ? result.records.length : result.rows.length} / {result.group_count} {masterData ? "条" : "组"}</span>}
    </div>
  </div>;
}
