import { api, ApiError } from './api';

export type ItemColumn = 'recent_price' | 'market_value' | 'supply' | 'listing_count' | 'item_id';
export type ItemSort = { id: ItemColumn | 'name'; desc: boolean };
export type DealMode = 'listings' | 'supply' | 'price';
export interface Preferences {
  market_id: number | null;
  explorer_days: 7 | 14 | 60 | 365 | 3650;
  item_page_size: 25 | 50 | 100;
  item_columns: Record<ItemColumn, boolean>;
  item_sort: ItemSort;
  deal_mode: DealMode;
  deal_change: number;
  deal_spend_gold: number;
  deal_coverage: number;
  deal_confidence: 'limited' | 'moderate' | 'strong';
  deal_direction: 'any' | 'increase' | 'decrease';
}
export type PreferenceChanges = Omit<Partial<Preferences>, 'item_columns'> & {
  item_columns?: Partial<Preferences['item_columns']>;
};
export interface PreferenceResource {
  schema_version: 1;
  user_id: number;
  revision: number;
  values: Preferences;
  effective_market_id: number | null;
  market_fallback: boolean;
  updated_at: string | null;
}
export function defaultPreferences(): Preferences {
  return {market_id:null, explorer_days:14, item_page_size:25,
    item_columns:{recent_price:true,market_value:true,supply:true,listing_count:true,item_id:true},
    item_sort:{id:'item_id',desc:false},deal_mode:'listings',deal_change:15,
    deal_spend_gold:500,deal_coverage:3,deal_confidence:'limited',deal_direction:'any'};
}
export function preferredMarket(markets: {id:number;enabled:boolean}[], saved: number | null) {
  return markets.find(m=>m.id===saved)?.id ?? markets.find(m=>m.enabled)?.id ?? markets[0]?.id ?? 0;
}

type Transport = (path:string,method?:string,body?:unknown,signal?:AbortSignal)=>Promise<PreferenceResource>;
type Dirty = {value:unknown; sequence:number};
export interface PreferenceSnapshot {
  ready:boolean;
  values:Preferences;
  status:'loading'|'saved'|'saving'|'offline'|'error';
  error:string;
}

