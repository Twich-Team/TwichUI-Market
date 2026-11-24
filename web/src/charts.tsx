import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { api, money } from "./api";
import { HistoryPoint, withMissingDays, exactPriceTooltip, observationLabel, currencyAxis, priceDetailWindow, chartTooltipText } from "./chart-data";
import { DeferredChart } from "./deferred-chart";
import { Currency, StackUnitPrice } from "./currency";
import { compareCopper } from "./listing-prices";
import { DataTable } from "./data-table";
import { Loading } from "./loading";
import { useCompactLayout } from "./responsive";

const palette = {
  price: "#dab567",
  reference: "#98baae",
  historical: "#c2a3d1",
  supply: "#b29a73",
  text: "#cfbea0",
  grid: "#54422e",
};

const historySeries = [
  { name: "Recent asking price", key: "recent_price", color: palette.price },
  { name: "14-day reference", key: "market_value", color: palette.reference },
  { name: "60-day reference", key: "historical_value", color: palette.historical },
  { name: "Listed supply", key: "supply", color: palette.supply },
] as const;

export function PriceHistory({ market, item, variant, days }: { market: number; item: number; variant: string; days: number }) {
  const compact = useCompactLayout();
  const history = useQuery({
    queryKey: ["private", "chart-history", market, item, variant, days],
    refetchInterval: 60_000,
    queryFn: ({ signal }) => api<{ points: HistoryPoint[]; synthetic: boolean }>(
      `/markets/${market}/items/${item}/${variant}/history?days=${days}&view=chart`, "GET", undefined, signal,
    ),
  });
  const points = history.data?.points;
  const rows = useMemo(() => withMissingDays(points ?? []), [points]);
  const window = useMemo(() => priceDetailWindow(rows.map((row) => row.recent_price)), [rows]);
  const [overlays, setOverlays] = useState({ market_value: false, historical_value: false, supply: false });
  const [detailMode, setDetailMode] = useState(false);
  const [zoom, setZoom] = useState<[number, number]>([0, 100]);
  const detail = detailMode ? window.detail : null;
  const option = useMemo(() => {
    const series = historySeries.filter(({ key }) => key === "recent_price" || (!detail && overlays[key]));
    const ceiling = detail?.cap ?? Math.max(window.maximum, ...series
      .filter(({ key }) => key !== "supply")
      .flatMap(({ key }) => rows.map((row) => Number(row[key]))));
    const unit = currencyAxis(ceiling);
    const supply = !detail && overlays.supply;
    const navigator = !compact && rows.length > 14;
    return {
      animation: false,
      grid: { left: compact ? 48 : 64, right: supply ? 55 : 13, top: 29, bottom: navigator ? 69 : 37 },
      textStyle: { color: palette.text, fontFamily: "inherit" },
      tooltip: {
        trigger: "axis", triggerOn: "mousemove|click", confine: true, renderMode: "html", className: "research-chart-tooltip",
        backgroundColor: "#211911", borderColor: "#8a7044",
        textStyle: { color: "#f1e2c7", fontSize: compact ? 11 : 13 },
        formatter: (params: unknown) => {
          const records = params as { dataIndex: number }[];
          const row = rows[records[0]?.dataIndex];
          return row ? chartTooltipText(exactPriceTooltip(row)) : "";
        },
      },
      xAxis: {
        type: "category",
        data: rows.map(observationLabel),
        axisLabel: {
          color: palette.text, hideOverlap: true,
          formatter: (_: string, index: number) => {
            const row = rows[index];
            if (!row) return "";
            const local = row.observed_at ? new Date(row.observed_at) : new Date(`${row.date}T12:00:00Z`);
            return local.toLocaleDateString(undefined, { month: "short", day: "numeric", ...(row.observed_at ? {} : { timeZone: "UTC" }) });
          },
        },
        axisLine: { lineStyle: { color: palette.grid } },
      },
      yAxis: [{
        type: "value",
        name: unit.label,
        nameTextStyle: { color: palette.text },
        min: 0,
        max: detail?.cap,
        splitNumber: 4,
        axisLabel: { color: palette.text, formatter: unit.format },
        splitLine: { lineStyle: { color: palette.grid, type: "dashed" } },
      }, {
        type: "value",
        name: "Units",
        show: supply,
        splitLine: { show: false },
        axisLabel: { color: palette.text },
        nameTextStyle: { color: palette.text },
      }],
      dataZoom: [{
        type: "slider", show: navigator, filterMode: "none",
        start: zoom[0], end: zoom[1], bottom: 9, height: 28,
        borderColor: palette.grid, fillerColor: "#b0925133", textStyle: { color: palette.text },
      }],
      series: series.map(({ name, key, color }) => ({
        name,
        type: "line",
        yAxisIndex: key === "supply" ? 1 : 0,
        connectNulls: false,
        showSymbol: rows.length < 90 || rows.filter((row) => row.recent_price !== null).length < 50,
        symbolSize: compact ? 7 : 6,
        lineStyle: { width: key === "recent_price" ? 2.2 : 1.5, type: key === "market_value" ? "dashed" : "solid" },
        itemStyle: { color },
        areaStyle: key === "recent_price" ? { color, opacity: 0.075 } : undefined,
        data: rows.map((row) => {
          const value = row[key];
          if (value == null) return null;
          return detail && key === "recent_price" && Number(value) > detail.cap ? null : Number(value);
        }),
      })),
    };
  }, [compact, detail, overlays, rows, window.maximum, zoom]);

  if (history.isPending) return <div className="chart-placeholder"><Loading label="Loading observed history…" skeleton/></div>;
  if (history.error && !history.data) return <p role="alert" className="notice error">
    Price history could not be loaded. <button onClick={() => history.refetch()}>Retry price history</button>
  </p>;
  if (!points?.length) return <p className="empty">No observations in this period. Try a longer range.</p>;

  const priced = points.filter((row) => row.recent_price != null).length;
  return <div className="research-chart-body">
    {history.error && <p role="alert" className="notice error">History could not refresh. Showing the last loaded observations. <button onClick={() => history.refetch()}>Retry price history</button></p>}
    <div className="chart-summary-line">
      <span><strong>{points.length} observed {points.length === 1 ? "day" : "days"}</strong> · {priced} with prices</span>
      {history.data?.synthetic && <span className="research-fixture">Fixture data</span>}
      {history.isFetching && <span className="muted">Refreshing…</span>}
    </div>
    {window.detail && <div className="chart-scale-choice">
      <span>{detail ? `${detail.omitted} high ${detail.omitted === 1 ? "price is" : "prices are"} outside this view.` : "High prices widen the chart scale."}</span>
      <button className="secondary" onClick={() => setDetailMode(!detail)}>{detail ? "Show full scale" : "Zoom in on lower prices"}</button>
    </div>}
    {!!priced ? <>
      <div className="research-chart-legend" aria-label="Chart legend">
        {historySeries.filter(({ key }) => key === "recent_price" || (!detail && overlays[key])).map(({ key, name, color }) =>
          <span key={name}><i style={{ borderColor: color, borderTopStyle: key === "market_value" ? "dashed" : "solid" }} aria-hidden="true"/>{name}</span>)}
      </div>
      <DeferredChart touchInspect option={option} label="Observed asking-price history" onZoom={(start, end) => setZoom([start, end])}/>
    </> : <p className="empty">No asking prices were recorded for this variant in this period.</p>}
    <p className="chart-footnote">Local observation times · {Intl.DateTimeFormat().resolvedOptions().timeZone}. Missing days are gaps.</p>
    <details className="chart-data-disclosure">
      <summary>Read exact chart data</summary>
      <HistoryData rows={rows}/>
    </details>
    {!!priced && <details className="chart-data-disclosure">
      <summary>Chart options</summary>
      {!detail && <div className="chart-controls" aria-label="Chart overlays">
        {historySeries.slice(1).map(({ key, name }) => key !== "recent_price" && <label key={key}>
          <input type="checkbox" checked={overlays[key]} onChange={(event) => setOverlays((current) => ({ ...current, [key]: event.target.checked }))}/>{name}
        </label>)}
      </div>}
      {rows.length > 1 && <div className="chart-controls" aria-label="Date zoom">
        <label>Start <input type="range" min={0} max={Math.max(0, zoom[1] - 1)} value={zoom[0]}
          aria-valuetext={observationLabel(rows[Math.round(zoom[0] / 100 * (rows.length - 1))])}
          onChange={(event) => setZoom([Number(event.target.value), zoom[1]])}/></label>
        <label>End <input type="range" min={Math.min(100, zoom[0] + 1)} max={100} value={zoom[1]}
          aria-valuetext={observationLabel(rows[Math.round(zoom[1] / 100 * (rows.length - 1))])}
          onChange={(event) => setZoom([zoom[0], Number(event.target.value)])}/></label>
        <button className="secondary" onClick={() => setZoom([0, 100])}>Reset dates</button>
      </div>}
    </details>}
  </div>;
}

