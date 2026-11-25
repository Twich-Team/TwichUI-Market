import { describe, expect, it } from "vitest";
import { parseRoute, safeBrowseUrl } from "./navigation";
import { compareCrates, crateUrl, crateView, parseFavor, type CrateRow, type ExactCopper } from "./waylaid-crates-data";

describe("Waylaid Crates filters and ordering", () => {
  it("round trips valid links and drops unsupported external parameters", () => {
    const raw = "?market=2&basis=14d&owned=true&q=Cloth&tier=apprentice&known=true&sort=total&direction=desc";
    const url = crateUrl(crateView(raw, 1));
    expect(crateView(url.split("?")[1], 1)).toEqual(crateView(raw, 1));
    expect(safeBrowseUrl(url + "&unrecognized=unsafe")).toBe(url);
    expect(parseRoute("/waylaid-crates").kind).toBe("waylaid-crates");
    expect(parseRoute("/admin/waylaid-crates").kind).toBe("admin");
    expect(crateView("?market=0&basis=__proto__&sort=__proto__&direction=invalid", 4))
      .toMatchObject({ market: 4, basis: "current", sort: "rate", direction: "asc" });
  });

  it("orders exact ratios above JavaScript's integer limit, with missing values last", () => {
    function row(id: number, rate: ExactCopper | null) {
      return { item: { item_id: id }, cost_per_favor: rate } as CrateRow;
    }
    const low = row(3, { numerator_copper: "90071992547409921", denominator: 10 });
    const high = row(2, { numerator_copper: "90071992547409922", denominator: 10 });
    const unknown = row(1, null);
    expect([unknown, high, low].sort((a, b) => compareCrates(a, b, "rate"))).toEqual([low, high, unknown]);
    expect([unknown, high, low].sort((a, b) => compareCrates(a, b, "rate", true))).toEqual([high, low, unknown]);
  });

  it("accepts blank or a bounded positive whole number for the reward form", () => {
    expect(parseFavor("")).toBeNull();
    expect(parseFavor(" 15 ")).toBe(15);
    expect(parseFavor("2147483647")).toBe(2147483647);
    for (const invalid of ["0", "-1", "2147483648", "1.5", "2e3"]) expect(parseFavor(invalid)).toBeUndefined();
  });
});
