import { useMemo, useState } from 'react';
import { DeferredChart } from './deferred-chart';
import { growthView, type StorageSample } from './storage-growth-data';
import { formatBytes } from './size';
import { LocalTime } from './admin-table';
export function DatabaseGrowth({samples,current}:{samples:StorageSample[];current:number|null}) {
  const [range,setRange]=useState('all');
  const all=useMemo(()=>growthView(samples),[samples]);
  const view=useMemo(()=>growthView(samples,range==='all'?null:Number(range)),[samples,range]);
  const option=useMemo(()=>({animation:false,grid:{left:85,right:25,top:30,bottom:65},
    textStyle:{color:'#c1b296'},xAxis:{type:'time',axisLabel:{formatter:(value:number)=>new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric'})}},
    yAxis:{type:'value',scale:true,axisLabel:{formatter:(value:number)=>formatBytes(value,2)},splitLine:{lineStyle:{color:'#4a3926'}}},
    tooltip:{trigger:'axis',renderMode:'richText',formatter:(params:unknown)=>{const p=(params as {value:[number,number|null]}[])[0]?.value;return p ? `${new Date(p[0]).toLocaleString()}\n${formatBytes(p[1])}` : '';}},
    series:[{type:'line',name:'Database allocation',data:view.points,connectNulls:false,showSymbol:false,symbolSize:5,lineStyle:{color:'#d9b365',width:2},areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:'#c49b493e'},{offset:1,color:'#c49b4903'}]}},itemStyle:{color:'#d9b365'}}],
  }),[view]);
  return <section className="panel padded database-growth" aria-labelledby="database-growth-heading">
    <div className="panel-heading"><h3 id="database-growth-heading">Database Growth</h3><label>Measurement range<select value={range} onChange={e=>setRange(e.target.value)}><option value="all">All available ({all.availableDays.toFixed(1)} days)</option>{[[1,'24 hours'],[7,'7 days'],[30,'30 days'],[90,'90 days']].filter(([days])=>Number(days)<=all.availableDays).map(([days,label])=><option key={days} value={days}>{label}</option>)}</select></label></div>
    <div className="metadata-stats">
      <div><span>Current allocation</span><strong>{formatBytes(current)}</strong></div>
      <div><span>Selected period change</span><strong>{view.delta===null?'Needs two samples':`${view.delta>0?'+':''}${formatBytes(view.delta)}`}</strong></div>
      <div><span>Approximate daily change</span><strong>{view.bytesPerDay===null?'Needs 24 hours':`${view.bytesPerDay>0?'+':''}${formatBytes(view.bytesPerDay)}`}</strong></div>
    </div>
    {view.rows.length ? <><p className="small muted">{view.rows.length} actual hourly measurements · {view.gaps} measurement gaps</p><DeferredChart option={option} label="Database allocated size over time; gaps have no measurements"/></> : <p>No recorded storage measurements yet.</p>}
    <details className="growth-measurement-note"><summary className="small muted">About these measurements</summary><p className="small muted">PostgreSQL allocation includes reusable space. Logical deletions do not immediately shrink filesystem allocation. Gaps are not filled. Hourly samples are retained for 90 days.</p><p className="small muted">Measured <LocalTime value={view.rows[0]?.sampled_at}/> through <LocalTime value={view.rows.at(-1)?.sampled_at}/></p></details>
  </section>;
}
