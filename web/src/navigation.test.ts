import {describe,it,expect} from 'vitest';
import {parseRoute,itemUrl,supportedId,explorerState,explorerUrl,safeBrowseUrl} from './navigation';
const variant='a'.repeat(64);
const defaults={market:2,query:'',sort:{id:'item_id' as const,desc:false},pageIndex:0,pageSize:25 as const};
describe('canonical item identities',()=>{
 it('accepts parent and exact routes without guessing names',()=>{expect(parseRoute('/markets/2/items/25')).toEqual({kind:'item',market:2,item:25});expect(parseRoute('/markets/2/items/25','?variant='+variant)).toEqual({kind:'item',market:2,item:25,variant});expect(itemUrl(2,25,variant)).toBe('/markets/2/items/25?variant='+variant);});
 it.each(['0','-1','1.5','NaN','2147483648','01','2e3','cloth','%32'])('rejects unsupported identity %s',id=>{expect(supportedId(id)).toBeNull();expect(parseRoute(`/markets/${id}/items/25`).kind).toBe('missing');expect(parseRoute(`/markets/2/items/${id}`).kind).toBe('missing');});
 it.each(['A'.repeat(64),'a'.repeat(63),'a'.repeat(65),'','../25','<script>'])('rejects malformed variants',key=>{expect(parseRoute('/markets/2/items/25','?variant='+encodeURIComponent(key)).kind).toBe('missing');expect(()=>itemUrl(2,25,key)).toThrow();});
 it('rejects duplicate variants and unknown paths',()=>{expect(parseRoute('/markets/2/items/25','?variant='+variant+'&variant='+variant).kind).toBe('missing');expect(parseRoute('/elsewhere').kind).toBe('missing');expect(parseRoute('/deals').kind).toBe('deals');expect(parseRoute('/companion/authorize').kind).toBe('approval');});
});
describe('restorable browsing URLs',()=>{
 it('round trips search, market, page, sorting and size ahead of preferences',()=>{const value={...defaults,market:7,query:'cloth & silk',sort:{id:'name' as const,desc:true},pageIndex:19,pageSize:100 as const};expect(explorerState(explorerUrl(value).slice(1),defaults)).toEqual(value);});
 it('bounds hostile parameters',()=>{const s=explorerState('?market=-1&page=999999999&page_size=1000&sort=password&q='+('x'.repeat(100)),defaults);expect(s).toMatchObject({market:2,pageIndex:0,pageSize:25,sort:defaults.sort});expect(s.query).toHaveLength(64);});
 it.each(['https://evil.example','//evil.example','/\\evil','/account','/deals\n/evil'])('rejects unsafe origin %s',url=>expect(safeBrowseUrl(url)).toBeNull());
 it('strips credentials and unknown parameters from return links',()=>{expect(safeBrowseUrl('/?market=2&q=cloth&token=secret')).toBe('/?market=2&q=cloth');expect(safeBrowseUrl('/deals?mode=supply&password=secret')).toBe('/deals?mode=supply');});
});
import {dealState,dealUrl,saveRestoration,restoration,navigate} from './navigation';
import {clearPrivateCache,setQueryIdentity} from './query';
import {vi,afterEach} from 'vitest';
const deals={market:2,mode:'listings' as const,filters:{change:15,spend:500,coverage:3,confidence:'limited',direction:'any'}};
describe('Deal Finder state',()=>{
 it('clamps saved defaults when a direct URL changes opportunity mode',()=>{expect(dealState('?mode=listings',{...deals,mode:'supply',filters:{...deals.filters,change:1000,coverage:60}}).filters).toMatchObject({change:99,coverage:15});});
 it('preserves applied filters and exact market through a shared URL',()=>{const value={market:7,mode:'supply' as const,filters:{change:30,spend:123.45,coverage:5,confidence:'moderate',direction:'decrease'}};expect(dealState(dealUrl(value).split('?')[1],deals)).toEqual(value);});
 it('rejects invalid numeric, mode and evidence state',()=>{expect(dealState('?mode=anything&change=NaN&spend=-1&coverage=99&confidence=bad&direction=bad',deals)).toEqual(deals);});
});
describe('private transient restoration',()=>{
 afterEach(()=>{clearPrivateCache();vi.unstubAllGlobals();});
 function browser(){
  const state={state:null as any,replaceState(next:unknown){this.state=next;},pushState(next:unknown){this.state=next;}};
  vi.stubGlobal('history',state);vi.stubGlobal('location',{pathname:'/',search:'?market=2'});vi.stubGlobal('HTMLElement',class{});vi.stubGlobal('document',{activeElement:null});vi.stubGlobal('window',{scrollY:120,scrollTo:vi.fn(),dispatchEvent:vi.fn()});return state;
 }
 it('retains a bounded origin entry and clears optional state on account change',()=>{const history=browser();setQueryIdentity('one:member');saveRestoration({focus:'catalogue-item-25',expanded:{25:true},draft:'cloth'});expect(restoration()).toMatchObject({scroll:120,draft:'cloth',focus:'catalogue-item-25',expanded:{25:true}});navigate(itemUrl(2,25));expect(history.state.marketOrigin).toBe('/?market=2');setQueryIdentity('two:member');expect(restoration()).toBeUndefined();});
 it('clears optional state on logout while retaining the direct URL',()=>{browser();saveRestoration({draft:'cloth'});clearPrivateCache();expect(restoration()).toBeUndefined();expect(location.search).toBe('?market=2');});
});

it('round trips bounded intraday ranges independently of stored daily preferences',()=>{
 expect(parseRoute('/markets/2/items/25','?hours=24')).toMatchObject({kind:'item',hours:24});
 expect(parseRoute('/markets/2/items/25','?hours=48&days=60')).toMatchObject({kind:'item',hours:48,days:60});
 expect(parseRoute('/markets/2/items/25','?hours=9999')).not.toHaveProperty('hours');
});
