import { api } from "./api";
import { queryClient } from "./query";
// Memory only, cleared with the account cache. Priorities never bypass worker backoff.
export async function requestItemMetadata(market: number, ids: number[]) {
  if(queryClient.getQueryData<{read_only:boolean}>(["private","environment"])?.read_only)return;
  const key = ["private", "metadata-priority", market];
  const previous = queryClient.getQueryData<Record<number, number>>(key) || {};
  const stamp = Date.now();
  const wanted = [...new Set(ids)].filter(
    (id) => stamp - (previous[id] || 0) >= 15 * 60_000,
  );
  if (!wanted.length) return;
  queryClient.setQueryData(key, {
    ...previous,
    ...Object.fromEntries(wanted.map((id) => [id, stamp])),
  });
  const pendingQuery = queryClient
    .getQueryCache()
    .find({ queryKey: key, exact: true });
  for (let offset = 0; offset < wanted.length; offset += 50) {
    const chunk = wanted.slice(offset, offset + 50);
    try {
      await api(`/markets/${market}/item-metadata-requests`, "POST", {
        item_ids: chunk,
      });
    } catch (error) {
      if (
        queryClient.getQueryCache().find({ queryKey: key, exact: true }) ===
        pendingQuery
      )
        queryClient.setQueryData<Record<number, number>>(key, (current) => {
          const next = { ...current };
          for (const id of wanted.slice(offset))
            if (next[id] === stamp) delete next[id];
          return next;
        });
      throw error;
    }
  }
}
