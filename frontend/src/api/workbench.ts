import { post, request } from "./client";

export type CustomModelInput = {
  full_url: boolean;
  api_format: "openai" | "anthropic";
  request_url: string;
  api_key: string;
  model_name: string;
  display_name: string;
};
export type CustomModel = Omit<CustomModelInput, "api_key"> & { id: string };
export type ModelTestResult = { model: string; duration_ms: number };

export const addCustomModel = (body: CustomModelInput, signal?: AbortSignal) =>
  request<CustomModel>("/models", { method: "POST", body: JSON.stringify(body), signal });
export const testCustomModel = (body: CustomModelInput, signal?: AbortSignal) =>
  request<ModelTestResult>("/models/test", { method: "POST", body: JSON.stringify(body), signal });

export type CustomModelEdit = Omit<CustomModelInput, "api_key"> & { api_key?: string };
export const editCustomModel = (id: string, body: CustomModelEdit, signal?: AbortSignal) =>
  request<CustomModel>(`/models/${id}`, { method: "PATCH", body: JSON.stringify(body), signal });
export const testEditedModel = (id: string, body: CustomModelEdit, signal?: AbortSignal) =>
  request<ModelTestResult>(`/models/${id}/test`, {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
export const deleteCustomModel = (id: string) =>
  request<AskSettings>(`/models/${id}`, { method: "DELETE" });

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
  model: {
    name: string;
    available: string[];
    configured: boolean;
    builtin_configured?: boolean;
    custom?: CustomModel[];
  };
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
  custom_model_id?: string | null;
  updated_at?: string;
};

export const getCatalog = (signal?: AbortSignal) => request<Catalog>("/catalog", { signal });
export const getWorkbenchSettings = (signal?: AbortSignal) =>
  request<AskSettings>("/workbench/settings", { signal });
export const updateWorkbenchSettings = (body: Partial<AskSettings>) =>
  request<AskSettings>("/workbench/settings", { method: "PATCH", body: JSON.stringify(body) });
export const testModel = (model: string, customModelId?: string) =>
  post<ModelTestResult>(
    "/model/test",
    customModelId ? { custom_model_id: customModelId } : { model },
  );
