/** 统一处理 JSON 请求、Cookie 和后端错误信息。 */
export async function request<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch("/api" + path, {
    credentials: "same-origin",
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : `请求失败 (${response.status})`);
  }
  return response.json();
}

export const post = <T = any>(path: string, data: unknown = {}) =>
  request<T>(path, { method: "POST", body: JSON.stringify(data) });

/** 流式问数和音频响应需要调用方直接读取 Response。 */
export async function rawRequest(path: string, options: RequestInit = {}) {
  return fetch("/api" + path, { credentials: "same-origin", ...options });
}
