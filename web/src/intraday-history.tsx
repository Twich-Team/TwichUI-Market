import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { Currency } from "./currency";
import { Loading } from "./loading";
import { DeferredChart } from "./deferred-chart";
import { DataTable } from "./data-table";
import { LocalTime } from "./admin-table";
import { compareCopper } from "./listing-prices";
import { currencyAxis, priceDetailWindow, chartTooltipText } from "./chart-data";
import { useMarketTouchLayout } from "./responsive";
import { withMissingHours, intradayLabel, intradayTooltip, type IntradayPoint, type IntradayResponse } from "./intraday-data";

export function IntradayHistory({ market, item, variant, hours }: { market: number; item: number; variant: string; hours: 24 | 48 }) {
  const compact = useMarketTouchLayout();
  const query = useQuery({
    queryKey: ["private", "intraday-history", market, item, variant, hours],
    queryFn: ({ signal }) => api<IntradayResponse>(`/markets/${market}/items/${item}/${variant}/intraday-history?hours=${hours}`, "GET", undefined, signal),
    refetchInterval: 60_000,
  });
  const rows = useMemo(() => query.data ? withMissingHours(query.data) : [], [query.data]);
  const [detailMode, setDetailMode] = useState(false);
  const priceWindow = useMemo(() => priceDetailWindow(rows.map((row) => row.recent_price)), [rows]);
  const detail = detailMode ? priceWindow.detail : null;
  const unit = currencyAxis(detail?.cap ?? priceWindow.maximum);
  const option = {
    animation: false,
    grid: { left: compact ? 48 : 64, right: 12, top: 29, bottom: 38 },
    textStyle: { color: "#cfbea0" },
    tooltip: {
      trigger: "axis", triggerOn: "mousemove|click", confine: true, renderMode: "html", className: "research-chart-tooltip",
      backgroundColor: "#211911", borderColor: "#8a7044", textStyle: { color: "#f1e2c7", fontSize: compact ? 11 : 13 },
      formatter: (params: unknown) => {
        const index = (params as { dataIndex: number }[])[0]?.dataIndex;
        return index === undefined || !rows[index] ? "" : chartTooltipText(intradayTooltip(rows[index]));
      },
    },
    xAxis: {
      type: "category", data: rows.map(intradayLabel),
      axisLabel: {
        hideOverlap: true, color: "#cfbea0",
        formatter: (_: string, index: number) => rows[index] ? new Date(rows[index].observed_at || rows[index].bucket_start)
          .toLocaleString(undefined, { hour: "numeric", ...(hours === 48 ? { day: "numeric" } : {}) }) : "",
      },
    },
    yAxis: {
      type: "value", name: unit.label, min: 0, max: detail?.cap, splitNumber: 4, nameTextStyle: { color: "#cfbea0" },
      axisLabel: { color: "#cfbea0", formatter: unit.format },
      splitLine: { lineStyle: { color: "#54422e", type: "dashed" } },
    },
    series: [{
      name: "Recent asking price", type: "line", connectNulls: false, showSymbol: true, symbolSize: 7,
      itemStyle: { color: "#dab567" }, areaStyle: { color: "#dab567", opacity: 0.075 },
      data: rows.map((row) => row.recent_price === null || (detail && Number(row.recent_price) > detail.cap) ? null : Number(row.recent_price)),
    }],
  };
  if (query.isPending) return <div className="chart-placeholder"><Loading label={`Loading ${hours}-hour observations…`} skeleton/></div>;
  if (query.error && !query.data) return <p className="notice error" role="alert">Hourly prices could not be loaded. <button onClick={() => query.refetch()}>Retry intraday history</button></p>;
  const actual = query.data?.points ?? [];
  const priced = actual.filter((row) => row.recent_price !== null).length;
  return <div className="research-chart-body intraday-history">
    {query.error && <p className="notice error" role="alert">Hourly prices could not refresh. Showing the last loaded observations. <button onClick={() => query.refetch()}>Retry intraday history</button></p>}
    <div className="chart-summary-line"><span><strong>{actual.length} observed hours</strong> · {priced} with prices</span>{query.data?.synthetic && <span className="research-fixture">Fixture data</span>}</div>
    {!actual.length && <p className="empty">No hourly observations in this period. Try a longer range.</p>}
    {!!actual.length && !priced && <p className="empty">These observations have no available asking prices for this variant.</p>}
    {!!priced && <>
      {priceWindow.detail && <div className="chart-scale-choice">
        <span>{detail ? `${detail.omitted} high ${detail.omitted === 1 ? "price is" : "prices are"} outside this view.` : "High prices widen the chart scale."}</span>
        <button className="secondary" onClick={() => setDetailMode(!detail)}>{detail ? "Show full scale" : "Zoom in on lower prices"}</button>
      </div>}
      <div className="research-chart-legend"><span><i aria-hidden="true"/>Recent asking price</span></div>
      <DeferredChart touchInspect option={option} label={`${hours}-hour observed asking-price history with genuine hourly gaps`}/>
    </>}
    <p className="chart-footnote">Local observation times · {rows.length - actual.length} unobserved hourly buckets.</p>
    <details className="chart-data-disclosure"><summary>Hourly observations &amp; provenance</summary>
      <p className="chart-footnote">Latest observation in each UTC hour. {query.data?.source_observation_count} checks were recorded. Edge hours can be partial.</p>
      <DataTable<IntradayPoint> compact label="intraday observations" data={rows} getRowId={(row) => row.bucket_start} columns={[
        { id: "time", header: "Observed locally", enableHiding: false, accessorFn: (row) => row.observed_at || row.bucket_start, cell: ({ row }) => row.original.observed_at ? <LocalTime value={row.original.observed_at}/> : <span>{intradayLabel(row.original)} · Unobserved</span> },
        { accessorKey: "recent_price", header: "Recent / unit", meta: { numeric: true }, sortingFn: (a, b) => compareCopper(a.original.recent_price, b.original.recent_price), cell: ({ row }) => <Currency value={row.original.recent_price}/> },
        { accessorKey: "lowest_buyout", header: "Lowest / unit", meta: { numeric: true }, sortingFn: (a, b) => compareCopper(a.original.lowest_buyout, b.original.lowest_buyout), cell: ({ row }) => <Currency value={row.original.lowest_buyout}/> },
        { accessorKey: "supply", header: "Listed units", meta: { numeric: true }, cell: ({ row }) => row.original.supply === null ? "Unknown" : row.original.supply.toLocaleString() },
        { accessorKey: "status", header: "Evidence", cell: ({ row }) => row.original.status.replaceAll("_", " ") },
      ]} renderDetails={(row) => <dl className="record-details">
        <dt>Observation / snapshot</dt><dd>{row.observation_id || "Unobserved"} / {row.snapshot_id || "Unknown"}</dd>
        <dt>Exact time</dt><dd>{row.observed_at || "Unobserved"}</dd>
        <dt>Namespace</dt><dd>{row.namespace || "Unknown"}</dd>
        <dt>Payload hash</dt><dd><code>{row.payload_hash || "Unknown"}</code></dd>
        <dt>Upstream source updated</dt><dd>{row.upstream_modified || "Unrecorded"}</dd>
      </dl>}/>
    </details>
  </div>;
}
