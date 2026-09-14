/** 工作区路径及其页面标识，菜单和页面跳转共用这一份定义。 */
export const ROUTES = {
  ask: "/ask",
  settings: "/settings",
  feedback: "/feedback",
} as const;

export const AUTH_ROUTES = {
  login: "/login",
  register: "/register",
} as const;

export type WorkspacePage = keyof typeof ROUTES;

export function pageFromPath(pathname: string): WorkspacePage | null {
  const entry = Object.entries(ROUTES).find(([, path]) => path === pathname);
  return (entry?.[0] as WorkspacePage | undefined) ?? null;
}
