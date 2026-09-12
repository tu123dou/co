export type Row = {
  label: string;
  value: number | null;
  previous: number | null;
  change: number | null;
  difference: number | null;
};
export type Msg = {
  id: string;
  role: string;
  content: string;
  created_at?: string;
  result?: any;
};
export const format = (n: number | null, unit = "元") =>
  n == null
    ? "—"
    : unit === "%"
      ? n.toFixed(2) + "%"
      : Math.abs(n) >= 1e8
        ? (n / 1e8).toFixed(2) + " 亿"
        : Math.abs(n) >= 1e4
          ? (n / 1e4).toFixed(2) + " 万"
          : n.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
