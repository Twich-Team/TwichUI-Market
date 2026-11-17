import { expect,it } from 'vitest';
import { formatBytes } from './size';
it('formats IEC thresholds, signed changes, zero and unavailable measurements',()=>{
 expect([0,1023,1024,1048576,1073741824,1099511627776].map(v=>formatBytes(v))).toEqual(['0 B','1023 B','1.0 KiB','1.0 MiB','1.0 GiB','1.0 TiB']);
 expect(formatBytes(-1073741824)).toBe('-1.0 GiB');
 expect(formatBytes(null)).toBe('Unavailable');expect(formatBytes(NaN)).toBe('Unavailable');
 expect(formatBytes(2802931379)).toBe('2.6 GiB');
});
