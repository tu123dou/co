import { post, rawRequest, request } from "./client";
import type { Conversation, ConversationSummary, Msg } from "../models/query";

export const listConversations = () => request<ConversationSummary[]>("/conversations");
export const createConversation = () => post<{ id: string }>("/conversations");
export const getConversation = (id: string) => request<Conversation>(`/conversations/${id}`);
export const updateConversation = (id: string, body: unknown) =>
  request(`/conversations/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteConversation = (id: string) => request(`/conversations/${id}`, { method: "DELETE" });
export const askQuestion = (id: string, question: string, signal: AbortSignal) =>
  rawRequest(`/conversations/${id}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
  });

export type AskEvent =
  | { type: "status"; stage: string; detail?: string }
  | { type: "analysis"; step: unknown }
  | { type: "result"; message: Msg };

/** Parse the backend's newline-delimited stream without leaking transport details into UI hooks. */
export async function readAskEvents(
  response: Response,
  onEvent: (event: AskEvent) => void,
) {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "问数失败");
  }
  if (!response.body) throw new Error("连接中断，未收到响应内容");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) if (line.trim()) onEvent(JSON.parse(line) as AskEvent);
    if (done) break;
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer) as AskEvent);
}
