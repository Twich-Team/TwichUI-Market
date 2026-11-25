import { LocalTime, Status } from "./admin-table";
import { ExactCurrency } from "./currency";
import { ItemAttribution, ItemIcon } from "./item-components";
import { ItemName } from "./item-name";
import { followItem, itemUrl } from "./navigation";
import {
  rewardSourceLabel, writStatus, type WritCatalogue, type WritItem, type WritMethod, type WritQuote,
  type WritRecipe, type WritRoute, type WritRow,
} from "./crafting-writs-data";

const foreverDb = "https://foreverdb.net";

function itemCredits(item: WritItem) {
  const credits = [...(item.metadata_attributions ?? []), item.metadata_attribution, item.icon_attribution];
  return [...new Map(credits.flatMap(credit => credit ? [[credit.url, credit] as const] : [])).values()];
}

function isForeverDb(url: string) {
  return url === foreverDb || url === foreverDb + "/";
}

export function WritAttribution({ catalogue, items }: { catalogue: WritCatalogue; items: WritItem[] }) {
  const includesForeverDb = items.some(item => itemCredits(item).some(credit => isForeverDb(credit.url)));
  return <small className="waylaid-attribution">
    <a href={catalogue.source_url} target="_blank" rel="noreferrer">{catalogue.source_label ?? "ForeverDB"}</a>
    {catalogue.faction_source_url && <> · Faction data from <a href={catalogue.faction_source_url} target="_blank" rel="noreferrer">ForeverChanges</a></>}
    {catalogue.build && <> · Build {catalogue.build}</>}
    {catalogue.source_observed_at && <> · Source observed <LocalTime value={catalogue.source_observed_at}/></>}
    {includesForeverDb && <> · Item data from <a href={foreverDb} target="_blank" rel="noreferrer">ForeverDB.net</a></>}
  </small>;
}

export function WritItemAttribution({ item }: { item: WritItem }) {
  const credits = itemCredits(item).filter(credit => !isForeverDb(credit.url));
  if (!credits.length) return null;
  return <span className="writ-item-attribution">
    <ItemAttribution item={{ ...item, metadata_attributions: credits }}/>
  </span>;
}

export function WritItemLink({ item, market, id, displayName }: { item: WritItem; market: number; id: string; displayName?: string }) {
  return <div>
    <a className="waylaid-item" href={itemUrl(market, item.item_id, item.variant_key ?? undefined)}
      id={id} aria-label={displayName ? item.name : undefined} title={displayName ? item.name : undefined} onClick={event => { event.stopPropagation(); followItem(event); }}>
      <ItemIcon item={item}/>
      <ItemName name={displayName ?? item.name} quality={item.quality} highContrast/>
    </a>
    <WritItemAttribution item={item}/>
  </div>;
}

export function DeliveryItems({ row, market, context }: { row: WritRow; market: number; context: string }) {
  if (!row.objectives.length) return <span className="muted">Unknown</span>;
  return <ul className="writ-delivery">
    {row.objectives.map(({ item, quantity }, index) => <li key={index}>
      <span className="waylaid-material-quantity">{quantity.toLocaleString()} × </span>
      <WritItemLink item={item} market={market} id={`writ-${row.item.item_id}-${context}-${index}`}/>
    </li>)}
  </ul>;
}

function ReasonList({ reasons }: { reasons: string[] }) {
  if (!reasons.length) return null;
  return <ul className="waylaid-reasons small muted">
    {[...new Set(reasons)].map(reason => <li key={reason}>{writStatus(reason)}</li>)}
  </ul>;
}

