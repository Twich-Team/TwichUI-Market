import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from './api';
import { defaultPreferences, PreferenceResource, PreferenceStore, preferredMarket } from './preferences-store';
import { clearPrivateCache, onPrivateCacheClear, queryClient, setQueryIdentity } from './query';

const resource=(revision=0,values={}):PreferenceResource=>({schema_version:1,user_id:1,revision,
  values:{...defaultPreferences(),...values},effective_market_id:null,market_fallback:false,updated_at:null});
function deferred<T>() {let resolve!:(value:T)=>void; const promise=new Promise<T>(r=>{resolve=r;});return {promise,resolve};}
const stores:PreferenceStore[]=[];
function store(...args:ConstructorParameters<typeof PreferenceStore>){const s=new PreferenceStore(...args);stores.push(s);return s;}
afterEach(()=>{stores.forEach(s=>s.dispose());stores.length=0;clearPrivateCache();vi.useRealTimers();});

it('falls back to the collecting market without overwriting an absent or historical choice',()=>{
 const markets=[{id:1,enabled:false},{id:2,enabled:true}];
 expect(preferredMarket(markets,null)).toBe(2);expect(preferredMarket(markets,999)).toBe(2);
 expect(preferredMarket(markets,1)).toBe(1);expect(preferredMarket([],999)).toBe(0);
});
it('coalesces rapid edits, serializes requests, and keeps a newer choice while an old response arrives',async()=>{
 const first=deferred<PreferenceResource>();
 const transport=vi.fn().mockReturnValueOnce(first.promise).mockResolvedValueOnce(resource(2,{market_id:2,explorer_days:365}));
 const s=store(transport);s.receive(resource());
 s.update({market_id:1});s.update({market_id:2,explorer_days:60});
 const pending=s.flush();expect(transport).toHaveBeenCalledTimes(1);
 s.update({explorer_days:365});
 first.resolve(resource(1,{market_id:2,explorer_days:60}));await pending;
 expect(transport).toHaveBeenCalledTimes(2);
 expect(transport.mock.calls[1][2]).toMatchObject({expected_revision:1,changes:{explorer_days:365}});
 expect(s.getSnapshot().values.explorer_days).toBe(365);expect(s.getSnapshot().status).toBe('saved');
});
it('merges dirty fields and individual columns over concurrent changes from another device',async()=>{
 const remote=resource(1,{deal_mode:'supply',item_columns:{...defaultPreferences().item_columns,supply:false}});
 const transport=vi.fn().mockRejectedValueOnce(new ApiError(409,'Conflict')).mockResolvedValueOnce(remote)
  .mockImplementationOnce(async(_path,_method,body)=>resource(2,{...remote.values,...body.changes,item_columns:{...remote.values.item_columns,...body.changes.item_columns}}));
 const s=store(transport);s.receive(resource());s.update({explorer_days:60,item_columns:{listing_count:false}});
 await s.flush();
 expect(transport.mock.calls[2][2]).toEqual({schema_version:1,expected_revision:1,changes:{explorer_days:60,item_columns:{listing_count:false}}});
 expect(s.getSnapshot().values).toMatchObject({deal_mode:'supply',explorer_days:60,item_columns:{supply:false,listing_count:false}});
});
it('ignores stale refetches and keeps local edits over incoming server data',async()=>{
 const s=store(vi.fn().mockResolvedValue(resource(3,{explorer_days:365})));
 s.receive(resource(2,{explorer_days:60}));s.update({explorer_days:365});
 s.receive(resource(1,{explorer_days:7}));expect(s.getSnapshot().values.explorer_days).toBe(365);
 await s.flush();s.receive(resource(2,{explorer_days:60}));expect(s.getSnapshot().values.explorer_days).toBe(365);
});
it('retains pending choices after a network interruption and retries automatically',async()=>{
 vi.useFakeTimers();
 const transport=vi.fn().mockRejectedValueOnce(new TypeError('offline')).mockResolvedValueOnce(resource(1,{item_page_size:100}));
 const s=store(transport);s.receive(resource());s.update({item_page_size:100});await s.flush();
 expect(s.getSnapshot()).toMatchObject({status:'offline',values:{item_page_size:100}});
 await vi.advanceTimersByTimeAsync(3000);
 expect(s.getSnapshot().status).toBe('saved');expect(transport).toHaveBeenCalledTimes(2);
});
it('times out a stalled save, keeps the latest choice and permits a later retry',async()=>{
 vi.useFakeTimers();
 const transport=vi.fn().mockImplementationOnce((_path,_method,_body,signal)=>new Promise((_resolve,reject)=>{
  signal.addEventListener('abort',()=>reject(new Error('aborted')),{once:true});
 })).mockResolvedValueOnce(resource(1,{explorer_days:60}));
 const s=store(transport);s.receive(resource());s.update({explorer_days:60});const pending=s.flush();
 await vi.advanceTimersByTimeAsync(10000);expect(await pending).toBe(false);
 expect(s.getSnapshot()).toMatchObject({status:'offline',values:{explorer_days:60}});
 await vi.advanceTimersByTimeAsync(3000);expect(s.getSnapshot().status).toBe('saved');
});
it('reset waits for an in-flight save, discards prior dirt, and keeps later edits',async()=>{
 const first=deferred<PreferenceResource>();
 const transport=vi.fn().mockReturnValueOnce(first.promise).mockResolvedValueOnce(resource(2))
  .mockResolvedValueOnce(resource(3,{deal_mode:'price'}));
 const s=store(transport);s.receive(resource());s.update({explorer_days:365});const pending=s.flush();
 s.reset();s.update({deal_mode:'price'});expect(s.getSnapshot().values.explorer_days).toBe(14);
 first.resolve(resource(1,{explorer_days:365}));await pending;
 expect(transport.mock.calls[1].slice(0,3)).toEqual(['/me/preferences/reset','POST',{schema_version:1,expected_revision:1}]);
 expect(transport.mock.calls[2][2]).toMatchObject({expected_revision:2,changes:{deal_mode:'price'}});
 expect(s.getSnapshot().values).toMatchObject({explorer_days:14,deal_mode:'price'});
});
it('another reset during an in-flight reset also resets intervening edits',async()=>{
 const first=deferred<PreferenceResource>();
 const transport=vi.fn().mockReturnValueOnce(first.promise).mockResolvedValueOnce(resource(2));
 const s=store(transport);s.receive(resource());s.reset();const pending=s.flush();
 s.update({explorer_days:365});s.reset();first.resolve(resource(1));await pending;
 expect(transport.mock.calls[1][0]).toBe('/me/preferences/reset');expect(s.getSnapshot().values.explorer_days).toBe(14);
});
it('cache clearing cancels the old account queue and stale replies cannot populate a new account',async()=>{
 setQueryIdentity('1:member');const first=deferred<PreferenceResource>();
 const old=store(vi.fn().mockReturnValue(first.promise),r=>queryClient.setQueryData(['private','preferences',1],r));
 old.receive(resource());const stop=onPrivateCacheClear(()=>old.dispose());old.update({market_id:1});const pending=old.flush();
 setQueryIdentity('2:member');stop();
 const next=store(undefined,r=>queryClient.setQueryData(['private','preferences',2],r));next.receive(resource());
 first.resolve(resource(1,{market_id:1}));await pending;
 expect(next.getSnapshot().values.market_id).toBeNull();expect(queryClient.getQueryData(['private','preferences',1])).toBeUndefined();
 expect(old.getSnapshot().ready).toBe(false);
});
it('a disposed Strict Mode generation cannot overwrite the restarted account store',async()=>{
 const first=deferred<PreferenceResource>();const s=store(vi.fn().mockReturnValue(first.promise));const pending=s.load();
 s.dispose();s.start();s.receive(resource(2,{explorer_days:60}));first.resolve(resource(1,{explorer_days:7}));await pending;
 expect(s.getSnapshot().values.explorer_days).toBe(60);
});
it('rejects a different session principal before caching or displaying another user’s values',async()=>{
 const cache=vi.fn();
 const s=store(vi.fn().mockResolvedValue({...resource(9,{market_id:99}),user_id:2}),cache,1);
 s.receive(resource(1,{market_id:1}));cache.mockClear();
 await expect(s.load()).rejects.toThrow('Your account changed');
 expect(cache).not.toHaveBeenCalled();expect(s.getSnapshot().values.market_id).toBe(1);
});
