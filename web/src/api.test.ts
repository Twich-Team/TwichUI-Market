import { describe, it, expect } from "vitest";
import { money } from "./api";
describe("copper formatting", () => {
  it("preserves values above JavaScript exact integer range", () => {
    expect(money("9007199254740993")).toBe("900,719,925,474g 09s 93c");
  });
  it("distinguishes unavailable values, zero and invalid data", () => {
    expect(money(null)).toBe("Unavailable");
    expect(money("0")).toBe("0g 00s 00c");
    expect(money("-1")).toBe("Invalid price");
  });
});
