// Internal HTTP fixture for the isolated review. No command execution or archive filesystem.
import {createServer} from 'node:http';
import {readFileSync} from 'node:fs';
import {timingSafeEqual} from 'node:crypto';
import {dashboardFixtures} from './storage-dashboard-fixtures.ts';

const expected = Buffer.from('Bearer ' + readFileSync('/review-token','utf8').trim());
const {storage,backups} = dashboardFixtures();
const rows = backups.items;
const vault = 'f'.repeat(32);
storage.active_id = vault;
storage.destinations[1].id = vault;
storage.destinations[1].name = 'Simulated network vault';
storage.health[vault] = storage.health.nas;
delete storage.health.nas;
backups.inventory_by_storage[vault] = backups.inventory_by_storage.nas;
delete backups.inventory_by_storage.nas;
for (const row of rows) {
  if (row.storage_id === 'nas') {row.storage_id = vault; row.storage_name = 'Simulated network vault';}
}
rows[0].active_use = true;
rows[0].required_by = ['simulated recovery'];
backups.policy.enabled = false;
backups.next_scheduled_at = null;
backups.service_status = 'scheduled_backups_disabled';
const days = new Map();
for (const item of rows) {
  const day = item.created_at.slice(0,10);
  days.set(day,{day,succeeded:(days.get(day)?.succeeded ?? 0)+1,failed:0});
}
const mixed = [...days.values()][1];
mixed.failed = 1;
const failed = new Date(Date.now()-12*86400000).toISOString().slice(0,10);
days.set(failed,{day:failed,succeeded:0,failed:1});
backups.reliability.days = [...days.values()];
backups.reliability.notice = 'Simulated UTC outcomes for the review calendar.';
backups.reliability.attempts = [mixed.day,failed].map(day=>({at:day+'T10:00:00Z',status:'failed',origin:'scheduled',backup_id:null,bytes:null}));

function inventory(params) {
  let matches = rows.filter(row => {
    const verification = params.get('verification');
    return (!params.get('search') || row.filename.toLowerCase().includes(params.get('search').toLowerCase())) &&
      (!params.get('storage_id') || row.storage_id === params.get('storage_id')) &&
      (!params.get('backup_type') || row.type === params.get('backup_type')) &&
      (!params.get('protection') || row.protected === (params.get('protection')==='protected')) &&
      (!verification || (verification==='restored' ? !!row.restoration_verified_at :
        (row.verification === 'archive_integrity_verified') === (verification === 'integrity')));
  });
  const sort = params.get('sort') || 'created_desc';
  matches.sort((a,b)=>(sort.startsWith('bytes') ? a.bytes-b.bytes : a.created_at.localeCompare(b.created_at))*(sort.endsWith('desc')?-1:1));
  const offset = Number(params.get('offset') || 0);
  return {...backups,measured_at:new Date().toISOString(),matched_total:matches.length,items:matches.slice(offset,offset+Number(params.get('limit') || 20))};
}
createServer((req,res)=>{
  function send(code,value) {res.writeHead(code,{'Content-Type':'application/json'});res.end(JSON.stringify(value));}
  const token = Buffer.from(req.headers.authorization || '');
  if (expected.length !== token.length || !timingSafeEqual(expected,token)) return send(403,{detail:'Review API credential required.'});
  const url = new URL(req.url,'http://backup-manager');
  if (req.method==='GET' && url.pathname==='/overview') return send(200,inventory(url.searchParams));
  if (req.method==='GET' && url.pathname==='/storage') return send(200,storage);
  const id = url.pathname.split('/')[2];
  const row = rows.find(item => item.id===id);
  if (req.method==='GET' && row && url.pathname==='/backups/'+id+'/manifest') return send(200,{fixture:true,...row});
  return send(409,{detail:'This preview uses simulated backup records. Archive operations require a configured backup service.'});
}).listen(8091,'0.0.0.0');
