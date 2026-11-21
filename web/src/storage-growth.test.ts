import { expect,it } from 'vitest';
import { growthView } from './storage-growth-data';
it('keeps real measurements, selected-period signed growth and honest gaps',()=>{
 const view=growthView([{sampled_at:'2026-11-14T00:00:00Z',database_bytes:100},{sampled_at:'2026-11-14T01:00:00Z',database_bytes:130},{sampled_at:'2026-11-15T00:00:00Z',database_bytes:90}]);
 expect(view.delta).toBe(-10);expect(view.bytesPerDay).toBe(-10);expect(view.gaps).toBe(1);expect(view.rows).toHaveLength(3);
 expect(view.points[2]).toEqual([Date.parse('2026-11-14T02:00:00Z'),null]);
 expect(growthView(view.rows,.5).delta).toBeNull();expect(growthView([]).delta).toBeNull();
});
