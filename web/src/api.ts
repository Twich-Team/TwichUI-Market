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
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(method === "GET" ? {} : { "X-CSRF-Token": csrf }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const result = await response.json();
      if (typeof result.detail === "string") message = result.detail;
      else if (response.status === 422) message = "Check the entered values.";
    } catch {}
    throw new ApiError(response.status, message);
  }
  return response.status === 204 ? (undefined as T) : response.json();
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
