export interface User {
  id: number;
  username: string;
  role: "member" | "admin";
  active: boolean;
}
export interface BrowserSession {
  user: User;
  csrf_token: string;
}
let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
  timeoutMs?: number,
): Promise<T> {
  const requestCsrf = csrf;
  const controller = timeoutMs === undefined ? undefined : new AbortController();
  let timedOut = false;
  const cancel = () => controller?.abort();
  if (signal?.aborted) cancel();
  else if (controller) signal?.addEventListener("abort", cancel, { once: true });
  const timer = controller && setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  try {
    const response = await fetch(`/api/v1${path}`, {
      method,
      signal: controller?.signal ?? signal,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(method === "GET" ? {} : { "X-CSRF-Token": csrf }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      if (
        response.status === 401 &&
        requestCsrf === csrf &&
        path !== "/auth/login" &&
        typeof window !== "undefined"
      )
        window.dispatchEvent(new Event("market-auth-expired"));
      let message = `Request failed (${response.status})`;
      try {
        const result = await response.json();
        if (typeof result.detail === "string") message = result.detail;
        else if (response.status === 422) message = "Check the entered values.";
      } catch {}
      throw new ApiError(response.status, message);
    }
    return response.status === 204 ? (undefined as T) : await response.json();
  } catch (error) {
    if (timedOut) throw new ApiError(408, "Search took too long. Try an item ID or a narrower search, then retry.");
    throw error;
  } finally {
    if (timer !== undefined) clearTimeout(timer);
    signal?.removeEventListener("abort", cancel);
  }
}
export function money(value: string | null | undefined): string {
  if (value == null) return "Unavailable";
  if (!/^(0|[1-9]\d*)$/.test(value)) return "Invalid price";
  const copper = BigInt(value),
    gold = copper / 10000n,
    silver = (copper % 10000n) / 100n,
    remainder = copper % 100n;
  return `${gold.toLocaleString()}g ${silver.toString().padStart(2, "0")}s ${remainder.toString().padStart(2, "0")}c`;
}
export function when(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "Never";
}
