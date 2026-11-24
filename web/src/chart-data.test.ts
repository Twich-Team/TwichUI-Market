import { expect, it } from "vitest";
import { withMissingDays, exactPriceTooltip, currencyAxis, priceDetailWindow } from "./chart-data";
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


it("chooses familiar denominations without converting a copper-scale chart to gold", () => {
  expect(currencyAxis(50).format(50)).toBe("50c");
  expect(currencyAxis(132).format(50)).toBe("50c");
  expect(currencyAxis(480).format(125)).toBe("1.25s");
  expect(currencyAxis(20_000).format(12_000)).toBe("1.2g");
});

it("detects a lower-price detail window without losing the full domain", () => {
  const prices = ["1836361542", "775738042", "3", "8", "9", "13", null];
  expect(priceDetailWindow(prices)).toEqual({
    maximum: 1836361542,
    detail: { cap: 45, omitted: 2 },
  });
  expect(priceDetailWindow(["3", "1836361542"]).detail).toBeNull();
  expect(prices).toHaveLength(7);
});
