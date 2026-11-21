import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ProviderRateLimits, ProviderUsage, type RateStatus } from "./provider-rate-limits";
import type { MetadataProvider } from "./metadata-admin";

const status: RateStatus = {
  configured:{hourly_budget:60,daily_budget:500,minute_budget:30,minimum_interval:3,requests_per_second:null,burst_capacity:null,max_concurrent:1,page_size:null},
  effective:{hourly_budget:60,daily_budget:500,minute_budget:30,minimum_interval:3,requests_per_second:null,burst_capacity:null,max_concurrent:1,page_size:null},
  limit_sources:{minute_budget:"officially_documented",daily_budget:"conservative_application_default"},documented:{minute_budget:30,daily_budget:5000},documentation_url:"https://foreverdb.net/developers",
  windows:{day:{used:20,limit:500,remaining:480,source:"application_estimate"}},provider_reported:null,available_tokens:null,
  next_eligible_at:"2026-11-16T12:01:00Z",cooling_down:false,adaptive_active:false,adaptive_until:null,last_rate_limit:null,last_http_success:null,last_useful_recovery:null,accounting_note:"This application's requests only.",
};
describe("provider rate controls",()=>{
  it("labels estimates and unknown provider quota without inventing a recovery",()=>{
    const html=renderToStaticMarkup(<ProviderUsage status={status}/>);
    expect(html).toContain("application estimate");expect(html).toContain("480 remaining");
    expect(html).toContain("Provider has not reported");expect(html).toContain("Last useful metadata recovery");
  });
  it("separates a captured provider observation and active cooldown from estimates",()=>{
    const html=renderToStaticMarkup(<ProviderUsage status={{...status,cooling_down:true,cooldown_reason:"rate_limited",adaptive_active:true,last_rate_limit:"2026-11-16T12:00:00Z",provider_reported:{remaining:12,limit:null,reset_at:null,observed_at:"2026-11-16T12:00:00Z"}}}/>);
    expect(html).toContain("Provider-reported observation: 12 remaining");
    expect(html).toContain("Rate limit cooldown");expect(html).toContain("Gradual recovery active");
    expect(html).not.toContain("of 2,000");
  });
  it("shows documented ForeverDB presets and keeps advanced safeguards collapsible",()=>{
    const provider={provider:"foreverdb",name:"ForeverDB",rate_limits:status} as MetadataProvider;
    const html=renderToStaticMarkup(<ProviderRateLimits provider={provider} disabled={false} save={()=>{}}/>);
    expect(html).toContain("Requests per minute");expect(html).toContain("Officially documented");
    expect(html).toContain("Documented paid allowance");expect(html).toContain("Advanced limits");
    expect(html).not.toContain("Maximum records per page");expect(html).toContain("Save rate limits");
  });
  it("offers token-bucket controls without representing burst as daily quota",()=>{
    const bucket={...status,configured:{...status.configured,minute_budget:null,requests_per_second:2,burst_capacity:120},documented:{requests_per_second:2,burst_capacity:120}};
    const provider={provider:"thewowdb",name:"TheWoWDB",rate_limits:bucket} as MetadataProvider;
    const html=renderToStaticMarkup(<ProviderRateLimits provider={provider} disabled save={()=>{}}/>);
    expect(html).toContain("Sustained requests per second");expect(html).toContain("Short burst allowance");
    expect(html).toContain("Daily safety budget");expect(html).not.toContain("Documented allowance preset");
    expect(html).toMatch(/disabled=""[^>]*>Save rate limits/);
  });
});