function Quote({ quote, market, id }: { quote: WritQuote; market: number; id: string }) {
  return <li className="waylaid-quote writ-quote">
    <div>
      <WritItemLink item={quote.item} market={market} id={id}/>
      <p className="small muted">
        {quote.quantity.toLocaleString()} required
        {quote.purchased_quantity != null && <> · {quote.purchased_quantity.toLocaleString()} bought</>}
        {!!quote.leftover_quantity && <> · {quote.leftover_quantity.toLocaleString()} extra</>}
      </p>
      {!!quote.covered_by_writ_quantity && <p className="small muted">
        {quote.covered_by_writ_quantity.toLocaleString()} from the writ purchase stack
      </p>}
      {!!quote.stacks?.length && <p className="small muted">
        Stacks {quote.stacks.map(stack => `${stack.count.toLocaleString()} × ${stack.quantity.toLocaleString()}`).join(", ")}
      </p>}
    </div>
    <div>
      <p><ExactCurrency exact={quote.unit_price_exact}/> <span className="small muted">/ unit</span></p>
      <p><ExactCurrency exact={quote.subtotal_exact}/> <span className="small muted">valuation</span></p>
      {quote.minimum_purchase_copper != null && <p><ExactCurrency copper={quote.minimum_purchase_copper}/> <span className="small muted">basket cost</span></p>}
    </div>
    <div className="small muted">
      <p>{quoteStatus(quote)}</p>
      {quote.stock_status !== "reference" && quote.available_at_minimum != null && <p>{quote.available_at_minimum.toLocaleString()} available at minimum</p>}
      {quote.coverage_days != null && <p>{quote.coverage_days.toLocaleString()} observed days</p>}
      {quote.quote_status !== "available" && quote.quality_reason && <p>{quote.quality_reason}</p>}
    </div>
  </li>;
}

function quoteStatus(quote: WritQuote) {
  return writStatus(quote.quote_status === "available" && quote.stock_status !== "unknown" ? quote.stock_status : quote.quote_status);
}

function RecipeFacts({ recipe }: { recipe: WritRecipe }) {
  const output = recipe.output_quantity ?? (recipe.output_min != null && recipe.output_max != null
    ? `${recipe.output_min}–${recipe.output_max}` : "unknown");
  return <>
    <p className="small muted">
      Skill {recipe.skill ?? "unknown"} · Output {output} per craft
      {recipe.craft_count != null && <> · {recipe.craft_count.toLocaleString()} {recipe.craft_count === 1 ? "craft" : "crafts"}</>}
    </p>
    {!!recipe.restrictions.length && <ul className="small muted">
      {recipe.restrictions.map(restriction => <li key={restriction}>{restriction}</li>)}
    </ul>}
  </>;
}

const routeNames: Record<WritMethod, string> = { craft: "Craft delivery", buy: "Buy finished items" };

function RouteDetail({ method, route, row, market, current }: {
  method: WritMethod; route: WritRoute; row: WritRow; market: number; current: boolean;
}) {
  const prefix = `writ-${row.item.item_id}-${method}`;
  return <section className="waylaid-bundle">
    <div className="waylaid-detail-heading">
      <h4>{routeNames[method]}</h4>
      <Status tone={row.selected_method === method ? "success" : route.eligible ? "neutral" : "warning"}>
        {row.selected_method === method ? "Selected method" : route.eligible ? "Eligible alternative" : "Unavailable for ranking"}
      </Status>
    </div>
    <ReasonList reasons={route.reasons}/>
    {route.recipes.map(recipe => <div className="writ-recipe" key={`${recipe.item_id}-${recipe.recipe_id}`}>
      <strong>{recipe.name ?? row.objectives.find(objective => objective.item_id === recipe.item_id)?.item.name ?? `Spell #${recipe.recipe_id}`}</strong>
      <RecipeFacts recipe={recipe}/>
    </div>)}
    {!!route.materials.length && <ul className="waylaid-materials">
      {route.materials.map((quote, index) => <Quote quote={quote} market={market} key={index} id={`${prefix}-material-${index}`}/>)}
    </ul>}
    {!!route.basket.length && current && <details className="writ-basket">
      <summary>Combined purchase basket</summary>
      <ul className="waylaid-materials">
        {route.basket.map((quote, index) => <Quote quote={quote} market={market} key={index} id={`${prefix}-basket-${index}`}/>)}
      </ul>
    </details>}
    <p className="waylaid-subtotal">Completion cost <ExactCurrency exact={route.completion_cost_exact}/></p>
    <p className="waylaid-subtotal">Total cost <ExactCurrency exact={route.total_cost_exact}/></p>
    {current && route.total_cost_exact === null && route.valuation_total_cost_exact != null && <p className="waylaid-subtotal">
      Minimum unit valuation <ExactCurrency exact={route.valuation_total_cost_exact}/>
    </p>}
  </section>;
}

