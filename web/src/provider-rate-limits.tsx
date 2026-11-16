import { useState } from "react";
import { LocalTime } from "./admin-table";
import type { MetadataProvider } from "./metadata-admin";

export interface RateConfiguration {
  hourly_budget: number; daily_budget: number; minute_budget: number | null;
  minimum_interval: number; requests_per_second: number | null;
  burst_capacity: number | null; max_concurrent: number; page_size: number | null;
}
export interface RateStatus {
  configured: RateConfiguration; effective: RateConfiguration;
  limit_sources: Record<string, string>; documented: Partial<RateConfiguration>; documentation_url: string;
  windows: Record<string, { used: number; limit: number; remaining: number; source: string }>;
  provider_reported: { remaining: number | null; limit: number | null; reset_at: string | null; observed_at: string } | null;
  available_tokens: number | null; next_eligible_at: string; cooling_down: boolean; cooldown_reason?: string | null;
  adaptive_active: boolean; adaptive_until: string | null; last_rate_limit: string | null;
  last_http_success: string | null; last_useful_recovery: string | null; accounting_note: string;
}
const sources: Record<string,string> = { officially_documented: "Officially documented", administrator_configured: "Administrator-configured", conservative_application_default: "Conservative application default" };
const numbers = (n: number) => n.toLocaleString();

export function ProviderUsage({ status }: { status: RateStatus }) {
  const reported = status.provider_reported;
  return <div className="provider-usage">
    {status.cooling_down && <p className="notice" role="status">{status.cooldown_reason === "rate_limited" ? "Rate limit cooldown" : "Provider cooldown"} · resumes <LocalTime value={status.next_eligible_at}/></p>}
    {status.adaptive_active && <p className="small">Gradual recovery active · reduced request pace until <LocalTime value={status.adaptive_until}/></p>}
    <dl className="provider-usage-windows">{Object.entries(status.windows).map(([window, usage]) => <div key={window}>
      <dt>Last {window} · application estimate</dt><dd><strong>{numbers(usage.remaining)} remaining</strong> of {numbers(usage.limit)} · {numbers(usage.used)} used</dd>
      <dd><progress aria-label={`${window} request usage`} max={usage.limit} value={Math.min(usage.used, usage.limit)}/></dd>
    </div>)}</dl>
    {reported && <p className="small">Provider-reported observation: {reported.remaining === null ? "remaining unknown" : `${numbers(reported.remaining)} remaining`}{reported.limit === null ? "" : ` of ${numbers(reported.limit)}`} · observed <LocalTime value={reported.observed_at}/>{reported.reset_at && <> · resets <LocalTime value={reported.reset_at}/></>}</p>}
    {!reported && <p className="small muted">Provider has not reported its remaining quota. Estimates cover this application’s requests.</p>}
    <p className="small">Next eligible request: <LocalTime value={status.next_eligible_at}/></p>
    <details><summary>Request history &amp; accounting</summary><dl className="record-details">
      <dt>Last rate limit</dt><dd><LocalTime value={status.last_rate_limit}/></dd>
      <dt>Last successful HTTP call</dt><dd><LocalTime value={status.last_http_success}/></dd>
      <dt>Last useful metadata recovery</dt><dd><LocalTime value={status.last_useful_recovery}/></dd>
      {status.available_tokens !== null && <><dt>Estimated burst allowance available</dt><dd>{status.available_tokens.toFixed(1)}</dd></>}
    </dl><p className="small muted">{status.accounting_note}</p></details>
  </div>;
}

export function ProviderRateLimits({ provider, disabled, save }: { provider: MetadataProvider; disabled: boolean; save: (config: RateConfiguration & { entitlement_acknowledged: boolean }) => void }) {
  const status = provider.rate_limits!;
  const [config, setConfig] = useState(status.configured), [acknowledged, setAcknowledged] = useState(false);
  const ident = provider.provider;
  const beyond = Object.entries(status.documented).some(([key,value]) => config[key as keyof RateConfiguration] !== null && config[key as keyof RateConfiguration]! > value!);
  function field(key: keyof RateConfiguration, label: string, maximum: number, minimum = 1, step = 1) {
    return <label>{label}<input type="number" min={minimum} max={maximum} step={step} required value={config[key] ?? ""} disabled={disabled} onChange={e => setConfig({ ...config, [key]: e.target.value === "" ? null : Number(e.target.value) })}/>
      <span className="small muted">{sources[status.limit_sources[key]] || "Conservative application default"}{status.documented[key] !== undefined && ` · documented ${numbers(status.documented[key]!)}`}</span>
    </label>;
  }
  return <section className="provider-rate-limits" aria-label={`${provider.name} rate limits`}>
    <h4>Rate limits</h4><ProviderUsage status={status}/>
    <form onSubmit={event => { event.preventDefault(); save({ ...config, entitlement_acknowledged: acknowledged }); }}>
      <p className="small muted">Enter the allowance granted to your key. Saved limits are application maximums; provider cooldowns always apply.</p>
      {ident === "foreverdb" && <label>Documented allowance preset<select aria-label="Documented allowance preset" defaultValue="custom" disabled={disabled} onChange={e => {
        if (e.target.value === "free") setConfig({ ...config, minute_budget: 30, hourly_budget: 1800, daily_budget: 5000, minimum_interval: 2 });
        if (e.target.value === "paid") setConfig({ ...config, minute_budget: 60, hourly_budget: 3600, daily_budget: 10000, minimum_interval: 1 });
        setAcknowledged(false);
      }}><option value="custom">Custom / current settings</option><option value="free">Documented free allowance · 30/minute, 5,000/day</option><option value="paid">Documented paid allowance · 60/minute, 10,000/day</option></select></label>}
      <div className="metadata-form-row">
        {ident === "foreverdb" && field("minute_budget", "Requests per minute", 1200)}
        {ident !== "foreverdb" && ident !== "thewowdb" && field("hourly_budget", "Hourly budget", ident === "blizzard" ? 240 : 72000)}
        {ident === "foreverdb" && field("daily_budget", "Daily budget", 1000000)}
        {ident === "thewowdb" && <>{field("requests_per_second", "Sustained requests per second", 2, 0.05, 0.05)}{field("burst_capacity", "Short burst allowance", 120)}</>}
      </div>
      <details><summary>Advanced limits</summary><div className="metadata-form-row">
        {["foreverdb","thewowdb"].includes(ident) && field("hourly_budget", "Hourly safety budget", 72000)}
        {ident !== "foreverdb" && field("daily_budget", "Daily safety budget", ident === "blizzard" ? 2000 : 1000000)}
        {field("minimum_interval", "Minimum interval (seconds)", 86400, ident === "blizzard" ? 15 : 0.05, 0.05)}
        {ident === "everloot" && field("page_size", "Maximum records per page", 5000)}
        <label>Maximum concurrent requests<input type="number" value="1" disabled/><span className="small muted">One shared request at a time keeps recovery and diagnostics safe.</span></label>
      </div></details>
      {ident === "blizzard" && <p className="small muted">These controls cover item metadata. Auction collection retains its separate schedule and safeguards.</p>}
      {beyond && <label className="check provider-entitlement"><input type="checkbox" checked={acknowledged} disabled={disabled} required onChange={e => setAcknowledged(e.target.checked)}/>I confirm that my provider contract grants these higher limits. This setting does not verify my entitlement.</label>}
      <div className="metadata-actions"><button disabled={disabled || (beyond && !acknowledged)}>Save rate limits</button><a href={status.documentation_url} target="_blank" rel="noopener noreferrer">Official limits</a></div>
    </form>
  </section>;
}
