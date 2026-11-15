import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Attempt, AttemptStatus } from "./metadata-attempts";
import { LocalTime, ProviderEmblem } from "./admin-table";
const attempt={outcome:"no_usable_data",fields_recovered:[],http_status:200} as unknown as Attempt;
describe("plain-language recovery results",()=>{
  it("does not label an HTTP 200 without fields as recovered",()=>{
    const html=renderToStaticMarkup(<AttemptStatus attempt={attempt}/>);
    expect(html).toContain("No usable metadata returned");expect(html).toContain('record-status error');expect(html).not.toContain('success');
  });
  it("lists exact newly recovered fields and a visible check",()=>{
    const html=renderToStaticMarkup(<AttemptStatus attempt={{...attempt,outcome:"name_recovered",fields_recovered:["name","icon_reference"]}}/>);
    expect(html).toContain("Recovered name and icon reference");expect(html).toContain('record-status success');
  });
  it("keeps unknown historical gains qualified",()=>{
    const html=renderToStaticMarkup(<AttemptStatus attempt={{...attempt,outcome:"metadata_returned"}}/>);
    expect(html).toContain("historical gain unrecorded");expect(html).toContain('record-status warning');
  });
  it("provides source text and a tooltip without external logos",()=>{
    const html=renderToStaticMarkup(<ProviderEmblem provider="thewowdb"/>);
    expect(html).toContain("TheWoWDB metadata source");expect(html).toContain('aria-hidden="true"');expect(html).not.toContain('<img');
  });
  it("provides the full original instant on local timestamps",()=>{
    const html=renderToStaticMarkup(<LocalTime value="2026-11-15T03:49:00Z"/>);
    expect(html).toContain('dateTime="2026-11-15T03:49:00Z"');expect(html).toContain('2026-11-15T03:49:00.000Z');
  });
});
