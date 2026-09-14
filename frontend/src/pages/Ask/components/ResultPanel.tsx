import { lazy, Suspense, useState } from "react";
import { Button, Empty, Segmented, Spin, Table, Tag, Tooltip } from "antd";
import {
  BarChartOutlined,
  DownloadOutlined,
  LineChartOutlined,
  PieChartOutlined,
  SafetyCertificateOutlined,
  TableOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { QueryResult, ResultRow } from "../../../models/ask";
import styles from "../AskPage.module.scss";

const ResultChart = lazy(() => import("./ResultChart"));
const DIMENSIONS: Record<string, string> = {
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
};

function readable(value: number | null | undefined, unit: string) {
  if (value == null) return "—";
  if (unit === "%") return `${value.toFixed(2)}%`;
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)} 亿`;
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(2)} 万`;
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

export default function ResultPanel({
  messageId,
  result,
}: {
  messageId: string;
  result: QueryResult;
}) {
  const [view, setView] = useState<QueryResult["plan"]["chart"]>(result.plan.chart);
  const plan = result.plan;
  const masterData = plan.query_kind === "master_data";
  const comparison = !masterData && plan.comparison !== "none";
  const unit = result.metric.unit;
  const rows = result.rows ?? [];
  const records = result.records ?? [];
  const recordDefinitions = result.record_columns ?? [];
  const delta = (unit === "%" ? result.difference : result.change) ?? null;
  const allowPie =
    !masterData &&
    !comparison &&
    unit !== "%" &&
    rows.length > 1 &&
    rows.every((row) => (row.value ?? 0) >= 0);

  const metricColumns: ColumnsType<ResultRow> = [
    { title: "分组", dataIndex: "label", key: "label", fixed: "left", width: 180 },
    {
      title: `${result.metric.name}（${unit}）`,
      dataIndex: "value",
      key: "value",
      align: "right",
      render: (value: number | null) =>
        value === null
          ? "—"
          : value.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
      sorter: (left, right) => (left.value ?? 0) - (right.value ?? 0),
    },
    ...(comparison
      ? [
          {
            title: "对比期",
            dataIndex: "previous",
            key: "previous",
            align: "right" as const,
            render: (value: number | null) => readable(value, unit),
          },
          {
            title: unit === "%" ? "变化（百分点）" : "变化率",
            dataIndex: unit === "%" ? "difference" : "change",
            key: "change",
            align: "right" as const,
            render: (value: number | null) =>
              value === null ? (
                "—"
              ) : (
                <span className={value >= 0 ? styles["ask-positive"] : styles["ask-negative"]}>
                  {value > 0 ? "+" : ""}
                  {value.toFixed(2)}
                  {unit === "%" ? "" : "%"}
                </span>
              ),
          },
        ]
      : []),
  ];

  const recordColumns: ColumnsType<Record<string, unknown>> = recordDefinitions.map((column) => ({
    title: column.title,
    dataIndex: column.key,
    key: column.key,
  }));

  return (
    <section className={styles["ask-result"]}>
      <header className={styles["ask-result__heading"]}>
        <div>
          <span>{masterData ? "当前基础资料快照" : `${plan.start_date} — ${plan.end_date}`}</span>
          <h3>
            {result.metric.name}
            {!masterData && plan.dimensions.length
              ? ` · ${plan.dimensions.map((key) => DIMENSIONS[key] ?? key).join(" / ")}`
              : ""}
          </h3>
        </div>
        <Tag bordered={false}>经营数据</Tag>
      </header>
      <div className={styles["ask-kpis"]}>
        <div>
          <span>{result.metric.name} · 全部符合条件数据</span>
          <strong>
            {masterData
              ? (result.total_count ?? 0).toLocaleString("zh-CN")
              : readable(result.total, unit)}
          </strong>
        </div>
        {comparison && (
          <>
            <div>
              <span>对比期</span>
              <strong>{readable(result.previous_total, unit)}</strong>
            </div>
            <div>
              <span>
                {unit === "%"
                  ? "变化（百分点）"
                  : !masterData && plan.comparison === "yoy"
                    ? "同比变化"
                    : "环比变化"}
              </span>
              <strong
                className={
                  delta !== null && delta >= 0 ? styles["ask-positive"] : styles["ask-negative"]
                }
              >
                {delta === null
                  ? "—"
                  : `${delta > 0 ? "+" : ""}${delta.toFixed(2)}${unit === "%" ? "" : "%"}`}
              </strong>
            </div>
          </>
        )}
      </div>
      {!masterData && (
        <div className={styles["ask-result__toolbar"]}>
          <Segmented
            value={view}
            onChange={(value) => setView(value as typeof view)}
            options={[
              { value: "bar", label: "柱状图", icon: <BarChartOutlined /> },
              { value: "line", label: "折线图", icon: <LineChartOutlined /> },
              ...(allowPie ? [{ value: "pie", label: "占比图", icon: <PieChartOutlined /> }] : []),
              { value: "table", label: "数据表", icon: <TableOutlined /> },
            ]}
          />
          <Tooltip title="导出当前结果">
            <Button
              type="text"
              icon={<DownloadOutlined />}
              href={`/api/messages/${messageId}/export`}
              aria-label="导出 CSV"
            />
          </Tooltip>
        </div>
      )}
      {result.empty ? (
        <Empty description="当前范围没有业务记录" />
      ) : masterData ? (
        <Table
          rowKey={(row) => String(row.code ?? row.name)}
          size="small"
          columns={recordColumns}
          dataSource={records}
          pagination={records.length > 10 ? { pageSize: 10, showSizeChanger: false } : false}
          scroll={{ x: 650 }}
        />
      ) : view === "table" ? (
        <Table
          rowKey="label"
          size="small"
          columns={metricColumns}
          dataSource={rows}
          pagination={rows.length > 10 ? { pageSize: 10, showSizeChanger: false } : false}
          scroll={{ x: 550 }}
        />
      ) : (
        <Suspense
          fallback={
            <div className={styles["ask-result__loading"]}>
              <Spin />
            </div>
          }
        >
          <ResultChart
            rows={rows}
            kind={view === "pie" && !allowPie ? "bar" : view}
            unit={unit}
            comparison={comparison}
          />
        </Suspense>
      )}
      <footer className={styles["ask-result__foot"]}>
        <SafetyCertificateOutlined />{" "}
        {masterData ? "基础资料实时查询" : `数据截止 ${result.cutoff_date}`}
        {result.truncated && (
          <span>
            展示 {masterData ? records.length : rows.length} / {result.group_count}{" "}
            {masterData ? "条" : "组"}
          </span>
        )}
      </footer>
    </section>
  );
}
