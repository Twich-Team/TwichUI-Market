import { describe, expect, it } from "vitest";
import { administrationSection, administrationUrl } from "./admin-navigation";
import { parseRoute, safeBrowseUrl } from "./navigation";
import { compareWrits, writRequest, writUrl, writView, type WritRow } from "./crafting-writs-data";

describe("Crafting Writ scenarios", () => {
  it("round-trips pricing and filters through the URL and sends only pricing inputs", () => {
    const search = "?market=8&basis=14d&owned=true&method=craft&profession=blacksmithing&max_skill=285&recipes=6,8,6&q=hammer&sort=total&direction=desc";
    const view = writView(search, 2);
    expect(view).toEqual({
      market: 8, basis: "14d", owned: true, method: "craft", profession: "blacksmithing", maxSkill: 285,
      confirmedRecipes: [6, 8], query: "hammer", sort: "total", direction: "desc",
    });
    expect(writView(writUrl(view).split("?")[1], 2)).toEqual(view);
    expect(writRequest(view)).toBe("/crafting-writs?market_id=8&basis=14d&owned=true&method=craft&profession=blacksmithing&max_skill=285&confirmed_recipes=6&confirmed_recipes=8");
  });

  it("uses exact rationals above JS integer precision and keeps unavailable rankings last", () => {
    function row(id: number, numerator: string, denominator: number, eligible = true) {
      return { item: { item_id: id }, eligible, cost_per_reputation: { numerator_copper: numerator, denominator } } as WritRow;
    }
    const rows = [
      row(40, "18014398509481985", 2),
      row(30, "9007199254740992", 1),
      row(10, "1", 100, false),
      row(20, "3", 7),
    ];
    expect([...rows].sort((a, b) => compareWrits(a, b, "rate")).map(value => value.item.item_id)).toEqual([20, 30, 40, 10]);
    expect([...rows].sort((a, b) => compareWrits(a, b, "rate", true)).map(value => value.item.item_id)).toEqual([40, 30, 20, 10]);
  });

  it("rejects malformed scenario inputs and keeps bounded item return state", () => {
    const safe = safeBrowseUrl("/crafting-writs?market=8&method=craft&max_skill=375&recipes=123%2C456&token=private");
    expect(safe).toBe("/crafting-writs?market=8&method=craft&max_skill=375&recipes=123%2C456");
    expect(writView("?market=0&basis=unknown&method=anything&profession=bad_slug&max_skill=1001&recipes=0,-1,2147483648&sort=wrong", 2))
      .toMatchObject({ market: 2, method: "cheapest", basis: "current", profession: null, maxSkill: null, confirmedRecipes: [], sort: "rate" });
    expect(parseRoute("/crafting-writs").kind).toBe("crafting-writs");
    expect(parseRoute("/admin/crafting-writs").kind).toBe("admin");
    expect(administrationSection(administrationUrl("crafting-writs"))).toBe("crafting-writs");
  });
});
