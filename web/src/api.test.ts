import { describe, it, expect, vi, afterEach } from "vitest";
import { money, api, setCsrf } from "./api";
describe("copper formatting", () => {
  it("preserves values above JavaScript exact integer range", () => {
    expect(money("9007199254740993")).toBe("900,719,925,474g 09s 93c");
  });
  it("distinguishes unavailable values, zero and invalid data", () => {
    expect(money(null)).toBe("Unavailable");
    expect(money("0")).toBe("0g 00s 00c");
    expect(money("-1")).toBe("Invalid price");
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  setCsrf("");
});

it("bounds a stalled search and reports an actionable timeout", async () => {
  vi.useFakeTimers();
  const external = new AbortController();
  vi.stubGlobal("fetch", vi.fn((_url, options: RequestInit) => new Promise((_resolve, reject) => {
    options.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
  })));
  const pending = api("/markets/2/catalogue?q=linen", "GET", undefined, external.signal, 15_000);
  const rejected = expect(pending).rejects.toMatchObject({ status: 408, message: expect.stringContaining("Try an item ID or a narrower search") });
  await vi.advanceTimersByTimeAsync(15_000);
  await rejected;
  expect(external.signal.aborted).toBe(false);
  expect(vi.getTimerCount()).toBe(0);
});

it("preserves navigation cancellation instead of reporting it as a timeout", async () => {
  vi.useFakeTimers();
  const external = new AbortController();
  vi.stubGlobal("fetch", vi.fn((_url, options: RequestInit) => new Promise((_resolve, reject) => {
    options.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
  })));
  const pending = api("/markets/2/catalogue", "GET", undefined, external.signal, 15_000);
  const rejected = expect(pending).rejects.toMatchObject({ name: "AbortError" });
  external.abort();
  await rejected;
  expect(vi.getTimerCount()).toBe(0);
});
it("ignores an old account's delayed unauthorized response", async () => {
  const events = new EventTarget(),
    expired = vi.fn();
  events.addEventListener("market-auth-expired", expired);
  vi.stubGlobal("window", events);
  let respond!: (response: Response) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise((resolve) => {
          respond = resolve;
        }),
    ),
  );
  setCsrf("old-session");
  const pending = api("/markets");
  setCsrf("new-session");
  respond(new Response('{"detail":"Expired"}', { status: 401 }));
  await expect(pending).rejects.toThrow("Expired");
  expect(expired).not.toHaveBeenCalled();
});
it("expires the current account when its session is rejected", async () => {
  const events = new EventTarget(),
    expired = vi.fn();
  events.addEventListener("market-auth-expired", expired);
  vi.stubGlobal("window", events);
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("{}", { status: 401 })),
  );
  setCsrf("current-session");
  await expect(api("/markets")).rejects.toThrow();
  expect(expired).toHaveBeenCalledOnce();
});