// One queue per mounted account. Only explicit user edits become dirty; restoring/fallback never saves.
export class PreferenceStore {
  private base:PreferenceResource | null = null;
  private dirty=new Map<string,Dirty>();
  private sequence=0;
  private resetQueued=0;
  private active=true;
  private timer:ReturnType<typeof setTimeout> | undefined;
  private running:Promise<boolean> | undefined;
  private abort=new AbortController();
  private listeners=new Set<()=>void>();
  epoch=0;
  private snapshot:PreferenceSnapshot={ready:false,values:defaultPreferences(),status:'loading',error:''};
  constructor(private transport:Transport=(...args)=>api<PreferenceResource>(...args),
    private cache:(resource:PreferenceResource)=>void=()=>{}, private userId?:number) {}
  getSnapshot=()=>this.snapshot;
  subscribe=(listener:()=>void)=>{this.listeners.add(listener);return()=>{this.listeners.delete(listener);};};
  start() { if(!this.active){this.active=true;this.abort=new AbortController();} }
  dispose() {
    this.active=false;this.epoch++;this.abort.abort();clearTimeout(this.timer);
    this.dirty.clear();this.resetQueued=0;this.base=null;this.running=undefined;
    this.snapshot={ready:false,values:defaultPreferences(),status:'loading',error:''};
  }
  private emit(status:PreferenceSnapshot['status'],error='') {
    if(!this.active)return;
    const values=this.resetQueued?defaultPreferences():structuredClone(this.base?.values??defaultPreferences());
    for(const [key,change] of this.dirty) {
      if(key.startsWith('item_columns.')) values.item_columns[key.slice(13) as ItemColumn]=change.value as boolean;
      else Object.assign(values,{[key]:change.value});
    }
    this.snapshot={ready:!!this.base,values,status,error};
    if(this.base)this.cache({...this.base,values});
    this.listeners.forEach(fn=>fn());
  }
  receive(resource:PreferenceResource,epoch=this.epoch) {
    if(!this.active||epoch!==this.epoch)return;
    if(this.userId!==undefined&&resource.user_id!==this.userId) {
      if(typeof window!=='undefined')window.dispatchEvent(new Event('market-auth-expired'));
      throw new ApiError(401,'Your account changed. Sign in again.');
    }
    if(resource.schema_version!==1)throw new Error('Your preferences require a newer website.');
    if(!this.base||resource.revision>=this.base.revision)this.base=resource;
    const pending=this.dirty.size||this.resetQueued;
    const keepError=pending&&(this.snapshot.status==='offline'||this.snapshot.status==='error');
    this.emit(pending?(keepError?this.snapshot.status:'saving'):'saved',keepError?this.snapshot.error:'');
  }
  private async request(path:string,method='GET',body?:unknown,signal?:AbortSignal) {
    const controller=new AbortController();
    const abort=()=>controller.abort();
    const parents=[this.abort.signal,...(signal?[signal]:[])];
    parents.forEach(parent=>{if(parent.aborted)abort();else parent.addEventListener('abort',abort,{once:true});});
    const timer=setTimeout(abort,10000);
    try {return await this.transport(path,method,body,controller.signal);}
    finally {clearTimeout(timer);parents.forEach(parent=>parent.removeEventListener('abort',abort));}
  }
  async load(signal?:AbortSignal) {
    const epoch=this.epoch;
    const result=await this.request('/me/preferences','GET',undefined,signal);
    this.receive(result,epoch);
    return this.base?{...this.base,values:this.snapshot.values}:result;
  }
  update=(changes:PreferenceChanges)=>{
    if(!this.active||!this.base)return;
    for(const [key,value] of Object.entries(changes)) {
      if(key==='item_columns') {
        for(const [column,visible] of Object.entries(value as object))
          this.dirty.set('item_columns.'+column,{value:visible,sequence:++this.sequence});
      } else this.dirty.set(key,{value,sequence:++this.sequence});
    }
    this.emit('saving');this.schedule(250);
  };
  reset=()=>{
    if(!this.active||!this.base)return;
    this.dirty.clear();this.resetQueued=++this.sequence;
    this.emit('saving');this.schedule(0);
  };
  private schedule(delay:number) {
    clearTimeout(this.timer);
    this.timer=setTimeout(()=>{void this.flush();},delay);
  }
  flush=():Promise<boolean>=>{
    clearTimeout(this.timer);
    if(this.running)return this.running;
    if(!this.active||!this.base)return Promise.resolve(false);
    const epoch=this.epoch;
    const running=this.save(epoch).finally(()=>{
      if(this.running===running)this.running=undefined;
      if(this.active&&epoch===this.epoch&&this.snapshot.status!=='error'&&(this.dirty.size||this.resetQueued))this.schedule(3000);
    });
    this.running=running;
    return running;
  };
  private async save(epoch:number) {
    let conflicts=0;
    while(this.active&&epoch===this.epoch&&this.base&&(this.dirty.size||this.resetQueued)) {
      const reset=this.resetQueued;
      const sent=new Map(this.dirty);
      const changes:Record<string,unknown>={};
      for(const [key,change] of sent) {
        if(key.startsWith('item_columns.')) {
          changes.item_columns??={};
          Object.assign(changes.item_columns as object,{[key.slice(13)]:change.value});
        } else changes[key]=change.value;
      }
      this.emit('saving');
      try {
        const result=await this.request('/me/preferences'+(reset?'/reset':''),reset?'POST':'PATCH',
          {schema_version:1,expected_revision:this.base.revision,...(reset?{}:{changes})},this.abort.signal);
        if(!this.active||epoch!==this.epoch)return false;
        if(reset) {
          // A newer reset must still run; choices made after this reset stay dirty.
          if(this.resetQueued===reset)this.resetQueued=0;
        } else for(const [key,change] of sent) {
          if(this.dirty.get(key)?.sequence===change.sequence)this.dirty.delete(key);
        }
        this.receive(result,epoch);
      } catch(error) {
        if(!this.active||epoch!==this.epoch)return false;
        if(error instanceof ApiError&&error.status===409&&conflicts++<4) {
          try { this.receive(await this.request('/me/preferences','GET'),epoch); }
          catch { this.emit('offline','Your choices are kept here. We’ll retry when connected.');return false; }
          continue;
        }
        const permanent=error instanceof ApiError&&[401,403,422].includes(error.status);
        this.emit(permanent?'error':'offline',permanent?'Preferences could not be saved. Retry or reset your choices.':'Your choices are kept here. We’ll retry when connected.');
        return false;
      }
    }
    if(this.active&&epoch===this.epoch)this.emit('saved');
    return true;
  }
}
