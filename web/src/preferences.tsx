import { createContext, useContext, useEffect, useState, useSyncExternalStore, ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { onPrivateCacheClear, queryClient } from './query';
import { PreferenceStore } from './preferences-store';

const Context=createContext<PreferenceStore|null>(null);
export function PreferencesProvider({userId,children}:{userId:number;children:ReactNode}) {
  const key=['private','preferences',userId];
  const [store]=useState(()=>new PreferenceStore(undefined,resource=>queryClient.setQueryData(key,resource),userId));
  const snapshot=useSyncExternalStore(store.subscribe,store.getSnapshot);
  useEffect(()=>{
    store.start();
    const stop=onPrivateCacheClear(()=>store.dispose());
    const online=()=>{void store.flush();};
    window.addEventListener('online',online);
    return()=>{stop();window.removeEventListener('online',online);store.dispose();};
  },[store]);
  const query=useQuery({queryKey:key,queryFn:({signal})=>store.load(signal),
    refetchInterval:30_000,refetchOnWindowFocus:'always'});
  if(!snapshot.ready)return <section className="empty panel">
    {query.isError?<><p role="alert">Your preferences could not be loaded. Please try again.</p><button onClick={()=>query.refetch()}>Retry preferences</button></>:<p role="status">Restoring your preferences…</p>}
  </section>;
  return <Context.Provider value={store}>{children}</Context.Provider>;
}
export function usePreferences() {
  const store=useContext(Context);
  if(!store)throw new Error('Preferences require an authenticated account');
  return {...useSyncExternalStore(store.subscribe,store.getSnapshot),update:store.update,reset:store.reset,flush:store.flush};
}
export function PreferenceStatus() {
  const {status,error,flush}=usePreferences();
  return <span className="small muted" role="status" aria-live="polite">
    {status==='saved'?'Preferences saved':status==='saving'?'Saving preferences…':error}
    {(status==='offline'||status==='error')&&<button className="text-button" onClick={()=>void flush()}>Retry saving preferences</button>}
  </span>;
}
