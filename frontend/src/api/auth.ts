import { post, request } from "./client";

export type CurrentUser = { id: number; display_name: string; is_superuser: boolean };
export type RegisterInput = { username: string; display_name: string; password: string };
export const getCurrentUser = () => request<CurrentUser>("/auth/me");
export const login = (body: { username: string; password: string }) =>
  post<CurrentUser>("/auth/login", body);
export const register = (body: RegisterInput) => post<CurrentUser>("/auth/register", body);
export const logout = () => post<{ ok: boolean }>("/auth/logout");
