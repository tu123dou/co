import type { AnalysisStep, QueryResult } from "../models/ask";
import type { AskStreamEvent, ChatMessage } from "./conversations";

const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const numeric = (value: unknown) => typeof value === "number" && Number.isFinite(value);
const nullableNumber = (value: unknown) => value === null || numeric(value);
const strings = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === "string");

function analysisStep(value: unknown): value is AnalysisStep {
  return (
    object(value) &&
    typeof value.key === "string" &&
    typeof value.title === "string" &&
    (value.status === undefined || value.status === "running" || value.status === "complete") &&
    (value.items === undefined || strings(value.items)) &&
    (value.executions === undefined ||
      (Array.isArray(value.executions) &&
        value.executions.every(
          (entry: unknown) =>
            object(entry) &&
            (entry.name === undefined || typeof entry.name === "string") &&
            typeof entry.executable_sql === "string" &&
            typeof entry.business_sql === "string",
        )))
  );
}

function queryResult(value: Record<string, unknown>): value is QueryResult {
  if (!object(value.plan) || !object(value.metric)) return false;
  const plan = value.plan;
  if (
    typeof value.metric.name !== "string" ||
    typeof value.metric.unit !== "string" ||
    (value.metric.definition !== undefined && typeof value.metric.definition !== "string") ||
    typeof value.empty !== "boolean" ||
    typeof value.truncated !== "boolean" ||
    !numeric(value.group_count) ||
    !numeric(value.duration_ms) ||
    typeof value.cutoff_date !== "string" ||
    !nullableNumber(value.previous_total) ||
    (value.completed_at !== undefined && typeof value.completed_at !== "string") ||
    (value.usage !== undefined &&
      (!object(value.usage) ||
        (value.usage.total_tokens !== undefined && !numeric(value.usage.total_tokens)))) ||
    (value.suggestions !== undefined && !strings(value.suggestions)) ||
    (value.analysis_process !== undefined &&
      (!Array.isArray(value.analysis_process) || !value.analysis_process.every(analysisStep)))
  )
    return false;

  // 基础资料没有指标汇总、比较期或维度字段，不用指标契约误判合法响应。
  if (plan.query_kind === "master_data") {
    return (
      plan.chart === "table" &&
      numeric(value.total_count) &&
      Array.isArray(value.records) &&
      value.records.every(object) &&
      Array.isArray(value.record_columns) &&
      value.record_columns.every(
        (column: unknown) =>
          object(column) && typeof column.key === "string" && typeof column.title === "string",
      )
    );
  }
  return (
    (plan.query_kind === "metric" || plan.query_kind === undefined) &&
    ["bar", "line", "pie", "table"].includes(String(plan.chart)) &&
    ["none", "yoy", "previous_period"].includes(String(plan.comparison)) &&
    typeof plan.start_date === "string" &&
    typeof plan.end_date === "string" &&
    strings(plan.dimensions) &&
    nullableNumber(value.total) &&
    nullableNumber(value.change) &&
    nullableNumber(value.difference) &&
    Array.isArray(value.rows) &&
    value.rows.every(
      (row: unknown) =>
        object(row) &&
        typeof row.label === "string" &&
        nullableNumber(row.value) &&
        nullableNumber(row.previous) &&
        nullableNumber(row.change) &&
        nullableNumber(row.difference),
    )
  );
}

function resultMessage(value: unknown): value is ChatMessage {
  if (
    !object(value) ||
    typeof value.id !== "string" ||
    value.role !== "assistant" ||
    typeof value.content !== "string" ||
    (value.created_at !== undefined && typeof value.created_at !== "string") ||
    !object(value.result)
  )
    return false;
  return value.result.status === "success"
    ? queryResult(value.result)
    : ["error", "cancelled", "clarify", "unsupported"].includes(String(value.result.status)) &&
        (value.result.error_code === undefined || typeof value.result.error_code === "string");
}

function parseEvent(line: string): AskStreamEvent {
  let value: unknown;
  try {
    value = JSON.parse(line);
  } catch {
    throw new Error("服务返回了无法识别的流式数据");
  }
  if (object(value)) {
    if (
      value.type === "status" &&
      typeof value.stage === "string" &&
      (value.detail === undefined || typeof value.detail === "string")
    ) {
      return { type: "status", stage: value.stage, detail: value.detail };
    }
    if (value.type === "analysis" && analysisStep(value.step))
      return { type: "analysis", step: value.step };
    if (value.type === "result" && resultMessage(value.message))
      return { type: "result", message: value.message };
  }
  throw new Error("服务返回的流式数据字段不完整或格式不正确");
}

export async function readAskStream(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
  onEvent: (event: AskStreamEvent) => void,
) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  let finished = false;
  let receivedResult = false;
  const cancel = () => {
    void reader.cancel().catch(() => undefined);
  };
  const consume = (line: string) => {
    signal.throwIfAborted();
    if (!line.trim()) return;
    const event = parseEvent(line);
    onEvent(event); // 消费方异常原样传播，不误报成 JSON 解析错误。
    if (event.type === "result") receivedResult = true;
  };
  signal.addEventListener("abort", cancel, { once: true });
  try {
    signal.throwIfAborted();
    while (true) {
      const chunk = await reader.read();
      signal.throwIfAborted();
      pending += decoder.decode(chunk.value, { stream: !chunk.done });
      const lines = pending.split("\n");
      pending = lines.pop() ?? "";
      lines.forEach(consume);
      if (chunk.done) {
        finished = true;
        break;
      }
    }
    consume(pending);
    if (!receivedResult) throw new Error("连接已结束，但没有收到完整回答，请重试");
  } finally {
    signal.removeEventListener("abort", cancel);
    if (!finished) cancel();
    reader.releaseLock();
  }
}
