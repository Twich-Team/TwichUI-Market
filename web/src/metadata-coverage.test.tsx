import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MetadataSummary } from './metadata-coverage';
import type { MetadataOverview } from './metadata-admin';

const coverage = {
  measured_at: '2026-11-24T12:00:00Z', observed: 400, resolved_names: 399, icons_available: 30, attributes_available: 0,
  missing_names: 1, icons_missing: 370, primary_names: 398, supplemental_names: 1,
  scoped_pending_items: 1, failed_or_blocked: 1, checked_unresolved: 0, unknown_not_tried: 0, tried_unavailable: 0,
} as MetadataOverview;

function render(state: MetadataOverview) { return renderToStaticMarkup(<MetadataSummary state={state} openRecovery={()=>{}}/>); }

describe('metadata coverage cards', () => {
  it('uses the latest snapshot item count for all three measures and exposes the partial attribute definition', () => {
    const html = render(coverage);
    expect(html.match(/role="meter"/g)).toHaveLength(3);
    expect(html).toContain('399 of 400 items');
    expect(html).toContain('30 of 400 items');
    expect(html).toContain('0 of 400 items');
    expect(html).toContain('99.8%');
    expect(html).toContain('7.5%');
    expect(html).toContain('0%');
    expect(html).toContain('At least one field beyond name and icon');
    expect(html).toContain('Open Recovery Tracker');
  });

  it('leaves coverage unavailable when no item snapshot was observed', () => {
    const html = render({...coverage, observed:0, resolved_names:0, attributes_available:0, icons_available:0});
    expect(html).toContain('No item observations in this market yet');
    expect(html).toContain('Awaiting an item snapshot');
    expect(html).not.toContain('role="meter"');
    expect(html).not.toContain('0%');
  });
});
