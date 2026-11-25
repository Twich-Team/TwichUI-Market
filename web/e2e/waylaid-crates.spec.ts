import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { defaultPreferences } from "../src/preferences-store";
import type { CrateItem, CrateQuote, CrateResults, CrateRow } from "../src/waylaid-crates-data";

const at = "2026-11-25T18:45:00Z";
const source = "https://foreverdb.net";
const catalogue = { source_url: source, build: "fixture-build", refreshed_at: at, stale: false, crate_count: 3, supported_count: 3 };
const item = (item_id: number, name: string, quality = "COMMON"): CrateItem => ({ item_id, name, quality, icon_url: null });
const linen = item(601, "Fixture Linen");
const leather = item(602, "Fixture Leather");
const copper = item(603, "Fixture Copper");
const mithril = item(604, "Fixture Mithril Bar");
const exact = (copper: number) => ({ numerator_copper: String(copper), denominator: 1 });
function quote(item: CrateItem, quantity: number, unit: number): CrateQuote {
  return {
    item_id: item.item_id, item, quantity, unit_price_copper: String(unit), subtotal_copper: String(quantity * unit),
    unit_price_exact: exact(unit), subtotal_exact: exact(quantity * unit),
    minimum_unit_copper: String(unit), minimum_purchase_copper: String(quantity * unit),
    stock_status: "sufficient_at_minimum", quote_status: "available", quality_reason: null,
    current_priced_quantity: 120, available_at_minimum: 30, coverage_days: null, source_kind: "commodities",
  };
}

function crate(item: CrateItem, fill: number, favor: number | null, owned: boolean): CrateRow {
  const purchase = owned ? 0 : 200;
  const total = fill + purchase;
  return {
    item, tier: favor === 10 ? "journeyman" : "apprentice", favor, required_level: 10, sealed_item_id: null,
    unavailable_reason: null, reward_unavailable_reason: favor === null ? "unverified_reward_quality" : null,
    eligible: favor !== null, reasons: favor === null ? ["unknown_favor"] : [],
    bundles: [
      { bundle_id: 1, materials: [quote(favor === 10 ? mithril : linen, 5, fill / 5)], fill_cost_copper: String(fill), fill_cost_exact: exact(fill), eligible: true },
      { bundle_id: 2, materials: [quote(leather, 10, 100), quote(copper, 1, 50)], fill_cost_copper: "1050", fill_cost_exact: exact(1050), eligible: true },
    ],
    selected_bundle_id: 1, purchase_quote: quote(item, 1, 200),
    fill_cost_copper: String(fill), purchase_cost_copper: String(purchase), total_cost_copper: String(total),
    fill_cost_exact: exact(fill), purchase_cost_exact: exact(purchase), total_cost_exact: exact(total),
    cost_per_favor: favor === null ? null : { numerator_copper: String(total), denominator: favor },
  };
}

async function setup(page: Page, role: "member" | "admin", readOnly = false) {
  const user = { id: 1, role, active: true, username: "fixture-user" };
  const prefs = { schema_version: 1, user_id: 1, revision: 0, values: { ...defaultPreferences(), market_id: 8 } };
  const requests: { path: string; method: string; body?: unknown }[] = [];
  const options = { failure: false, empty: false, stale: false, conflict: false };
  let reward = { tier: "apprentice", favor: 5 as number | null, revision: 1, updated_at: at, updated_by: "fixture-user" };
  let refresh: { state: string; error: null; next_attempt_at: string | null } = { state: "idle", error: null, next_attempt_at: null };
  await page.route("**/api/v1/**", route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    const method = route.request().method();
    const body = route.request().postData() ? route.request().postDataJSON() : undefined;
    requests.push({ path, method, body });
    if (path === "/auth/session") return route.fulfill({ json: { user, csrf_token: "isolated-fixture" } });
    if (path === "/environment") return route.fulfill({ json: { read_only: readOnly, review_fixtures: true } });
    if (path === "/me/preferences") return route.fulfill({ json: prefs });
    if (path === "/markets") return route.fulfill({
      json: { markets: [8, 9].map(id => ({ id, label: `Fixture market ${id}`, region: "us", house_id: 114, enabled: true, verified: true, freshness: "current", last_success: at })) },
    });
    if (path === "/waylaid-crates") {
      if (options.failure) return route.fulfill({ status: 503, json: { detail: "Isolated fixture unavailable" } });
      const owned = url.searchParams.get("owned") === "true";
      const regional = url.searchParams.get("basis") === "regional";
      const result: CrateResults = {
        catalogue: { ...catalogue, stale: options.stale },
        pricing: { snapshot_id: "1", observed_at: at, freshness: options.stale ? "stale" : "current", synthetic: true },
        rows: options.empty ? [] : [
          crate(item(101, "Waylaid Crate: Fixture Small"), 500, 5, owned),
          crate(item(102, "Waylaid Crate: Fixture Large"), 600, 10, owned),
          {
            ...crate(item(103, "Waylaid Crate: Fixture Uncommon", "UNCOMMON"), 100, null, owned),
            fill_cost_copper: "0", fill_cost_exact: { numerator_copper: "1", denominator: "10" },
          },
        ],
      };
      if (regional) result.rows = result.rows.map(row => ({ ...row, purchase_cost_copper: owned ? "0" : null,
        total_cost_copper: null, fill_cost_copper: null, total_cost_exact: null, fill_cost_exact: null,
        purchase_cost_exact: owned ? exact(0) : null, cost_per_favor: null, eligible: false, reasons: ["regional_unavailable"] }));
      return route.fulfill({ json: result });
    }
    if (path === "/admin/waylaid-crates") return route.fulfill({ json: { catalogue, rewards: [reward], refresh } });
    if (path === "/admin/waylaid-crates/refresh" && method === "POST") {
      refresh = { state: "queued", error: null, next_attempt_at: at };
      return route.fulfill({ status: 202, json: refresh });
    }
    if (path === "/admin/waylaid-crates/rewards/apprentice" && method === "PUT") {
      if (options.conflict) {
        reward = { ...reward, favor: 12, revision: reward.revision + 1 };
        return route.fulfill({ status: 409, json: { detail: "Concurrent fixture update" } });
      }
      reward = { ...reward, favor: body.favor, revision: reward.revision + 1 };
      return route.fulfill({ json: reward });
    }
    if (/^\/markets\/\d+\/catalogue$/.test(path)) return route.fulfill({ json: { items: [], total_items: 0 } });
    return route.fulfill({ status: 404, json: { detail: "Unavailable in this isolated fixture" } });
  });
  return { requests, options };
}

