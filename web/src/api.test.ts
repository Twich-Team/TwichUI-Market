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
  setCsrf("");
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
