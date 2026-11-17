import { useId, type ReactNode } from 'react';
import { Popover } from '@base-ui/react/popover';
export function InfoTooltip({label,children}:{label:string;children:ReactNode}) {
  const id=useId();
  return <Popover.Root><Popover.Trigger className="info-tooltip-trigger" aria-label={`About ${label}`} aria-describedby={id} openOnHover delay={180} closeDelay={150}><span aria-hidden="true">i</span></Popover.Trigger>
    <Popover.Portal><Popover.Positioner side="top" sideOffset={8}><Popover.Popup id={id} role="tooltip" className="metric-tooltip">{children}</Popover.Popup></Popover.Positioner></Popover.Portal>
  </Popover.Root>;
}
export const metricExplanations={
 lowest:'Lowest current asking price per unit for this exact variant, rounded to the nearest copper. Asking prices are not completed sales.',
 recent:'Current buyout totals divided by the number of priced units for this variant, rounded to the nearest copper. Bid-only listings are excluded.',
 reference:'Average of the last observation’s unit price on each UTC day within 14 days. Days whose last observation has no buyout price are omitted; even one priced day can produce a reference. These are asking prices; check the day count.',
 supply:'Total listed units for this exact variant in the selected market snapshot, including bid-only listings. This is the whole current supply, rather than one deal’s stack.',
 evidence:'Evidence reflects source freshness, verified mapping and observed days. Moderate needs at least 3 days; strong needs 7. Stale, unverified or synthetic data stays limited. It is not a chance of profit.',
};
