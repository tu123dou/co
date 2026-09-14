import { post, request } from "./client";

export type CommonQuestion = {
  id: number;
  question: string;
  success_count: number;
  last_asked_at?: string;
};

export type FavoriteQuestion = {
  id: number;
  question: string;
  created_at?: string;
};

export const listCommonQuestions = () => request<CommonQuestion[]>("/common-questions");
export const deleteCommonQuestion = (id: number) =>
  request(`/common-questions/${id}`, { method: "DELETE" });
export const listFavorites = () => request<FavoriteQuestion[]>("/favorites");
export const addFavorite = (question: string) => post("/favorites", { question });
export const deleteFavorite = (id: number) => request(`/favorites/${id}`, { method: "DELETE" });
