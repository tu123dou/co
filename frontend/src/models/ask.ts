export type ResultRow = {
  label: string;
  value: number | null;
  previous: number | null;
  change: number | null;
  difference: number | null;
};

export type QueryPlan =
  | {
      // 早期保存的指标计划没有 query_kind；基础资料始终显式标记。
      query_kind?: "metric";
      chart: "bar" | "line" | "pie" | "table";
      comparison: "none" | "yoy" | "previous_period";
      start_date?: string;
      end_date?: string;
      dimensions: string[];
    }
  | { query_kind: "master_data"; chart: "table" };

export type AnalysisStep = {
  key: string;
  title: string;
  status?: "running" | "complete";
  items?: string[];
  executions?: Array<{
    name?: string;
    executable_sql: string;
    business_sql: string;
  }>;
};

export type QueryResult = {
  status: "success";
  plan: QueryPlan;
  metric: { name: string; unit: string; definition?: string };
  rows?: ResultRow[];
  records?: Record<string, unknown>[];
  record_columns?: Array<{ key: string; title: string }>;
  total?: number | null;
  total_count?: number;
  previous_total: number | null;
  change?: number | null;
  difference?: number | null;
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