function HistoryData({ rows }: { rows: HistoryPoint[] }) {
  const columns: ColumnDef<HistoryPoint>[] = [
    { id: "date", accessorKey: "date", header: "Observation", cell: ({ row }) => <>{observationLabel(row.original)}<small>UTC bucket {row.original.date}</small></> },
    ...([["lowest_buyout", "Lowest / unit"], ["recent_price", "Recent / unit"], ["market_value", "14-day reference"], ["historical_value", "60-day reference"]] as const).map(([key, header]): ColumnDef<HistoryPoint> => {
      return {
        accessorKey: key, header,
        meta: { numeric: true },
        sortingFn: (a, b) => compareCopper(a.original[key] ?? null, b.original[key] ?? null),
        cell: ({ row }) => <Currency value={row.original[key]}/>,
      };
    }),
    { accessorKey: "supply", header: "Supply", meta: { numeric: true }, cell: ({ row }) => row.original.supply?.toLocaleString() ?? "Unobserved" },
  ];
  return <DataTable compact={rows.length <= 100} label="Exact historical observations" data={rows} columns={columns} getRowId={(row) => row.date}/>;
}

interface Band {
  bucket?: number;
  minimum: string;
  maximum: string;
  supply: number;
  listing_count: number;
}
interface Cheapest {
  numerator: string;
  denominator: number;
  supply: number;
  listing_count: number;
}
interface Distribution {
  bands: Band[];
  cheapest?: Cheapest | null;
  priced_supply: number;
  unpriced_supply: number;
  priced_listing_count: number;
  synthetic: boolean;
}

