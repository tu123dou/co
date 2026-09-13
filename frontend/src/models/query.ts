export type Row = {
  label: string;
  value: number | null;
  previous: number | null;
  change: number | null;
  difference: number | null;
};

export type QueryPlan = {
  query_kind: "metric" | "master_data";
  chart: "bar" | "line" | "pie" | "table";
  comparison: "none" | "yoy" | "mom";
  start_date?: string;
  end_date?: string;
  dimensions: string[];
};

export type AnalysisExecution = {
  name: string;
  executable_sql: string;
  business_sql: string;
};

export type AnalysisStep = {
  key: string;
  title: string;
  status?: "running" | "complete";
  items?: string[];
  executions?: AnalysisExecution[];
};

export type QueryResult = {
  status: "success";
  plan: QueryPlan;
  metric: { name: string; unit: string; definition?: string };
  rows: Row[];
  records: Record<string, unknown>[];
  record_columns: Array<{ key: string; title: string }>;
  total: number | null;
  total_count: number;
  previous_total: number | null;
  change: number | null;
  difference: number | null;
  empty: boolean;
  truncated: boolean;
  group_count: number;
  cutoff_date: string;
  duration_ms: number;
  completed_at?: string;
  usage?: { total_tokens?: number };
  analysis_process?: AnalysisStep[];
  suggestions?: string[];
};
export type Msg = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
  result?: QueryResult | { status: "error" | "cancelled" };
};

export type ConversationSummary = {
  id: string;
  title: string;
  pinned: boolean;
  created_at?: string;
  updated_at?: string;
};

export type Conversation = ConversationSummary & { messages: Msg[] };
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
