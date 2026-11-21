/** Version 1 data-only contracts; amounts are integer copper strings. */
export type Copper = string | null;
export interface PriceSummary {
  recent_price:Copper;
  lowest_buyout:Copper;
  market_value:Copper;
  historical_value:Copper;
  supply:number;
  priced_supply:number;
  listing_count:number;
  coverage_days:number;
  market_coverage_days:number;
  synthetic:boolean;
}
export type SyncChange = {item_id:number;variant_key:string} & (
  {operation:'upsert';value:PriceSummary} | {operation:'delete';value:null}
);
export interface SyncPage {
  contract_version:1;
  market_id:number;
  algorithm:'asking-v1-provisional';
  changes:SyncChange[];
  cursor:string;
  has_more:boolean;
  target_observation_id:string;
  observed_at:string|null;
  synthetic:boolean;
}
export interface AddonExport {
  format:'twichui-market-addon-data';
  contract_version:1;
  algorithm:'asking-v1-provisional';
  server:string;
  market_id:number;
  observed_at:string|null;
  generated_at:string;
  synthetic:boolean;
  items:{item_id:number;variant_key:string;value:PriceSummary}[];
}
