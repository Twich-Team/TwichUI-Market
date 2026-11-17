import { useSyncExternalStore } from 'react';
const query='(max-width: 700px)';
function subscribe(callback:()=>void){const media=matchMedia(query);media.addEventListener('change',callback);return()=>media.removeEventListener('change',callback);}
export function useCompactLayout(){return useSyncExternalStore(subscribe,()=>matchMedia(query).matches,()=>false);}
