import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { SortingState } from "@tanstack/react-table";
import { api } from "./api";
import { DataTable } from "./data-table";
import { Currency } from "./currency";
import {
  Auction,
  unitBuyout,
  stackBuyout,
  compareUnits,
  compareCopper,
  durationLabel,
} from "./listing-prices";
function UnitPrice({ row }: { row: Auction }) {
  const price = unitBuyout(row);
  if (!price) return <>Bid only</>;
  const [numerator, denominator] = price;
  const remainder = numerator % denominator;
  return (
    <>
      <Currency value={String(numerator / denominator)} />
      {remainder > 0n && (
        <span className="small">
          {" "}
          + {String(remainder)}/{String(denominator)} copper
        </span>
      )}
    </>
  );
}
export function CurrentListings({
  market,
  item,
  variant,
}: {
  market: number;
  item: number;
  variant: string;
}) {
  const [advanced, setAdvanced] = useState(false);
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 25 });
  const [sorting, setSorting] = useState<SortingState>([
    { id: "unit", desc: false },
  ]);
  const sort = sorting[0] || { id: "unit", desc: false };
  const response = useQuery({
    queryKey: [
      "private",
      "current-listings",
      market,
      item,
      variant,
      pagination,
      sort,
    ],
    refetchInterval: 60000,
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) =>
      api<{ listings: Auction[]; total: number; snapshot_id: string }>(
        `/markets/${market}/items/${item}/${variant}/listings?page=${pagination.pageIndex}&page_size=${pagination.pageSize}&sort=${sort.id}&direction=${sort.desc ? "desc" : "asc"}`,
        "GET",
        undefined,
        signal,
      ),
  });
  const listings = response.data?.listings || [];

  return (
    <section
      className="panel padded"
      aria-label="Current auctions"
      aria-busy={response.isFetching}
    >
      <div className="panel-heading">
        <h3>Current listings</h3>
        <span className="muted">
          All observed listings · {response.data?.total.toLocaleString() || 0}{" "}
          total
        </span>
      </div>
      <p className="small muted">
        Asking listings, not completed sales. Time remaining is an upstream
        duration category; exact expiry is unavailable.
      </p>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={advanced}
          onChange={(e) => setAdvanced(e.target.checked)}
        />
        Advanced auction diagnostics
      </label>
      {response.error && <p role="alert">{response.error.message}</p>}
      {response.isFetching && <p role="status">Loading current listings…</p>}
      <DataTable<Auction>
        label="current listings"
        data={listings}
        server={{
          rowCount: response.data?.total || 0,
          pagination,
          sorting,
          onPaginationChange: setPagination,
          onSortingChange: (updater) => {
            setSorting(updater);
            setPagination((p) => ({ ...p, pageIndex: 0 }));
          },
        }}
        getRowId={(row) => row.auction_id}
        columns={[
          {
            id: "unit",
            enableHiding: false,
            header: "Unit buyout",
            accessorFn: (row) => row.unit_price ?? row.buyout,
            sortingFn: (a, b) => compareUnits(a.original, b.original),
            meta: { numeric: true },
            cell: ({ row }) => <UnitPrice row={row.original} />,
          },
          {
            accessorKey: "quantity",
            header: "Quantity / stack",
            meta: { numeric: true },
          },
          {
            id: "total",
            header: "Total stack buyout",
            accessorFn: stackBuyout,
            meta: { numeric: true },
            sortingFn: (a, b) =>
              compareCopper(stackBuyout(a.original), stackBuyout(b.original)),
            cell: ({ row }) =>
              stackBuyout(row.original) === null ? (
                <>Bid only</>
              ) : (
                <Currency value={stackBuyout(row.original)} />
              ),
          },
          {
            accessorKey: "time_left",
            header: "Time remaining",
            sortingFn: (a, b) =>
              ["SHORT", "MEDIUM", "LONG", "VERY_LONG"].indexOf(
                a.original.time_left || "",
              ) -
              ["SHORT", "MEDIUM", "LONG", "VERY_LONG"].indexOf(
                b.original.time_left || "",
              ),
            cell: ({ row }) => durationLabel(row.original.time_left),
          },
          ...(advanced
            ? [
                {
                  accessorKey: "auction_id",
                  header: "Auction ID",
                  sortingFn: (
                    a: { original: Auction },
                    b: { original: Auction },
                  ) =>
                    compareCopper(a.original.auction_id, b.original.auction_id),
                },
                {
                  accessorKey: "bid",
                  header: "Bid / stack",
                  meta: { numeric: true },
                  cell: ({ row }: { row: { original: Auction } }) => (
                    <Currency value={row.original.bid} />
                  ),
                },
              ]
            : []),
        ]}
      />
    </section>
  );
}
