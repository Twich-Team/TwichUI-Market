import type { CSSProperties } from 'react';
import './metadata-summary.css';

export function MetadataMeter({label, value, total, valueText, atLimit = false}: {
  label: string;
  value: number;
  total: number;
  valueText: string;
  atLimit?: boolean;
}) {
  const bounded = Math.min(value, total);
  return <div className={`metadata-meter${atLimit ? ' at-limit' : ''}`}
    role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={total}
    aria-valuenow={bounded} aria-valuetext={valueText}
    style={{'--measurement': `${bounded / total * 100}%`} as CSSProperties}>
    <span aria-hidden="true"/>
  </div>;
}
