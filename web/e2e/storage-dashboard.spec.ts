import {test,expect,type Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {mkdir} from 'node:fs/promises';
import {dashboardFixtures} from './storage-dashboard-fixtures';
const output='../docs/evidence/storage-redesign/screenshots';
async function setup(page:Page,change?:(fixture:ReturnType<typeof dashboardFixtures>)=>void) {
 const fixture=dashboardFixtures();change?.(fixture);const mutations:{path:string;body:unknown}[]=[];
 await page.route('**/api/v1/**',async route=>{
  const url=new URL(route.request().url()),path=url.pathname.replace('/api/v1','');
  if(route.request().method()!=='GET') {
   mutations.push({path,body:route.request().postDataJSON()});
   if(path.endsWith('/browse'))return route.fulfill({json:{directory:route.request().postDataJSON().directory,folders:['Archives','Daily'],next_offset:null}});
   if(path.endsWith('/test'))return route.fulfill({json:fixture.storage.health.nas});
   if(path.endsWith('/migration-preview'))return route.fulfill({json:{source_id:'local',destination_id:'nas',count:12,bytes:fixture.backups.total_bytes,available_bytes:690*1024**3,enough_space:true,protected_count:3,originals_preserved:true,token:'synthetic'}});
   if(path.endsWith('/save'))return route.fulfill({json:fixture.storage.destinations[1]});
   return route.fulfill({json:{status:'queued'}});
  }
  if(path==='/admin/retention/preview')return route.fulfill({json:{stages:[],confirmation:'synthetic',next_stage:null,next_batch_rows:0,estimated_logical_bytes:0,estimate_notice:'Logical row counts, not disk reclaimed.'}});
  const body=fixture.paths[path];
  if(body===undefined)return route.fulfill({status:404,json:{detail:'Unconfigured isolated fixture '+path}});
  if(path==='/admin/backups'){
   let rows=[...fixture.backups.items];
   if(url.searchParams.get('search'))rows=rows.filter(i=>i.filename.includes(url.searchParams.get('search')!));
   if(url.searchParams.get('protection'))rows=rows.filter(i=>i.protected===(url.searchParams.get('protection')==='protected'));
   if(url.searchParams.get('storage_id'))rows=rows.filter(i=>i.storage_id===url.searchParams.get('storage_id'));
   if(url.searchParams.get('verification'))rows=rows.filter(i=>url.searchParams.get('verification')==='restored'?i.restoration_verified_at:url.searchParams.get('verification')==='integrity'?i.verification==='archive_integrity_verified':i.verification!=='archive_integrity_verified');
   if(url.searchParams.get('sort')==='size_asc')rows.sort((a,b)=>a.bytes-b.bytes);
   return route.fulfill({json:{...fixture.backups,matched_total:rows.length,items:rows.slice(Number(url.searchParams.get('offset')||0),Number(url.searchParams.get('offset')||0)+100)}});
  }
  return route.fulfill({json:body});
 });
 return {fixture,mutations};
}
async function shot(page:Page,name:string){await page.locator('h1').evaluateAll(els=>els.forEach(el=>(el as HTMLElement).blur()));for(const canvas of await page.locator('.storage-page .chart-viewport').all()){await canvas.scrollIntoViewIfNeeded();await expect(canvas.locator('canvas')).toBeVisible();}await page.evaluate(()=>scrollTo(0,0));await mkdir(output,{recursive:true});await page.screenshot({path:`${output}/${name}.png`,fullPage:!(await page.getByRole('dialog').count())});}
async function open(page:Page,view='overview'){await page.goto(`/administration?admin_tab=storage&storage_view=${view}`);await expect(page.getByRole('heading',{name:'Storage & Backups',exact:true})).toBeVisible();}

test('storage dashboard: overview, routes/history, dialogs, filters, safeguards and screenshots',async({page})=>{
 test.setTimeout(90000);const {mutations}=await setup(page);await page.setViewportSize({width:1920,height:1080});await open(page);
 await expect(page.getByText('System health',{exact:true})).toBeVisible();await expect(page.locator('.storage-metric').filter({hasText:'Restore verification'})).toContainText('Verified');await expect(page.getByRole('region',{name:'Attention and activity'})).toHaveCount(0);
 await expect(page.locator('.database-growth canvas')).toBeVisible();await shot(page,'overview-1920');
 const nav=page.getByRole('navigation',{name:'Storage & Backups pages'});await nav.getByRole('link',{name:'Backups',exact:true}).click();await expect(page).toHaveURL(/storage_view=backups/);await expect(page.getByRole('heading',{name:'Recovery points',exact:true})).toBeVisible();await shot(page,'backups');
 await page.getByLabel('Search recovery points').fill('preview-1.dump');await expect(page.locator('.backup-table tbody tr')).toHaveCount(1);await page.getByLabel('Search recovery points').fill('');await expect(page.locator('.backup-table tbody tr')).toHaveCount(10);
 await page.getByRole('button',{name:'Details',exact:true}).first().click();await expect(page.getByRole('dialog',{name:'Backup details'})).toContainText('SHA-256');await shot(page,'backup-details');await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
 await page.getByRole('button',{name:'Delete',exact:true}).first().click();const deletion=page.getByRole('dialog',{name:'Delete backup archive'});await expect(deletion.getByRole('button',{name:'Confirm archive deletion'})).toBeDisabled();await shot(page,'protected-delete');await page.keyboard.press('Escape');
 await page.getByRole('checkbox',{name:/Select market-/}).first().check();await page.getByRole('checkbox',{name:/Select market-/}).nth(1).check();await page.getByRole('button',{name:'Delete selected (2)'}).click();await expect(page.getByRole('dialog',{name:'Delete selected backups'}).getByRole('button',{name:'Confirm selected backup deletion'})).toBeDisabled();await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Backup Policy',exact:true}).click();await expect(page.getByRole('dialog',{name:'Backup Policy'})).toBeVisible();await shot(page,'backup-policy');await page.keyboard.press('Escape');
 await nav.getByRole('link',{name:'Storage',exact:true}).click();await expect(page.getByRole('heading',{name:'Storage locations',exact:true})).toBeVisible();await shot(page,'storage');
 await page.locator('.storage-device').filter({has:page.getByRole('heading',{name:'Network vault',exact:true})}).getByRole('button',{name:'Configure',exact:true}).click();await expect(page.getByRole('dialog',{name:'Configure backup storage'})).toBeVisible();await expect(page.getByLabel('NAS password',{exact:true})).toHaveAttribute('type','password');await expect(page.getByLabel('NAS password',{exact:true})).toHaveValue('');await shot(page,'nas-configuration');await page.getByRole('button',{name:'Browse NAS folders',exact:true}).click();await expect(page.getByRole('region',{name:'Choose NAS folder'})).toContainText('Archives');await shot(page,'nas-folders');await page.keyboard.press('Escape');
 await nav.getByRole('link',{name:'Maintenance',exact:true}).click();await expect(page.getByRole('heading',{name:'The life of your market history'})).toBeVisible();await expect(page.getByText('365 days',{exact:false})).toBeVisible();await shot(page,'maintenance');await page.getByRole('button',{name:'Edit Retention Policy',exact:true}).click();await expect(page.getByRole('dialog',{name:'Edit Retention Policy'})).toBeVisible();await shot(page,'retention-policy');await page.keyboard.press('Escape');
 await page.goBack();await expect(page).toHaveURL(/storage_view=storage/);await page.goForward();await expect(page).toHaveURL(/storage_view=maintenance/);await page.reload();await expect(page.getByRole('heading',{name:'The life of your market history'})).toBeVisible();
 expect(mutations.filter(m=>m.path.includes('delete')||m.path.includes('/apply')||m.path.includes('/migrate'))).toEqual([]);
 const accessibility=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();expect(accessibility.violations).toEqual([]);
 for(const width of [1280,2560,800]){await page.setViewportSize({width,height:width===1280?720:1080});await open(page);await shot(page,`overview-${width}`);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);}
});