test.describe("Waylaid Crates desktop workflows", () => {
  test.use({ viewport: { width: 1440, height: 950 }, hasTouch: false, isMobile: false });

  test("members compare exact numeric estimates, inspect bundles and return from market item links", async ({ page }) => {
    const { requests } = await setup(page, "member");
    await page.goto("/waylaid-crates?market=9");
    const table = page.getByRole("table", { name: "Waylaid Crates estimates" });
    await expect(table.getByRole("rowheader").first()).toContainText("Fixture Large");
    const selected = table.getByRole("cell").filter({ hasText: "Fixture Mithril Bar" });
    await expect(selected).toContainText("5 ×");
    await expect(selected.getByRole("link", { name: "Fixture Mithril Bar" })).toHaveAttribute("href", "/markets/9/items/604");
    await expect(table.getByRole("columnheader", { name: "Cost / Favor" })).toHaveAttribute("aria-sort", "ascending");
    await expect(page.getByRole("button", { name: "Waylaid Crates", exact: true })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("link", { name: "ForeverDB" })).toHaveAttribute("href", source);
    const uncommon = table.getByRole("row").filter({ hasText: "Fixture Uncommon" });
    await expect(uncommon).toContainText("Unavailable");
    await expect(uncommon.getByRole("img", { name: "Less than 1 copper" })).toBeVisible();
    await table.getByRole("button", { name: "Fill cost" }).click();
    await expect(table.getByRole("rowheader").first()).toContainText("Fixture Uncommon");
    await expect(page).toHaveURL(/sort=fill&direction=asc/);

    const details = page.getByRole("button", { name: "Show materials for Waylaid Crate: Fixture Large" });
    await details.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "Choose one" })).toBeVisible();
    await expect(page.getByText("Used in estimate")).toBeVisible();
    const material = page.getByRole("link", { name: "Fixture Copper" });
    await expect(material).toHaveAttribute("href", "/markets/9/items/603");
    await material.click();
    await expect(page).toHaveURL(/markets\/9\/items\/603$/);
    await page.getByRole("link", { name: /Back to Waylaid Crates/ }).click();
    await expect(material).toBeFocused();
    await expect(page).toHaveURL(/market=9/);

    await page.getByRole("checkbox", { name: "I already own the crate" }).check();
    await expect(page).toHaveURL(/owned=true/);
    await expect(table.getByRole("row").filter({ hasText: "Fixture Small" }).getByRole("img", { name: "0 gold, 0 silver, 0 copper" })).toBeVisible();
    await page.getByLabel("Price basis").selectOption("regional");
    await expect(page).toHaveURL(/basis=regional/);
    await expect(page.getByText("This market has no regional reference.", { exact: false })).toBeVisible();
    await page.getByLabel("Price basis").selectOption("14d");
    await expect(page).toHaveURL(/basis=14d/);

    const search = page.getByLabel("Search crates");
    await search.fill("Fixture Large");
    await search.press("Enter");
    await expect(table.getByRole("rowheader")).toHaveCount(1);
    await page.reload();
    await expect(search).toHaveValue("Fixture Large");
    await expect(table.getByRole("rowheader")).toHaveAccessibleName("Waylaid Crate: Fixture Large");
    await expect(page.getByRole("button", { name: "Administration", exact: true })).toHaveCount(0);
    await page.goto("/admin/waylaid-crates");
    await expect(page.getByRole("heading", { name: "Administrator access required" })).toBeVisible();
    expect(requests.some(request => request.path.includes("/admin/waylaid-crates"))).toBe(false);
  });

  test("loading failures, empty data, stale evidence and accessible retry are explicit", async ({ page }) => {
    const { options } = await setup(page, "member");
    options.failure = true;
    await page.goto("/waylaid-crates");
    await expect(page.getByRole("alert")).toContainText("Waylaid Crates could not be loaded");
    options.failure = false;
    options.empty = true;
    await page.getByRole("button", { name: "Retry estimates" }).click();
    await expect(page.getByText("No crate catalogue is available yet.")).toBeVisible();
    options.empty = false;
    options.stale = true;
    await page.getByRole("button", { name: "Refresh prices" }).click();
    await expect(page.getByText("Market observations are stale.", { exact: false })).toBeVisible();
    await expect(page.getByText("Catalogue data is stale.", { exact: false })).toBeVisible();
  });

  test("admin nav, positive whole rewards, audit display, revision conflict and queued refresh", async ({ page }) => {
    const { requests, options } = await setup(page, "admin");
    await page.goto("/administration");
    const sections = page.getByRole("navigation", { name: "Administration sections" });
    await sections.getByRole("link", { name: "Waylaid Crates", exact: true }).click();
    await expect(page).toHaveURL(/\/admin\/waylaid-crates$/);
    await expect(sections.getByRole("link", { name: "Waylaid Crates", exact: true })).toHaveAttribute("aria-current", "page");
    const input = page.getByRole("textbox", { name: "Favor per crate for Apprentice" });
    const save = page.getByRole("button", { name: "Save Apprentice reward" });
    await expect(input).toHaveValue("5");
    await input.fill("1.5");
    await save.click();
    await expect(page.getByRole("alert")).toContainText("positive whole number");
    expect(requests.filter(request => request.method === "PUT")).toHaveLength(0);
    await input.fill("20");
    await save.click();
    await expect(page.getByText("Apprentice reward saved.")).toBeVisible();
    expect(requests.filter(request => request.method === "PUT").at(-1)?.body).toEqual({ favor: 20, revision: 1 });
    await expect(page.getByText("by fixture-user", { exact: false })).toBeVisible();

    options.conflict = true;
    await input.fill("30");
    await save.click();
    await expect(page.getByRole("alert")).toContainText("changed while you were editing");
    await expect(input).toHaveValue("30");
    await page.getByRole("button", { name: "Load latest Apprentice reward" }).click();
    await expect(input).toHaveValue("12");
    options.conflict = false;
    await input.fill("");
    await save.click();
    await expect(page.getByText("Apprentice is now unconfigured.")).toBeVisible();
    expect(requests.filter(request => request.method === "PUT").at(-1)?.body).toEqual({ favor: null, revision: 3 });

    await page.getByRole("button", { name: "Queue catalogue refresh" }).click();
    await expect(page.getByText("Catalogue refresh queued.", { exact: false })).toBeVisible();
    await expect(page.getByRole("button", { name: "Queue catalogue refresh" })).toBeDisabled();
    expect(requests.filter(request => request.path.endsWith("/refresh") && request.method === "POST")).toHaveLength(1);
  });
});

