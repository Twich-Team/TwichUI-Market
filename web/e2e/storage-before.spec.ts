import {test,expect} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
import {dashboardFixtures} from './storage-dashboard-fixtures';
test('baseline storage screenshot from unmodified c6946cd source',async({page})=>{
 test.skip(process.env.STORAGE_BASELINE!=='1','Only run against the retained baseline build.');
 const fixture=dashboardFixtures();
 await page.route('**/api/v1/**',route=>{
  const path=new URL(route.request().url()).pathname.replace('/api/v1','');
  return route.fulfill({json:fixture.paths[path]??{}});
 });
 await page.setViewportSize({width:1920,height:1080});await page.goto('/administration');await page.getByRole('tab',{name:'Storage & backups',exact:true}).click();await expect(page.getByRole('heading',{name:'Backup Management',exact:true})).toBeVisible();await page.locator('.database-growth').scrollIntoViewIfNeeded();await expect(page.locator('.database-growth canvas')).toBeVisible();await page.evaluate(()=>scrollTo(0,0));await page.locator('h1').evaluateAll(els=>els.forEach(el=>(el as HTMLElement).blur()));await mkdir('../docs/evidence/storage-redesign/screenshots',{recursive:true});await page.screenshot({path:'../docs/evidence/storage-redesign/screenshots/before-storage.png',fullPage:true});
});
