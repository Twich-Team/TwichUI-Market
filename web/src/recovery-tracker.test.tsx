import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { RecoveryProviderStatus, RecoveryEfficiency } from "./recovery-tracker";
describe("Recovery Tracker evidence labels",()=>{
  it("makes provider failure visible without implying item nonexistence",()=>{
    const html=renderToStaticMarkup(<RecoveryProviderStatus value={{status:"missing",checked_at:null,next_at:null,waiting:"waiting_for_refresh"}}/>);
    expect(html).toContain("Missing from provider");expect(html).toContain("Waiting for refresh");expect(html).toContain("✕");expect(html).not.toContain("nonexistent");
  });
  it("qualifies historical evidence and refuses to invent an efficiency percentage",()=>{
    const html=renderToStaticMarkup(<RecoveryEfficiency days={7} setDays={()=>{}} loading={false} data={{days:7,providers:[],metadata_requests:0,useful_requests:0,useful_rate:null,historical_task_records:12,notice:"Historical records are incomplete."}}/>);
    expect(html).toContain("No measured requests");expect(html).toContain("12 historical task records");expect(html).not.toContain("NaN");expect(html).not.toContain("100%");
  });
  it("defines useful recovery against actual requests without adding field counts",()=>{
    const html=renderToStaticMarkup(<RecoveryEfficiency days={1} setDays={()=>{}} loading={false} data={{days:1,providers:[],metadata_requests:4,useful_requests:1,useful_rate:.25,historical_task_records:0,notice:"Crash reservations remain unknown."}}/>);
    expect(html).toContain("25.0% useful recovery rate");expect(html).toContain("1 requests committed");expect(html).toContain("4 actual metadata requests");
  });
});
