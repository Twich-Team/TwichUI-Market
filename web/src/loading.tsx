import { useEffect, useState } from 'react';
/** No fabricated progress; delay the spinner for short requests while reserving its space. */
export function Loading({label='Loading…',skeleton=false,inline=false,compact=false}:{label?:string;skeleton?:boolean;inline?:boolean;compact?:boolean}) {
  const [visible,setVisible]=useState(false);
  useEffect(()=>{const timer=setTimeout(()=>setVisible(true),160);return()=>clearTimeout(timer);},[]);
  const Tag=compact?'span':'div';
  return <Tag className={`loading-state ${inline?'inline':''} ${compact?'compact':''}`} role="status" aria-live="polite">
    <span className={`loading-spinner ${visible?'visible':''}`} aria-hidden="true"/>
    <span className={compact?'sr-only':undefined}>{label}</span>
    {skeleton&&!compact&&<div className="loading-skeleton" aria-hidden="true"><span/><span/><span/></div>}
  </Tag>;
}
