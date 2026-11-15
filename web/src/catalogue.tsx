import { usePreferences } from "./preferences";
import type { ItemSort } from "./preferences-store";
import { Currency } from "./currency";
import { variantLabel } from "./variant-label";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ColumnDef,
  PaginationState,
  SortingState,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { requestItemMetadata } from "./metadata-priority";
import { api, when } from "./api";
import { ItemIdentity, ItemInfo, ItemAttribution } from "./item-components";
import type { Item } from "./types";
interface Range {
  minimum: string | null;
  maximum: string | null;
}
interface Group extends ItemIdentity {
  variant_count: number;
  priced_variant_count: number;
  supply: number;
  listing_count: number;
  price_ranges: {
    recent_price: Range;
    market_value: Range;
    historical_value: Range;
  };
  synthetic: boolean;
}
interface Variant extends ItemIdentity {
  name_verified: boolean;
  variant_key: string;
  variant: unknown;
  recent_price: string | null;
  market_value: string | null;
  historical_value: string | null;
  supply: number;
  listing_count: number;
  coverage_days: number;
}
interface Page {
  items: Group[];
  total_items: number;
  page: number;
  page_size: number;
  snapshot_id: string | null;
  observed_at: string | null;
  synthetic: boolean;
}
interface VariantPage {
  variants: Variant[];
  total_variants: number;
  snapshot_id: string | null;
}
function range(value: Range) {
  return value.minimum === value.maximum ? (
    <Currency value={value.minimum} />
  ) : (
    <>
      <Currency value={value.minimum} /> – <Currency value={value.maximum} />
    </>
  );
}
export function ItemCatalogue({
  market,
  query,
  focus,
  onSelect,
  onSummary,
}: {
  market: number;
  query: string;
  focus?: { item_id: number; variant_key: string } | null;
  onSelect: (item: Item) => void;
  onSummary: (summary: { synthetic: boolean; empty: boolean }) => void;
}) {
  const preferences = usePreferences();
  const [pageIndex, setPageIndex] = useState(0);
  const pagination: PaginationState = {pageIndex, pageSize:preferences.values.item_page_size};
  const sorting: SortingState = [preferences.values.item_sort];
  function setPagination(updater: typeof pagination | ((previous:typeof pagination)=>typeof pagination)) {
    const next=typeof updater==='function'?updater(pagination):updater;
    setPageIndex(next.pageIndex);
    if(next.pageSize!==pagination.pageSize)preferences.update({item_page_size:next.pageSize as 25|50|100});
  }
  useEffect(()=>setPageIndex(0),[preferences.values.item_page_size,preferences.values.item_sort.id,preferences.values.item_sort.desc]);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const selectRef = useRef(onSelect),
    summaryRef = useRef(onSummary);
  selectRef.current = onSelect;
  summaryRef.current = onSummary;
  const [choice, setChoice] = useState<{
    query: string;
    item_id: number;
    variant_key?: string;
  } | null>(focus ? { query, ...focus } : null);
  useEffect(() => {
    setPagination((p) => ({ ...p, pageIndex: 0 }));
    setExpanded({});
  }, [market, query]);
  const sort = sorting[0] || { id: "item_id", desc: false };
  const response = useQuery({
    queryKey: [
      "private",
      "catalogue",
      market,
      query,
      sort.id,
      sort.desc,
      pagination,
    ],
    enabled: !!market,
    queryFn: ({ signal }) =>
      api<Page>(
        `/markets/${market}/catalogue?q=${encodeURIComponent(query)}&sort=${sort.id}&direction=${sort.desc ? "desc" : "asc"}&page=${pagination.pageIndex}&page_size=${pagination.pageSize}`,
        "GET",
        undefined,
        signal,
      ),
    refetchInterval: 60_000,
  });
  const first = response.data?.items[0];
  const target = choice?.query === query ? choice.item_id : first?.item_id;
  const firstVariants = useQuery({
    queryKey: [
      "private",
      "variants",
      market,
      target,
      0,
      response.data?.snapshot_id,
    ],
    enabled: !!market && !!target,
    queryFn: ({ signal }) =>
      api<VariantPage>(
        `/markets/${market}/catalogue/${target}/variants?page_size=50&expected_snapshot=${response.data?.snapshot_id || ""}`,
        "GET",
        undefined,
        signal,
      ),
  });
  useEffect(() => {
    if (!firstVariants.data || !target) return;
    const preferred =
      choice?.query === query ? choice.variant_key : focus?.variant_key;
    const row = preferred
      ? firstVariants.data.variants.find((r) => r.variant_key === preferred)
      : firstVariants.data.variants[0];
    if (row) {
      if (choice?.query !== query)
        setChoice({
          query,
          item_id: row.item_id,
          variant_key: row.variant_key,
        });
      const identity = response.data?.items.find(
        (r) => r.item_id === row.item_id,
      );
      selectRef.current({
        ...row,
        icon_url: identity?.icon_url,
        quality: identity?.quality,
        metadata_attribution: identity?.metadata_attribution,
      });
    }
  }, [firstVariants.data, target, query, choice?.variant_key]);
  function choose(item: Group) {
    setChoice({ query, item_id: item.item_id });
  }
  useEffect(() => {
    const data = response.data;
    if (!data) return;
    summaryRef.current({
      synthetic: data.synthetic,
      empty: data.items.length === 0,
    });
    if (data.items.length)
      requestItemMetadata(
        market,
        data.items.map((r) => r.item_id),
      ).catch(() => {});
  }, [response.data, market]);
  const columns = useMemo<ColumnDef<Group>[]>(
    () => [
      {
        id: "name",
        enableHiding: false,
        accessorKey: "name",
        header: "Item",
        cell: ({ row }) => (
          <div className="catalogue-identity">
            <div>
              <ItemInfo
                market={market}
                item={row.original}
                ranges={row.original.price_ranges}
              />
              <ItemAttribution item={row.original} />
              <button
                className={`select-item quality-text-${row.original.quality?.toLowerCase() || "unknown"}`}
                onClick={() => choose(row.original)}
                aria-label={`Select ${row.original.name}`}
                aria-pressed={target === row.original.item_id}
              >
                {row.original.name}
              </button>
              {row.original.variant_count > 1 && (
                <button
                  className="item-name-button"
                  onClick={() =>
                    setExpanded((p) =>
                      p[row.original.item_id]
                        ? {}
                        : { [row.original.item_id]: true },
                    )
                  }
                  aria-expanded={!!expanded[row.original.item_id]}
                >
                  <small>
                    #{row.original.item_id} · {row.original.variant_count}{" "}
                    {row.original.variant_count === 1 ? "variant" : "variants"}{" "}
                    {expanded[row.original.item_id] ? "▴" : "▾"}
                  </small>
                </button>
              )}
            </div>
          </div>
        ),
      },
      {
        id: "recent_price",
        accessorFn: (row) => row.price_ranges.recent_price.minimum,
        header: "Recent price / unit",
        cell: ({ row }) => (
          <span>
            {range(row.original.price_ranges.recent_price)}
            {row.original.variant_count > 1 && (
              <small className="muted">
                Variant range · {row.original.priced_variant_count} priced
              </small>
            )}
          </span>
        ),
      },
      {
        id: "market_value",
        accessorFn: (row) => row.price_ranges.market_value.minimum,
        header: "14-day reference",
        cell: ({ row }) => range(row.original.price_ranges.market_value),
      },
      {
        id: "supply",
        accessorKey: "supply",
        header: "Supply",
        cell: ({ getValue }) => Number(getValue()).toLocaleString(),
      },
      {
        id: "listing_count",
        accessorKey: "listing_count",
        header: "Listings",
        cell: ({ getValue }) => Number(getValue()).toLocaleString(),
      },
      { id: "item_id", accessorKey: "item_id", header: "ID" },
    ],
    [market, expanded, target, query],
  );
  const table = useReactTable({
    data: response.data?.items || [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    sortDescFirst: false,
    manualPagination: true,
    enableSortingRemoval: false,
    enableMultiSort: false,
    rowCount: response.data?.total_items || 0,
    state: { sorting, pagination, columnVisibility:preferences.values.item_columns },
    onColumnVisibilityChange:updater=>{
      const next=typeof updater==='function'?updater(preferences.values.item_columns):updater;
      preferences.update({item_columns:next});
    },
    onSortingChange: (updater) => {
      const next=typeof updater==='function'?updater(sorting):updater;
      preferences.update({item_sort:next[0] as ItemSort});
      setPagination((p) => ({ ...p, pageIndex: 0 }));
    },
    onPaginationChange: setPagination,
    getRowId: (row) => String(row.item_id),
  });
  return (
    <section
      className="catalogue-panel"
      aria-label="Item catalogue"
      aria-busy={response.isFetching}
    >
      <div className="catalogue-heading">
        <span>
          <strong>
            {(response.data?.total_items || 0).toLocaleString()} items
          </strong>
          <small>Exact prices stay with their variants</small>
        </span>
        <span className="small muted">
          {response.isFetching
            ? "Updating catalogue…"
            : `Snapshot ${response.data?.snapshot_id || "—"} · ${when(response.data?.observed_at)}`}
        </span>
      </div>
      <button className="text-button" onClick={() => response.refetch()}>
        Refresh catalogue
      </button>
      {firstVariants.error && <p role="alert">{firstVariants.error.message}</p>}
      {response.error && (
        <p role="alert" className="notice error">
          {response.error.message}
        </p>
      )}
      <details className="column-controls">
        <summary>Item columns</summary>
        <fieldset aria-label="Item table columns">
          {table.getAllLeafColumns().filter(column=>column.getCanHide()).map(column=><label key={column.id}>
            <input type="checkbox" checked={column.getIsVisible()} onChange={column.getToggleVisibilityHandler()} />
            {String(column.columnDef.header)}
          </label>)}
        </fieldset>
      </details>
      <div
        className="table-scroll"
        tabIndex={0}
        role="region"
        aria-label="Scrollable item catalogue"
      >
        <table className="catalogue-table">
          <caption className="sr-only">
            Select an item to inspect its details. Expand multiple variants
            separately for exact prices.
          </caption>
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => (
                  <th
                    key={header.id}
                    scope="col"
                    aria-sort={
                      header.column.getIsSorted() === "asc"
                        ? "ascending"
                        : header.column.getIsSorted() === "desc"
                          ? "descending"
                          : "none"
                    }
                  >
                    <button onClick={header.column.getToggleSortingHandler()}>
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                      <span aria-hidden="true">
                        {header.column.getIsSorted() === "asc"
                          ? " ↑"
                          : header.column.getIsSorted() === "desc"
                            ? " ↓"
                            : " ↕"}
                      </span>
                    </button>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <Fragment key={row.id}>
                <tr
                  className={
                    target === row.original.item_id
                      ? "item-selected"
                      : undefined
                  }
                  onClick={(event) => {
                    if (
                      !(event.target as HTMLElement).closest(
                        "button,a,input,select",
                      )
                    )
                      choose(row.original);
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </td>
                  ))}
                </tr>
                {expanded[row.original.item_id] && (
                  <tr className="variant-container">
                    <td colSpan={table.getVisibleLeafColumns().length}>
                      <Variants
                        market={market}
                        item={row.original}
                        snapshot={response.data?.snapshot_id}
                        onSelect={(item) => {
                          setChoice({
                            query,
                            item_id: item.item_id,
                            variant_key: item.variant_key,
                          });
                          selectRef.current(item);
                        }}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {response.data?.items.length === 0 && (
        <p className="empty">
          {query
            ? "No matching current items. Try an item ID or another search."
            : "No collected items are available yet."}
        </p>
      )}
      <div className="table-pagination">
        <label>
          Items per page
          <select
            value={pagination.pageSize}
            onChange={(e) => table.setPageSize(Number(e.target.value))}
          >
            {[25, 50, 100].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <span role="status">
          Page {pagination.pageIndex + 1} of {Math.max(1, table.getPageCount())}
        </span>
        <button
          onClick={() => table.previousPage()}
          disabled={!table.getCanPreviousPage()}
        >
          Previous items
        </button>
        <button
          onClick={() => table.nextPage()}
          disabled={!table.getCanNextPage()}
        >
          Next items
        </button>
      </div>
    </section>
  );
}
function Variants({
  market,
  item,
  snapshot,
  onSelect,
}: {
  market: number;
  item: Group;
  snapshot?: string | null;
  onSelect: (item: Item) => void;
}) {
  const [page, setPage] = useState(0);
  const result = useQuery({
    queryKey: ["private", "variants", market, item.item_id, page, snapshot],
    queryFn: ({ signal }) =>
      api<VariantPage>(
        `/markets/${market}/catalogue/${item.item_id}/variants?page=${page}&page_size=50&expected_snapshot=${snapshot || ""}`,
        "GET",
        undefined,
        signal,
      ),
  });
  return (
    <div className="variant-panel">
      <p className="small muted">
        Variants are priced separately. Base-item tooltips do not guess their
        extra bonuses.
      </p>
      {result.isPending && <p role="status">Loading exact variant prices…</p>}
      {result.error && <p role="alert">{result.error.message}</p>}
      <table aria-label={`Variants of ${item.name}`}>
        <thead>
          <tr>
            <th scope="col">Variant</th>
            <th scope="col">Recent / unit</th>
            <th scope="col">14-day reference</th>
            <th scope="col">Supply</th>
            <th scope="col">Listings</th>
            <th scope="col">Inspect</th>
          </tr>
        </thead>
        <tbody>
          {result.data?.variants.map((variant) => (
            <tr key={variant.variant_key}>
              <td>
                <ItemInfo
                  market={market}
                  item={{ ...variant, icon_url: item.icon_url }}
                  prices={variant}
                />
                <span> {variantLabel(variant.variant)}</span>
              </td>
              <td>
                <Currency value={variant.recent_price} />
              </td>
              <td>
                <Currency value={variant.market_value} />
                <small>{variant.coverage_days} observed days</small>
              </td>
              <td>{variant.supply.toLocaleString()}</td>
              <td>{variant.listing_count.toLocaleString()}</td>
              <td>
                <button
                  onClick={() =>
                    onSelect({
                      ...variant,
                      icon_url: item.icon_url,
                      quality: item.quality,
                    })
                  }
                  aria-label={`Inspect ${item.name}: ${variantLabel(variant.variant)}`}
                >
                  Inspect variant
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {(result.data?.total_variants || 0) > 50 && (
        <div className="table-pagination">
          <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            Previous variants
          </button>
          <span>Variant page {page + 1}</span>
          <button
            disabled={(page + 1) * 50 >= (result.data?.total_variants || 0)}
            onClick={() => setPage((p) => p + 1)}
          >
            Next variants
          </button>
        </div>
      )}
    </div>
  );
}
