import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { defaultPreferences } from "../src/preferences-store";
import type { WritItem, WritQuote, WritRecipe, WritRoute, WritRow } from "../src/crafting-writs-data";

const at = "2026-11-25T18:45:00Z";
const catalogue = { source_url: "https://foreverdb.net", build: "fixture-build", refreshed_at: null,
  stale: false, writ_count: 3, supported_count: 3, incomplete_count: 0, partial_count: 1 };
const professions = [{ slug: "alchemy", label: "Alchemy" }, { slug: "tailoring", label: "Tailoring" }];
const item = (item_id: number, name: string): WritItem => ({ item_id, name, quality: "COMMON", icon_url: null });
const elixir = { ...item(310, "Fixture Elixir"),
  metadata_attribution: { text: "Data from ForeverDB.net", url: "https://foreverdb.net" } };
const thread = item(311, "Fixture Thread");
const reagent = item(312, "Fixture Reagent");
const alchemyWrit = { ...item(101, "Crafting Writ: Fixture Elixir"), quality: "RARE" };
const tailoringWrit = item(102, "Crafting Writ: Fixture Cloth");
const unknownWrit = item(103, "Crafting Writ: Fixture Unknown");
const exact = (amount: number, denominator = 1) => ({ numerator_copper: String(amount), denominator });

function quote(item: WritItem, quantity: number, price: number): WritQuote {
  return {
    item_id: item.item_id, item, quantity, unit_price_copper: String(price), subtotal_copper: String(quantity * price),
    unit_price_exact: exact(price), subtotal_exact: exact(quantity * price), minimum_unit_copper: String(price),
    minimum_purchase_copper: String(quantity * price), purchased_quantity: quantity, leftover_quantity: 0,
    stock_status: "sufficient_at_minimum", quote_status: "available", quality_reason: null,
    current_priced_quantity: 80, available_at_minimum: 20, coverage_days: null, source_kind: "commodities",
  };
}

function writ(writ: WritItem, profession: string, delivery: WritItem, reward: number | null, params: URLSearchParams): WritRow {
  const purchase = params.get("owned") === "true" ? 0 : 100;
  const method = params.get("method");
  const confirmed = params.getAll("confirmed_recipes").includes("77");
  const highSkill = !params.get("max_skill") || Number(params.get("max_skill")) >= 180;
  const recipe: WritRecipe = {
    recipe_id: 77, item_id: delivery.item_id, name: "Elixir Recipe", skill: 180, craft_count: 2, output_quantity: 2,
    restrictions: [], reasons: highSkill ? confirmed ? [] : ["recipe_unconfirmed"] : ["recipe_skill_above_maximum"],
  };
  const craftAllowed = profession === "alchemy";
  const buyUnitCost = profession === "tailoring" ? 50 : params.get("basis") === "14d" ? 15 : 100;
  const route = (cost: number, quotes: WritQuote[], reasons: string[], recipes: WritRecipe[] = []): WritRoute => ({
    eligible: !reasons.length, reasons, recipes, materials: quotes, basket: quotes,
    purchase_cost_exact: exact(purchase), completion_cost_exact: exact(cost), total_cost_exact: exact(cost + purchase),
    valuation_completion_cost_exact: exact(cost), valuation_total_cost_exact: exact(cost + purchase),
  });
  const craft = {
    ...route(60, [quote(reagent, 6, 10)], craftAllowed ? recipe.reasons ?? [] : ["recipe_unverified"], craftAllowed ? [recipe] : []),
    recipe_options: craftAllowed ? [recipe] : [],
  };
  const buy = route(3 * buyUnitCost, [quote(delivery, 3, buyUnitCost)], []);
  const display_method = method === "craft" || (method !== "buy" && craft.eligible && buyUnitCost > 20) ? "craft" : "buy";
  const selected = display_method === "craft" ? craft : buy;
  const selected_method = selected.eligible ? display_method : null;
  return {
    item: writ, profession, tier: "expert", quest_id: 801 + writ.item_id, faction: { id: 220, name: "Fixture Faction" },
    objectives: [{ item: delivery, item_id: delivery.item_id, quantity: 3, buy_allowed: true }],
    restrictions: ["Repeatability is unverified."], incomplete_reason: null, reputation: reward, provider_reputation: null,
    reward_source: reward === null ? "unknown" : "tier_setting",
    ...selected,
    purchase_quote: quote(writ, 1, 100), craft, buy, selected_method, display_method,
    eligible: !!selected_method && reward !== null,
    cost_per_reputation: selected_method && reward !== null
      ? exact(purchase + Number(selected.completion_cost_exact?.numerator_copper), reward) : null,
  };
}

