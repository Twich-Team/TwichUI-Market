import { supportedId } from "./navigation";
import { bases, type CrateItem, type CrateQuote, type CrateResults, type ExactCopper } from "./waylaid-crates-data";

export const methods = {
  cheapest: "Cheapest eligible method",
  craft: "Craft delivery",
  buy: "Buy finished items",
} as const;

export const writColumns = {
  purchase: "Writ cost",
  completion: "Completion cost",
  total: "Total cost",
  reputation: "Reputation",
  rate: "Cost / reputation",
} as const;

export const writQueryKey = ["private", "crafting-writs"];
export const maxConfirmedRecipes = 40;
export const maxRecipeSkill = 1000;

export type WritSort = keyof typeof writColumns;
export type WritMethod = Exclude<keyof typeof methods, "cheapest">;
export type RewardSource = "writ_override" | "tier_setting" | "provider" | "unknown";

export interface Profession {
  slug: string;
  label: string;
}

export interface WritItem extends CrateItem {
  variant_key?: string;
}

export interface WritDelivery {
  item: WritItem;
  item_id: number;
  quantity: number;
  buy_allowed: boolean | null;
}

export interface WritQuote extends CrateQuote {
  item: WritItem;
  purchased_quantity: number | null;
  leftover_quantity: number | null;
  covered_by_writ_quantity?: number | null;
  stacks?: { quantity: number; count: number }[] | null;
}

export interface WritRecipe {
  recipe_id: number;
  item_id: number;
  name?: string | null;
  skill: number | null;
  craft_count: number | null;
  output_quantity: number | null;
  output_min?: number | null;
  output_max?: number | null;
  restrictions: string[];
  reasons?: string[];
}

export interface WritRoute {
  eligible: boolean;
  reasons: string[];
  purchase_cost_exact: ExactCopper | null;
  completion_cost_exact: ExactCopper | null;
  total_cost_exact: ExactCopper | null;
  valuation_completion_cost_exact: ExactCopper | null;
  valuation_total_cost_exact: ExactCopper | null;
  materials: WritQuote[];
  basket: WritQuote[];
  recipes: WritRecipe[];
}

export interface WritRow {
  item: WritItem;
  tier: string | null;
  profession: string | null;
  quest_id: number | null;
  faction: { id: number | null; name: string } | null;
  objectives: WritDelivery[];
  restrictions: string[];
  incomplete_reason: string | null;
  reputation: number | null;
  reward_source: RewardSource;
  provider_reputation: number | null;
  purchase_quote: WritQuote;
  purchase_cost_exact: ExactCopper | null;
  completion_cost_exact: ExactCopper | null;
  total_cost_exact: ExactCopper | null;
  valuation_completion_cost_exact: ExactCopper | null;
  valuation_total_cost_exact: ExactCopper | null;
  cost_per_reputation: ExactCopper | null;
  selected_method: WritMethod | null;
  display_method: WritMethod | null;
  craft: WritRoute & { recipe_options: WritRecipe[] };
  buy: WritRoute;
  eligible: boolean;
  reasons: string[];
}

export interface WritCatalogue {
  source_url: string;
  source_label?: string | null;
  source_observed_at?: string | null;
  build: string | null;
  refreshed_at: string | null;
  stale: boolean;
  writ_count: number;
  supported_count: number;
  incomplete_count: number;
  partial_count: number;
}

export interface WritResults {
  catalogue: WritCatalogue;
  pricing: CrateResults["pricing"];
  professions: Profession[];
  rows: WritRow[];
}

export interface WritView {
  market: number;
  basis: keyof typeof bases;
  owned: boolean;
  method: keyof typeof methods;
  profession: string | null;
  maxSkill: number | null;
  confirmedRecipes: number[];
  query: string;
  sort: WritSort;
  direction: "asc" | "desc";
}

export function writView(search: string, market: number): WritView {
  const params = new URLSearchParams(search);
  const basis = params.get("basis");
  const method = params.get("method");
  const sort = params.get("sort");
  const maxSkill = supportedId(params.get("max_skill"));
  const recipeIds = (params.get("recipes") ?? "").slice(0, 440).split(",").map(supportedId);
  return {
    market: supportedId(params.get("market")) ?? market,
    basis: basis && Object.hasOwn(bases, basis) ? basis as WritView["basis"] : "current",
    owned: params.get("owned") === "true",
    method: method && Object.hasOwn(methods, method) ? method as WritView["method"] : "cheapest",
    profession: params.get("profession")?.match(/^[a-z][a-z0-9-]{0,47}$/)?.[0] ?? null,
    maxSkill: maxSkill && maxSkill <= maxRecipeSkill ? maxSkill : null,
    confirmedRecipes: [...new Set(recipeIds.filter(id => id !== null))].sort((a, b) => a - b).slice(0, maxConfirmedRecipes),
    query: (params.get("q") ?? "").slice(0, 64).trim(),
    sort: sort && Object.hasOwn(writColumns, sort) ? sort as WritSort : "rate",
    direction: params.get("direction") === "desc" ? "desc" : "asc",
  };
}