export function SupplyDistribution({ market, item, variant }: { market: number; item: number; variant: string }) {
  const result = useQuery({
    queryKey: ["private", "distribution", market, item, variant],
    refetchInterval: 60_000,
    queryFn: ({ signal }) => api<Distribution>(`/markets/${market}/distribution/${item}/${variant}`, "GET", undefined, signal),
  });
  const data = result.data;
  const option = useMemo(() => {
    const unit = currencyAxis(Math.max(0, ...(data?.bands.map((band) => Number(band.maximum)) ?? [])));
    return {
      animation: false,
      grid: { left: 48, right: 12, top: 25, bottom: 44 },
      textStyle: { color: palette.text },
      xAxis: {
        type: "category",
        data: data?.bands.map((band) => unit.format(Number(band.minimum))),
        axisLabel: { color: palette.text, hideOverlap: true },
        name: unit.label, nameLocation: "middle", nameGap: 27,
      },
      yAxis: {
        type: "value", name: "Units", nameTextStyle: { color: palette.text },
        splitNumber: 4, splitLine: { lineStyle: { color: palette.grid, type: "dashed" } },
        axisLabel: { color: palette.text },
      },
      tooltip: {
        trigger: "axis", triggerOn: "mousemove|click", confine: true, renderMode: "html", className: "research-chart-tooltip",
        backgroundColor: "#211911", borderColor: "#8a7044", textStyle: { color: "#f1e2c7", fontSize: 11 },
        formatter: (params: unknown) => {
          const band = data?.bands[(params as { dataIndex: number }[])[0]?.dataIndex];
          return band ? chartTooltipText(`${band.minimum === band.maximum ? money(band.minimum) : `${money(band.minimum)} – ${money(band.maximum)}`} / unit\n${band.supply.toLocaleString()} units · ${band.listing_count} listings`) : "";
        },
      },
      series: [{ type: "bar", data: data?.bands.map((band) => band.supply), itemStyle: { color: palette.supply }, barMaxWidth: 36 }],
    };
  }, [data]);

  if (result.isPending) return <Loading label="Loading supply by price…" skeleton/>;
  if (result.error && !data) return <p role="alert" className="notice error">Supply by price could not be loaded. <button onClick={() => result.refetch()}>Retry supply distribution</button></p>;
  if (!data?.bands.length) return <p className="empty">No current buyouts for this variant.</p>;

  const cheapest = data.cheapest;
  const onePrice = cheapest?.supply === data.priced_supply;
  const ratio = cheapest ? cheapest.supply / data.priced_supply : null;
  const concentration = ratio !== null && ratio < 1 && ratio >= 0.995 ? "Over 99%"
    : ratio !== null && ratio > 0 && ratio < 0.005 ? "Under 1%"
    : ratio === null ? null : ratio.toLocaleString(undefined, { style: "percent", maximumFractionDigits: 1 });
  return <div className="research-chart-body">
    {result.error && <p role="alert" className="notice error">Supply could not refresh. Showing the last loaded snapshot. <button onClick={() => result.refetch()}>Retry supply distribution</button></p>}
    {cheapest && (onePrice
      ? <p className="supply-fact"><strong>{data.priced_supply.toLocaleString()} units</strong> at <StackUnitPrice total={cheapest.numerator} quantity={cheapest.denominator}/> per unit.</p>
      : <p className="supply-fact"><strong>{concentration}</strong> of priced supply is at the cheapest price. <span>{cheapest.supply.toLocaleString()} units at <StackUnitPrice total={cheapest.numerator} quantity={cheapest.denominator}/> per unit.</span></p>)}
    {!onePrice && <DeferredChart touchInspect option={option} label="Current listed supply by price"/>}
    <p className="chart-footnote">{data.priced_listing_count.toLocaleString()} priced listings · {data.priced_supply.toLocaleString()} units{data.unpriced_supply > 0 ? ` · ${data.unpriced_supply.toLocaleString()} bid-only units excluded` : ""}.</p>
    <details className="chart-data-disclosure"><summary>Read distribution data</summary>
      <p className="chart-footnote">Band prices are rounded to copper. Current listings show exact fractional unit costs.</p>
      <DataTable<Band> compact label="Supply by price data" data={data.bands} getRowId={(row) => String(row.bucket ?? data.bands.indexOf(row))}
        columns={[
          { id: "range", header: "Asking price / unit", accessorKey: "minimum", sortingFn: (a, b) => compareCopper(a.original.minimum, b.original.minimum), cell: ({ row }) => row.original.minimum === row.original.maximum
            ? <Currency value={row.original.minimum}/> : <><Currency value={row.original.minimum}/> – <Currency value={row.original.maximum}/></> },
          { accessorKey: "supply", header: "Units", meta: { numeric: true }, cell: ({ row }) => row.original.supply.toLocaleString() },
          { accessorKey: "listing_count", header: "Listings", meta: { numeric: true }, cell: ({ row }) => row.original.listing_count.toLocaleString() },
        ]}/>
    </details>
  </div>;
}
