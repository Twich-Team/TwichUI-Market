import { money } from "./api";
import {localTimestamp,localObservationDate} from "./local-time";
export function observationLabel(row:HistoryPoint):string {return row.observed_at ? localObservationDate(row.observed_at) : `${row.date} UTC day`;}
export interface HistoryPoint {
  date: string;
  observed_at?: string;
  recent_price: string | null;
  lowest_buyout?: string | null;
  market_value?: string | null;
  historical_value?: string | null;
  supply: number | null;
  listing_count?: number;
  synthetic?: boolean;
  reference_synthetic?: boolean;
}
export function withMissingDays(points: HistoryPoint[]): HistoryPoint[] {
  if (!points.length) return [];
  const byDay = new Map(points.map((row) => [row.date, row]));
  const start = Date.parse(points[0].date + "T00:00:00Z"),
    end = Date.parse(points.at(-1)!.date + "T00:00:00Z");
  if (
    !Number.isFinite(start) ||
    !Number.isFinite(end) ||
    end < start ||
    (end - start) / 86400000 > 3710
  )
    return [];
  const result: HistoryPoint[] = [];
  for (let stamp = start; stamp <= end; stamp += 86400000) {
    const date = new Date(stamp).toISOString().slice(0, 10);
    result.push(
      byDay.get(date) || {
        date,
        recent_price: null,
        market_value: null,
        historical_value: null,
        supply: null,
      },
    );
  }
  return result;
}
export function exactPriceTooltip(row: HistoryPoint): string {
  return `${row.observed_at ? localTimestamp(row.observed_at) : "Observation time unrecorded"}\nUTC-day bucket: ${row.date}\nRecent: ${money(row.recent_price)}\n14-day: ${money(row.market_value)}\n60-day: ${money(row.historical_value)}\nSupply: ${row.supply?.toLocaleString() ?? "Unobserved"}`;
}

const coinUnits = [
  { divisor: 10_000, suffix: "g" },
  { divisor: 100, suffix: "s" },
  { divisor: 1, suffix: "c" },
] as const;

export function currencyAxis(ceiling: number) {
  const unit = ceiling < 200 ? coinUnits[2] : ceiling < 10_000 ? coinUnits[1] : coinUnits[0];
  const formatter = new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 2,
    ...(ceiling / unit.divisor >= 10_000 ? { notation: "compact" as const } : {}),
  });
  return {
    label: `Price / unit (${unit.suffix})`,
    format: (value: number) => `${formatter.format(value / unit.divisor)}${unit.suffix}`,
  };
}

export function priceDetailWindow(values: readonly unknown[]) {
  const prices = values.flatMap((value) => {
    if (typeof value !== "string" && typeof value !== "number") return [];
    const price = Number(value);
    return Number.isFinite(price) && price >= 0 ? [price] : [];
  }).sort((a, b) => a - b);
  const maximum = prices.at(-1) ?? 0;
  const usual = prices[Math.floor((prices.length - 1) / 2)] ?? 0;
  const cap = usual > 0 ? Math.ceil(usual * 5) : 0;
  const omitted = prices.filter((price) => price > cap).length;
  return {
    maximum,
    detail: prices.length >= 3 && usual > 0 && maximum >= usual * 100 && omitted < prices.length / 2
      ? { cap, omitted } : null,
  };
}


export function chartTooltipText(text: string): string {
  return text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}
