import { useSyncExternalStore } from 'react';
const query='(max-width: 700px)';
function subscribe(callback:()=>void){const media=matchMedia(query);media.addEventListener('change',callback);return()=>media.removeEventListener('change',callback);}
export function useCompactLayout(){return useSyncExternalStore(subscribe,()=>matchMedia(query).matches,()=>false);}

const marketTouchQuery = '(max-width: 700px), (pointer: coarse) and (max-width: 900px)';
function subscribeMarketTouch(callback: () => void) {
  const media = matchMedia(marketTouchQuery);
  media.addEventListener('change', callback);
  return () => media.removeEventListener('change', callback);
}
export function useMarketTouchLayout() {
  return useSyncExternalStore(subscribeMarketTouch, () => matchMedia(marketTouchQuery).matches, () => false);
}
