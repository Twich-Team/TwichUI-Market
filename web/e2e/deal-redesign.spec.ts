import { expect, test, type Page } from "@playwright/test";
import { defaultPreferences } from "../src/preferences-store";

const variant = "a".repeat(64);
const reference = { state: "needs_review", reason: "Daily unit asks vary by at least 100×. Check the price history before using this average." };
const market = { id: 1, label: "Fixture market", region: "us", ruleset_id: 2, house_id: 114, source_kind: "auctions",
  enabled: true, verified: true, freshness: "current", last_modified: new Date().toUTCString(),
  last_success: new Date().toISOString(), interval_seconds: 300, failures: 0, last_error: null };
const deal = { item_id: 117, name: "Tough Jerky", variant: {id:117}, variant_key: variant, name_verified: true,
  auction_id:"101", quantity: 3, total_buyout: "10", current_supply: 57, market_value: "373157356",
  discount_percent: 99.99, reference_quality: reference, confidence:"strong", coverage_days:7, matching_listings:2 };
const common = { market, history_coverage:{observed_days:8,required_days:3,status:"available",basis:"prior_utc_days"},
  snapshot_id:"1", synthetic:true, candidates_truncated:false };

async function fixture(page:Page) {
  let prefs = defaultPreferences(), revision=1, failed=false;
  let hold: Promise<void> | undefined;
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url()), path=url.pathname;
    const reply = (payload:unknown) => route.fulfill({json:payload});
    if(path.endsWith("/auth/session")) return reply({user:{id:1,username:"fixture",role:"member"},csrf_token:"test"});
    if(path.endsWith("/me/preferences")) {
      if(route.request().method()==="PATCH") {prefs={...prefs,...route.request().postDataJSON().changes};revision++;}
      return reply({schema_version:1,user_id:1,values:prefs,revision,effective_market_id:1,market_fallback:false,updated_at:null});
    }
    if(path.endsWith("/environment")) return reply({read_only:true});
    if(path.endsWith("/markets")) return reply({markets:[market]});
    if(path.endsWith("/deals")) {
      if (hold) await hold;
      if (failed) return route.fulfill({status:503,json:{detail:"Fixture service temporarily unavailable."}});
      if(url.searchParams.get("minimum_coverage")==="12") return reply({...common,deals:[]});
      if(url.searchParams.has("item_id")) return reply({...common,deals:[deal,{...deal,auction_id:"102",quantity:7,total_buyout:"28"}]});
      if(url.searchParams.get("offset")==="20") return reply({...common,deals:[{...deal,name:"Second-page item",item_id:501}]});
      return reply({...common,deals:[deal],candidates_truncated:true});
    }
    if(path.endsWith("/signals")) {
      const kind=url.searchParams.get("kind");
      return reply({...common,signals:[{...deal,kind,current_price:"3",reference_price:"373157356",
        current_supply:57,reference_supply:100,observed_market_days:7,change_percent:kind==="price"?-99.99:-43,
        reference_quality:kind==="price"?reference:null}]});
    }
    return reply({});
  });
  return {prefs:()=>prefs,fail:(value:boolean)=>{failed=value;},delay:(gate:Promise<void>)=>{hold=gate;}};
}

test.use({viewport:{width:375,height:667},hasTouch:true,isMobile:true});

test("phone groups exact variant stacks, qualifies extreme references, saves all modes and pages",async({page})=>{
  const mock=await fixture(page);
  await page.goto("/deals");
  const card=page.locator("article.deal");
  await expect(card).toHaveCount(1);
  await expect(card).toContainText("Reference needs review");
  await expect(card).not.toContainText("%");
  await expect(card).toContainText("57 units");
  await expect(card).toContainText("1/3 copper");
  await expect(page.getByRole("button",{name:/^Filters/})).toHaveAttribute("aria-expanded","false");
  await expect(card.getByRole("link",{name:"Inspect item ↗"})).toHaveAttribute("href",`/markets/1/items/117?variant=${variant}`);
  await card.getByRole("button",{name:"Show 2 matching listings"}).tap();
  const table = page.getByRole("table",{name:"Matching listings",exact:true});
  await expect(table.locator("tbody tr")).toHaveCount(2);
  await expect(table.getByRole("img",{name:"0 gold, 0 silver, 28 copper"})).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.getByRole("button",{name:"Next",exact:true}).tap();
  await expect(card).toContainText("Second-page item");
  await expect(page).toHaveURL(/page=1/);
  await page.reload();
  await expect(card).toContainText("Second-page item");
  await page.getByRole("tab",{name:"Supply changes"}).tap();
  await expect(card).toContainText("Prior average supply");
  await expect(card).toContainText("-43%");
  await expect.poll(()=>mock.prefs().deal_mode).toBe("supply");
  await page.getByRole("button",{name:/^Filters/}).tap();
  await page.getByLabel("Minimum change (%)").fill("30");
  await page.getByRole("combobox",{name:"Direction",exact:true}).selectOption("decrease");
  await page.getByRole("button",{name:"Apply filters"}).tap();
  await expect(page).toHaveURL(/change=30/);
  await expect.poll(()=>mock.prefs().deal_direction).toBe("decrease");
  await page.getByRole("tab",{name:"Price changes"}).tap();
  await expect(card).toContainText("Reference needs review");
  await expect(card).not.toContainText("%");
  await expect.poll(()=>mock.prefs().deal_mode).toBe("price");
  await page.goto("/deals");
  await expect(page.getByRole("tab",{name:"Price changes"})).toHaveAttribute("aria-selected","true");
  await expect(page.getByRole("button",{name:/^Filters/})).toContainText("30% minimum");
});

test("loading, retry and no-match states keep the chosen filters",async({page})=>{
  const mock=await fixture(page);
  mock.fail(true);
  let release!:()=>void;
  mock.delay(new Promise<void>(resolve=>{release=resolve;}));
  const pending=page.waitForRequest(r=>r.url().includes("/deals?"));
  await page.goto("/deals");
  await pending;
  await expect(page.getByText("Loading opportunities…",{exact:true})).toBeVisible();
  await expect(page.getByText("0 opportunities",{exact:true})).toHaveCount(0);
  release();
  await expect(page.getByRole("heading",{name:"Deal Finder",exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"Retry results"})).toBeVisible();
  mock.fail(false);
  await page.getByRole("button",{name:"Retry results"}).tap();
  await expect(page.locator("article.deal")).toHaveCount(1);
  await page.getByRole("button",{name:/^Filters/}).tap();
  await page.getByLabel("Minimum observed days").fill("12");
  await page.getByRole("button",{name:"Apply filters"}).tap();
  await expect(page.getByText("No listings match these filters.",{exact:false})).toBeVisible();
  await expect.poll(()=>mock.prefs().deal_coverage).toBe(12);
});
