import { useMemo, useState } from "react";
import { DataTable } from "./data-table";
import { DeferredChart } from "./deferred-chart";
import { Status } from "./admin-table";
import { Loading } from "./loading";

const outcomes = [
  { key: "collected", label: "Collected", color: "#a9bc82" },
  { key: "unchanged", label: "Unchanged", color: "#8599bc" },
  { key: "partial", label: "Partial", color: "#e0b66d" },
  { key: "failed", label: "Failed", color: "#df8c7a" },
  { key: "other", label: "Other", color: "#b2a1bb" },
] as const;

const snapshotColor = "#8fc8bc";

type Outcome = typeof outcomes[number]["key"];
export type CollectionDay = { date: string; checks: number; snapshots: number } & Record<Outcome, number>;
export interface ActivitySummary { days: CollectionDay[]; latest_snapshot_at: string | null }

const readableDate = new Intl.DateTimeFormat(undefined, { dateStyle: "full", timeZone: "UTC" });
const axisDate = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
const toUtcDate = (date: string) => new Date(`${date}T00:00:00Z`);
const periodChoices = [7, 14, 30, 90];

export function CollectionActivity({
  days, period, onPeriod, loading, failed, retry,
}: {
  days?: CollectionDay[];
  period: number;
  onPeriod: (period: number) => void;
  loading: boolean;
  failed: boolean;
  retry: () => void;
}) {
  const [selectedDate, setSelectedDate] = useState<string>();
  const checkDays = days?.filter(({ checks }) => checks > 0) ?? [];
  const snapshotDays = days?.filter(({ snapshots }) => snapshots > 0) ?? [];
  const hasEvidence = checkDays.length > 0 || snapshotDays.length > 0;
  const selected = days?.find(day => day.date === selectedDate)
    ?? days?.filter(day => day.checks > 0 || day.snapshots > 0).at(-1);
  const problems = checkDays.reduce((sum, day) => sum + day.partial + day.failed, 0);
  const option = useMemo(() => ({
    animation: false,
    grid: { left: 43, right: snapshotDays.length ? 45 : 15, top: 30, bottom: 33 },
    textStyle: { fontFamily: "system-ui", color: "#d2c1a6" },
    tooltip: {
      trigger: "axis", confine: true, renderMode: "richText",
      backgroundColor: "#211911", borderColor: "#8a7044", textStyle: { color: "#f1e2c7", fontSize: 12 },
      formatter: (params: unknown) => {
        const row = days?.[(params as {dataIndex: number}[])[0]?.dataIndex];
        if (!row) return "";
        const date = `${readableDate.format(toUtcDate(row.date))} UTC`;
        return [date, row.checks ? `${row.checks.toLocaleString()} recorded checks` : "No checks recorded",
          ...outcomes.filter(({key}) => row[key] > 0).map(({key,label}) => `${label}  ${row[key].toLocaleString()}`),
          `${row.snapshots.toLocaleString()} new snapshots`].join("\n");
      },
    },
    xAxis: {
      type: "category", data: days?.map(day => day.date),
      axisLabel: { hideOverlap: true, formatter: (value: string) => axisDate.format(toUtcDate(value)), color: "#d2c1a6" },
      axisLine: { lineStyle: { color: "#716049" } },
    },
    yAxis: [
      {
        type: "value", name: "Checks", show: checkDays.length > 0, minInterval: 1, splitNumber: 4,
        nameTextStyle: { color: "#d2c1a6" }, axisLabel: { color: "#d2c1a6" },
        splitLine: { lineStyle: { color: "#51412f", type: "dashed" } },
      },
      {
        type: "value", name: "Snapshots", show: snapshotDays.length > 0, minInterval: 1, splitNumber: 4,
        nameTextStyle: { color: snapshotColor }, axisLabel: { color: snapshotColor },
        splitLine: { show: !checkDays.length, lineStyle: { color: "#51412f", type: "dashed" } },
      },
    ],
    series: [
      ...outcomes.map(({key, label, color}) => ({
        name: label, type: "bar", stack: "checks", barMaxWidth: 44, itemStyle: { color },
        data: days?.map(day => day.checks ? day[key] : null),
      })),
      {
        name: "No checks recorded", type: "line", connectNulls: false, lineStyle: { opacity: 0 },
        symbol: "emptyCircle", symbolSize: 6, itemStyle: { color: "#bdad98" },
        data: days?.map(day => day.checks ? null : 0),
      },
      ...(snapshotDays.length ? [{
        name: "New snapshots", type: "line", yAxisIndex: 1,
        symbol: "diamond", symbolSize: 9, itemStyle: { color: snapshotColor },
        lineStyle: { color: snapshotColor, type: "dashed" },
        data: days?.map(day => day.snapshots),
      }] : []),
    ],
  }), [days, checkDays.length, snapshotDays.length]);
  return (
    <section className="panel collection-activity" aria-labelledby="collection-activity-heading">
      <div className="collection-section-header">
        <div>
          <h2 id="collection-activity-heading" tabIndex={-1}>Collection activity</h2>
          {days && <p>{checkDays.length} of {days.length} UTC days with checks{loading && " · Refreshing…"}</p>}
        </div>
        <label><span className="sr-only">History period</span><select value={period} onChange={event=>onPeriod(Number(event.target.value))}>
          {periodChoices.map(days => <option key={days} value={days}>Last {days} days</option>)}
        </select></label>
      </div>
      {loading && !days && <Loading label="Loading collection history…" skeleton/>}
      {failed && <p className="notice error" role="alert">
        {days ? "Collection history could not refresh. Showing the last loaded results." : "Collection history could not be loaded."} <button onClick={retry}>Retry history</button>
      </p>}
      {days && !hasEvidence && <p className="empty">No checks or new snapshots were retained in this window. Try a longer period or choose another market.</p>}
      {hasEvidence && selected && <>
        <p className="collection-problem-count">
          <Status tone={problems ? "warning" : "neutral"}>{checkDays.length ? `${problems.toLocaleString()} failed or partial checks` : "No checks recorded in this window"}</Status>
        </p>
        <ul className="collection-legend" aria-label="Collection outcome legend">
          {outcomes.filter(({key})=>checkDays.some(day=>day[key]>0)).map(({key,label,color}) =>
            <li key={key}><span style={{backgroundColor: color}} aria-hidden="true"/>{label}</li>)}
          {!!snapshotDays.length && <li><span className="collection-legend-snapshots" aria-hidden="true"/>New snapshots</li>}
          {checkDays.length < (days?.length ?? 0) && <li><span className="collection-legend-gap" aria-hidden="true"/>No checks recorded</li>}
        </ul>
        <DeferredChart
          option={option}
          label="Recorded collection checks and new snapshots by UTC day"
          touchInspect
          onSelect={index=>setSelectedDate(days?.[index]?.date)}
        />
        <div className="collection-day">
          <label>Inspect UTC date<select value={selected.date} onChange={event=>setSelectedDate(event.target.value)}>
            {days?.slice().reverse().map(day => <option key={day.date} value={day.date}>{readableDate.format(toUtcDate(day.date))}</option>)}
          </select></label>
          <div aria-live="polite">
            {selected.checks ? <>
              <strong>{selected.checks.toLocaleString()} {selected.checks === 1 ? "check" : "checks"}</strong>
              <ul aria-label="Selected day outcomes">{outcomes.filter(({key})=>selected[key]>0).map(({key,label}) =>
                <li key={key}>{selected[key].toLocaleString()} {label.toLowerCase()}</li>)}</ul>
            </> : <span>No checks recorded on this UTC date.</span>}
            <p className="collection-day-snapshots">{selected.snapshots.toLocaleString()} new {selected.snapshots===1?"snapshot":"snapshots"}</p>
          </div>
        </div>
        <details className="collection-exact-data">
          <summary>View daily counts</summary>
          <DataTable compact
            label="daily collection counts"
            data={days ?? []}
            getRowId={row=>row.date}
            columns={[
              { accessorKey:"date", header:"UTC date", cell:({row})=><time dateTime={row.original.date}>{axisDate.format(toUtcDate(row.original.date))}</time> },
              { accessorKey:"checks", header:"Checks", meta:{numeric:true}, cell:({row})=>row.original.checks || <Status>No checks recorded</Status> },
              ...outcomes.map(({key,label})=>({accessorKey:key,header:label,meta:{numeric:true}})),
              { accessorKey:"snapshots", header:"New snapshots", meta:{numeric:true} },
            ]}
          />
        </details>
      </>}
    </section>
  );
}
