import { Loading } from "./loading";
import { ForeverDBFacts, type RichFacts } from "./foreverdb-facts";
import { ItemName } from "./item-name";
import { Currency } from "./currency";
import { useEffect, useId, useState, useRef, useSyncExternalStore } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Popover } from "@base-ui/react/popover";
import { Dialog } from "@base-ui/react/dialog";
import { requestItemMetadata } from "./metadata-priority";
import { api, when } from "./api";
export interface ItemIdentity {
  item_id: number;
  name: string;
  quality?: string | null;
  name_verified?: boolean;
  icon_url?: string | null;
  metadata_provider?: string | null;
  metadata_attribution?: { text: string; url: string } | null;
  metadata_attributions?: { text: string; url: string; notice?: string }[];
  icon_attribution?: { text: string; url: string } | null;
  variant_key?: string;
}
export interface ItemProfile extends ItemIdentity {
  catalog?: { schema_version: number; fields: Record<string, unknown>; provenance: Record<string, { provider: string; confidence: string; build?: string; current_build?: string; retrieved_at?: string; qualifiers?: {dataFromBuild?:string;betaEvent?:boolean;speculation?:boolean}; attribution?: { text: string; url: string; license?: string; notice?: string } }>; conflicts: { field: string; selected: string; alternative_provider: string }[] } | null;
  attributes: RichFacts & {
    scope: string;
    quality: string | null;
    class?: string; subclass?: string; slot?: string; binding?: string;
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
  const [visibleSource, setVisibleSource] = useState<string | null>(null);
  const container = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    setFailed(false);
    setVisibleSource(null);
    if (!item.icon_url || !container.current) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisibleSource(item.icon_url);
      return;
    }
    const source = item.icon_url;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisibleSource(source);
          observer.disconnect();
        }
      },
      { rootMargin: "120px" },
    );
    observer.observe(container.current);
    return () => observer.disconnect();
  }, [item.icon_url, item.item_id]);
  return (
    <span
      ref={container}
      className={`wow-icon quality-${item.quality?.toLowerCase() || "unknown"}`}
    >
      {item.icon_url && visibleSource === item.icon_url && !failed ? (
        <img
          src={item.icon_url}
          alt=""
          width={36}
          height={36}
          loading="eager"
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
        className="wow-name"
      >
        <ItemName name={profile.name} quality={profile.quality}/>
      </div>
      {!profile.metadata_provider && <p className="small muted">Name unavailable · Item #{profile.item_id}</p>}
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
          {[facts.slot, facts.subclass || facts.class, facts.binding].filter(Boolean).map((value,index)=><div key={index}>{value}</div>)}
          {facts.lines.map((line, index) => (
            <div key={index} className={`item-line ${line.kind}`}>
              {line.text}
            </div>
          ))}
          <ForeverDBFacts facts={{...facts,stats:facts.lines.some(line=>line.kind==="stat") ? undefined : facts.stats,effects:facts.lines.some(line=>line.kind==="effect") ? undefined : facts.effects}}/>
          {facts.required_level !== undefined && (
            <div>Requires Level {facts.required_level}</div>
          )}
          {facts.vendor_sell !== undefined && (
            <div className="vendor-value">
              Vendor sell: <Currency value={facts.vendor_sell} />
            </div>
          )}
        </>
      )}
      {profile.source?.confidence === "synthetic" && <p className="small muted">Synthetic fixture metadata</p>}
      {Object.values(profile.catalog?.provenance || {}).some(origin=>["game_file_unconfirmed","client_record_unverified"].includes(origin.confidence)) && <p className="small muted">Unconfirmed client-file attributes may differ.</p>}
      {profile.source?.confidence === "community_beta" && <p className="small muted">Community / beta attributes may differ.</p>}
      {profile.source?.status && profile.source.status !== "available" && <p className="small muted">Previously observed metadata · latest check unavailable.</p>}
      {Object.values(profile.catalog?.provenance || {}).some(origin=>origin.confidence==="retained_earlier_build" || origin.qualifiers?.dataFromBuild) && <p className="notice">Some retained fields come from an earlier build; current-client verification is unavailable.</p>}
      {Object.values(profile.catalog?.provenance || {}).some(origin=>origin.qualifiers?.betaEvent || origin.qualifiers?.speculation) && <p className="notice">Some fields describe historical beta or unconfirmed availability.</p>}
      {new Set(Object.values(profile.catalog?.provenance || {}).filter(origin=>origin.provider==="foreverdb").map(origin=>origin.current_build || origin.build).filter(Boolean)).size>1 && <p className="notice">Retained ForeverDB fields span different client builds. Check field provenance before treating them as current.</p>}
      <ProfileCredits profile={profile}/>
      <details className="item-technical">
        <summary>Technical details</summary>
        <p className="small muted">{profile.variant_notice}</p>
        {profile.source && <p className="small">{profile.source.provider} · {profile.source.namespace || profile.source.build} · {profile.source.confidence.replaceAll("_", " ")}<br/>Metadata retrieved: {when(profile.source.observed_at)}</p>}
        {profile.catalog && <div className="item-provenance small">
          <strong>Field provenance</strong>
          {Object.entries(profile.catalog.provenance).map(([field, origin]) => <div key={field}>{field.replaceAll("_", " ")} · {origin.provider} · {origin.confidence.replaceAll("_", " ")}{origin.build ? ` · ${origin.build}` : ""}{origin.retrieved_at && <span> · Retrieved {when(origin.retrieved_at)}</span>}</div>)}
          {profile.catalog.conflicts.length > 0 && <p>Conflicting provider fields retained for review. Higher-confidence fields are shown.</p>}
        </div>}
      </details>
    </>
  );
}
// Deduplicate only identical credits; retain every supplied license and notice.
function ProfileCredits({profile}:{profile:ItemProfile}) {
  const credits = [...(profile.metadata_attributions || []), profile.metadata_attribution, profile.icon_attribution,
    profile.source?.attribution, profile.icon_source?.attribution,
    ...Object.values(profile.catalog?.provenance || {}).map(origin=>origin.attribution)].filter(Boolean) as {text:string;url:string;notice?:string;license?:string}[];
  const unique = [...new Map(credits.map(credit=>[JSON.stringify([credit.text,credit.url,credit.notice,credit.license]),credit])).values()];
  return <div className="item-credits small">{unique.map((credit,index)=><div key={index}><a href={credit.url} target="_blank" rel="noopener noreferrer">{credit.text}</a>{credit.license && !credit.text.includes(credit.license) && <span> · {credit.license}</span>}{credit.notice && <span> · {credit.notice}</span>}</div>)}</div>;
}
export function ItemAttribution({ item }: { item: ItemIdentity }) {
  const credits = item.metadata_attributions?.length ? item.metadata_attributions : [item.metadata_attribution || item.icon_attribution].filter(Boolean);
  return <>{credits.map((source, index) => source && <a key={index} className="item-credit small" href={source.url} target="_blank" rel="noopener noreferrer">{source.text}</a>)}</>;
}
const itemInfoSheet = "(max-width: 700px), (pointer: coarse) and (max-width: 900px)";
function subscribeToSheetLayout(callback: () => void) {
  const query = matchMedia(itemInfoSheet);
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

export function ItemInfo({
  item,
  market,
  prices,
  label = false,
  ranges,
  eager = false,
}: {
  item: ItemIdentity;
  market: number;
  label?: boolean;
  eager?: boolean;
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
  const sheet = useSyncExternalStore(subscribeToSheetLayout, () => matchMedia(itemInfoSheet).matches, () => false);
  const title = useRef<HTMLHeadingElement>(null);
  const titleId = useId();
  const cache = useQueryClient();
  const profile = useQuery({
    queryKey: ["private", "item-profile", market, item.item_id],
    enabled: open || eager,
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
  const triggerLabel = `Item details for ${displayItem.name}`;
  const triggerContent = <>
    <ItemIcon item={displayItem}/>
    {label && <span className="item-trigger-label"><ItemName name={displayItem.name} quality={displayItem.quality}/></span>}
  </>;
  const content = <>
    {profile.data ? <ItemFacts profile={profile.data}/> : profile.error
      ? <p role="alert">Item facts could not be loaded. <button onClick={() => profile.refetch()}>Retry item facts</button></p>
      : <Loading label="Loading item facts…"/>}
    {ranges && <section className="tooltip-market" aria-label="Variant market ranges">
      <strong>Asking prices across variants</strong>
      <div>Recent range <Currency value={ranges.recent_price.minimum}/> – <Currency value={ranges.recent_price.maximum}/></div>
      <div>14-day reference range <Currency value={ranges.market_value.minimum}/> – <Currency value={ranges.market_value.maximum}/></div>
    </section>}
    {prices && <section className="tooltip-market" aria-label="Market estimates">
      <strong>Asking prices and supply</strong>
      {prices.recent_price !== undefined && <div>Recent <Currency value={prices.recent_price}/></div>}
      {prices.market_value !== undefined && <div>14-day reference <Currency value={prices.market_value}/></div>}
      {prices.supply !== undefined && <div>Supply {prices.supply.toLocaleString()} units</div>}
    </section>}
  </>;
  if (sheet) return <Dialog.Root open={open} onOpenChange={setOpen}>
    <Dialog.Trigger className="item-info-trigger" aria-label={triggerLabel}>{triggerContent}</Dialog.Trigger>
    <Dialog.Portal>
      <Dialog.Backdrop className="item-sheet-backdrop"/>
      <Dialog.Popup className="item-sheet" initialFocus={title} aria-labelledby={titleId}>
        <div className="item-sheet-heading">
          <Dialog.Title id={titleId} ref={title} tabIndex={-1}>{displayItem.name} item details</Dialog.Title>
          <Dialog.Close className="secondary" aria-label="Close item details">Close</Dialog.Close>
        </div>
        <div className="item-sheet-content">{content}</div>
      </Dialog.Popup>
    </Dialog.Portal>
  </Dialog.Root>;
  return <Popover.Root open={open} onOpenChange={setOpen}>
    <Popover.Trigger className="item-info-trigger" aria-label={triggerLabel} openOnHover delay={180} closeDelay={160}>
      {triggerContent}
    </Popover.Trigger>
    <Popover.Portal>
      <Popover.Positioner side="right" sideOffset={10} className="item-popover-positioner">
        <Popover.Popup className="wow-tooltip" initialFocus={false} onClick={(event) => event.stopPropagation()}>
          <Popover.Title className="sr-only">{item.name} item details</Popover.Title>
          {content}
          <Popover.Close className="text-button">Close item details</Popover.Close>
        </Popover.Popup>
      </Popover.Positioner>
    </Popover.Portal>
  </Popover.Root>;
}
