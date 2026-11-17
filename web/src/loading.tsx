import { useEffect, useState } from 'react';
/** No fabricated progress; delay the spinner for short requests while reserving its space. */
export function Loading({label='Loading…',skeleton=false,inline=false}:{label?:string;skeleton?:boolean;inline?:boolean}) {
  const [visible,setVisible]=useState(false);
  useEffect(()=>{const timer=setTimeout(()=>setVisible(true),160);return()=>clearTimeout(timer);},[]);
  return <div className={`loading-state ${inline?'inline':''}`} role="status" aria-live="polite">
    <span className={`loading-spinner ${visible?'visible':''}`} aria-hidden="true"/>
    <span>{label}</span>
    {skeleton&&<div className="loading-skeleton" aria-hidden="true"><span/><span/><span/></div>}
  </div>;
}
