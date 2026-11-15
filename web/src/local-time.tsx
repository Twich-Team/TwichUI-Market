export function localTimestamp(value?:string|null):string {
  if(!value || !Number.isFinite(Date.parse(value)))return "Not recorded";
  return new Date(value).toLocaleString(undefined,{year:"numeric",month:"2-digit",day:"2-digit",hour:"numeric",minute:"2-digit",second:"2-digit",timeZoneName:"short"});
}
export function localObservationDate(value:string):string {
  return new Date(value).toLocaleString(undefined,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"});
}
export function LastSeen({value}:{value?:string|null}) {
  if(!value || !Number.isFinite(Date.parse(value)))return <span className="small muted">Last seen unknown</span>;
  const date=new Date(value),label=`${String(date.getMonth()+1).padStart(2,"0")}/${String(date.getDate()).padStart(2,"0")}/${date.getFullYear()}`;
  return <time className="small muted" dateTime={value} title={localTimestamp(value)}>Last seen {label}</time>;
}