export function WritDetails({ row, market, owned, current, confirmed, canConfirm, toggleRecipe }: {
  row: WritRow; market: number; owned: boolean; current: boolean; confirmed: number[];
  canConfirm: boolean; toggleRecipe: (id: number) => void;
}) {
  const selectedRecipes = new Set(row.craft.recipes.map(recipe => recipe.recipe_id));
  const candidates = row.craft.recipe_options.filter(recipe =>
    !selectedRecipes.has(recipe.recipe_id) || confirmed.includes(recipe.recipe_id) || recipe.reasons?.includes("recipe_unconfirmed"));
  return <div className="waylaid-details">
    <div className="waylaid-detail-heading"><h3>Delivery and eligibility</h3>
      {row.quest_id != null && <span className="small muted">Quest #{row.quest_id}</span>}
    </div>
    <DeliveryItems row={row} market={market} context="details"/>
    <dl className="writ-rule-facts">
      <div><dt>Reputation faction</dt><dd>{row.faction?.name ?? "Unknown"}</dd></div>
      <div><dt>Base reward source</dt><dd>{rewardSourceLabel(row.reward_source)}</dd></div>
    </dl>
    {row.restrictions.length > 0
      ? <ul className="waylaid-reasons small muted">{row.restrictions.map(restriction => <li key={restriction}>{restriction}</li>)}</ul>
      : <p className="small muted">Completion limits are unverified.</p>}
    {row.incomplete_reason && <p className="small muted">{writStatus(row.incomplete_reason)}</p>}
    <ReasonList reasons={row.reasons.filter(reason => reason !== row.incomplete_reason)}/>
    <div className="waylaid-bundles">
      <RouteDetail method="craft" route={row.craft} row={row} market={market} current={current}/>
      <RouteDetail method="buy" route={row.buy} row={row} market={market} current={current}/>
    </div>
    {candidates.length > 0 && <section className="waylaid-bundle waylaid-purchase" aria-label="Other recipes and scenario settings">
      <div className="waylaid-detail-heading">
        <h4>Recipes and scenario settings</h4>
      </div>
      {candidates.map(recipe => {
        const checked = confirmed.includes(recipe.recipe_id);
        const name = recipe.name ?? row.objectives.find(objective => objective.item_id === recipe.item_id)?.item.name ?? `Spell #${recipe.recipe_id}`;
        return <div className="writ-recipe" key={`${recipe.item_id}-${recipe.recipe_id}`}>
          <strong>{name}</strong> <small className="muted">Spell #{recipe.recipe_id}</small>
          <RecipeFacts recipe={recipe}/>
          <ReasonList reasons={(recipe.reasons ?? []).filter(reason => reason !== "recipe_unconfirmed")}/>
          {(checked || recipe.reasons?.includes("recipe_unconfirmed")) &&
            <label className="checkbox">
              <input type="checkbox" checked={checked} disabled={!checked && !canConfirm} onChange={() => toggleRecipe(recipe.recipe_id)}/>
              I can use this recipe <span className="sr-only">for {name}, spell {recipe.recipe_id}</span>
            </label>}
        </div>;
      })}
    </section>}
    <section className="waylaid-bundle waylaid-purchase">
      <div className="waylaid-detail-heading">
        <h4>Writ purchase</h4>
        {owned && <span className="small muted">Already owned · excluded from cash cost</span>}
      </div>
      <ul className="waylaid-materials">
        <Quote quote={row.purchase_quote} market={market} id={`writ-${row.item.item_id}-purchase`}/>
      </ul>
    </section>
  </div>;
}
