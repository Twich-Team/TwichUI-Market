import type { PriceSummary } from "../../contracts/v1/types";
export interface Market {
  id: number;
  label: string;
  region: string;
  ruleset_id: number;
  house_id: number;
  source_kind: string;
  enabled: boolean;
  verified: boolean;
  player_identity_verified?: boolean;
  interval_seconds: number;
  last_success: string | null;
  last_modified: string | null;
  freshness: "unknown" | "stale" | "current";
  last_error: string | null;
  failures: number;
  coverage_status?: 'complete' | 'partial';
  feeds?: { source_kind: string; enabled: boolean; status: string; last_success: string | null;
    last_check: string | null; upstream_modified: string | null; listing_count: number | null;
    item_count: number | null; failures: number; last_error: string | null }[];
}
export interface Item {
  icon_url?: string | null;
  quality?: string | null;
  metadata_attribution?: { text: string; url: string } | null;
  item_id: number;
  name: string;
  name_verified: boolean;
  variant_key: string;
  variant: unknown;
}
export interface History {
  date: string;
  recent_price: string | null;
  supply: number;
}
export interface Valuation extends PriceSummary {
  observed_at: string | null;
  algorithm: string;
  history: History[];
}
export interface Detail {
  quality?: string | null;
  market: Market;
  item_id: number;
  variant_key: string;
  name: string;
  name_verified: boolean;
  valuation: Valuation;
  last_seen_at?: string | null;
  listings: {
    auction_id: string;
    quantity: number;
    buyout: string | null;
    unit_price: string | null;
    bid: string | null;
    time_left: string | null;
  }[];
  listings_truncated: boolean;
}
export interface Deal {
  icon_url?: string | null;
  quality?: string | null;
  name: string;
  name_verified: boolean;
  auction_id: string;
  item_id: number;
  variant_key: string;
  quantity: number;
  total_buyout: string;
  market_value: string;
  discount_percent: number;
  coverage_days: number;
  confidence: string;
  reason: string;
  cautions: string[];
}

export interface Signal {
  icon_url?: string | null;
  quality?: string | null;
  kind: "supply" | "price";
  item_id: number;
  variant_key: string;
  name: string;
  current_price: string | null;
  reference_price: string | null;
  current_supply: number;
  reference_supply: number;
  change_percent: number;
  coverage_days: number;
  observed_market_days: number;
  confidence: string;
  reason: string;
  cautions: string[];
}
