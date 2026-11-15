import { Currency } from "./currency";
import {
  lazy,
  Suspense,
  useMemo,
  useRef,
  useState,
  useEffect,
  ComponentProps,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { api, money } from "./api";
import { HistoryPoint, withMissingDays, exactPriceTooltip } from "./chart-data";
const ChartEngine = lazy(() => import("./chart-engine"));
function DeferredChart(props: ComponentProps<typeof ChartEngine>) {
  const container = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (visible || !container.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "150px" },
    );
    observer.observe(container.current);
    return () => observer.disconnect();
  }, [visible]);
  return (
    <div ref={container} className="chart-viewport">
      {visible ? (
        <Suspense fallback={<p role="status">Opening interactive chart…</p>}>
          <ChartEngine {...props} />
        </Suspense>
      ) : (
        <button className="secondary" onClick={() => setVisible(true)}>
          Load {props.label.toLowerCase()}
        </button>
      )}
    </div>
  );
}
const palette = {
  price: "#d9b365",
  reference: "#83aca1",
  historical: "#b694c3",
  supply: "#9a8565",
  text: "#c1b296",
  grid: "#4a3926",
};
export function PriceHistory({
  market,
  item,
  variant,
  days,
}: {
  market: number;
  item: number;
  variant: string;
  days: number;
}) {
  const history = useQuery({
    queryKey: ["private", "chart-history", market, item, variant, days],
    refetchInterval: 60_000,
    queryFn: ({ signal }) =>
      api<{ points: HistoryPoint[]; synthetic: boolean }>(
        `/markets/${market}/items/${item}/${variant}/history?days=${days}&view=chart`,
        "GET",
        undefined,
        signal,
      ),
  });
  const rows = useMemo(
    () => withMissingDays(history.data?.points || []),
    [history.data],
  );
  const [overlays, setOverlays] = useState({
    market: true,
    historical: false,
    supply: false,
  });
  const [zoom, setZoom] = useState<[number, number]>([0, 100]);
  const option = useMemo(() => {
    const series = [
      {
        name: "Recent asking price",
        key: "recent_price",
        color: palette.price,
        enabled: true,
      },
      {
        name: "14-day reference",
        key: "market_value",
        color: palette.reference,
        enabled: overlays.market,
      },
      {
        name: "60-day reference",
        key: "historical_value",
        color: palette.historical,
        enabled: overlays.historical,
      },
      {
        name: "Listed supply",
        key: "supply",
        color: palette.supply,
        enabled: overlays.supply,
      },
    ].filter((row) => row.enabled);
    return {
      animation: false,
      aria: {
        enabled: true,
        description:
          "Observed asking prices and listed supply. Missing days are gaps; exact copper values are available in the data table.",
      },
      legend: { top: 0, textStyle: { color: palette.text, fontSize: 13 } },
      grid: { left: 75, right: overlays.supply ? 60 : 20, top: 55, bottom: 80 },
      textStyle: { color: palette.text, fontFamily: "inherit" },
      tooltip: {
        trigger: "axis",
        renderMode: "richText",
        backgroundColor: "#17130f",
        borderColor: "#8a7044",
        textStyle: { color: "#eee0c5" },
        formatter: (params: unknown) => {
          const records = params as { dataIndex: number }[];
          const row = rows[records[0]?.dataIndex];
          return row ? exactPriceTooltip(row) : "";
        },
      },
      xAxis: {
        type: "category",
        data: rows.map((r) => r.date),
        axisLabel: { color: palette.text, hideOverlap: true },
        axisLine: { lineStyle: { color: palette.grid } },
      },
      yAxis: [
        {
          type: "value",
          name: "Gold / unit",
          splitLine: { lineStyle: { color: palette.grid, type: "dashed" } },
          axisLabel: {
            color: palette.text,
            formatter: (value: number) =>
              (value / 10000).toLocaleString(undefined, {
                maximumFractionDigits: 4,
              }),
          },
          nameTextStyle: { color: palette.text },
        },
        {
          type: "value",
          name: "Units",
          show: overlays.supply,
          splitLine: { show: false },
          axisLabel: { color: palette.text },
          nameTextStyle: { color: palette.text },
        },
      ],
      dataZoom: [
        { type: "inside", start: zoom[0], end: zoom[1], filterMode: "none" },
        {
          type: "slider",
          start: zoom[0],
          end: zoom[1],
          bottom: 10,
          height: 22,
          borderColor: palette.grid,
          fillerColor: "#b0925133",
          textStyle: { color: palette.text },
        },
      ],
      series: series.map((series) => ({
        name: series.name,
        type: "line",
        yAxisIndex: series.key === "supply" ? 1 : 0,
        connectNulls: false,
        showSymbol: rows.filter((row) => row.recent_price != null).length < 90,
        symbolSize: 6,
        lineStyle: {
          width: series.key === "recent_price" ? 2 : 1.4,
          type: series.key === "market_value" ? "dashed" : "solid",
        },
        itemStyle: { color: series.color },
        areaStyle: series.key === "supply" ? { opacity: 0.06 } : undefined,
        data: rows.map((row) => {
          const value = row[series.key as keyof HistoryPoint];
          return value === null || value === undefined ? null : Number(value);
        }),
      })),
    };
  }, [rows, overlays, zoom]);
  if (history.isPending) return <p role="status">Loading observed history…</p>;
  if (history.error)
    return (
      <p role="alert" className="notice error">
        {history.error.message}
      </p>
    );
  if (!rows.length)
    return (
      <p className="empty">
        No observations were collected for this range. Try a longer range or
        allow collection to build history.
      </p>
    );
  return (
    <>
      <p className="small muted">
        Recent price is quantity-weighted asking price. The dashed 14-day
        reference averages observed daily prices; the 60-day reference uses the
        longer observed window.
      </p>
      {(history.data?.points.length || 0) < 3 && (
        <p className="notice">
          Only {history.data?.points.length} observed day(s). Points are actual
          observations; a trend needs more history.
        </p>
      )}
      <details>
        <summary>Advanced chart controls</summary>
        <div className="chart-controls" aria-label="Chart overlays">
          {(
            [
              ["market", "14-day reference"],
              ["historical", "60-day reference"],
              ["supply", "Listed supply"],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              <input
                type="checkbox"
                checked={overlays[key]}
                onChange={(event) =>
                  setOverlays((p) => ({ ...p, [key]: event.target.checked }))
                }
              />
              {label}
            </label>
          ))}
          <button onClick={() => setZoom([0, 100])}>Reset zoom</button>
        </div>
        <div className="chart-controls" aria-label="Keyboard chart zoom">
          <label>
            Zoom start (%)
            <input
              type="range"
              min={0}
              max={Math.max(0, zoom[1] - 1)}
              value={zoom[0]}
              onChange={(e) => setZoom([Number(e.target.value), zoom[1]])}
            />
          </label>
          <label>
            Zoom end (%)
            <input
              type="range"
              min={Math.min(100, zoom[0] + 1)}
              max={100}
              value={zoom[1]}
              onChange={(e) => setZoom([zoom[0], Number(e.target.value)])}
            />
          </label>
        </div>
      </details>
      {history.data?.synthetic && (
        <p className="notice warning">
          This chart includes synthetic fixture observations or references.
        </p>
      )}
      <DeferredChart
        option={option}
        label="Observed asking-price history"
        onZoom={(a, b) => setZoom([a, b])}
      />
      <p className="small muted">
        {history.data?.points.length} observed UTC days · gaps remain
        unobserved. Chart scales are approximate; tooltips and data retain exact
        copper values.
      </p>
      <details>
        <summary>Read exact chart data</summary>
        <HistoryData rows={rows} />
      </details>
    </>
  );
}
function HistoryData({ rows }: { rows: HistoryPoint[] }) {
  const [page, setPage] = useState(0),
    [virtual, setVirtual] = useState(false);
  return (
    <div>
      <div className="table-pagination">
        <span>{rows.length.toLocaleString()} calendar days</span>
        {rows.length > 200 && (
          <label>
            <input
              type="checkbox"
              checked={virtual}
              onChange={(e) => setVirtual(e.target.checked)}
            />
            Virtual scrolling (paginated alternative below)
          </label>
        )}
      </div>
      {virtual ? (
        <VirtualHistory rows={rows} />
      ) : (
        <>
          <HistoryTable rows={rows.slice(page * 50, (page + 1) * 50)} />
          <div className="table-pagination">
            <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              Previous history rows
            </button>
            <span>
              Data page {page + 1} of {Math.max(1, Math.ceil(rows.length / 50))}
            </span>
            <button
              disabled={(page + 1) * 50 >= rows.length}
              onClick={() => setPage((p) => p + 1)}
            >
              Next history rows
            </button>
          </div>
        </>
      )}
    </div>
  );
}
function HistoryTable({ rows }: { rows: HistoryPoint[] }) {
  return (
    <div
      className="table-scroll"
      tabIndex={0}
      role="region"
      aria-label="Scrollable exact historical observations"
    >
      <table aria-label="Exact historical observations">
        <thead>
          <tr>
            <th scope="col">UTC day</th>
            <th scope="col">Recent price</th>
            <th scope="col">14-day</th>
            <th scope="col">60-day</th>
            <th scope="col">Supply</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <HistoryRow key={row.date} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
function HistoryRow({ row, index }: { row: HistoryPoint; index?: number }) {
  return (
    <tr aria-rowindex={index === undefined ? undefined : index + 2}>
      <th scope="row">{row.date}</th>
      <td>
        <Currency value={row.recent_price} />
      </td>
      <td>
        <Currency value={row.market_value} />
      </td>
      <td>
        <Currency value={row.historical_value} />
      </td>
      <td>{row.supply?.toLocaleString() ?? "Unobserved"}</td>
    </tr>
  );
}
function VirtualHistory({ rows }: { rows: HistoryPoint[] }) {
  const scroll = useRef<HTMLDivElement>(null);
  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroll.current,
    estimateSize: () => 43,
    overscan: 6,
  });
  const items = virtual.getVirtualItems();
  return (
    <div
      ref={scroll}
      className="history-virtual"
      role="region"
      aria-label="Virtual historical data; use arrow keys to scroll or switch to paginated data"
      tabIndex={0}
    >
      <table
        aria-label="Virtual historical observations"
        aria-rowcount={rows.length + 1}
      >
        <thead>
          <tr>
            <th scope="col">UTC day</th>
            <th scope="col">Recent price</th>
            <th scope="col">14-day</th>
            <th scope="col">60-day</th>
            <th scope="col">Supply</th>
          </tr>
        </thead>
        <tbody>
          {items.length > 0 && (
            <tr aria-hidden="true">
              <td colSpan={5} style={{ height: items[0].start, padding: 0 }} />
            </tr>
          )}
          {items.map((item) => (
            <HistoryRow
              key={rows[item.index].date}
              row={rows[item.index]}
              index={item.index}
            />
          ))}
          {items.length > 0 && (
            <tr aria-hidden="true">
              <td
                colSpan={5}
                style={{
                  height: virtual.getTotalSize() - items.at(-1)!.end,
                  padding: 0,
                }}
              />
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
export function SupplyDistribution({
  market,
  item,
  variant,
}: {
  market: number;
  item: number;
  variant: string;
}) {
  const result = useQuery({
    queryKey: ["private", "distribution", market, item, variant],
    refetchInterval: 60_000,
    queryFn: ({ signal }) =>
      api<{
        bands: {
          minimum: string;
          maximum: string;
          supply: number;
          listing_count: number;
        }[];
        priced_supply: number;
        unpriced_supply: number;
        priced_listing_count: number;
        synthetic: boolean;
      }>(
        `/markets/${market}/distribution/${item}/${variant}`,
        "GET",
        undefined,
        signal,
      ),
  });
  const option = useMemo(
    () => ({
      animation: false,
      aria: { enabled: true },
      grid: { left: 60, right: 15, top: 20, bottom: 70 },
      textStyle: { color: palette.text },
      xAxis: {
        type: "category",
        data: result.data?.bands.map((b) => money(b.minimum)),
        axisLabel: { color: palette.text, rotate: 25, fontSize: 13 },
      },
      yAxis: {
        type: "value",
        name: "Units",
        splitLine: { lineStyle: { color: palette.grid } },
        axisLabel: { color: palette.text },
        nameTextStyle: { color: palette.text },
      },
      tooltip: {
        trigger: "axis",
        renderMode: "richText",
        formatter: (params: unknown) => {
          const record = (params as { dataIndex: number }[])[0];
          const band = result.data?.bands[record?.dataIndex];
          return band
            ? `$<Currency value={band.minimum} /> – $<Currency value={band.maximum} />\n${band.supply.toLocaleString()} units · ${band.listing_count} priced listings`
            : "";
        },
      },
      series: [
        {
          type: "bar",
          data: result.data?.bands.map((b) => b.supply),
          itemStyle: { color: palette.supply },
        },
      ],
    }),
    [result.data],
  );
  if (result.isPending)
    return <p role="status">Loading complete distribution…</p>;
  if (result.error) return <p role="alert">{result.error.message}</p>;
  if (!result.data?.bands.length)
    return (
      <p className="empty">
        No buyout prices are observed. Bid-only listings cannot establish a
        buyout distribution.
      </p>
    );
  return (
    <>
      <DeferredChart option={option} label="Current listed supply by price" />
      <p className="small muted">
        All {result.data.priced_listing_count.toLocaleString()} priced listings
        · {result.data.priced_supply.toLocaleString()} units.{" "}
        {result.data.unpriced_supply.toLocaleString()} bid-only units excluded.
      </p>
      <details>
        <summary>Read distribution data</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">Asking price range</th>
              <th scope="col">Supply</th>
            </tr>
          </thead>
          <tbody>
            {result.data.bands.map((b, i) => (
              <tr key={i}>
                <td>
                  <Currency value={b.minimum} /> –{" "}
                  <Currency value={b.maximum} />
                </td>
                <td>{b.supply.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}