async function setup(page: Page, role: "member" | "admin") {
  const user = { id: 1, role, active: true, username: "fixture-user" };
  const prefs = { schema_version: 1, user_id: 1, revision: 0, values: { ...defaultPreferences(), market_id: 8 } };
  const writes: { path: string; body: unknown; csrf: string | undefined }[] = [];
  const options = { conflict: false, offline: false };
  let tier = { key: "expert", reputation: 90 as number | null, revision: 1, updated_at: at, updated_by: "fixture-user" };
  let override = { key: "101", reputation: null as number | null, revision: 0, updated_at: null as string | null, updated_by: null as string | null };
  let refresh = { state: "idle", error: null, next_attempt_at: null as string | null, operation: "metadata_backfill" };
  await page.route("**/api/v1/**", route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/auth/session") return route.fulfill({ json: { user, csrf_token: "isolated-fixture" } });
    if (path === "/environment") return route.fulfill({ json: { read_only: false, review_fixtures: true } });
    if (path === "/me/preferences") return route.fulfill({ json: prefs });
    if (path === "/markets") return route.fulfill({ json: {
      markets: [8, 9].map(id => ({ id, label: `Fixture market ${id}`, region: "us", house_id: 114, enabled: true, verified: true,
        freshness: "current", last_success: at })),
    } });
    if (path === "/crafting-writs") {
      if (options.offline) return route.fulfill({ status: 503, json: { detail: "Fixture prices are unavailable" } });
      const rows = [
        writ(alchemyWrit, "alchemy", elixir, override.reputation ?? tier.reputation, url.searchParams),
        writ(tailoringWrit, "tailoring", thread, 25, url.searchParams),
        writ(unknownWrit, "tailoring", thread, null, url.searchParams),
      ];
      const profession = url.searchParams.get("profession");
      return route.fulfill({ json: {
        catalogue, professions, pricing: { snapshot_id: "1", observed_at: at, freshness: "current", synthetic: true },
        rows: profession ? rows.filter(row => row.profession === profession) : rows,
      } });
    }
    if (path === "/admin/crafting-writs") return route.fulfill({ json: {
      catalogue, refresh, tiers: [tier], writs: [{
        ...override, item: alchemyWrit, tier: "expert", quest_id: 902, provider_reputation: 50,
        effective_reputation: override.reputation ?? tier.reputation ?? 50,
        reward_source: override.reputation !== null ? "writ_override" : tier.reputation !== null ? "tier_setting" : "provider",
      }],
    } });
    if (request.method() === "PUT" && path.startsWith("/admin/crafting-writs/rewards/")) {
      const body = request.postDataJSON();
      writes.push({ path, body, csrf: request.headers()["x-csrf-token"] });
      if (path.endsWith("/tier/expert")) {
        if (options.conflict) {
          tier = { ...tier, reputation: 70, revision: tier.revision + 1 };
          return route.fulfill({ status: 409, json: { detail: "Fixture concurrent edit" } });
        }
        tier = { ...tier, reputation: body.reputation, revision: body.revision + 1 };
        return route.fulfill({ json: tier });
      }
      override = { ...override, reputation: body.reputation, revision: body.revision + 1, updated_at: at, updated_by: user.username };
      return route.fulfill({ json: override });
    }
    if (path === "/admin/crafting-writs/refresh" && request.method() === "POST") {
      refresh = { ...refresh, state: "queued", next_attempt_at: at };
      return route.fulfill({ status: 202, json: refresh });
    }
    if (/^\/markets\/\d+\/catalogue$/.test(path)) return route.fulfill({ json: { items: [], total_items: 0 } });
    return route.fulfill({ status: 404, json: { detail: "Unavailable in this isolated fixture" } });
  });
  return { writes, options };
}

