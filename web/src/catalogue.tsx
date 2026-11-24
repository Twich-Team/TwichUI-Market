import { useCompactLayout } from "./responsive";
import { Loading } from "./loading";
import { ColumnMenu, DataTable, SortIndicator } from "./data-table";
import { ItemName } from "./item-name";
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
import { ApiError, api } from "./api";
import { ItemIdentity, ItemInfo, ItemAttribution } from "./item-components";
import type { Market } from "./types";
import "./player-ux.css";
import { type ExplorerState, itemUrl, followItem, navigate, restoration, saveRestoration, useRestoreView } from "./navigation";
export interface Range {
  minimum: string | null;
  maximum: string | null;
}
export interface Group extends ItemIdentity {
  variant_count: number;
  sole_variant_key?: string | null;
  priced_variant_count: number;
  supply: number;
  listing_count: number;
  price_ranges: {
    lowest_buyout?: Range;
    recent_price: Range;
    market_value: Range;
    historical_value: Range;
  };
  synthetic: boolean;
}
export interface Variant extends ItemIdentity {
  name_verified: boolean;
  variant_key: string;
  variant: unknown;
  lowest_buyout: string | null;
  recent_price: string | null;
  market_value: string | null;
  historical_value: string | null;
  supply: number;
  listing_count: number;
  coverage_days: number;
}
export interface CatalogueSummary {
  synthetic: boolean;
  refreshedAt?: number;
  market?: Market;
}

