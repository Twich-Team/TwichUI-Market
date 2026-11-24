import { useMemo } from 'react';
import { DeferredChart } from './deferred-chart';
import { DataTable } from './data-table';
import { ProviderEmblem, providerNames, LocalTime } from './admin-table';
import type { MetadataOverview } from './metadata-admin';
function CoverageBars({label,rows,series}:{label:string;rows:string[];series:{name:string;values:number[];color:string}[]}) {
  const option=useMemo(()=>({animation:false,grid:{left:125,right:25,top:45,bottom:35},legend:{top:0,textStyle:{color:'#c1b296'}},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'},renderMode:'richText'},
    xAxis:{type:'value',min:0,minInterval:1,axisLabel:{color:'#c1b296'},splitLine:{lineStyle:{color:'#4a3926'}}},yAxis:{type:'category',data:rows,axisLabel:{color:'#c1b296'}},
    series:series.map(s=>({name:s.name,type:'bar',stack:'coverage',data:s.values,itemStyle:{color:s.color},barMaxWidth:30})),
  }),[rows,series]);
  return <div className="coverage-chart"><DeferredChart label={label} option={option}/></div>;
}
export function MetadataSummary({state}:{state:MetadataOverview}) {
  const fields = [
    ["Item names", state.resolved_names],
    ["Icons", state.icons_available],
    ["Essential attributes", state.attributes_available],
  ] as const;
  return <section aria-label="Item metadata summary">
    <section className="panel padded">
      <h2>Coverage in the selected market</h2>
      <ul className="admin-health-list">{fields.map(([field, count])=><li key={field}>
        <strong>{field}</strong><span>{state.observed ? `${count.toLocaleString()} / ${state.observed.toLocaleString()} available` : "No item observations"}</span>
      </li>)}</ul>
      <p className="muted">{state.scoped_pending_items.toLocaleString()} items queued or in progress in this market.</p>
      {state.failed_or_blocked > 0 && <p className="notice">{state.failed_or_blocked.toLocaleString()} items remain unnamed after a provider error or access restriction. Review Provider evidence or the Recovery Tracker.</p>}
    </section>
    <details className="panel padded"><summary>Coverage charts and measurement details</summary>
    <p className="muted">Measured <LocalTime value={state.measured_at}/> · {state.coverage_identity} {state.attributes_definition}</p>
    <div className="coverage-grid">
      <section className="panel padded"><h3>Stored field coverage</h3><p className="small muted">Each bar uses the same {state.observed.toLocaleString()} observed IDs. Available plus missing equals that denominator.</p><CoverageBars label="Stored names, icons and attributes; available versus missing" rows={['Names','Icons','Attributes']} series={[
        {name:'Available',values:[state.resolved_names,state.icons_available,state.attributes_available],color:'#d9b365'},
        {name:'Missing / unknown',values:[state.missing_names,state.icons_missing,state.observed-state.attributes_available],color:'#685642'},
      ]}/></section>
      <section className="panel padded"><h3>Name selection</h3><p className="small muted">Selected names count once; retained alternate provider names can overlap.</p><CoverageBars label="Selected Blizzard and supplemental names versus unnamed IDs" rows={['Selected names']} series={[
        {name:'Blizzard',values:[state.primary_names],color:'#83aca1'}, {name:'Supplemental',values:[state.supplemental_names],color:'#d9b365'}, {name:'Unnamed',values:[state.missing_names],color:'#685642'},
      ]}/><p className="small">Blizzard {state.primary_names} · supplemental {state.supplemental_names} · unnamed {state.missing_names}</p></section>
    </div>
    <section className="panel padded"><h3>Recovery evidence</h3>
      <div className="metadata-stats">{[['Unknown / not tried',state.unknown_not_tried],['Tried / unavailable',state.tried_unavailable],['Failed or access blocked',state.failed_or_blocked],['Checked / still unresolved',state.checked_unresolved]].map(([label,count])=><div key={label}><span className="small muted">{label}</span><strong>{count}</strong></div>)}</div>
      <CoverageBars label="Name recovery evidence across observed IDs" rows={['Observed IDs']} series={[
        {name:'Named',values:[state.resolved_names],color:'#83aca1'},{name:'Not tried',values:[state.unknown_not_tried],color:'#685642'},{name:'Unavailable',values:[state.tried_unavailable],color:'#b59a76'},{name:'Failed / blocked',values:[state.failed_or_blocked],color:'#bd8d6b'},{name:'Unresolved',values:[state.checked_unresolved],color:'#b694c3'},
      ]}/>
      <p className="small muted">{state.recovery_notice} Unavailable means an observed 404 without a recorded error; errors include blocked access and rate limits.</p>
      <p className="small">{state.scoped_pending_items} observed items with queued/running tasks · {state.pending_queue} tasks queued across all markets · {state.active_jobs} active jobs · Last enrichment <LocalTime value={state.last_enrichment}/></p>
    </section>
    </details>
  </section>;
}
export function ProviderCoverage({state}:{state:MetadataOverview}) {
  return <section className="panel padded" aria-labelledby="provider-coverage-heading"><h3 id="provider-coverage-heading">Provider metadata coverage</h3>
    <p className="small muted">Retained source records for {state.observed.toLocaleString()} observed IDs in this scope. Sources can overlap: {state.provider_name_overlap} IDs have multiple name sources; {state.conflicting_names} have conflicting names. Source counts must not be added to obtain overall coverage. Missing fields are unknown, not evidence of remote provider capability.</p>
    <div className="metadata-provider-grid">{Object.keys(providerNames).map(provider=>{
      const record=state.provider_records.find(r=>r.provider===provider);
      return <article className="provider-coverage" key={provider} aria-label={`${providerNames[provider]} coverage`}>
        <h4><ProviderEmblem provider={provider}/></h4>
        <dl className="coverage-facts"><div><dt>Retained names</dt><dd>{record?.names_available||0}</dd></div><div><dt>Attribute records</dt><dd>{record?.detailed_records||0}</dd></div><div><dt>Name only</dt><dd>{record?.name_only||0}</dd></div><div><dt>Overlapping names</dt><dd>{record?.overlapping_names||0}</dd></div><div><dt>Conflicting names</dt><dd>{record?.conflicting_names||0}</dd></div></dl>
        <details><summary>Field breakdown</summary><DataTable compact label={`${providerNames[provider]} field coverage`} getRowId={row=>row.field} data={Object.entries(record?.fields_available||{}).map(([field,count])=>({field,available:count,missing:state.observed-count}))} columns={[
          {accessorKey:'field',header:'Field',enableHiding:false,cell:({row})=>row.original.field.replaceAll('_',' ')},
          {accessorKey:'available',header:'Available',meta:{numeric:true}},{accessorKey:'missing',header:'Missing / unknown',meta:{numeric:true}},
        ]}/></details>
        <details><summary>Build &amp; source qualifications</summary><p className="small muted">Stored en_US Forever base-item or related metadata. Attributes may retain earlier field origins; exact field provenance remains available in the item tooltip. A source response build does not verify every retained field against that build.</p>
          {record?.builds?.length ? <ul>{record.builds.map(b=><li key={b.build||'unknown'}>{b.build||'Build not recorded'} · {b.records} source records</li>)}</ul>:<p className="small muted">No stored build evidence for this scope.</p>}
          <p className="small muted">{record?.checked||0} stored source identities, including failed checks. Retained good fields survive failed refreshes. Counts describe stored contributions, not completeness or availability guarantees.</p>
        </details>
      </article>;
    })}</div>
  </section>;
}
