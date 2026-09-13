import { useEffect, useRef } from "react";
import type { Row } from "../models/query";

// 图表统一最多显示两位小数；整数不额外补零，避免 Tooltip 暴露计算精度尾数。
const formatChartNumber = (value: unknown) => {
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("zh-CN", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      })
    : "—";
};

export default function Chart({
  rows,
  type,
  unit,
  comparison,
}: {
  rows: Row[];
  type: string;
  unit: string;
  comparison: boolean;
}) {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let chart: any;
    let alive = true;
    let resize: ResizeObserver;
    import("../lib/echarts").then((echarts) => {
      if (!alive || !element.current) return;
      chart = echarts.init(element.current);
      const valid = rows.filter((r) => r.value !== null);
      const pie = type === "pie";
      const money = unit === "元";
      chart.setOption({
        color: [
          "#3d75ed",
          "#9ebced",
          "#57b2a4",
          "#9b8ce3",
          "#f0ba64",
          "#7eb7d7",
        ],
        textStyle: { fontFamily: "inherit" },
        tooltip: {
          trigger: pie ? "item" : "axis",
          confine: true,
          // 柱状图和折线图中的金额已经换算成万元，这里只控制展示精度。
          ...(!pie && {
            valueFormatter: (value: unknown) =>
              `${formatChartNumber(value)}${money ? " 万元" : "%"}`,
          }),
        },
        legend: {
          show: pie || comparison,
          bottom: 0,
          type: "scroll",
          textStyle: { color: "#66758c" },
        },
        grid: {
          top: 25,
          right: 24,
          bottom: comparison ? 70 : 50,
          left: money ? 68 : 52,
        },
        xAxis: pie
          ? undefined
          : {
              type: "category",
              data: valid.map((r) => r.label),
              axisLine: { lineStyle: { color: "#e6ebf2" } },
              axisTick: { show: false },
              axisLabel: {
                color: "#79869a",
                interval: 0,
                rotate: valid.length > 8 ? 35 : 0,
                formatter: (v: string) =>
                  v.length > 12 ? v.slice(0, 11) + "…" : v,
              },
            },
        yAxis: pie
          ? undefined
          : {
              type: "value",
              name: money ? "万元" : "%",
              nameTextStyle: { color: "#8a96a8" },
              splitLine: { lineStyle: { color: "#edf1f7", type: "dashed" } },
              axisLabel: {
                color: "#79869a",
                formatter: (value: unknown) => formatChartNumber(value),
              },
            },
        series: pie
          ? [
              {
                type: "pie",
                radius: ["45%", "70%"],
                center: ["50%", "43%"],
                avoidLabelOverlap: true,
                label: { formatter: "{b}\n{d}%", fontSize: 12 },
                data: valid.map((r) => ({ name: r.label, value: r.value })),
              },
            ]
          : [
              {
                name: "本期",
                type,
                smooth: false,
                barMaxWidth: 44,
                itemStyle: {
                  borderRadius: type === "bar" ? [4, 4, 0, 0] : undefined,
                },
                areaStyle: type === "line" ? { opacity: 0.06 } : undefined,
                data: valid.map((r) =>
                  r.value === null ? null : money ? r.value / 10000 : r.value,
                ),
              },
              ...(comparison
                ? [
                    {
                      name: "对比期",
                      type,
                      smooth: false,
                      barMaxWidth: 44,
                      data: valid.map((r) =>
                        r.previous === null
                          ? null
                          : money
                            ? r.previous / 10000
                            : r.previous,
                      ),
                    },
                  ]
                : []),
            ],
      });
      resize = new ResizeObserver(() => chart.resize());
      resize.observe(element.current);
    });
    return () => {
      alive = false;
      resize?.disconnect();
      chart?.dispose();
    };
  }, [rows, type, unit, comparison]);
  return (
    <div
      ref={element}
      className="chart"
      role="img"
      aria-label="查询结果图表，详细数值可切换数据表查看"
    />
  );
}