test.describe("Waylaid Crates touch layout", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("phone cards expose sort, keyboard focus, material links and no page overflow", async ({ page }) => {
    await setup(page, "member");
    await page.goto("/waylaid-crates");
    const sort = page.getByLabel("Sort crates");
    await expect(sort).toBeVisible();
    await expect(sort).toHaveValue("rate");
    const firstCard = page.locator(".waylaid-card").first();
    await expect(firstCard.getByRole("link", { name: "Fixture Mithril Bar" })).toHaveAttribute("href", "/markets/8/items/604");
    await expect(firstCard.locator(".waylaid-selected-materials")).toContainText("5 ×");
    await page.getByRole("button", { name: "Show materials for Waylaid Crate: Fixture Large" }).tap();
    await expect(page.getByRole("heading", { name: "Choose one" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Fixture Leather" })).toBeVisible();
    await expect(page.getByRole("table", { name: "Waylaid Crates estimates" })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
    await page.setViewportSize({ width: 320, height: 700 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
    const accessibility = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(accessibility.violations).toEqual([]);
  });

  test("phone admin section switch and read-only controls", async ({ page }) => {
    await setup(page, "admin", true);
    await page.goto("/administration");
    await page.getByRole("combobox", { name: "Administration section", exact: true }).selectOption("waylaid-crates");
    await expect(page).toHaveURL(/\/admin\/waylaid-crates$/);
    await expect(page.getByRole("textbox", { name: "Favor per crate for Apprentice" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Queue catalogue refresh" })).toBeDisabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  });
});
