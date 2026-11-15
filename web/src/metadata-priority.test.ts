import { afterEach, expect, it, vi } from "vitest";
vi.mock("./api", () => ({
  api: vi.fn(),
  ApiError: class extends Error {
    status = 500;
  },
}));
import { api } from "./api";
import { queryClient, clearPrivateCache } from "./query";
import { requestItemMetadata } from "./metadata-priority";
afterEach(() => {
  clearPrivateCache();
  vi.clearAllMocks();
});
it("splits a 100-item page into bounded batches and deduplicates repeated views", async () => {
  await requestItemMetadata(
    1,
    Array.from({ length: 100 }, (_, i) => i + 1),
  );
  expect(api).toHaveBeenCalledTimes(2);
  expect(
    vi
      .mocked(api)
      .mock.calls.map(
        (call) => (call[2] as { item_ids: number[] }).item_ids.length,
      ),
  ).toEqual([50, 50]);
  await requestItemMetadata(1, [1, 1, 2]);
  expect(api).toHaveBeenCalledTimes(2);
});
it("clears priority state between accounts", async () => {
  await requestItemMetadata(1, [25]);
  clearPrivateCache();
  await requestItemMetadata(1, [25]);
  expect(api).toHaveBeenCalledTimes(2);
  expect(
    queryClient.getQueryData(["private", "metadata-priority", 2]),
  ).toBeUndefined();
});
it("allows failed priorities to be retried", async () => {
  vi.mocked(api).mockRejectedValueOnce(new Error("offline"));
  await expect(requestItemMetadata(1, [25])).rejects.toThrow("offline");
  await requestItemMetadata(1, [25]);
  expect(api).toHaveBeenCalledTimes(2);
});

it("retries unprocessed chunks after an early failure", async () => {
  vi.mocked(api).mockRejectedValueOnce(new Error("offline"));
  const ids = Array.from({ length: 100 }, (_, i) => i + 1);
  await expect(requestItemMetadata(1, ids)).rejects.toThrow();
  await requestItemMetadata(1, ids);
  expect(api).toHaveBeenCalledTimes(3);
});
it("does not restore old account state when an outstanding request fails", async () => {
  let reject!: (error: Error) => void;
  vi.mocked(api).mockImplementationOnce(
    () =>
      new Promise((_, fail) => {
        reject = fail;
      }),
  );
  const pending = requestItemMetadata(1, [25]);
  clearPrivateCache();
  reject(new Error("signed out"));
  await expect(pending).rejects.toThrow();
  expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
});

it("does not request metadata writes in a read-only preview",async()=>{queryClient.setQueryData(["private","environment"],{read_only:true});await requestItemMetadata(1,[25]);expect(api).not.toHaveBeenCalled()});
