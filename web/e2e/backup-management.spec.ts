import {test,expect,type Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {mkdir} from 'node:fs/promises';
test.use({timezoneId:'America/Denver'});
const output='../artifacts/backup-management/screenshots';
const GIB=1024**3;
const policy={revision:1,enabled:false,interval_seconds:86400,daily:2,weekly:2,monthly:0,max_bytes:null,minimum_recovery_points:1,warning_free_bytes:3*GIB};
function fixture(){
  const items=Array.from({length:13},(_,i)=>({id:(i+1).toString(16).padStart(32,'0'),filename:`market-${i===0?'release':'scheduled'}-202611${String(18-i).padStart(2,'0')}T010000Z.dump`,type:i===0?'release':'scheduled',origin:i===0?'release':'scheduled',created_at:`2026-11-${String(18-i).padStart(2,'0')}T01:00:00+00:00`,bytes:(180+i*4)*1024**2,sha256:'b'.repeat(64),verification:'archive_integrity_verified',restoration_verified_at:i===0?'2026-11-18T01:05:00+00:00':null,protected:i===0,required_by:i===0?['active-release']:[],eligible:i!==0,reason:i===0?'Protected or required by a recovery operation':'Eligible for explicit deletion'}));
  return {policy:{...policy},service_status:'scheduled_backups_disabled',last_success:'2026-11-18T01:00:00+00:00',last_restoration_verified_at:'2026-11-18T01:05:00+00:00',total:items.length,total_bytes:3*GIB,items,artifact_count:2,artifacts:[{name:'market-legacy.json',type:'orphan_manifest'},{name:'market-failed.partial',type:'incomplete'}],filesystem:{capacity_bytes:98*GIB,available_bytes:5.5*GIB,reserve_bytes:2*GIB,filesystem_id:'synthetic-fixture',measurement:'Synthetic backup filesystem measurement'},storage_pressure:false,next_scheduled_at:null,estimate_bytes:512*1024**2,job:{status:'succeeded'},preview:{candidates:items.slice(8).map(({id,filename,bytes})=>({id,filename,bytes})),reclaimable_bytes:GIB,budget_exceeded:false,scope:'Only scheduled v2 archives outside retained UTC day/week/month buckets. Protected, manual, release and legacy archives are excluded.'},receipts:[{id:'receipt',at:'2026-11-18T01:05:00+00:00',actor:'admin:1',action:'backup.published',detail:{}}]};
}
async function setup(page:Page){
  const data=fixture();const deletions:unknown[]=[];const policies:unknown[]=[];
  await page.route('**/api/v1/admin/backups**',async route=>{
    const request=route.request(),url=new URL(request.url());
    if(request.method()==='GET'){
      if(url.pathname.endsWith('/storage'))return route.fulfill({json:{active_id:'local',destinations:[{id:'local',revision:1,type:'local',name:'Local backups',directory:''}],health:{},migration:{},share_notice:'Enter a known share',mounted_notice:'Existing persistent backup root'}});
      if(url.pathname.endsWith('/download'))return route.fulfill({contentType:'application/octet-stream',headers:{'Content-Disposition':'attachment; filename="synthetic.dump"'},body:'PGDMP synthetic'});
      const offset=Number(url.searchParams.get('offset')||0),limit=Number(url.searchParams.get('limit')||10);
      return route.fulfill({json:{...data,items:data.items.slice(offset,offset+limit)}});
    }
    const body=request.postDataJSON();
    if(url.pathname.endsWith('/delete')){deletions.push(body);const id=url.pathname.split('/').at(-2);data.items=data.items.filter(row=>row.id!==id);data.total=data.items.length;return route.fulfill({json:{status:'deleted',archive_removed:true,manifest_removed:true,unlinked_bytes:184*1024**2}});}
    if(url.pathname.endsWith('/policy')){policies.push(body);data.policy={...body.values,revision:body.revision+1};return route.fulfill({json:data.policy});}
    if(url.pathname.endsWith('/protect')){const row=data.items.find(row=>url.pathname.includes(row.id))!;row.protected=body.protected;return route.fulfill({json:{protected:body.protected}});}
    return route.fulfill({status:202,json:{status:'queued'}});
  });
  await page.goto('/');await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('synthetic browser owner password');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();
  await page.goto('/administration');
  await page.getByRole('button',{name:'Storage & backups ↗',exact:true}).click();
  await page.getByRole('navigation',{name:'Storage & Backups pages'}).getByRole('link',{name:'Backups',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Recovery points',exact:true})).toBeVisible();
  await mkdir(output,{recursive:true});return {data,deletions,policies};
}
async function axe(page:Page){expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations).toEqual([]);}

test('backup management: inventory, details, pagination, exact-name deletion and policy review',async({page})=>{
  const {deletions,policies}=await setup(page);
  const management=page.getByRole('region',{name:'Backup Management',exact:true});
  await expect(management.getByRole('heading',{name:'Backup size history'})).toBeVisible();
  await expect(management.getByRole('region',{name:'Backup reliability calendar'})).toBeVisible();
  const table=page.getByRole('table',{name:'Managed backup archives'});
  await expect(table.getByRole('row')).toHaveCount(11);
  await expect(table.getByRole('row').nth(1).locator('time')).toContainText('Nov 17, 2026');
  await expect(table.getByRole('row').nth(1).getByRole('button',{name:'Delete',exact:true})).toBeDisabled();
  await page.screenshot({path:`${output}/desktop-inventory.png`,fullPage:true});
  await table.getByRole('row').nth(2).getByRole('button',{name:'Details',exact:true}).click();
  await expect(page.getByRole('dialog')).toContainText('SHA-256');await axe(page);
  await page.screenshot({path:`${output}/backup-details.png`});
  await page.getByRole('button',{name:'Close details',exact:true}).click();
  await table.getByRole('row').nth(2).getByRole('button',{name:'Delete',exact:true}).click();
  const dialog=page.getByRole('dialog');await expect(dialog.getByRole('button',{name:'Confirm archive deletion'})).toBeDisabled();
  const name='market-scheduled-20261117T010000Z.dump';await dialog.getByLabel(`Type ${name} to confirm`,{exact:true}).fill(name);
  await page.screenshot({path:`${output}/delete-confirmation.png`});await axe(page);
  await dialog.getByLabel('I acknowledge the risk of removing the newest or last known-good backup.',{exact:true}).check();
  await dialog.getByRole('button',{name:'Confirm archive deletion'}).click();await expect(dialog).toHaveCount(0);
  expect(deletions).toEqual([{confirmation:name,confirm_recovery_loss:true}]);await expect(page.getByRole('status').filter({hasText:'unlinked'})).toBeVisible();
  await page.getByRole('button',{name:'Next backups',exact:true}).click();await expect(table.getByRole('row')).toHaveCount(3);
  await page.getByRole('button',{name:'Previous backups',exact:true}).click();
  await page.getByRole('button',{name:'Backup Policy',exact:true}).click();
  await page.getByLabel('Daily backups to keep',{exact:true}).fill('3');await page.getByLabel('Enable scheduled backups',{exact:true}).check();
  await page.getByRole('button',{name:'Review backup policy',exact:true}).click();await expect(page.getByRole('dialog',{name:'Save backup retention policy',exact:true})).toContainText('Enable scheduled backups every 24 hours');
  await page.screenshot({path:`${output}/policy-confirmation.png`});await page.getByRole('button',{name:'Confirm backup policy'}).click();
  expect(policies).toHaveLength(1);expect((policies[0] as {values:{daily:number}}).values.daily).toBe(3);
});

test('backup management: mobile storage pressure, safeguards and disclosures',async({page})=>{
  await page.setViewportSize({width:390,height:844});const {data}=await setup(page);data.storage_pressure=true;data.filesystem.available_bytes=2.5*GIB;
  await page.getByRole('button',{name:'Refresh backups',exact:true}).click();await expect(page.getByText('Storage pressure.',{exact:true})).toBeVisible();
  await page.screenshot({path:`${output}/mobile-storage-pressure.png`,fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.getByText('Retention preview & emergency cleanup',{exact:true}).click();await expect(page.getByText(/This is a dry run/)).toBeVisible();
  await page.getByText('Service details & audit receipts',{exact:true}).click();await expect(page.getByText('market-legacy.json · orphan manifest',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Create manual backup',exact:true}).click();await expect(page.getByRole('dialog')).toContainText('protected');await axe(page);
  await page.screenshot({path:`${output}/mobile-manual-confirmation.png`});await page.getByRole('button',{name:'Cancel',exact:true}).click();
});

test('backup management: unavailable and empty states show no fabricated measurements',async({page})=>{
  const {data}=await setup(page);data.items=[];data.total=0;data.total_bytes=0;data.last_success=null;data.last_restoration_verified_at=null;
  await page.getByRole('button',{name:'Refresh backups',exact:true}).click();await expect(page.getByText(/No recovery points match these filters/)).toBeVisible();
  await page.screenshot({path:`${output}/empty-state.png`,fullPage:true});
  await page.route('**/api/v1/admin/backups?*',route=>route.fulfill({status:503,json:{detail:'Backup management service is unavailable'}}));
  await page.getByRole('button',{name:'Refresh backups',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'Storage measurements'})).toBeVisible();
});


test('backup management real boundary: create protect download and delete through actual API and service',async({page})=>{
  test.setTimeout(90000);
  await page.goto('/');await page.getByLabel('Username',{exact:true}).fill('owner');await page.getByLabel('Password',{exact:true}).fill('synthetic browser owner password');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Market Explorer',exact:true})).toBeVisible();
  const me=await (await page.request.get('/api/v1/auth/session')).json();
  const headers={'X-CSRF-Token':me.csrf_token};
  const read=async()=>await (await page.request.get('/api/v1/admin/backups')).json();
  const before=await read();expect(before.policy.enabled).toBe(false);
  const sourceBefore=await (await page.request.get('/api/v1/admin/storage')).json();
  const created=[];
  for(let i=0;i<2;i++){
    const queued=await page.request.post('/api/v1/admin/backups/create',{headers,data:{}});expect(queued.status(),await queued.text()).toBe(202);
    const job=await queued.json();
    await expect.poll(async()=>{const state=await read();return state.job.id===job.id?state.job.status:'waiting';},{timeout:30000}).toBe('succeeded');
    const row=(await read()).items.find((item:{id:string})=>item.id!==(created[0]?.id)&&!before.items.some((previous:{id:string})=>previous.id===item.id));
    expect(row.protected).toBe(true);expect(row.restoration_verified_at).toBeNull();created.push(row);
  }
  const older=created[0];
  const refused=await page.request.post(`/api/v1/admin/backups/${older.id}/delete`,{headers,data:{confirmation:older.filename}});expect(refused.status()).toBe(409);
  const manifest=await page.request.get(`/api/v1/admin/backups/${older.id}/manifest`);expect(manifest.status()).toBe(200);expect((await manifest.json()).postgres_major).toBe(17);
  const download=await page.request.get(`/api/v1/admin/backups/${older.id}/download`);expect(download.status()).toBe(200);expect((await download.body()).subarray(0,5).toString()).toBe('PGDMP');
  expect((await page.request.post(`/api/v1/admin/backups/${older.id}/protect`,{headers,data:{protected:false}})).status()).toBe(200);
  await page.goto('/administration');
  await page.getByRole('button',{name:'Storage & backups ↗',exact:true}).click();
  await page.getByRole('navigation',{name:'Storage & Backups pages'}).getByRole('link',{name:'Backups',exact:true}).click();
  const row=page.getByRole('row').filter({hasText:older.filename});await row.getByRole('button',{name:'Delete',exact:true}).click();
  await page.getByRole('dialog').getByLabel(`Type ${older.filename} to confirm`,{exact:true}).fill(older.filename);
  await page.getByRole('dialog').getByLabel('I acknowledge the risk of removing the newest or last known-good backup.',{exact:true}).check();
  await mkdir(output,{recursive:true});await page.screenshot({path:`${output}/actual-service-deletion.png`});
  await page.getByRole('dialog').getByRole('button',{name:'Confirm archive deletion'}).click();await expect(row).toHaveCount(0);
  const sourceAfter=await (await page.request.get('/api/v1/admin/storage')).json();
  expect(sourceAfter.snapshots).toBe(sourceBefore.snapshots);expect(sourceAfter.observations).toBe(sourceBefore.observations);
  const after=await read();expect(after.policy.enabled).toBe(false);expect(after.total).toBe(before.total+1);expect(after.receipts.some((receipt:{action:string})=>receipt.action==='deletion.result')).toBe(true);
});