export interface Page {
  market?: Market;
  items: Group[];
  total_items: number;
  page: number;
  page_size: number;
  snapshot_id: string | null;
  observed_at: string | null;
  synthetic: boolean;
}
export interface VariantPage {
  variants: Variant[];
  total_variants: number;
  snapshot_id: string | null;
}
export function range(value: Range) {
  return value.minimum === value.maximum ? (
    <Currency value={value.minimum} />
  ) : (
    <>
      <Currency value={value.minimum} /> – <Currency value={value.maximum} />
    </>
  );
}
export function ItemCatalogue({market,query,state,onChange,onSummary}: {
  market:number; query:string; state:ExplorerState;
  onChange:(state:ExplorerState)=>void;
  onSummary:(summary:CatalogueSummary)=>void;
}) {
  const compact=useCompactLayout();
  const preferences=usePreferences();
  const pagination:PaginationState={pageIndex:state.pageIndex,pageSize:state.pageSize};
  const sorting:SortingState=[state.sort];
  function setPagination(updater:PaginationState|((previous:PaginationState)=>PaginationState)){
    const next=typeof updater==='function'?updater(pagination):updater;
    onChange({...state,pageIndex:next.pageSize===state.pageSize?next.pageIndex:0,pageSize:next.pageSize as ExplorerState['pageSize']});
    if(next.pageSize!==state.pageSize)preferences.update({item_page_size:next.pageSize as 25|50|100});
  }
  const [expanded,setExpanded]=useState<Record<number,boolean>>(()=>restoration()?.expanded??{});
  const [clamped,setClamped]=useState(false);
  const scrollRegion = useRef<HTMLDivElement>(null);
  const restoredScroll = useRef(false);
  const summaryRef=useRef(onSummary);summaryRef.current=onSummary;
  const expandedRef=useRef(expanded);expandedRef.current=expanded;
  const sort=state.sort;
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
        15_000,
      ),
    retry: false,
    placeholderData: (previous, previousQuery) => previousQuery?.queryKey[2] === market && previousQuery?.queryKey[3] === query ? previous : undefined,
    refetchInterval: 60_000,
  });
  const scope=`${market}:${query}`;
  const retained=useRef<{scope:string;data:Page}|undefined>(undefined);
  if(response.data&&!response.isPlaceholderData)retained.current={scope,data:response.data};
  const data=response.data ?? (retained.current?.scope===scope ? retained.current.data : undefined);
  useEffect(()=>{
    if(!response.data || response.isPlaceholderData || response.isError)return;
    const last=Math.max(0,Math.ceil(response.data.total_items/pagination.pageSize)-1);
    if(pagination.pageIndex>last){setClamped(true);onChange({...state,pageIndex:last});}
  },[response.data,pagination.pageIndex,pagination.pageSize]);
  useEffect(() => {
    const data = response.data;
    if (!data || response.isPlaceholderData) return;
    summaryRef.current({
      synthetic: data.synthetic,
      refreshedAt: response.dataUpdatedAt,
      market: data.market,
    });
  }, [response.data, response.dataUpdatedAt, response.isPlaceholderData]);
  useEffect(() => {
    const data = response.data;
    if (!data || response.isPlaceholderData || !data.items.length) return;
    requestItemMetadata(
        market,
        data.items.map((r) => r.item_id),
      ).catch(() => {});
  }, [response.data, response.isPlaceholderData, market]);
  useEffect(() => {
    if (compact || !data || restoredScroll.current || !scrollRegion.current) return;
    scrollRegion.current.scrollLeft = restoration()?.catalogueScrollLeft ?? 0;
    restoredScroll.current = true;
  }, [compact, data]);
  useRestoreView(!response.isPending&&!response.isFetching,`${market}:${query}:${state.pageIndex}`);
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
                ranges={row.original.variant_count>1 ? row.original.price_ranges : undefined}
                prices={row.original.variant_count===1 ? {recent_price:row.original.price_ranges.recent_price.minimum,market_value:row.original.price_ranges.market_value.minimum,supply:row.original.supply} : undefined}
              />
              <ItemAttribution item={row.original} />
              <a className="select-item" id={`catalogue-item-${row.original.item_id}`}
                href={itemUrl(market,row.original.item_id,row.original.variant_count===1 ? row.original.sole_variant_key ?? undefined : undefined)} onClick={followItem}
                aria-label={`Research ${row.original.name}`}>
                <ItemName name={row.original.name} quality={row.original.quality}/>
              </a>

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
              <small className="muted">Range · {row.original.priced_variant_count} priced variants</small>
            )}
          </span>
        ),
      },
      {
        id: "market_value",
        accessorFn: (row) => row.price_ranges.market_value.minimum,
        header: "14-day reference",
        cell: ({ row }) => <>{range(row.original.price_ranges.market_value)}{row.original.variant_count > 1 && <small>Variant range</small>}</>,
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
      { id: "expand", header: "Variants", enableSorting: false, enableHiding: false,
        cell: ({row}) => row.original.variant_count > 1 ? <button className="variant-chevron"
          aria-label={`${expandedRef.current[row.original.item_id] ? "Collapse" : "Expand"} ${row.original.variant_count} variants of ${row.original.name}`}
          aria-expanded={!!expandedRef.current[row.original.item_id]} aria-controls={`variants-${row.original.item_id}`}
          onClick={()=>{const next={...expandedRef.current,[row.original.item_id]:!expandedRef.current[row.original.item_id]};setExpanded(next);saveRestoration({expanded:next});}}>
          <span aria-hidden="true">{expandedRef.current[row.original.item_id] ? "−" : "+"}</span><span>{row.original.variant_count}</span></button> : null },
    ],
    [market],
  );
  const table = useReactTable({
    data: data?.items || [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    sortDescFirst: false,
    manualPagination: true,
    enableSortingRemoval: false,
    enableMultiSort: false,
    rowCount: data?.total_items || 0,
    state: { sorting, pagination, columnVisibility:preferences.values.item_columns },
    onColumnVisibilityChange:updater=>{
      const next=typeof updater==='function'?updater(preferences.values.item_columns):updater;
      preferences.update({item_columns:next});
    },
    onSortingChange: (updater) => {
      const next=typeof updater==='function'?updater(sorting):updater;
      preferences.update({item_sort:next[0] as ItemSort});
      onChange({...state,sort:next[0] as ItemSort,pageIndex:0});
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
      <div className="catalogue-heading catalogue-toolbar">
        <strong>{data ? `${data.total_items.toLocaleString()} ${data.total_items === 1 ? "item" : "items"}` : "Items"}</strong>
        {response.isFetching && data && <span className="small muted catalogue-updated">Refreshing…</span>}
        {!compact && <ColumnMenu table={table} closeAfterChange/>}
        <button className="icon-button" aria-label="Refresh catalogue" title="Refresh catalogue" disabled={response.isFetching} onClick={()=>response.refetch()}>{response.isFetching&&data?.items.length ? <Loading compact label="Refreshing item catalogue…"/> : <span aria-hidden="true">↻</span>}</button>
      </div>
      <p role="status" aria-live="polite" className="sr-only">{response.isFetching ? "Loading item catalogue…" : response.error ? "Catalogue update failed." : `Catalogue page ${data?.page != null ? data!.page+1 : 1} loaded.`}</p>
      {clamped && <p role="status" className="notice">The live results changed. Your saved page was moved to the last available page.</p>}
      {response.error && <p role="alert" className="notice error">Items could not be refreshed. {data ? "Showing the last loaded results." : response.error.message} <button onClick={()=>response.refetch()}>Retry catalogue</button></p>}
      {compact ? <>
        {data?.total_items !== 0 && <div className="mobile-sort">
          <label>Sort items<select value={sort.id} onChange={e=>table.setSorting([{id:e.target.value,desc:sort.desc}])}>
            {columns.filter(column=>column.id!=="expand").map(column=><option key={column.id} value={column.id}>{String(column.header)}</option>)}
          </select></label>
          <button className="secondary" aria-label={`Sort direction: ${sort.desc ? "descending" : "ascending"}`} onClick={()=>table.setSorting([{id:sort.id,desc:!sort.desc}])}>{sort.desc ? "Descending ↓" : "Ascending ↑"}</button>
        </div>}
        <div className={`mobile-catalogue ${response.isFetching ? "catalogue-loading" : ""}`}>
          {response.isFetching && !data?.items.length && <Loading label="Loading item catalogue…" skeleton/>}
          {table.getRowModel().rows.map(({original:item})=><article className="mobile-item" key={item.item_id}>
            <div className="mobile-item-heading">
              <ItemInfo market={market} item={item} ranges={item.variant_count>1 ? item.price_ranges : undefined}/>
              <div><a className="select-item" id={`catalogue-item-${item.item_id}`} href={itemUrl(market,item.item_id,item.variant_count===1 ? item.sole_variant_key ?? undefined : undefined)} onClick={followItem} aria-label={`Research ${item.name}`}><ItemName name={item.name} quality={item.quality}/></a><ItemAttribution item={item}/></div>
            </div>
            <dl className="mobile-item-prices">
              <div><dt>Recent / unit{item.variant_count>1 ? " · range" : ""}</dt><dd>{range(item.price_ranges.recent_price)}</dd></div>
              <div><dt>14-day reference{item.variant_count>1 ? " · range" : ""}</dt><dd>{range(item.price_ranges.market_value)}</dd></div>
              <div><dt>Supply</dt><dd>{item.supply.toLocaleString()} <span className="muted">· {item.listing_count.toLocaleString()} listings</span></dd></div>
            </dl>
            {item.variant_count>1 && <button className="secondary mobile-variants-toggle" aria-expanded={!!expanded[item.item_id]} aria-controls={`variants-${item.item_id}`} onClick={()=>{const next={...expanded,[item.item_id]:!expanded[item.item_id]};setExpanded(next);saveRestoration({expanded:next});}}>{expanded[item.item_id] ? "Hide" : "Show"} {item.variant_count} exact variants {expanded[item.item_id] ? "−" : "+"}</button>}
            {expanded[item.item_id] && <div id={`variants-${item.item_id}`}><Variants market={market} item={item} snapshot={data?.snapshot_id} onRefreshCatalogue={() => { void response.refetch(); }}/></div>}
          </article>)}
        </div>
      </> :       <div
        ref={scrollRegion}
        className={`table-scroll catalogue-scroll ${response.isFetching ? "catalogue-loading" : ""}`}
        onScroll={(event) => {
          const offset = event.currentTarget.scrollLeft;
          if (offset !== (restoration()?.catalogueScrollLeft ?? 0)) saveRestoration({ catalogueScrollLeft: offset });
        }}
        tabIndex={0}
        role="region"
        aria-label="Scrollable item catalogue"
      >
        {response.isFetching && !data?.items.length && <Loading label="Loading item catalogue…" skeleton/>}
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
                    {header.column.getCanSort() ? <button className="table-sort" onClick={header.column.getToggleSortingHandler()}>
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                      <SortIndicator direction={header.column.getIsSorted()} />
                    </button> : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <Fragment key={row.id}>
                <tr
                  onClick={(event) => {
                    const target = event.target as HTMLElement;
                    if (!event.currentTarget.contains(target) || target.closest("button,a,input,select,summary") || window.getSelection()?.type === "Range") return;
                    saveRestoration({focus:`catalogue-item-${row.original.item_id}`});
                    navigate(itemUrl(market,row.original.item_id,row.original.variant_count===1 ? row.original.sole_variant_key ?? undefined : undefined));
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
                  <tr className="variant-container" id={`variants-${row.original.item_id}`}>
                    <td colSpan={table.getVisibleLeafColumns().length}>
                      <Variants
                        market={market}
                        item={row.original}
                        snapshot={data?.snapshot_id}
                        onRefreshCatalogue={() => { void response.refetch(); }}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      }
      {data?.items.length === 0 && (
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
        <span role="status" aria-label="Catalogue page">
          Page {(data?.page ?? pagination.pageIndex) + 1} of {Math.max(1, table.getPageCount())}{response.isFetching ? " · Loading…" : ""}
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
export function Variants({
  market,
  item,
  snapshot,
  replaceSelection = false,
  selectedVariant,
  onRefreshCatalogue,
}: {
  market: number;
  item: Group;
  snapshot?: string | null;
  replaceSelection?: boolean;
  selectedVariant?: string;
  onRefreshCatalogue?: () => void;
}) {
  const [comparison, setComparison] = useState(() => restoration()?.variantComparison?.[item.item_id] ?? {
    pageIndex: 0, pageSize: 25, sorting: [{ id: "lowest_buyout", desc: false }], pricedOnly: false,
  });
  const { pageIndex, pageSize, sorting, pricedOnly } = comparison;
  const pagination = { pageIndex, pageSize };
  function changeComparison(changed: Partial<typeof comparison>) {
    const next = { ...comparison, ...changed };
    setComparison(next);
    saveRestoration({ variantComparison: { ...restoration()?.variantComparison, [item.item_id]: next } });
  }
  const sort = sorting[0] ?? { id: "lowest_buyout", desc: false };
  const linkedRange = new URLSearchParams(location.search);
  const linkedHours = Number(linkedRange.get("hours"));
  const linkedDays = Number(linkedRange.get("days"));
  const rangeSuffix = !replaceSelection ? "" : [24, 48].includes(linkedHours)
    ? `&hours=${linkedHours}`
    : [7, 14, 60, 365, 3650].includes(linkedDays) ? `&days=${linkedDays}` : "";
  const result = useQuery({
    queryKey: ["private", "variants", market, item.item_id, pagination, snapshot, sort, pricedOnly],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({
        page: String(pagination.pageIndex), page_size: String(pagination.pageSize),
        sort: sort.id, direction: sort.desc ? "desc" : "asc", priced_only: String(pricedOnly),
      });
      if (snapshot) params.set("expected_snapshot", snapshot);
      return api<VariantPage>(`/markets/${market}/catalogue/${item.item_id}/variants?${params}`, "GET", undefined, signal);
    },
    placeholderData: (previous, query) => query?.queryKey[2] === market && query.queryKey[3] === item.item_id
      && query.queryKey[5] === snapshot ? previous : undefined,
    retry: false,
  });
  const snapshotChanged = result.error instanceof ApiError && result.error.status === 409
    && result.error.message.startsWith("Market snapshot changed");
  const columns = useMemo<ColumnDef<Variant>[]>(() => {
    const destination = (key: string) => itemUrl(market, item.item_id, key) + rangeSuffix;
    return [
      {
        id: "variant",
        header: "Variant",
        enableHiding: false,
        enableSorting: false,
        cell: ({ row }) => <div className="variant-caption">
          <strong>{variantLabel(row.original.variant)}</strong>
          <details><summary>Variant identifier</summary><code className="variant-key">{row.original.variant_key}</code></details>
        </div>,
      },
      { accessorKey: "lowest_buyout", header: "Lowest / unit", meta: { numeric: true }, cell: ({ row }) => <Currency value={row.original.lowest_buyout}/> },
      { accessorKey: "recent_price", header: "Recent / unit", meta: { numeric: true }, cell: ({ row }) => <Currency value={row.original.recent_price}/> },
      { accessorKey: "market_value", header: "14-day reference", meta: { numeric: true }, cell: ({ row }) => <><Currency value={row.original.market_value}/><small>{row.original.coverage_days} observed days</small></> },
      { accessorKey: "supply", header: "Supply", meta: { numeric: true }, cell: ({ row }) => row.original.supply.toLocaleString() },
      { accessorKey: "listing_count", header: "Listings", meta: { numeric: true }, cell: ({ row }) => row.original.listing_count.toLocaleString() },
      {
        id: "inspect", header: "Research", enableSorting: false, enableHiding: false,
        cell: ({ row }) => <a className="secondary" id={`variant-${row.id}`} aria-current={selectedVariant === row.id ? "page" : undefined}
          href={destination(row.id)}
          onClick={(event) => {
            if (selectedVariant === row.id && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
              event.preventDefault();
            } else if (replaceSelection && event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
              event.preventDefault();
              navigate(destination(row.id), true);
              document.getElementById("research-title")?.focus();
            } else followItem(event);
          }}
          aria-label={`Inspect ${item.name}: ${variantLabel(row.original.variant)}`}>
          {selectedVariant === row.id ? "Selected" : "Inspect variant"}
        </a>,
      },
    ];
  }, [market, item.item_id, item.name, rangeSuffix, replaceSelection, selectedVariant]);
  return (
    <div className="variant-panel">
      <DataTable
        compact
        label={`Variants of ${item.name}`}
        data={result.data?.variants ?? []}
        columns={columns}
        getRowId={(row) => row.variant_key}
        loading={result.isFetching}
        error={result.error && <>
          Variants could not be loaded. {snapshotChanged ? "New market data is available." : result.error.message}{" "}
          <button onClick={() => snapshotChanged && onRefreshCatalogue ? onRefreshCatalogue() : result.refetch()}>
            {snapshotChanged && onRefreshCatalogue ? "Refresh market snapshot" : "Retry variants"}
          </button>
        </>}
        emptyMessage={pricedOnly ? "No variants with a buyout. Change the filter to see all variants." : "No variants are listed in this snapshot."}
        toolbar={<label className="variant-filter">Filter variants
          <select aria-label="Filter variants" value={pricedOnly ? "priced" : "all"} onChange={(event) => {
            changeComparison({ pricedOnly: event.target.value === "priced", pageIndex: 0 });
          }}>
            <option value="all">All variants</option><option value="priced">With a buyout</option>
          </select>
        </label>}
        server={{
          rowCount: result.data?.total_variants ?? 0,
          pagination,
          sorting,
          onPaginationChange: (updater) => changeComparison(typeof updater === "function" ? updater(pagination) : updater),
          onSortingChange: (updater) => changeComparison({
            sorting: typeof updater === "function" ? updater(sorting) : updater, pageIndex: 0,
          }),
        }}
      />
    </div>
  );
}
