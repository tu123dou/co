import { post, request } from "./client";
import type { CommonQuestion } from "../config/workbench";
import type { FavoriteQuestion } from "../models/workbench";

export const listCommonQuestions = () => request<CommonQuestion[]>("/common-questions");
export const deleteCommonQuestion = (id: number) => request(`/common-questions/${id}`, { method: "DELETE" });
export const listFavorites = () => request<FavoriteQuestion[]>("/favorites");
export const addFavorite = (question: string) => post("/favorites", { question });
export const deleteFavorite = (id: number) => request(`/favorites/${id}`, { method: "DELETE" });
