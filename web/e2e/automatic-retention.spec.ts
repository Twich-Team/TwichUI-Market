import {test,expect} from '@playwright/test';
import {mkdir} from 'node:fs/promises';

test('automatic retention: exact authorization gates, real dry run and responsive storage facts',async({page})=>{
  await page.goto('/');
  await page.getByLabel('Username',{exact:true}).fill('owner');
  await page.getByLabel('Password',{exact:true}).fill('synthetic browser owner password');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();
  await page.goto('/administration');
  await page.getByRole('link',{name:'Storage & Backups',exact:true}).click();
  await page.getByRole('navigation',{name:'Storage & Backups pages'}).getByRole('link',{name:'Maintenance',exact:true}).click();
  await page.getByText('Advanced database & legacy diagnostics',{exact:true}).click();
  const capacity=page.getByRole('region',{name:'Storage safeguards',exact:true});
  await expect(capacity.getByText('Collector allocation cap',{exact:true})).toBeVisible();
  await expect(capacity.getByText('Filesystem safety reserve',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Edit Retention Policy',exact:true}).click();
  await expect(page.getByRole('button',{name:'Enable authorized maintenance',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Preview retention impact',exact:true}).click();
  await expect(page.getByRole('table',{name:'retention preview',exact:true})).toBeVisible();
  await expect(page.getByText('Historical cutoffs (UTC)',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Apply confirmed batch',exact:true})).toBeDisabled();
  await mkdir('../artifacts/automatic-retention/screenshots',{recursive:true});
  await page.screenshot({path:'../artifacts/automatic-retention/screenshots/desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('button',{name:'Enable authorized maintenance',exact:true})).toBeDisabled();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'../artifacts/automatic-retention/screenshots/mobile.png',fullPage:true});
});

test('automatic retention: enabled maintenance does not inherit obsolete legacy compaction claims',async({page})=>{
  await page.route('**/api/v1/admin/retention',async route=>{
    if(route.request().method()!=='GET')return route.continue();
    const response=await route.fetch();const value=await response.json();
    value.application_authorized=true;value.backup_restore_ready=true;value.completed_batches=9;
    value.automation={...value.automation,installed:true,authorized:true,enabled:true,paused_reason:null,rows_by_stage:{raw_listings:45000}};
    await route.fulfill({response,json:value});
  });
  await page.goto('/');await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('synthetic browser owner password');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();
  await page.goto('/administration');await page.getByRole('link',{name:'Storage & Backups',exact:true}).click();
  await page.getByRole('navigation',{name:'Storage & Backups pages'}).getByRole('link',{name:'Maintenance',exact:true}).click();
  await page.getByRole('button',{name:'Edit Retention Policy',exact:true}).click();
  await expect(page.getByRole('button',{name:'Pause automatic maintenance',exact:true})).toBeEnabled();
  await expect(page.getByText('Schedule enabled · 9 completed batches',{exact:true})).toBeVisible();
  await expect(page.getByText('raw listings: 45,000 rows processed',{exact:true})).toBeVisible();
  await expect(page.getByText('Compaction disabled; raw details preserved',{exact:true})).toHaveCount(0);
  await expect(page.getByText('Historical compaction is disabled',{exact:true})).toHaveCount(0);
});