test('actual operation states, failures, stale and empty observations are explicit',async({page})=>{
 test.setTimeout(90000);await setup(page,f=>{f.storage.migration={id:'migration-fixture',status:'running',started_at:f.at(.5),copied:3,bytes_copied:4*1024**3,plan:{source_id:'local',destination_id:'nas',count:12,bytes:18*1024**3}} as never;f.storage.active_id='local';});await page.setViewportSize({width:1920,height:1080});await open(page);await expect(page.getByRole('region',{name:'Attention and activity'})).toContainText('copied and verified');await shot(page,'overview-active-migration');await page.getByRole('button',{name:'Open migration →'}).click();await shot(page,'migration-progress');
});
for(const scenario of ['local-healthy','backup-running','nas-disconnected','capacity-warning','backup-failed','restore-expired','cleanup-paused','migration-failed','migration-interrupted','migration-completed','empty-history','stale-inventory'] as const){
 test(`honest ${scenario} presentation`,async({page})=>{
  await setup(page,f=>{
   if(scenario==='local-healthy')f.storage.active_id='local';
   if(scenario==='backup-running')f.backups.job.status='running';
   if(scenario==='nas-disconnected'){f.storage.health.nas.healthy=false;(f.storage.health.nas as Record<string,unknown>).error='NAS authentication failed';}
   if(scenario==='capacity-warning')f.backups.storage_pressure=true;
   if(scenario==='backup-failed')f.backups.job.status='failed';
   if(scenario==='restore-expired'){f.maintenance.automation.recovery.expires_at=f.at(2);f.maintenance.automation.recovery.required_evidence_recent=false;}
   if(scenario==='cleanup-paused'){f.maintenance.status='paused';f.maintenance.automation.paused_reason='Cleanup paused: restore verification has expired.' as never;}
   if(scenario.startsWith('migration-'))f.storage.migration={id:'synthetic',status:scenario==='migration-completed'?'succeeded':scenario==='migration-failed'?'failed':'interrupted',copied:3,bytes_copied:4*1024**3,plan:{source_id:'local',destination_id:'nas',count:12,bytes:18*1024**3}} as never;
   if(scenario==='empty-history'){f.summary.growth.samples=[];f.maintenance.activity.days=[];f.backups.items=[];f.backups.total=0;f.backups.total_bytes=0;}
   if(scenario==='stale-inventory'){f.backups.inventory_stale=true;f.backups.measured_at=f.at(2);}
  });await open(page);
  if(scenario==='migration-completed'||scenario==='local-healthy')await expect(page.getByRole('region',{name:'Attention and activity'})).toHaveCount(0);
  else if(scenario!=='empty-history')await expect(page.getByRole('region',{name:'Attention and activity'})).toBeVisible();
  if(scenario==='restore-expired')await expect(page.locator('.storage-metric').filter({hasText:'Restore verification'})).toContainText('Needs attention');
  if(scenario==='empty-history')await expect(page.getByText('No recorded storage measurements yet.')).toBeVisible();
  await shot(page,scenario);
 });
}

