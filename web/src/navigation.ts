import { useEffect, useState, useRef, type MouseEvent } from 'react';
import { onPrivateCacheClear } from './query';
import type { ItemSort, Preferences } from './preferences-store';
export const MAX_ID = 2147483647;
export const VARIANT = /^[0-9a-f]{64}$/;
const sorts = ['item_id','name','recent_price','market_value','supply','listing_count'];
export type ItemRoute = {kind:'item'; market:number; item:number; variant?:string; days?:Preferences['explorer_days']; hours?:24|48};
export type Route = ItemRoute | {kind:'explorer'|'deals'|'admin'|'account'|'companion'|'approval'|'missing'; error?:string};
export function supportedId(text: string | null): number | null {
  return text && /^[1-9]\d{0,9}$/.test(text) && Number(text)<=MAX_ID ? Number(text) : null;
}
export function parseRoute(path: string, search=''): Route {
  const fixed:Record<string,Route['kind']>={'/':'explorer','/deals':'deals','/administration':'admin','/account':'account','/companion':'companion','/companion/authorize':'approval'};
  if(fixed[path])return {kind:fixed[path]} as Route;
  const match=/^\/markets\/([^/]+)\/items\/([^/]+)$/.exec(path);
  if(!match)return {kind:'missing',error:'This page could not be found.'};
  const market=supportedId(match[1]),item=supportedId(match[2]),params=new URLSearchParams(search),variant=params.get('variant');
  if(!market||!item||params.getAll('variant').length>1||(variant!==null&&!VARIANT.test(variant)))return {kind:'missing',error:'This item link has an invalid market, item ID or exact variant.'};
  const hours=Number(params.get('hours'));
  const days=Number(params.get('days'));
  return {kind:'item',market,item,...([24,48].includes(hours)&&params.getAll('hours').length===1?{hours:hours as 24|48}:{}),...(variant?{variant}:{}),...([7,14,60,365,3650].includes(days)?{days:days as Preferences['explorer_days']}: {})};
}
export function itemUrl(market:number,item:number,variant?:string):string {
  if(!supportedId(String(market))||!supportedId(String(item))||(variant!==undefined&&!VARIANT.test(variant)))throw new Error('Invalid item identity');
  return `/markets/${market}/items/${item}${variant?`?variant=${variant}`:''}`;
}
export interface ExplorerState {market:number; query:string; sort:ItemSort; pageIndex:number; pageSize:25|50|100}
export function explorerState(search:string,defaults:ExplorerState):ExplorerState {
  const p=new URLSearchParams(search),sort=p.get('sort'),size=Number(p.get('page_size')),page=p.get('page');
  return {market:supportedId(p.get('market'))??defaults.market,query:(p.get('q')??defaults.query).slice(0,64),sort:{id:sort&&sorts.includes(sort)?sort as ItemSort['id']:defaults.sort.id,desc:p.has('direction')?p.get('direction')==='desc':defaults.sort.desc},pageIndex:page&&/^(0|[1-9]\d{0,5})$/.test(page)&&Number(page)<=100000?Number(page):defaults.pageIndex,pageSize:[25,50,100].includes(size)?size as ExplorerState['pageSize']:defaults.pageSize};
}
export function explorerUrl(state:ExplorerState):string {
  const p=new URLSearchParams({market:String(state.market),q:state.query,sort:state.sort.id,direction:state.sort.desc?'desc':'asc',page:String(state.pageIndex),page_size:String(state.pageSize)});
  return '/?'+p;
}
export function canonicalizeExplorerUrl(renderedSearch:string,state:ExplorerState) {
  // A passive effect from the previous page must not undo a newer navigation.
  if(currentLocation()!=='/'+renderedSearch)return;
  const canonical=explorerUrl(state);
  if(currentLocation()!==canonical)navigate(canonical,true);
}
export function safeBrowseUrl(value:unknown):string|null {
  if(typeof value!=='string'||value.length>2048||!value.startsWith('/')||value.startsWith('//')||/[\\\r\n]/.test(value))return null;
  const u=new URL(value,'https://market.invalid');
  if(u.origin!=='https://market.invalid'||!['/','/deals'].includes(u.pathname))return null;
  const allowed=u.pathname==='/'?['market','q','sort','direction','page','page_size']:['market','mode','change','spend','coverage','confidence','direction'];
  const p=new URLSearchParams();for(const k of allowed){const v=u.searchParams.get(k);if(v!==null)p.set(k,v.slice(0,64));}
  return u.pathname+(p.size?'?'+p:'');
}
const event='market-location-change';
export function currentLocation(){return location.pathname+location.search;}
export function useLocation(){const [url,setUrl]=useState(currentLocation);useEffect(()=>{const read=()=>setUrl(currentLocation());window.addEventListener('popstate',read);window.addEventListener(event,read);return()=>{window.removeEventListener('popstate',read);window.removeEventListener(event,read);};},[]);return url;}
interface Restoration {scroll:number; focus?:string; draft?:string; expanded?:Record<number,boolean>; dealDraft?:DealFilters}
// Optional view state is private, bounded and disposable; applied controls live in URLs.
const restorations=new Map<string,Restoration>();
let sequence=0;
onPrivateCacheClear(()=>{restorations.clear();if(typeof history!=='undefined')history.replaceState(null,'');});
function entryKey(){const key=history.state?.marketEntry;if(typeof key==='string')return key;const next=String(++sequence);history.replaceState({...history.state,marketEntry:next},'');return next;}
export function saveRestoration(extra:Partial<Restoration>={}) {
  const key=entryKey(),previous=restorations.get(key);
  const focus=document.activeElement instanceof HTMLElement?document.activeElement.id||previous?.focus:previous?.focus;
  restorations.set(key,{...previous,scroll:window.scrollY,focus,...extra});
  if(restorations.size>50)restorations.delete(restorations.keys().next().value!);
}
export function restoration(){return restorations.get(entryKey());}
export function navigate(url:string,replace=false){
  if(replace)history.replaceState(history.state,'',url);
  else {saveRestoration();const origin=safeBrowseUrl(currentLocation());history.pushState(origin?{marketOrigin:origin}:{},'',url);window.scrollTo(0,0);}
  window.dispatchEvent(new Event(event));
}
export function followItem(event:MouseEvent<HTMLAnchorElement>){
  saveRestoration({focus:event.currentTarget.id||undefined});
  if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
  event.preventDefault();navigate(event.currentTarget.getAttribute('href')!);
}
export function backDestination(market:number){return safeBrowseUrl(history.state?.marketOrigin)??`/?market=${market}`;}
export function returnToBrowse(event:MouseEvent<HTMLAnchorElement>){
  if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
  if(safeBrowseUrl(history.state?.marketOrigin)){event.preventDefault();history.back();}
}
export interface DealFilters {change:number;spend:number;coverage:number;confidence:string;direction:string}
export interface DealState {market:number;mode:'listings'|'supply'|'price';filters:DealFilters}
export function dealState(search:string,defaults:DealState):DealState {
  const p=new URLSearchParams(search),mode=p.get('mode'),selected=['listings','supply','price'].includes(mode??'')?mode as DealState['mode']:defaults.mode;
  const bounded=(key:string,fallback:number,min:number,max:number,integer=false)=>{const raw=p.get(key),n=Number(raw),safeDefault=Math.max(min,Math.min(max,integer?Math.trunc(fallback):fallback));return raw!==null&&raw!==''&&Number.isFinite(n)&&n>=min&&n<=max&&(!integer||Number.isInteger(n))?n:safeDefault;};
  return {market:supportedId(p.get('market'))??defaults.market,mode:selected,filters:{change:bounded('change',defaults.filters.change,1,selected==='listings'?99:1000,true),spend:bounded('spend',defaults.filters.spend,0.01,100000000),coverage:bounded('coverage',defaults.filters.coverage,1,selected==='listings'?15:14,true),confidence:['limited','moderate','strong'].includes(p.get('confidence')??'')?p.get('confidence')!:defaults.filters.confidence,direction:['any','increase','decrease'].includes(p.get('direction')??'')?p.get('direction')!:defaults.filters.direction}};
}
export function dealUrl(state:DealState){return '/deals?'+new URLSearchParams({market:String(state.market),mode:state.mode,...Object.fromEntries(Object.entries(state.filters).map(([k,v])=>[k,String(v)]))});}
export function useRestoreView(ready:boolean,identity:string){
  const restored=useRef<string|null>(null);
  useEffect(()=>{const key=entryKey()+'|'+identity;if(!ready||restored.current===key)return;const saved=restoration();if(!saved)return;const frame=requestAnimationFrame(()=>{if(saved.focus)document.getElementById(saved.focus)?.focus({preventScroll:true});window.scrollTo(0,saved.scroll);restored.current=key;});return()=>cancelAnimationFrame(frame);},[ready,identity]);
}
