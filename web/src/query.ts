import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./api";
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 15 * 60_000,
      refetchOnWindowFocus: false,
      retry: (failures, error) =>
        !(
          error instanceof ApiError &&
          [401, 403, 404, 409, 422].includes(error.status)
        ) && failures < 1,
    },
  },
});
let account: string | null = null;
const clearListeners = new Set<() => void>();
export function onPrivateCacheClear(listener: () => void) {
  clearListeners.add(listener);
  return () => { clearListeners.delete(listener); };
}
export function setQueryIdentity(identity: string | null) {
  if (account !== identity) {
    clearListeners.forEach((listener) => listener());
    queryClient.clear();
    account = identity;
  }
}
export function clearPrivateCache() {
  clearListeners.forEach((listener) => listener());
  queryClient.clear();
  account = null;
}
