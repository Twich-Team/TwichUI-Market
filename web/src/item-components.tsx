import { useEffect, useState, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Popover } from "@base-ui/react/popover";
import { requestItemMetadata } from "./metadata-priority";
import { api, money, when } from "./api";
export interface ItemIdentity {
  item_id: number;
  name: string;
  quality?: string | null;
  name_verified?: boolean;
  icon_url?: string | null;
  metadata_provider?: string | null;
  metadata_attribution?: { text: string; url: string } | null;
  icon_attribution?: { text: string; url: string } | null;
  variant_key?: string;
}
export interface ItemProfile extends ItemIdentity {
  attributes: {
    scope: string;
    quality: string | null;
    level?: number;
    required_level?: number;
    vendor_sell?: string;
    lines: { text: string; kind: string }[];
  } | null;
  source: {
    provider: string;
    namespace?: string;
    build?: string;
    observed_at: string | null;
    confidence: string;
    status?: string;
    attribution?: { text: string; url: string };
  } | null;
  icon_source?: {
    provider: string;
    attribution?: { text: string; url: string };
  } | null;
  media_status: string;
  metadata_status: string;
  variant_notice: string;
}
export function ItemIcon({ item }: { item: ItemIdentity }) {
  const [failed, setFailed] = useState(false);
  const [visibleSource,setVisibleSource]=useState<string|null>(null);
  const container=useRef<HTMLSpanElement>(null);
  useEffect(()=>{
    setFailed(false);
    if(!item.icon_url || !container.current)return;
    if(typeof IntersectionObserver==='undefined'){setVisibleSource(item.icon_url);return;}
    const source=item.icon_url;
    const observer=new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting)){setVisibleSource(source);observer.disconnect();}},{rootMargin:'120px'});
    observer.observe(container.current);return()=>observer.disconnect();
  },[item.icon_url,item.item_id]);
  return (
    <span
      ref={container}
      className={`wow-icon quality-${item.quality?.toLowerCase() || "unknown"}`}
    >
      {item.icon_url && visibleSource===item.icon_url && !failed ? (
        <img
          src={item.icon_url}
          alt=""
          width={36}
          height={36}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <span aria-hidden="true">?</span>
      )}
    </span>
  );
}
export function ItemFacts({ profile }: { profile: ItemProfile }) {
  const facts = profile.attributes;
  return (
    <>
      <div
        className={`wow-name quality-text-${profile.quality?.toLowerCase() || "unknown"}`}
      >
        {profile.name}
      </div>
      {!facts ? (
        <p className="muted">
          Verified item attributes are unavailable. Missing facts are not
          guessed.
        </p>
      ) : (
        <>
          {facts.level !== undefined && (
            <div className="item-level">Item Level {facts.level}</div>
          )}
          {facts.lines.map((line, index) => (
            <div key={index} className={`item-line ${line.kind}`}>
              {line.text}
            </div>
          ))}
          {facts.required_level !== undefined && (
            <div>Requires Level {facts.required_level}</div>
          )}
          {facts.vendor_sell !== undefined && (
            <div className="vendor-value">
              Vendor sell: {money(facts.vendor_sell)}
            </div>
          )}
        </>
      )}
      <p className="small muted">{profile.variant_notice}</p>
      {profile.source && (
        <div className="item-source small">
          {profile.source.confidence === "community_beta" ? (
            <>
              <strong>Community / beta build · attributes may differ</strong>
              <br />
              {profile.source.build}
              <br />
              {profile.source.attribution && (
                <a
                  href={profile.source.attribution.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {profile.source.attribution.text}
                </a>
              )}
            </>
          ) : (
            <span>
              {profile.source.confidence === "synthetic"
                ? "Synthetic fixture metadata"
                : "Blizzard Forever base-item metadata"}{" "}
              · {profile.source.namespace}
            </span>
          )}
          {profile.source.status && profile.source.status !== "available" && (
            <>
              <br />
              Previously observed · latest refresh unavailable
            </>
          )}
          <br />
          Observed {when(profile.source.observed_at)}
        </div>
      )}
    </>
  );
}
export function ItemAttribution({ item }: { item: ItemIdentity }) {
  const source = item.metadata_attribution || item.icon_attribution;
  return source ? (
    <a
      className="item-credit small"
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
    >
      Data from TheWoWDB · beta build
    </a>
  ) : null;
}
export function ItemInfo({
  item,
  market,
  prices,
  label = false,
  ranges,
}: {
  item: ItemIdentity;
  market: number;
  label?: boolean;
  ranges?: {
    recent_price: { minimum: string | null; maximum: string | null };
    market_value: { minimum: string | null; maximum: string | null };
  };
  prices?: {
    recent_price?: string | null;
    market_value?: string | null;
    supply?: number;
  };
}) {
  const [open, setOpen] = useState(false);
  const cache = useQueryClient();
  const profile = useQuery({
    queryKey: ["private", "item-profile", market, item.item_id],
    enabled: open,
    queryFn: ({ signal }) =>
      api<ItemProfile>(
        `/markets/${market}/item-profiles/${item.item_id}`,
        "GET",
        undefined,
        signal,
      ),
    refetchInterval: (query) => (query.state.data?.attributes ? false : 5000),
  });
  useEffect(() => {
    if (open && (!profile.data?.attributes || !profile.data?.icon_url))
      requestItemMetadata(market, [item.item_id]).catch(() => {});
  }, [open, market, item.item_id]);
  useEffect(() => {
    if (
      profile.data &&
      (profile.data.name !== item.name || profile.data.quality !== item.quality)
    )
      cache.invalidateQueries({ queryKey: ["private", "catalogue", market] });
  }, [profile.data, market, item.name, item.quality, cache]);
  const displayItem = profile.data || item;
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger
        className="item-info-trigger"
        openOnHover
        delay={180}
        closeDelay={160}
        onFocus={(event) => {
          if (event.currentTarget.matches(":focus-visible")) setOpen(true);
        }}
        aria-label={`Item details for ${displayItem.name}`}
      >
        <ItemIcon item={displayItem} />
        {label && (
          <span
            className={`item-trigger-label quality-text-${displayItem.quality?.toLowerCase() || "unknown"}`}
          >
            {displayItem.name}
          </span>
        )}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner
          side="right"
          sideOffset={10}
          className="item-popover-positioner"
        >
          <Popover.Popup className="wow-tooltip" initialFocus={false}>
            <Popover.Title className="sr-only">
              {item.name} item details
            </Popover.Title>
            {profile.data ? (
              <ItemFacts profile={profile.data} />
            ) : (
              <p role="status">
                {profile.error
                  ? "Item metadata could not be loaded."
                  : "Loading verified item facts…"}
              </p>
            )}
            {profile.data?.icon_source?.provider === "thewowdb" &&
              profile.data.source?.provider !== "thewowdb" &&
              profile.data.icon_source.attribution && (
                <a
                  href={profile.data.icon_source.attribution.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="small"
                >
                  Artwork data from TheWoWDB · community source
                </a>
              )}
            {ranges && (
              <section
                className="tooltip-market"
                aria-label="Variant market ranges"
              >
                <strong>Asking-price ranges across variants</strong>
                <div>
                  Recent: {money(ranges.recent_price.minimum)} –{" "}
                  {money(ranges.recent_price.maximum)}
                </div>
                <div>
                  14-day: {money(ranges.market_value.minimum)} –{" "}
                  {money(ranges.market_value.maximum)}
                </div>
                <small>
                  Expand variants for exact prices. These are not completed
                  sales.
                </small>
              </section>
            )}
            {prices && (
              <section className="tooltip-market" aria-label="Market estimates">
                <strong>Market estimates · asking listings</strong>
                <div>Recent: {money(prices.recent_price)}</div>
                <div>14-day reference: {money(prices.market_value)}</div>
                <div>
                  Supply: {prices.supply?.toLocaleString() ?? "Unknown"}
                </div>
                <small>
                  Variant-specific market data is separate from base item
                  attributes.
                </small>
              </section>
            )}
            <Popover.Close className="text-button">
              Close item details
            </Popover.Close>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}
