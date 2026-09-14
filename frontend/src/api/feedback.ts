import { post, request } from "./client";

export type FeedbackRecord = {
  id: number;
  display_name: string;
  question: string;
  answer: string;
  comment: string;
  status: "pending" | "resolved";
  resolution_note?: string;
  created_at: string;
};

type FeedbackList = { items: FeedbackRecord[]; total: number };

export const listFeedbacks = (query: URLSearchParams, signal?: AbortSignal) =>
  request<FeedbackList>(`/feedbacks?${query}`, { signal });
export const createFeedback = (messageId: string, comment: string) =>
  post("/feedbacks", { message_id: messageId, comment });
export const reviewFeedback = (
  id: number,
  body: { status: "pending" | "resolved"; resolution_note: string },
) => request(`/feedbacks/${id}`, { method: "PATCH", body: JSON.stringify(body) });
