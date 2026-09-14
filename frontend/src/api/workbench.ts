import { post, request } from "./client";

export type Catalog = {
  metrics: Record<string, { name: string; unit: string; definition: string }>;
  dimensions: Record<string, unknown>;
  values: Record<string, string[]>;
  dataset: {
    start_date: string;
    cutoff_date: string;
    counts: Record<string, number>;
  };
  data_tables: Array<{ table: string; description: string; count: number }>;
  model: { name: string; available: string[]; configured: boolean };
  examples: string[];
};

export type AskSettings = {
  welcome_enabled: boolean;
  welcome_title: string;
  welcome_message: string;
  starter_questions: string[];
  suggestions_enabled: boolean;
  common_questions_enabled: boolean;
  common_question_threshold: number;
  llm_model: string;
  updated_at?: string;
};

export const getCatalog = (signal?: AbortSignal) => request<Catalog>("/catalog", { signal });
export const getWorkbenchSettings = (signal?: AbortSignal) =>
  request<AskSettings>("/workbench/settings", { signal });
export const updateWorkbenchSettings = (body: Partial<AskSettings>) =>
  request<AskSettings>("/workbench/settings", { method: "PATCH", body: JSON.stringify(body) });
export const testModel = (model: string) =>
  post<{ model: string; duration_ms: number }>("/model/test", { model });
