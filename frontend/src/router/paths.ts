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

export const ASK_CONVERSATION_ROUTE = `${ROUTES.ask}/:conversationId`;

export function askConversationPath(conversationId: string) {
  return `${ROUTES.ask}/${encodeURIComponent(conversationId)}`;
}

export function conversationIdFromPath(pathname: string) {
  const prefix = `${ROUTES.ask}/`;
  if (!pathname.startsWith(prefix)) return null;
  const encodedId = pathname.slice(prefix.length);
  if (!encodedId || encodedId.includes("/")) return null;
  try {
    return decodeURIComponent(encodedId);
  } catch {
    return null;
  }
}

export type WorkspacePage = keyof typeof ROUTES;

export function pageFromPath(pathname: string): WorkspacePage | null {
  if (pathname === ROUTES.ask || conversationIdFromPath(pathname)) return "ask";
  const entry = Object.entries(ROUTES).find(([, path]) => path === pathname);
  return (entry?.[0] as WorkspacePage | undefined) ?? null;
}
