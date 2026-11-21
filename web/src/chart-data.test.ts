import { expect, it } from "vitest";
import { withMissingDays, exactPriceTooltip } from "./chart-data";
it("preserves explicit missing-day gaps instead of inventing prices or zero supply", () => {
  const rows = withMissingDays([
    { date: "2026-11-01", recent_price: "100", supply: 5 },
    { date: "2026-11-03", recent_price: "200", supply: 3 },
  ]);
  expect(rows).toHaveLength(3);
  expect(rows[1].recent_price).toBeNull();
  expect(rows[1].supply).toBeNull();
  expect(rows[2].recent_price).toBe("200");
});
it("shows exact copper beyond JavaScript integer precision in tooltips", () => {
  expect(
    exactPriceTooltip({
      date: "2026-11-14",
      recent_price: "9007199254740993",
      supply: 1,
    }),
  ).toContain("900,719,925,474g 09s 93c");
});
it("rejects invalid or unbounded date spans", () => {
  expect(
    withMissingDays([{ date: "invalid", recent_price: "1", supply: 1 }]),
  ).toEqual([]);
  expect(
    withMissingDays([
      { date: "2000-01-01", recent_price: "1", supply: 1 },
      { date: "2026-11-14", recent_price: "2", supply: 1 },
    ]),
  ).toEqual([]);
});
