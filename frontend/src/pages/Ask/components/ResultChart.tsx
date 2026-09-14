import { useEffect, useRef } from "react";
import type { ResultRow } from "../../../models/ask";
import styles from "../AskPage.module.scss";

const compactNumber = (input: unknown) => {
  const value = Number(input);
  return Number.isFinite(value) ? value.toLocaleString("zh-CN", { maximumFractionDigits: 2 }) : "—";
};

export default function ResultChart({
  rows,
  kind,
  unit,
  comparison,
}: {
  rows: ResultRow[];
  kind: "bar" | "line" | "pie";
  unit: string;
  comparison: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    let instance: {
      setOption: (options: unknown) => void;
      resize: () => void;
      dispose: () => void;
    } | null = null;
    let observer: ResizeObserver | null = null;
    import("../../../lib/echarts").then((echarts) => {
      if (!alive || !host.current) return;
      instance = echarts.init(host.current);
      const data = rows.filter((row) => row.value !== null);
      const isPie = kind === "pie";
      const isMoney = unit === "元";
      instance.setOption({
        color: ["#316cdd", "#7e9edc", "#52a899", "#9386dc", "#e5ad55"],
        textStyle: { fontFamily: "inherit" },
        tooltip: {
          trigger: isPie ? "item" : "axis",
          confine: true,
          ...(!isPie && {
            valueFormatter: (value: unknown) =>
              `${compactNumber(value)}${isMoney ? " 万元" : unit}`,
          }),
        },
        legend: { show: isPie || comparison, bottom: 0, type: "scroll" },
        grid: { top: 48, right: 24, bottom: comparison ? 68 : 48, left: isMoney ? 70 : 54 },
        xAxis: isPie
          ? undefined
          : {
              type: "category",
              data: data.map((row) => row.label),
              axisTick: { show: false },
              axisLabel: {
                interval: 0,
                rotate: data.length > 8 ? 35 : 0,
                formatter: (label: string) =>
                  label.length > 12 ? `${label.slice(0, 11)}…` : label,
              },
            },
        yAxis: isPie
          ? undefined
          : {
              type: "value",
              name: isMoney ? "万元" : unit,
              splitLine: { lineStyle: { color: "#e8edf5", type: "dashed" } },
              axisLabel: { formatter: compactNumber },
            },
        series: isPie
          ? [
              {
                type: "pie",
                radius: ["40%", "66%"],
                center: ["50%", "46%"],
                label: { formatter: "{b}\n{d}%" },
                data: data.map((row) => ({ name: row.label, value: row.value })),
              },
            ]
          : [
              {
                name: "本期",
                type: kind,
                barMaxWidth: 44,
                itemStyle: { borderRadius: kind === "bar" ? [5, 5, 0, 0] : undefined },
                data: data.map((row) =>
                  isMoney && row.value !== null ? row.value / 10000 : row.value,
                ),
              },
              ...(comparison
                ? [
                    {
                      name: "对比期",
                      type: kind,
                      barMaxWidth: 44,
                      data: data.map((row) =>
                        isMoney && row.previous !== null ? row.previous / 10000 : row.previous,
                      ),
                    },
                  ]
                : []),
            ],
      });
      observer = new ResizeObserver(() => instance?.resize());
      observer.observe(host.current);
    });
    return () => {
      alive = false;
      observer?.disconnect();
      instance?.dispose();
    };
  }, [comparison, kind, rows, unit]);

  return (
    <div
      ref={host}
      className={styles["ask-result-chart"]}
      role="img"
      aria-label="查询结果图表，可切换到数据表查看精确数值"
    />
  );
}
