import { afterEach, expect, it } from "vitest";
import { queryClient, setQueryIdentity, clearPrivateCache } from "./query";
afterEach(clearPrivateCache);
it("retains same-account requests but removes private data on identity or role changes", () => {
  setQueryIdentity("1:member");
  queryClient.setQueryData(["private", "catalogue", 1], {
    price: "9007199254740993",
  });
  setQueryIdentity("1:member");
  expect(queryClient.getQueryCache().getAll()).toHaveLength(1);
  setQueryIdentity("2:member");
  expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
  queryClient.setQueryData(["private", "administration"], { users: ["owner"] });
  setQueryIdentity("2:admin");
  expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
});
it("clears all private server state at sign-out", () => {
  setQueryIdentity("1:admin");
  queryClient.setQueryData(["private", "item-profile", 25], {
    name: "Private",
  });
  clearPrivateCache();
  expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
});
