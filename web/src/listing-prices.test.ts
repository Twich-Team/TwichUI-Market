import { describe, expect, it } from "vitest";
import {
  compareUnits,
  stackBuyout,
  unitBuyout,
  compareCopper,
  durationLabel,
  Auction,
} from "./listing-prices";
const row = (values: Partial<Auction>): Auction => ({
  auction_id: "1",
  quantity: 3,
  buyout: null,
  unit_price: null,
  bid: null,
  time_left: null,
  ...values,
});
describe("exact listing prices", () => {
  it("keeps stack totals distinct and preserves fractional unit copper", () => {
    expect(unitBuyout(row({ buyout: "100" }))).toEqual([100n, 3n]);
    expect(stackBuyout(row({ buyout: "100" }))).toBe("100");
    expect(
      compareUnits(row({ buyout: "100" }), row({ unit_price: "34" })),
    ).toBe(-1);
  });
  it("multiplies commodities without number precision loss and separates bids", () => {
    expect(stackBuyout(row({ unit_price: "9007199254740993" }))).toBe(
      "27021597764222979",
    );
    expect(unitBuyout(row({ bid: "120" }))).toBeNull();
    expect(stackBuyout(row({ bid: "120" }))).toBeNull();
    expect(compareCopper("9007199254740993", "9007199254740992")).toBe(1);
  });
  it("does not invent an expiry from a duration category", () => {
    expect(durationLabel("LONG")).toBe("Long remaining");
    expect(durationLabel(null)).toBe("Duration unavailable");
    expect(durationLabel("UNKNOWN")).toBe("Duration unavailable");
  });
});
