import type { AnalysisStep, QueryResult } from "../models/ask";
import { post, rawRequest, request } from "./client";
import { readAskStream } from "./askStream";

export type MessageResult =
  | QueryResult
  | {
      status: "error" | "cancelled" | "clarify" | "unsupported";
      error_code?: string;
    };

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
  result?: MessageResult;
};

export type ConversationSummary = {
  id: string;
  title: string;
  pinned: boolean;
  created_at?: string;
  updated_at?: string;
};

export type Conversation = ConversationSummary & { messages: ChatMessage[] };

export type AskStreamEvent =
  | { type: "status"; stage: string; detail?: string }
  | { type: "analysis"; step: AnalysisStep }
  | { type: "result"; message: ChatMessage };

export const listConversations = () => request<ConversationSummary[]>("/conversations");
export const createConversation = () => post<{ id: string }>("/conversations");
export const fetchConversation = (id: string, signal?: AbortSignal) =>
  request<Conversation>(`/conversations/${id}`, { signal });
export const updateConversation = (id: string, body: { title?: string; pinned?: boolean }) =>
  request(`/conversations/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteConversation = (id: string) =>
  request(`/conversations/${id}`, { method: "DELETE" });

export async function streamQuestion(
  conversationId: string,
  question: string,
  signal: AbortSignal,
  onEvent: (event: AskStreamEvent) => void,
) {
  const response = await rawRequest(`/conversations/${conversationId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => ({}));
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? payload.detail
        : undefined;
    throw new Error(typeof detail === "string" ? detail : `问数失败 (${response.status})`);
  }
  if (!response.body) throw new Error("连接已建立，但没有收到响应内容");

  await readAskStream(response.body, signal, onEvent);
}