export function writUrl(view: WritView) {
  const params = new URLSearchParams({
    market: String(view.market), basis: view.basis, owned: String(view.owned),
    method: view.method, sort: view.sort, direction: view.direction,
  });
  if (view.profession) params.set("profession", view.profession);
  if (view.maxSkill !== null) params.set("max_skill", String(view.maxSkill));
  if (view.confirmedRecipes.length) params.set("recipes", view.confirmedRecipes.join(","));
  if (view.query) params.set("q", view.query);
  return "/crafting-writs?" + params;
}

export function writRequest(view: WritView) {
  const params = new URLSearchParams({
    market_id: String(view.market), basis: view.basis, owned: String(view.owned), method: view.method,
  });
  if (view.profession) params.set("profession", view.profession);
  if (view.maxSkill !== null) params.set("max_skill", String(view.maxSkill));
  for (const id of view.confirmedRecipes) params.append("confirmed_recipes", String(id));
  return "/crafting-writs?" + params;
}

export function writSortValue(row: WritRow, sort: WritSort): ExactCopper | null {
  switch (sort) {
    case "purchase": return row.purchase_cost_exact;
    case "completion": return row.completion_cost_exact ?? row.valuation_completion_cost_exact;
    case "total": return row.total_cost_exact ?? row.valuation_total_cost_exact;
    case "reputation": return row.reputation === null ? null : {
      numerator_copper: String(row.reputation), denominator: 1,
    };
    case "rate": return row.eligible ? row.cost_per_reputation : null;
  }
}

export function compareWrits(left: WritRow, right: WritRow, sort: WritSort, descending = false) {
  const a = writSortValue(left, sort);
  const b = writSortValue(right, sort);
  const identity = left.item.item_id - right.item.item_id;
  if (!a || !b) return a ? -1 : b ? 1 : identity;
  const difference = BigInt(a.numerator_copper) * BigInt(b.denominator) -
    BigInt(b.numerator_copper) * BigInt(a.denominator);
  const order = difference < 0n ? -1 : difference > 0n ? 1 : 0;
  return (descending ? -order : order) || identity;
}

const rewardSources: Record<RewardSource, string> = {
  writ_override: "Administrator writ override",
  tier_setting: "Administrator tier setting",
  provider: "Verified provider reward",
  unknown: "Unconfigured",
};

export function rewardSourceLabel(source: RewardSource) {
  return rewardSources[source];
}

const statuses: Record<string, string> = {
  available: "Price observed",
  basket_search_limit: "The listing mix exceeds the purchase search limit",
  buying_not_allowed: "A purchased item cannot satisfy the delivery",
  buyability_unknown: "Finished-item eligibility is unknown",
  hand_in_unknown: "Hand-in requirements are unverified",
  hand_in_restricted: "Hand-in restrictions prevent an eligible estimate",
  insufficient_at_minimum: "Insufficient quantity at the minimum",
  limited: "Limited historical price coverage",
  missing_price: "Price unobserved",
  needs_review: "Price reference needs review",
  no_delivery: "Delivery requirements are unverified",
  reference: "Reference price",
  recipe_combination_limit: "The possible recipe combinations exceed the search limit",
  recipe_ingredients_unknown: "Recipe ingredients are unverified",
  recipe_output_random: "Recipe output varies",
  recipe_output_unknown: "Recipe output is unverified",
  recipe_restricted: "Recipe restrictions prevent an eligible estimate",
  recipe_restrictions_unknown: "Recipe restrictions are unverified",
  recipe_skill_above_maximum: "Recipe exceeds your skill limit",
  recipe_skill_unknown: "Recipe skill is unverified",
  recipe_unconfirmed: "Confirm you can use this recipe",
  recipe_unverified: "Recipe is unverified",
  regional_unavailable: "Market has no regional reference",
  rounded_estimate: "Whole-stack buyout needed to validate the unit estimate",
  stale_freshness: "Market observations are stale",
  sufficient_at_minimum: "Required quantity available at the minimum",
  synthetic_observations: "Illustrative observations",
  unknown: "Current stock unknown",
  unavailable: "Price reference unavailable",
  unknown_freshness: "Market freshness unknown",
  unknown_reputation: "Base reputation is unconfigured",
  unsupported_statistics: "Compatible retained statistics unavailable",
  unverified_market: "Market mapping unverified",
  whole_stack_overshoot: "Whole stacks include extra units",
};

export function writStatus(reason: string) {
  return statuses[reason] ?? reason.replaceAll("_", " ").replace(/^./, character => character.toUpperCase());
}
