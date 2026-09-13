import { post, request } from "./client";

export const listCommonQuestions = () => request<any[]>("/common-questions");
export const deleteCommonQuestion = (id: number) => request(`/common-questions/${id}`, { method: "DELETE" });
export const listFavorites = () => request<any[]>("/favorites");
export const addFavorite = (question: string) => post("/favorites", { question });
export const deleteFavorite = (id: number) => request(`/favorites/${id}`, { method: "DELETE" });
