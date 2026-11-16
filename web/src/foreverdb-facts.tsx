import { Currency } from './currency';

interface Origin { build?: string; retrieved_at?: string; resource?: string }
interface Recipe {
  spellId: number; name: string; requiredLevel?: number | null; speculation?: boolean;
  skill?: {orange?: number;yellow?: number;green?: number;grey?: number;orangeSource?: string;orangeClassic?: number};
  makes?: {itemId:number;name:string;count?:number;min?:number;max?:number} | null;
  reagents: {itemId:number;name:string;count:number}[];
  learnedFrom?: {automatic?:boolean; trainer?:string|null; known?:boolean; sources?: Record<string, unknown>};
  newInForever?: boolean; changedFromClassic?: unknown[];
}
export interface RichFacts {
  stats?: {stat_id:number;label:string;value:number}[];
  weapon?: {damage?: {min:string;max:string;school:string};speed_seconds?:string};
  effects?: {spell_id:number;trigger:string;text:string}[];
  unique?: boolean; disenchantable?: boolean;
  disenchant?: {source:string;skill?:number|null;results?:{itemId:number;name:string;chancePercent?:number;min?:number;max?:number}[]; [key:string]:unknown};
  availability?: {betaEvent?:boolean;speculation?:boolean;speculationReasons?:string[];dataFromBuild?:string;liveClient?:unknown};
  crafting?: {profession:string;profession_name:string;recipe:Recipe;source:Origin}[];
  vendors?: {vendor:{id:number;name:string;zone?:string;source?:string;seenInForever?:boolean;reputationFaction?:{name:string}};offer:{price?:number;price_copper?:string;stack?:number;limited?:boolean;limitedStockCount?:number|null;seenInForever?:boolean;costs?:unknown;[key:string]:unknown};source:Origin}[];
  item_sets?: {set:{id:number;name:string;betaEvent?:boolean;speculation?:boolean;speculationReasons?:string[];bonuses?:{pieces:number;text:string;spellId:number}[]};source:Origin}[];
}
function Quantity({value}:{value:{count?:number;min?:number;max?:number}}) {
  return <>{value.count !== undefined ? value.count : value.min !== undefined && value.max !== undefined ? `${value.min}–${value.max}` : 'Unknown quantity'}</>;
}
// Escaped text only. Preserve the provider's nested source distinctions and nulls;
// do not turn arbitrary provider URLs into links or remote markup into HTML.
function SourceDetails({value}:{value:unknown}) {
  if(value===null || value===undefined)return <span>Unknown</span>;
  if(Array.isArray(value))return <ul>{value.map((v,i)=><li key={i}><SourceDetails value={v}/></li>)}</ul>;
  if(typeof value==='object')return <dl>{Object.entries(value).map(([k,v])=><div key={k}><dt>{k.replace(/([A-Z])/g,' $1')}</dt><dd><SourceDetails value={v}/></dd></div>)}</dl>;
  return <span>{typeof value==='boolean' ? value ? 'Yes' : 'No' : String(value)}</span>;
}
export function ForeverDBFacts({facts}:{facts:RichFacts}) {
 const availability=facts.availability;
 return <>
  {availability?.betaEvent && <p className="notice">Historical beta-event item · not a normal launch recommendation.</p>}
  {availability?.speculation && <p className="notice">Availability unconfirmed. {availability.speculationReasons?.join(' ')}</p>}
  {availability?.dataFromBuild && <p className="notice">Details retained from build {availability.dataFromBuild}; current-client verification is unavailable.</p>}
  {availability?.liveClient && <details><summary>Live-client changes from beta</summary><SourceDetails value={availability.liveClient}/></details>}
  {facts.unique && <div>Unique</div>}
  {facts.weapon?.damage && <div>{facts.weapon.damage.min}–{facts.weapon.damage.max} {facts.weapon.damage.school} damage</div>}
  {facts.weapon?.speed_seconds !== undefined && <div>Speed {facts.weapon.speed_seconds} seconds</div>}
  {facts.stats?.map((stat,i)=><div className="item-line stat" key={`${stat.stat_id}-${i}`}>{stat.value>0 ? '+' : ''}{stat.value} {stat.label}</div>)}
  {facts.effects?.map((effect,i)=><div className="item-line effect" key={`${effect.spell_id}-${i}`}>{effect.trigger}: {effect.text || 'Effect description unavailable'} <a href={`https://foreverdb.net/spell/${effect.spell_id}`} target="_blank" rel="noopener noreferrer">Spell #{effect.spell_id}</a></div>)}
  {facts.disenchant && <details className="item-related"><summary>Disenchant reference</summary><p className="small muted">{facts.disenchant.source}</p>{facts.disenchant.results?.map((r,i)=><div key={i}>{r.name} (#{r.itemId}) · {r.min!==undefined && r.max!==undefined ? `${r.min}–${r.max}` : 'Unknown quantity'}{r.chancePercent!==undefined ? ` · ${r.chancePercent}% reference chance` : ''}</div>)}<p className="small muted">Reference results are not guaranteed yields. Forever observations and Classic reference data retain their source labels.</p><details><summary>Source observations and qualifiers</summary><SourceDetails value={facts.disenchant}/></details></details>}
  {facts.disenchantable===false && <p className="small muted">Provider marks this item as not disenchantable.</p>}
  {facts.crafting?.length ? <details className="item-related"><summary>Crafting relationships ({facts.crafting.length})</summary>{facts.crafting.map(entry=><section key={`${entry.profession}-${entry.recipe.spellId}`}><strong>{entry.profession_name} · {entry.recipe.name}</strong>{entry.recipe.makes && <p>Creates <Quantity value={entry.recipe.makes}/> × {entry.recipe.makes.name} (#{entry.recipe.makes.itemId})</p>}<p>Reagents: {entry.recipe.reagents.map(r=>`${r.count} × ${r.name} (#${r.itemId})`).join(', ')}</p>{entry.recipe.skill && <p className="small">Skill colors: {Object.entries(entry.recipe.skill).map(([k,v])=>`${k}: ${v}`).join(' · ')}</p>}{entry.recipe.speculation && <p className="notice">Recipe availability unconfirmed.</p>}{entry.recipe.newInForever && <p className="small">New in Forever client data.</p>}<p className="small muted">ForeverDB · build {entry.source.build || 'unknown'} · trainer/vendor/quest/drop evidence remains individually qualified.</p><details><summary>Learning sources and requirements</summary><SourceDetails value={entry.recipe.learnedFrom}/><SourceDetails value={{requiredLevel:entry.recipe.requiredLevel,changedFromClassic:entry.recipe.changedFromClassic}}/></details></section>)}</details> : null}
  {facts.vendors?.length ? <details className="item-related"><summary>Vendor acquisition ({facts.vendors.length})</summary>{facts.vendors.map(entry=><section key={entry.vendor.id}><strong>{entry.vendor.name}</strong><p>{entry.vendor.zone || 'Location unknown'} · {entry.vendor.source || 'Source unknown'}</p><p>Purchase price: {entry.offer.price_copper!==undefined ? <Currency value={entry.offer.price_copper}/> : 'Unknown'} · purchase stack {entry.offer.stack ?? 'unknown'}</p>{entry.offer.limited && <p>Limited stock · count {entry.offer.limitedStockCount ?? 'unknown'}</p>}{entry.vendor.reputationFaction && <p>Reputation discounts: {entry.vendor.reputationFaction.name}</p>}<details><summary>Costs, location and source qualifiers</summary><SourceDetails value={{vendor:entry.vendor,offer:entry.offer}}/></details></section>)}</details> : null}
  {facts.item_sets?.length ? <details className="item-related"><summary>Item sets ({facts.item_sets.length})</summary>{facts.item_sets.map(entry=><section key={entry.set.id}><strong>{entry.set.name}</strong>{(entry.set.betaEvent||entry.set.speculation) && <p className="notice">Set availability unconfirmed / historical beta. {entry.set.speculationReasons?.join(' ')}</p>}{entry.set.bonuses?.map((bonus,i)=><p key={i}>{bonus.pieces} pieces: {bonus.text}</p>)}<p className="small muted">ForeverDB client build {entry.source.build || 'unknown'}</p></section>)}</details> : null}
 </>;
}
