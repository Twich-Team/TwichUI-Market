import { useState, type ComponentProps } from 'react';
import { DayButton, DayPicker, TZDate, Weekdays, type DayButtonProps } from 'react-day-picker';
import type { Backup, BackupOverview } from './backup-management';
import { backupOutcome, reliabilityCounts, utcBackupDay, type BackupOutcome } from './backup-data';

const utcDate = (date: string) => TZDate.tz('UTC', `${date}T12:00:00Z`);
const fullDate = new Intl.DateTimeFormat('en-US', { dateStyle: 'full', timeZone: 'UTC' });
const outcomes = {
  success: { icon: '✓', label: 'Successful' },
  failed: { icon: '×', label: 'Failed' },
  mixed: { icon: '±', label: 'Mixed' },
  unknown: { icon: '?', label: 'Unknown' },
};
function CalendarDay(props: DayButtonProps) {
  const outcome = (Object.keys(outcomes) as BackupOutcome[]).find(key => props.modifiers[key]);
  return <DayButton {...props}>
    {props.children}
    {outcome && <span className={`calendar-marker ${outcome}`} aria-hidden="true">{outcomes[outcome].icon}</span>}
  </DayButton>;
}

function CalendarWeekdays(props: ComponentProps<typeof Weekdays>) {
  return <thead><tr {...props}/></thead>;
}

export function BackupCalendar({ data, onSelect, onShowInventory, refreshing, error }: {
  data: BackupOverview;
  onSelect: (row: Backup, trigger: HTMLElement) => void;
  onShowInventory: (date: string) => void;
  refreshing: boolean;
  error?: string;
}) {
  const today = utcBackupDay(new Date());
  const [month, setMonth] = useState<Date>(() => utcDate(today));
  const [selected, setSelected] = useState(today);
  const evidence = data.reliability;
  const counts = reliabilityCounts(data.items, data.receipts, evidence?.days);
  const outcomeFor = (day: string) => backupOutcome(day, today, counts);
  const selectedCounts = selected <= today ? counts.get(selected) : undefined;
  const archives = data.items.filter(row => row.created_at && utcBackupDay(row.created_at) === selected);
  const modifiers = {
    success: (date: Date) => outcomeFor(utcBackupDay(date)) === 'success',
    failed: (date: Date) => outcomeFor(utcBackupDay(date)) === 'failed',
    mixed: (date: Date) => outcomeFor(utcBackupDay(date)) === 'mixed',
    unknown: (date: Date) => outcomeFor(utcBackupDay(date)) === 'unknown',
  };
  return <section className="panel padded recovery-calendar" aria-label="Backup reliability calendar">
    <div className="panel-heading"><h3>Backup reliability</h3><span className="muted">UTC</span></div>
    {refreshing && <p role="status">Refreshing recorded outcomes…</p>}
    {error && <p role="alert">Backup history could not be refreshed. Showing the last reading. Use Refresh backups to try again.</p>}
    <DayPicker
      mode="single"
      required
      timeZone="UTC"
      today={utcDate(today)}
      month={month}
      onMonthChange={setMonth}
      showOutsideDays
      fixedWeeks
      navLayout="around"
      selected={utcDate(selected)}
      onSelect={date => { setSelected(utcBackupDay(date)); setMonth(date); }}
      modifiers={modifiers}
      components={{ DayButton: CalendarDay, Weekdays: CalendarWeekdays }}
      labels={{ labelDayButton: (date, modifiers) =>
        `${fullDate.format(date)} UTC, ${outcomes[outcomeFor(utcBackupDay(date))].label}${modifiers.today ? ', today' : ''}${modifiers.selected ? ', selected' : ''}` }}
    />
    <button type="button" onClick={() => { setMonth(utcDate(today)); setSelected(today); }}>Current month</button>
    <div className="recovery-calendar-legend" aria-label="Outcome legend">
      {(Object.entries(outcomes) as [BackupOutcome, { icon: string; label: string }][]).map(([key, entry]) =>
        <span key={key}><b className={`calendar-marker ${key}`} aria-hidden="true">{entry.icon}</b> {entry.label}</span>)}
    </div>
    <div className="calendar-summary" aria-live="polite">
      <h4>{fullDate.format(utcDate(selected))} UTC</h4>
      <p>{selectedCounts
        ? `${selectedCounts.successes} successful · ${selectedCounts.failures} failed`
        : selected > today ? 'Future date. No outcomes expected yet.'
        : 'No recorded outcomes for this date.'}</p>
      {archives.length > 0 && <ul>{archives.slice(0,3).map(row => <li key={row.id}>
        <button type="button" onClick={event => onSelect(row,event.currentTarget)}>{row.filename}</button>
      </li>)}</ul>}
      {(archives.length > 0 || Boolean(selectedCounts?.successes)) &&
        <button type="button" onClick={() => onShowInventory(selected)}>Find archives from this date</button>}
    </div>
    <p className="muted">{evidence
      ? `Execution receipts since ${new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(evidence.since))} UTC.`
      : 'Execution history is unavailable. Outcomes reflect available archive and audit records.'}
      {evidence?.truncated && ' Some older receipts were omitted.'} Dates with no receipts have an unknown outcome.</p>
  </section>;
}
