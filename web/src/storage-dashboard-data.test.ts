import {describe,it,expect} from 'vitest';
import {capacityParts,physicalBackupBytes,isFresh,storageView,storageUrl} from './storage-dashboard-data';
describe('storage dashboard measurement contracts',()=>{
 it('uses direct administration URLs and defaults invalid tabs to overview',()=>{expect(storageView('storage_view=storage')).toBe('storage');expect(storageView('storage_view=wrong')).toBe('overview');expect(storageUrl('maintenance')).toBe('/administration?admin_tab=storage&storage_view=maintenance');});
 it('rejects incomplete, zero and inconsistent capacity totals',()=>{expect(capacityParts(null,30)).toBeNull();expect(capacityParts(0,0)).toBeNull();expect(capacityParts(100,101)).toBeNull();expect(capacityParts(100,-1)).toBeNull();expect(capacityParts(Infinity,1)).toBeNull();expect(capacityParts(100,30)).toEqual({total:100,available:30,used:70,percent:70});});
 it('keeps unknown physical sizes unavailable and includes retained copies',()=>{expect(physicalBackupBytes(undefined)).toBeNull();expect(physicalBackupBytes({local:{bytes:100},nas:{bytes:null}})).toBeNull();expect(physicalBackupBytes({local:{bytes:100},nas:{bytes:100}})).toBe(200);expect(physicalBackupBytes({local:{bytes:0}})).toBe(0);});
 it('does not call missing, stale or future observations current',()=>{const now=Date.parse('2026-11-24T18:00:00Z');expect(isFresh(undefined,now)).toBe(false);expect(isFresh('2026-11-24T17:50:00Z',now)).toBe(false);expect(isFresh('2026-11-24T19:00:00Z',now)).toBe(false);expect(isFresh('2026-11-24T17:59:00Z',now)).toBe(true);});
});
