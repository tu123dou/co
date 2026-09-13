import { post, request } from "./client";

export const listFeedbacks = (query: URLSearchParams) => request<any>(`/feedbacks?${query}`);
export const createFeedback = (messageId: string, comment: string) =>
  post("/feedbacks", { message_id: messageId, comment });
export const reviewFeedback = (id: number, body: unknown) =>
  request(`/feedbacks/${id}`, { method: "PATCH", body: JSON.stringify(body) });