test('subsystem failure leaves other monitoring and navigation available',async({page})=>{
 await setup(page);await page.route('**/api/v1/admin/backups?**',route=>route.fulfill({status:503,json:{detail:'Isolated backup service unavailable'}}));await open(page);await expect(page.getByRole('region',{name:'Attention and activity'})).toContainText('Backup service unavailable');await expect(page.getByText('System health',{exact:true})).toBeVisible();await expect(page.locator('.storage-metric').filter({hasText:'Database size'})).toContainText('GiB');
});

 test('all detail pages and dialogs remain usable at narrow desktop widths',async({page})=>{
 test.setTimeout(90000);await setup(page);
 for(const width of [320,1280,800]){await page.setViewportSize({width,height:720});for(const view of ['backups','storage','maintenance']){await open(page,view);await shot(page,`${view}-${width}`);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);}}
 await page.setViewportSize({width:1280,height:720});await open(page,'storage');await page.locator('.storage-device').filter({has:page.getByRole('heading',{name:'Network vault',exact:true})}).getByRole('button',{name:'Configure',exact:true}).click();await shot(page,'nas-configuration-1280');await expect(page.getByRole('dialog')).toBeVisible();await page.getByRole('button',{name:'Close storage settings'}).click();await expect(page.getByRole('dialog')).toHaveCount(0);
 });
