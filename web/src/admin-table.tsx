import { ReactNode, useState } from "react";
import { PaginationState, SortingState } from "@tanstack/react-table";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "./api";

export function LocalTime({ value }: { value?: string | null }) {
  if (!value) return <span className="muted">Not recorded</span>;
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return <span className="muted">Not recorded</span>;
  return <time dateTime={value} title={`${date.toLocaleString(undefined, { timeZoneName: "long" })} · ${date.toISOString()}`}>{date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</time>;
}
export function Status({ tone = "neutral", children }: { tone?: "success" | "warning" | "error" | "neutral"; children: ReactNode }) {
  return <span className={`record-status ${tone}`}><span aria-hidden="true">{({ success: "✓", warning: "◐", error: "✕", neutral: "−" })[tone]}</span> {children}</span>;
}
export const providerNames: Record<string, string> = { blizzard: "Blizzard", everloot: "Everloot", foreverdb: "ForeverDB", thewowdb: "TheWoWDB" };
export function ProviderEmblem({ provider }: { provider: string }) {
  const name = providerNames[provider] || "Unknown source";
  return <span className="provider-emblem" title={`${name} metadata source`}><span className={`source-symbol source-${provider}`} aria-hidden="true">{({blizzard:"❄",everloot:"◆",foreverdb:"∞",thewowdb:"▤"} as Record<string,string>)[provider] || "?"}</span><span>{name}</span></span>;
}
export function useRecordPage<T>(path: string, filters: Record<string, string>, initialSort: string, desc = true) {
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: 25 });
  const [sorting, setSorting] = useState<SortingState>([{ id: initialSort, desc }]);
  const params = new URLSearchParams(filters);
  params.set("offset", String(pagination.pageIndex * pagination.pageSize));
  params.set("limit", String(pagination.pageSize));
  params.set("sort", sorting[0]?.id || initialSort);
  params.set("desc", String(sorting[0]?.desc ?? desc));
  const query = useQuery({ queryKey: ["private", "admin-records", path, params.toString()], placeholderData:keepPreviousData, queryFn: ({ signal }) => api<{ rows: T[]; total: number; summary?: Record<string, number> }>(`/admin/records/${path}?${params}`, "GET", undefined, signal), refetchInterval: 5000 });
  return { query, pagination, reset: () => setPagination(value => ({ ...value, pageIndex: 0 })), server: { rowCount: query.data?.total || 0, pagination, sorting, onPaginationChange: setPagination, onSortingChange: setSorting } };
}
