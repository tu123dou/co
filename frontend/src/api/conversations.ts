import { post, rawRequest, request } from "./client";

export const listConversations = () => request<any[]>("/conversations");
export const createConversation = () => post<{ id: string }>("/conversations");
export const getConversation = (id: string) => request<any>(`/conversations/${id}`);
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