test.describe("Crafting Writs desktop", () => {
  test.use({ viewport: { width: 1440, height: 950 } });

  test("member chooses an eligible recipe, changes price basis, and returns to focused market item link", async ({ page }) => {
    await setup(page, "member");
    await page.goto("/crafting-writs?market=9");
    const table = page.getByRole("table", { name: "Crafting Writs estimates" });
    const firstWrit = table.getByRole("rowheader").first().getByRole("link", { name: "Crafting Writ: Fixture Elixir" });
    await expect(firstWrit.locator(".item-name")).toHaveText("Fixture Elixir");
    await expect(firstWrit).toHaveAttribute("title", "Crafting Writ: Fixture Elixir");
    await expect(page.getByRole("link", { name: "ForeverDB.net", exact: true })).toHaveCount(1);
    await expect(table.getByRole("link", { name: "Data from ForeverDB.net" })).toHaveCount(0);
    await expect(table.getByRole("columnheader", { name: "Cost / reputation" })).toHaveAttribute("aria-sort", "ascending");
    await expect(table.getByRole("row").filter({ hasText: "Fixture Unknown" })).toContainText("Unconfigured");
    const filter = page.getByLabel("Profession", { exact: true });
    await filter.selectOption("alchemy");
    await expect(table.getByRole("rowheader")).toHaveCount(1);
    await expect(filter.locator("option[value=tailoring]")).toHaveCount(1);
    const row = table.getByRole("row").filter({ has: page.getByRole("rowheader", { name: /Fixture Elixir/ }) });
    await expect(row).toContainText("Buy finished items");
    await expect(row.getByRole("link", { name: "Fixture Elixir", exact: true })).toHaveAttribute("href", "/markets/9/items/310");

    const details = row.getByRole("button", { name: /Show details for Crafting Writ: Fixture Elixir/ });
    await details.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "Delivery and eligibility" })).toBeVisible();
    await expect(page.getByText("Repeatability is unverified.")).toBeVisible();
    const checkbox = page.getByRole("checkbox", { name: /I can use this recipe for Elixir Recipe/ });
    await checkbox.check();
    await expect(page).toHaveURL(/recipes=77/);
    await expect(row).toContainText("Craft delivery");
    const selected = page.locator(".waylaid-bundle").filter({ hasText: "Selected method" });
    await expect(selected).toContainText("Output 2 per craft · 2 crafts");
    const reagentLink = selected.getByRole("link", { name: "Fixture Reagent" });
    await expect(reagentLink).toHaveAttribute("href", "/markets/9/items/312");
    await reagentLink.click();
    await expect(page).toHaveURL(/markets\/9\/items\/312$/);
    await page.getByRole("link", { name: /Back to Crafting Writs/ }).click();
    await expect(reagentLink).toBeFocused();

    await page.getByLabel("Price basis").selectOption("14d");
    await expect(row).toContainText("Buy finished items");
    await page.getByLabel("Completion method").selectOption("craft");
    await expect(row).toContainText("Craft delivery");
    await page.getByLabel("Maximum recipe skill").fill("100");
    await page.getByLabel("Search writs").fill("310");
    await page.getByRole("button", { name: "Apply filters" }).click();
    await expect(row).toContainText("Recipe exceeds your skill limit");
    await page.getByLabel("I already own the writ").check();
    await expect(row).toContainText("Owned");
    await page.reload();
    await expect(filter).toHaveValue("alchemy");
    await expect(page.getByLabel("Price basis")).toHaveValue("14d");
    await expect(page.getByLabel("Completion method")).toHaveValue("craft");
    await expect(page.getByLabel("Maximum recipe skill")).toHaveValue("100");
    await expect(page.getByLabel("Search writs")).toHaveValue("310");
    await expect(page.getByLabel("I already own the writ")).toBeChecked();
    await page.goto("/admin/crafting-writs");
    await expect(page.getByRole("heading", { name: "Administrator access required" })).toBeVisible();
  });

  test("administrator sets and resets overrides, resolves conflicts, and queues bounded metadata refresh", async ({ page }) => {
    const { writes, options } = await setup(page, "admin");
    await page.goto("/administration");
    await page.getByRole("navigation", { name: "Administration sections" }).getByRole("link", { name: "Crafting Writs" }).click();
    await expect(page).toHaveURL(/\/admin\/crafting-writs$/);
    await expect(page.getByText("Provider reward 50 · differs from effective reward")).toBeVisible();
    const tier = page.getByRole("textbox", { name: "Reputation per writ for Expert" });
    const save = page.getByRole("button", { name: "Save reward for Expert" });
    await tier.fill("1.5");
    await save.click();
    await expect(page.getByRole("alert")).toContainText("positive whole number");
    expect(writes).toHaveLength(0);

    await tier.fill("120");
    await save.click();
    await expect(page.getByText("Effective reward 120 · Administrator tier setting")).toBeVisible();
    expect(writes.at(-1)).toEqual({ path: "/admin/crafting-writs/rewards/tier/expert", body: { reputation: 120, revision: 1 }, csrf: "isolated-fixture" });
    const override = page.getByRole("textbox", { name: "Reputation override for Crafting Writ: Fixture Elixir" });
    const saveOverride = page.getByRole("button", { name: "Save reward for Crafting Writ: Fixture Elixir" });
    await override.fill("150");
    await saveOverride.click();
    await expect(page.getByText("Effective reward 150 · Administrator writ override")).toBeVisible();
    await page.reload();
    await expect(override).toHaveValue("150");
    await override.fill("");
    await saveOverride.click();
    await expect(page.getByText("Effective reward 120 · Administrator tier setting")).toBeVisible();

    options.conflict = true;
    await tier.fill("200");
    await save.click();
    await expect(page.getByRole("alert")).toContainText("changed while you were editing");
    await page.getByRole("button", { name: "Load latest reward for Expert" }).click();
    await expect(tier).toHaveValue("70");
    await page.getByRole("button", { name: "Refresh item metadata" }).click();
    await expect(page.getByText("Item metadata refresh queued.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Refresh item metadata" })).toBeDisabled();
  });
});

test.describe("Crafting Writs phone", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("profession, primary prices, keyboard-accessible details, and retry fit narrow screens", async ({ page }) => {
    const { options } = await setup(page, "member");
    options.offline = true;
    await page.goto("/crafting-writs");
    await expect(page.getByRole("alert")).toContainText("Fixture prices are unavailable");
    options.offline = false;
    await page.getByRole("button", { name: "Retry estimates" }).tap();
    await expect(page.getByLabel("Profession", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Sort writs")).toHaveValue("rate");
    const card = page.locator(".waylaid-card").first();
    await expect(card).toContainText("Cost / reputation");
    await expect(card).toContainText("3 ×");
    await expect(card.getByRole("link", { name: "Fixture Elixir", exact: true })).toHaveAttribute("href", "/markets/8/items/310");
    await card.getByRole("button", { name: /Show details/ }).tap();
    await expect(card.getByRole("heading", { name: "Delivery and eligibility" })).toBeVisible();
    await expect(page.getByRole("table", { name: "Crafting Writs estimates" })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
    await page.setViewportSize({ width: 320, height: 700 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
    const accessibility = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(accessibility.violations).toEqual([]);
  });
});
