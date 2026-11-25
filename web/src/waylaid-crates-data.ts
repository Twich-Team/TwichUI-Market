import { supportedId } from "./navigation";

type Copper = string | null;
export interface ExactCopper {
  numerator_copper: string;
  denominator: number | string;
}

export interface CrateItem {
  item_id: number;
  name: string;
  quality: string | null;
  icon_url: string | null;
  metadata_attribution?: { text: string; url: string } | null;
  metadata_attributions?: { text: string; url: string; notice?: string }[];
}

export interface CrateQuote {
  item_id: number;
  item: CrateItem;
  quantity: number;
  unit_price_copper: Copper;
  subtotal_copper: Copper;
  unit_price_exact: ExactCopper | null;
  subtotal_exact: ExactCopper | null;
  minimum_unit_copper: Copper;
  minimum_purchase_copper: Copper;
  quality_reason: string | null;
  available_at_minimum: number | null;
  current_priced_quantity: number | null;
  stock_status: string;
  quote_status: string;
  coverage_days: number | null;
  source_kind: string | null;
}

export interface CrateBundle {
  bundle_id: string | number;
  materials: CrateQuote[];
  fill_cost_copper: Copper;
  fill_cost_exact: ExactCopper | null;
  eligible: boolean;
}

export interface CrateRow {
  item: CrateItem;
  tier: string | null;
  required_level: number | null;
  sealed_item_id: number | null;
  favor: number | null;
  bundles: CrateBundle[];
  selected_bundle_id: CrateBundle["bundle_id"] | null;
  fill_cost_copper: Copper;
  fill_cost_exact: ExactCopper | null;
  purchase_cost_copper: Copper;
  purchase_cost_exact: ExactCopper | null;
  total_cost_copper: Copper;
  total_cost_exact: ExactCopper | null;
  cost_per_favor: ExactCopper | null;
  purchase_quote: CrateQuote;
  eligible: boolean;
  reasons: string[];
  unavailable_reason: string | null;
  reward_unavailable_reason: string | null;
}

export interface CrateCatalogue {
  source_url: string;
  build: string | null;
  refreshed_at: string | null;
  stale: boolean;
  crate_count: number;
  supported_count: number;
}

export interface CrateResults {
  catalogue: CrateCatalogue;
  pricing: {
    snapshot_id: string | null;
    observed_at: string | null;
    freshness: "current" | "stale" | "unknown";
    synthetic: boolean;
  };
  rows: CrateRow[];
}

export const bases = {
  current: "Current minimum",
  regional: "Regional reference",
  "14d": "14-day reference",
} as const;

export const basisDescriptions: Record<keyof typeof bases, string> = {
  current: "Estimates use the lowest observed unit ask. Stock and whole-stack availability are checked separately.",
  regional: "Uses a regional estimate when available. Current stock is shown separately.",
  "14d": "Uses a 14-day historical estimate when available. Current stock is shown separately.",
};

export const crateColumns = {
  tier: "Tier",
  favor: "Favor",
  purchase: "Crate purchase",
  fill: "Fill cost",
  total: "Total cost",
  rate: "Cost / Favor",
} as const;

type CrateSort = keyof typeof crateColumns;

export interface CrateView {
  market: number;
  basis: keyof typeof bases;
  owned: boolean;
  query: string;
  tier: string | null;
  known: boolean;
  sort: CrateSort;
  direction: "asc" | "desc";
}

export function crateView(search: string, market: number): CrateView {
  const params = new URLSearchParams(search);
  const basis = params.get("basis");
  const sort = params.get("sort");
  return {
    market: supportedId(params.get("market")) ?? market,
    basis: basis && Object.hasOwn(bases, basis) ? basis as CrateView["basis"] : "current",
    owned: params.get("owned") === "true",
    query: (params.get("q") ?? "").slice(0, 64).trim(),
    tier: params.get("tier")?.match(/^[a-z][a-z0-9_-]{0,47}$/)?.[0] ?? null,
    known: params.get("known") === "true",
    sort: sort && Object.hasOwn(crateColumns, sort) ? sort as CrateSort : "rate",
    direction: params.get("direction") === "desc" ? "desc" : "asc",
  };
}

export function crateUrl(view: CrateView): string {
  const params = new URLSearchParams({
    market: String(view.market), basis: view.basis, owned: String(view.owned),
    sort: view.sort, direction: view.direction,
  });
  if (view.query) params.set("q", view.query);
  if (view.tier !== null) params.set("tier", String(view.tier));
  if (view.known) params.set("known", "true");
  return "/waylaid-crates?" + params;
}

export function tierLabel(tier: string) {
  return tier.replace(/[-_]/g, " ").replace(/^./, character => character.toUpperCase());
}

function sortValue(row: CrateRow, field: Exclude<CrateSort, "tier">): ExactCopper | null {
  return {
    favor: row.favor === null ? null : { numerator_copper: String(row.favor), denominator: 1 },
    purchase: row.purchase_cost_exact,
    fill: row.fill_cost_exact,
    total: row.total_cost_exact,
    rate: row.cost_per_favor,
  }[field];
}

export function compareCrates(left: CrateRow, right: CrateRow, field: CrateSort, descending = false) {
  if (field === "tier") {
    if (left.tier === null && right.tier !== null) return 1;
    if (left.tier !== null && right.tier === null) return -1;
    const tiers = ["apprentice", "journeyman", "expert", "artisan"];
    const rank = (tier: string | null) => {
      const index = tier === null ? -1 : tiers.indexOf(tier);
      return index < 0 ? tiers.length : index;
    };
    const order = rank(left.tier) - rank(right.tier) ||
      (left.tier ?? "").localeCompare(right.tier ?? "");
    return (descending ? -order : order) || left.item.item_id - right.item.item_id;
  }
  const a = sortValue(left, field);
  const b = sortValue(right, field);
  if (!a || !b) {
    if (!a && b) return 1;
    if (a && !b) return -1;
    return left.item.item_id - right.item.item_id;
  }
  const difference = BigInt(a.numerator_copper) * BigInt(b.denominator) -
    BigInt(b.numerator_copper) * BigInt(a.denominator);
  const order = difference < 0n ? -1 : difference > 0n ? 1 : 0;
  return (descending ? -order : order) || left.item.item_id - right.item.item_id;
}

export function parseFavor(value: string): number | null | undefined {
  if (!value.trim()) return null;
  return supportedId(value.trim()) ?? undefined;
}
