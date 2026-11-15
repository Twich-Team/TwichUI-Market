import {test,expect} from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {mkdir} from "node:fs/promises";
test("stored item qualities use game colors in Explorer, details, tooltips and deals",async({page})=>{
  await mkdir("../artifacts/item-quality",{recursive:true});
  await page.goto("/");await page.getByLabel("Username",{exact:true}).fill("owner");await page.getByLabel("Password",{exact:true}).fill("synthetic browser owner password");await page.getByRole("button",{name:"Sign in",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Market Explorer",exact:true})).toBeVisible();
  const search=page.getByLabel("Search items",{exact:true});await search.fill("Synthetic");await page.getByRole("button",{name:"Search",exact:true}).click();
  for(const [name,color] of [["Synthetic Common Item","rgb(255, 255, 255)"],["Synthetic Arcane Crystal","rgb(30, 255, 0)"],["Synthetic Enchanted Blade","rgb(0, 112, 221)"],["Synthetic Epic Item","rgb(163, 53, 238)"]]){
    const button=page.getByRole("button",{name:`Select ${name}`,exact:true});await expect(button.locator('.item-name')).toHaveCSS('color',color);await button.hover();await expect(button.locator('.item-name')).toHaveCSS('color',color);
  }
  await page.screenshot({path:"../artifacts/item-quality/explorer.png",fullPage:true});
  await page.getByRole("button",{name:"Select Synthetic Epic Item",exact:true}).click();await expect(page.getByRole("heading",{name:"Synthetic Epic Item",exact:true}).locator('.item-name')).toHaveCSS('color','rgb(163, 53, 238)');
  await page.getByRole("button",{name:"Item details for Synthetic Epic Item",exact:true}).first().click();await expect(page.getByRole("dialog").locator('.wow-name .item-name')).toHaveCSS('color','rgb(163, 53, 238)');await page.screenshot({path:"../artifacts/item-quality/epic-tooltip.png",fullPage:true});await page.keyboard.press("Escape");
  expect((await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa"]).analyze()).violations).toEqual([]);
  await page.getByRole("button",{name:"Deal Finder",exact:true}).click();const deal=page.locator('.deal').getByRole("button",{name:"Item details for Synthetic Arcane Crystal",exact:true});await expect(deal.locator('.item-name')).toHaveCSS('color','rgb(30, 255, 0)');
  await page.screenshot({path:"../artifacts/item-quality/deals.png",fullPage:true});
});
