export type StorageView = 'overview'|'backups'|'storage'|'maintenance';
export function storageView(search:string):StorageView {
  const value = new URLSearchParams(search).get('storage_view');
  return ['overview','backups','storage','maintenance'].includes(value||'') ? value as StorageView : 'overview';
}
export function storageUrl(view:StorageView) {
  return '/administration?admin_tab=storage&storage_view='+view;
}
export function isFresh(stamp?:string|null,now=Date.now(),maxAge=180000) {
  const value=Date.parse(stamp||'');return Number.isFinite(value)&&value<=now+60000&&now-value<=maxAge;
}
export function capacityParts(total:number|null|undefined,available:number|null|undefined) {
  if(typeof total!=='number'||typeof available!=='number'||!Number.isFinite(total)||!Number.isFinite(available)||total<=0||available<0||available>total)return null;
  return {total,available,used:total-available,percent:(total-available)/total*100};
}
