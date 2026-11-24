import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {StorageCapacity,MigrationProgress} from './backup-storage';
describe('storage observations',()=>{
  it('does not invent a capacity breakdown from account available space',()=>{const html=renderToStaticMarkup(<StorageCapacity health={{healthy:true,tested_at:'2026-11-24T18:00:00Z',capacity_bytes:1000,available_bytes:400}}/>);expect(html).toContain('Capacity unavailable');expect(html).not.toContain('role="meter"');});
  it('uses actual filesystem free space for used percentage',()=>{const html=renderToStaticMarkup(<StorageCapacity health={{healthy:true,tested_at:'2026-11-24T18:00:00Z',capacity_bytes:1000,free_bytes:300,available_bytes:200}}/>);expect(html).toContain('70.0% used');expect(html).toContain('aria-valuenow="70"');expect(html).toContain('200 B available to this account');});
  it('keeps active activation stage pending even when all bytes are copied',()=>{const html=renderToStaticMarkup(<MigrationProgress migration={{status:'running',copied:2,bytes_copied:100,plan:{count:2,bytes:100}}}/>);expect(html).toContain('Copying &amp; verifying');expect(html).not.toContain('Destination activated');expect(html).toContain('time remaining are not reported');});
  it('shows interruption and preservation without claiming activation',()=>{const html=renderToStaticMarkup(<MigrationProgress migration={{status:'interrupted',copied:1,plan:{count:2,bytes:100}}}/>);expect(html).toContain('Interrupted');expect(html).toContain('Original recovery copies remain preserved');expect(html).not.toContain('Destination activated');});
});
