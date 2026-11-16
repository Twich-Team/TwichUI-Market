import { ColumnMenu } from "./data-table";
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
import { api, when } from "./api";
import { ItemIdentity, ItemInfo, ItemAttribution } from "./item-components";
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
  recent_price: string | null;
  market_value: string | null;
  historical_value: string | null;
  supply: number;
  listing_count: number;
  coverage_days: number;
}
export interface Page {
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
  onSummary:(summary:{synthetic:boolean;empty:boolean})=>void;
}) {
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
      empty: data.items.length === 0,
    });
    if (data.items.length)
      requestItemMetadata(
        market,
        data.items.map((r) => r.item_id),
      ).catch(() => {});
  }, [response.data, market]);
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
      { id: "expand", header: "Variants", enableSorting: false, enableHiding: false,
        cell: ({row}) => row.original.variant_count > 1 ? <button className="variant-chevron"
          aria-label={`${expandedRef.current[row.original.item_id] ? "Collapse" : "Expand"} ${row.original.variant_count} variants of ${row.original.name}`}
          aria-expanded={!!expandedRef.current[row.original.item_id]} aria-controls={`variants-${row.original.item_id}`}
          onClick={()=>{const next={...expandedRef.current,[row.original.item_id]:!expandedRef.current[row.original.item_id]};setExpanded(next);saveRestoration({expanded:next});}}>
          <span aria-hidden="true">{expandedRef.current[row.original.item_id] ? "⌄" : "›"}</span></button> : null },
    ],
    [market, query],
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
        <strong>{(data?.total_items || 0).toLocaleString()} items</strong>
        <span className="small muted catalogue-updated" title={when(data?.observed_at)}>{data?.observed_at ? `Updated ${new Date(data.observed_at!).toLocaleTimeString(undefined,{hour:"numeric",minute:"2-digit"})}` : ""}</span>
        <ColumnMenu table={table} closeAfterChange/>
        <button className="icon-button" aria-label="Refresh catalogue" title="Refresh catalogue" disabled={response.isFetching} onClick={()=>response.refetch()}><span aria-hidden="true">↻</span></button>
      </div>
      <p role="status" aria-live="polite" className="sr-only">{response.isFetching ? "Loading item catalogue…" : response.error ? "Catalogue update failed." : `Catalogue page ${data?.page != null ? data!.page+1 : 1} loaded.`}</p>
      {clamped && <p role="status" className="notice">The live results changed. Your saved page was moved to the last available page.</p>}
      {response.error && <p role="alert" className="notice error">{response.error.message} <button onClick={()=>response.refetch()}>Retry catalogue</button></p>}
      <div
        className={`table-scroll catalogue-scroll ${response.isFetching ? "catalogue-loading" : ""}`}
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
                    {header.column.getCanSort() ? <button onClick={header.column.getToggleSortingHandler()}>
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
                    </button> : <span className="sr-only">Variants</span>}
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
                    if (
                      !(event.target as HTMLElement).closest(
                        "button,a,input,select",
                      )
                    )
                      {saveRestoration({focus:`catalogue-item-${row.original.item_id}`});navigate(itemUrl(market,row.original.item_id,row.original.variant_count===1 ? row.original.sole_variant_key ?? undefined : undefined));}
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
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
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
  replaceSelection=false,
  selectedVariant,
}: {
  market: number;
  item: Group;
  snapshot?: string | null;
  replaceSelection?: boolean;
  selectedVariant?:string;
}) {
  const [page, setPage] = useState(0);
  const linkedDays=Number(new URLSearchParams(location.search).get('days'));
  const destination=(key:string)=>itemUrl(market,item.item_id,key)+(replaceSelection&&[7,14,60,365,3650].includes(linkedDays)?`&days=${linkedDays}`:'');
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
      {result.error && <p role="alert">{result.error.message} <button onClick={()=>result.refetch()}>Retry variants</button></p>}
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
            <tr key={variant.variant_key} className={selectedVariant===variant.variant_key?"item-selected":undefined}>
              <td>
                <ItemInfo
                  market={market}
                  item={{ ...variant, icon_url: item.icon_url }}
                  prices={variant}
                />
                <span> Variant {page * 50 + (result.data?.variants.indexOf(variant) ?? 0) + 1}</span><details className="small"><summary>Variant properties</summary>{variantLabel(variant.variant)}<code className="variant-key">{variant.variant_key}</code></details>
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
                <a className="secondary" id={`variant-${variant.variant_key}`} aria-current={selectedVariant===variant.variant_key?"page":undefined} href={destination(variant.variant_key)} onClick={event=>{
                    if(replaceSelection&&event.button===0&&!event.ctrlKey&&!event.metaKey&&!event.shiftKey&&!event.altKey){event.preventDefault();navigate(destination(variant.variant_key),true);}else followItem(event);
                  }}
                  aria-label={`Inspect ${item.name}: ${variantLabel(variant.variant)}`}>Inspect variant</a>
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
