import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir } from "node:fs/promises";
const output="../artifacts/admin-modernization/screenshots";
test.use({timezoneId:"America/Denver"});
test("administration tables support real server pages, readable outcomes, actions and narrow screens",async({page})=>{
  test.setTimeout(60000);
  await mkdir(output,{recursive:true});
  const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));
  await page.goto("/");await page.getByLabel("Username",{exact:true}).fill("owner");await page.getByLabel("Password",{exact:true}).fill("synthetic browser owner password");await page.getByRole("button",{name:"Sign in",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Market Explorer",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Administration",exact:true}).click();
  for(const tab of ["Overview","Members & invitations","Markets & schedules","Collection","Storage & backups","Devices","Security events","Data Sources","Item Metadata"]){
    await page.getByRole("tab",{name:tab,exact:true}).click();
    if(tab==="Members & invitations") {await page.getByRole("combobox",{name:"Filter member role",exact:true}).selectOption("admin");await expect(page.getByRole("table",{name:"members",exact:true}).getByRole("row")).toHaveCount(2);await page.getByRole("combobox",{name:"Filter member role",exact:true}).selectOption("");}
    if(tab==="Storage & backups") await page.getByText("Recent storage measurements",{exact:true}).click();
    await expect(page.locator('.managed-table:visible').first()).toBeVisible();
    await page.screenshot({path:`${output}/${tab.replaceAll(/[^a-zA-Z]/g,"-").toLowerCase()}.png`,fullPage:true});
  }
  const attempts=page.getByRole("table",{name:"provider attempts",exact:true});
  await expect(attempts).toBeVisible();
  await expect(attempts.getByRole("cell",{name:/Recovered name/}).first()).toBeVisible();
  await attempts.locator("..").locator("..").getByRole("combobox",{name:"Rows per page",exact:true}).selectOption("10");
  await attempts.locator("..").locator("..").locator("..").screenshot({path:`${output}/provider-attempts-focused.png`});
  await page.getByRole("button",{name:"Next provider attempts",exact:true}).click();
  await expect(attempts.locator("..").locator("..").getByText(/records · Page 2/)).toBeVisible();
  await page.getByRole("combobox",{name:"Provider",exact:true}).selectOption("everloot");
  await page.getByLabel("Item ID",{exact:true}).fill("20001");
  await expect(attempts.getByRole("row")).toHaveCount(2);
  await page.getByRole("button",{name:/Show details for provider attempts/}).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText("No HTTP response recorded",{exact:false})).toBeVisible();
  await expect(page.getByText("Newly recovered fields",{exact:true})).toBeVisible();
  await page.getByRole("combobox",{name:"Outcome",exact:true}).selectOption("name_recovered");
  await expect(page.getByText("No matching records.",{exact:true})).toBeVisible();
  await page.getByRole("combobox",{name:"Outcome",exact:true}).selectOption("");
  await attempts.getByRole("button",{name:"Item ↕",exact:true}).click();
  await expect(attempts.locator('th[aria-sort="descending"]')).toHaveCount(1);
  await attempts.getByRole("button",{name:"Item ↓",exact:true}).click();
  await expect(attempts.locator('th[aria-sort="ascending"]')).toHaveCount(1);
  await page.getByLabel("Item ID",{exact:true}).fill("");
  const jobs=page.getByRole("table",{name:"recovery jobs",exact:true});
  await jobs.getByRole("button",{name:/Job #/}).first().click();
  await expect(page.getByRole("table",{name:"job results",exact:true})).toBeVisible();
  expect((await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa"]).analyze()).violations).toEqual([]);
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:`${output}/item-metadata-mobile.png`,fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.getByRole("tab",{name:"Security events",exact:true}).click();
  await page.getByLabel("Search account or event").fill("metadata");
  await page.screenshot({path:`${output}/security-mobile.png`,fullPage:true});
  expect(errors).toEqual([]);
});

test("attempt date filters and failed or loading pages stay understandable",async({page})=>{
  await page.goto("/");await page.getByLabel("Username",{exact:true}).fill("owner");await page.getByLabel("Password",{exact:true}).fill("synthetic browser owner password");await page.getByRole("button",{name:"Sign in",exact:true}).click();
  await page.getByRole("button",{name:"Administration",exact:true}).click();await page.getByRole("tab",{name:"Item Metadata",exact:true}).click();
  const attempts=page.getByRole("table",{name:"provider attempts",exact:true}),container=attempts.locator("..").locator("..");
  await expect(attempts.getByRole("row").nth(1)).toBeVisible();
  await page.getByLabel("From (local time)",{exact:true}).fill("2099-01-01T00:00");
  await expect(container.getByText("No matching records.",{exact:true})).toBeVisible();
  await page.getByLabel("From (local time)",{exact:true}).fill("");
  await expect(attempts.getByRole("row").nth(1)).toBeVisible();
  await page.route("**/api/v1/admin/records/metadata-attempts?**",async route=>{await new Promise(resolve=>setTimeout(resolve,500));await route.fulfill({status:503,contentType:"application/json",body:'{"detail":"Provider history is temporarily unavailable"}'});});
  await page.getByLabel("Item ID",{exact:true}).fill("290000");
  await expect(container.getByRole("status",{name:""}).filter({hasText:"Loading provider attempts"})).toBeVisible();
  await expect(container.getByRole("alert")).toContainText("Provider history is temporarily unavailable");
  await page.unroute("**/api/v1/admin/records/metadata-attempts?**");await page.getByLabel("Item ID",{exact:true}).fill("");await expect(attempts.getByRole("row").nth(1)).toBeVisible();
});
