import {test,expect,Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
async function openMarket(page:Page,width:number){
 await page.setViewportSize({width,height:900});await page.goto('/?market=1');
 await page.getByLabel('Username',{exact:true}).fill('commodity_fixture');
 await page.getByLabel('Password',{exact:true}).fill('synthetic commodity browser password');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();
 const response=await page.request.get('/api/v1/markets');expect(response.status()).toBe(200);
 const market=(await response.json()).markets.find((m:{label:string})=>m.label==='Synthetic unified coverage');expect(market).toBeTruthy();
 await page.goto(`/?market=${market.id}`);return market.id as number;
}
for(const width of [390,1440])test(`unified commodities search prices and item details at ${width}px`,async({page})=>{
 const market=await openMarket(page,width);
 for(const [id,name] of [[4306,'Silk Cloth'],[14342,'Mooncloth'],[6657,'Savory Deviate Delight']] as const){
  await page.getByLabel('Search items',{exact:true}).fill(name);await page.getByRole('button',{name:'Search',exact:true}).click();
  await expect(page.getByRole('link',{name:`Research ${name}`,exact:true})).toBeVisible();
  await page.getByLabel('Search items',{exact:true}).fill(String(id));await page.getByRole('button',{name:'Search',exact:true}).click();
  await expect(page.getByRole('link',{name:`Research ${name}`,exact:true})).toBeVisible();
 }
 await page.getByLabel('Search items',{exact:true}).fill('4306');await page.getByRole('button',{name:'Search',exact:true}).click();
 await page.getByRole('link',{name:'Research Silk Cloth',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Silk Cloth',exact:true})).toBeVisible();
 await expect(page.getByLabel('Exact variant current market')).toContainText('30 units');
 const table=page.getByRole('table',{name:'current listings',exact:true});
 await expect(table).toContainText('Unit price');await expect(table).toContainText('Total listing cost');
 await expect(table.getByRole('img',{name:'0 gold, 1 silver, 23 copper',exact:true})).toBeVisible();
 await expect(table.getByRole('img',{name:'0 gold, 24 silver, 60 copper',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'24H',exact:true}).click();
 await expect(page.getByRole('region',{name:'Price history',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBe(width);
 expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations).toEqual([]);
 expect((await page.request.get(`/api/v1/markets/${market}/catalogue?q=25`)).status()).toBe(200);
});
