import type { ReactNode } from 'react';
import { LocalTime } from './admin-table';
import type { BackupOverview } from './backup-management';
import type { MetadataOverview, MetadataSourceSummary } from './metadata-admin';
import { followItem } from './navigation';
import type { AdminAccessSummary, Storage } from './settings';
import { formatBytes } from './size';
import { isFresh, storageUrl } from './storage-dashboard-data';
import type { Market } from './types';
import './admin-overview.css';

type Tone = 'success' | 'error' | 'warning' | 'neutral' | 'loading' | 'unavailable';
type Status = { tone: Tone; label: string; reason: ReactNode; detail?: ReactNode };
type Destination = { href: string; label: string };
type Module = Status & { id: string; title: string; links: Destination[] };
type Check = 'storage' | 'backups' | 'coverage' | 'devices' | 'sources' | 'access';
type CheckFlags = Partial<Record<Check, boolean>>;

interface DeviceSummary {
  authorized: number;
  recently_connected: number;
  recent_window_minutes?: number;
}

interface OverviewProps {
  access?: AdminAccessSummary;
  storage?: Storage;
  backups?: BackupOverview;
  coverage?: MetadataOverview;
  coverageMarket?: Market;
  devices?: DeviceSummary;
  markets: Market[];
  marketStatus?: 'loading' | 'unavailable' | 'available';
  sources?: MetadataSourceSummary[];
  pending?: CheckFlags;
  errors?: CheckFlags;
}

const signals: Record<Tone, string> = {
  success: '✓', error: '✕', warning: '!', neutral: '–', loading: '…', unavailable: '?',
};

const sectionLink = (tab: string, label: string): Destination => ({
  href: `/administration?admin_tab=${tab}`,
  label,
});

const status = (tone: Tone, label: string, reason: ReactNode, detail?: ReactNode): Status =>
  ({ tone, label, reason, detail });

function waiting(loading: boolean, subject: string) {
  return loading
    ? status('loading', 'Checking', `Loading ${subject}…`)
    : status('unavailable', 'Unavailable', `Could not read ${subject}.`);
}

function count(value: number, singular: string, plural = `${singular}s`) {
  return `${value.toLocaleString()} ${value === 1 ? singular : plural}`;
}

function marketStatusCards(markets: Market[], available: OverviewProps['marketStatus'], now: number) {
  if (available === 'loading' || available === 'unavailable') {
    const state = waiting(available === 'loading', 'market and collection status');
    return { schedules: state, collection: state };
  }
  const enabled = markets.filter(market => market.enabled);
  const unverified = enabled.filter(market => !market.verified);
  const active = enabled.filter(market => market.verified);
  const disabled = markets.length - enabled.length;
  const scheduleDetail = disabled ? `${count(disabled, 'market')} paused.` : undefined;
  const schedules = !markets.length
    ? status('neutral', 'Not configured', 'Add a market to set up collection.')
    : unverified.length
      ? status('warning', 'Verification needed', `${count(unverified.length, 'enabled market')} awaiting verification.`, scheduleDetail)
      : !active.length
        ? status('neutral', 'Paused', 'Collection is paused for every configured market.')
        : status('success', 'Schedules enabled', `${count(active.length, 'verified market')} scheduled to collect.`, scheduleDetail);

  const failedFeed = (market: Market) => market.feeds?.find(feed =>
    feed.enabled && (feed.failures > 0 || feed.last_error || feed.status === 'failed'));
  const failed = active.filter(market => market.failures > 0 || market.last_error || failedFeed(market));
  const stale = active.filter(market => market.freshness === 'stale' || market.coverage_status === 'partial');
  const unconfirmed = active.filter(market => market.freshness !== 'current' ||
    !isFresh(market.last_success, now, Math.max(300_000, market.interval_seconds * 3_000)));
  const latest = active.map(market => market.last_success).filter(Boolean).sort().at(-1);
  const lastCheck = latest ? <>Last successful check <LocalTime value={latest}/></> : undefined;

  let collection: Status;
  if (failed.length) {
    const first = failed[0];
    const reason = failedFeed(first)?.last_error || first.last_error;
    collection = status('error', 'Collection failing', `${count(failed.length, 'market')} reporting failed checks.`,
      [first.label, reason].filter(Boolean).join(' · '));
  } else if (stale.length) {
    collection = status('warning', 'Prices may be old', `${count(stale.length, 'market')} with stale or incomplete source data.`, lastCheck);
  } else if (unconfirmed.length) {
    collection = status('warning', 'Freshness unconfirmed', `${count(unconfirmed.length, 'market')} missing recent successful checks or reliable price timestamps.`, lastCheck);
  } else if (!active.length) {
    collection = status('neutral', 'No active collection', 'Collection needs an enabled, verified market.');
  } else {
    collection = status('success', 'Checks current', `Recent checks and current prices for ${count(active.length, 'active market')}.`, lastCheck);
  }
  return { schedules, collection };
}

function capacityStatus(storage: Storage): Status {
  const capacity = storage.operations?.capacity;
  const allocated = capacity?.database_allocated_bytes;
  const free = capacity?.filesystem.available_bytes;
  const detail = storage.database_bytes == null ? undefined : `${formatBytes(storage.database_bytes)} allocated to the database.`;
  if (capacity?.paused_reason) {
    return status('error', 'Collection paused', capacity.paused_reason, detail);
  }
  if (!capacity || allocated == null || free == null) {
    return status('unavailable', 'Capacity unconfirmed', 'Database allocation and filesystem headroom need current measurements.', detail);
  }
  const capacityWarnings = storage.operations?.warnings.filter(warning =>
    warning.startsWith('Database allocation approaches') || warning.startsWith('Filesystem free space approaches'));
  if (capacityWarnings?.length) {
    return status('warning', 'Low headroom', capacityWarnings.join(' · '), `${formatBytes(free)} of filesystem space available.`);
  }
  return status('success', 'Within limits', `${formatBytes(free)} of filesystem space available, above the configured reserve.`, detail);
}

function backupStatus(backups: BackupOverview, now: number): Status {
  const points = count(backups.total, 'recovery point');
  const schedule = backups.policy.enabled ? 'Scheduled backups on.' : 'Scheduled backups off.';
  const detail = `${points} · ${schedule}`;
  if (backups.service_status === 'operation_busy') {
    return status('loading', 'Operation in progress', 'The backup service is busy. Inventory will refresh after the operation.');
  }
  if (backups.storage_error || backups.service_status === 'storage_unavailable') {
    return status('error', 'Backup storage unavailable', 'The backup service could not read its storage. Review the destination.');
  }
  if (backups.inventory_stale || !isFresh(backups.measured_at, now)) {
    return status('unavailable', 'Inventory unconfirmed', 'A current backup inventory is unavailable.');
  }
  if (backups.job.status === 'failed') {
    return status('error', 'Latest operation failed', backups.job.error || 'The backup service recorded a failed operation.', detail);
  }
  if (backups.storage_pressure) {
    return status('warning', 'Low backup space', 'Available space is below the backup warning limit.', detail);
  }
  if (backups.job.status === 'queued' || backups.job.status === 'running') {
    return status('loading', 'Operation in progress', 'A backup operation is queued or running.', detail);
  }
  if (!backups.total || !backups.last_success) {
    return status('warning', 'Recovery point needed', 'No archive with verified integrity is recorded.', detail);
  }
  if (!backups.last_restoration_verified_at) {
    return status('warning', 'Restore unverified', 'No successful restore rehearsal is recorded.', detail);
  }
  const restore = <>Last restore rehearsal <LocalTime value={backups.last_restoration_verified_at}/></>;
  if (!backups.policy.enabled) {
    return status('neutral', 'Schedule off', `${points} available. Automatic backups are disabled.`, restore);
  }
  if (backups.filesystem.available_bytes == null) {
    return status('unavailable', 'Backup space unconfirmed', 'Backup inventory is available. Free space could not be measured.', detail);
  }
  return status('success', 'Inventory checks passed', detail, restore);
}

function coverageStatus(coverage: MetadataOverview, market?: Market): Status {
  const scope = market?.label;
  if (!coverage.observed) {
    return status('neutral', 'No items observed', 'Item coverage is based on observed catalogue items.', scope);
  }
  if (!Number.isFinite(coverage.attributes_available)) {
    return status('unavailable', 'Coverage unconfirmed', 'An item attribute measurement is unavailable.', scope);
  }
  const missingAttributes = Math.max(coverage.observed - coverage.attributes_available, 0);
  if (coverage.missing_names || coverage.icons_missing || missingAttributes || coverage.failed_or_blocked) {
    const missing = [
      coverage.missing_names && count(coverage.missing_names, 'missing name'),
      coverage.icons_missing && count(coverage.icons_missing, 'missing icon'),
      missingAttributes && `${count(missingAttributes, 'item')} without stored attributes`,
    ].filter(Boolean).join(' · ');
    const blocked = coverage.failed_or_blocked ? `${count(coverage.failed_or_blocked, 'item')} still unnamed after a provider error or access restriction.` : undefined;
    return status('warning', 'Coverage gaps', missing || blocked, [scope, missing && blocked].filter(Boolean).join(' · '));
  }
  return status('success', 'Core coverage available', `Names, icons, and attributes are stored for all ${count(coverage.observed, 'observed item')}.`, scope);
}

function sourceStatus(sources: MetadataSourceSummary[]): Status {
  const enabled = sources.filter(source => source.enabled);
  const needsReview = enabled.filter(source => source.tone === 'warning');
  if (needsReview.length) {
    const detail = needsReview.length === 1 ? undefined : `${count(needsReview.length, 'source')} awaiting review.`;
    const blocked = needsReview.length === enabled.length && needsReview.every(source => source.label === 'Recovery blocked');
    return status(blocked ? 'error' : 'warning', blocked ? 'Recovery blocked' : 'Source needs review',
      `${needsReview[0].name} · ${needsReview[0].label}.`, detail);
  }
  const automatic = enabled.filter(source => source.automatic);
  if (!automatic.length) {
    return status('neutral', 'Automatic recovery off', enabled.length
      ? `${count(enabled.length, 'enabled source')}. Automatic recovery is off.`
      : 'No metadata sources are enabled.');
  }
  const successful = automatic.filter(source => source.lastSuccess).length;
  if (successful < automatic.length) {
    return status('neutral', 'Awaiting source evidence', `${count(automatic.length - successful, 'automatic source')} without a recorded success.`);
  }
  return status('success', 'No reported blockers', `${count(automatic.length, 'automatic source')} with recorded successful requests.`);
}

function deviceStatus(devices: DeviceSummary): Status {
  const authorized = count(devices.authorized, 'authorized device');
  if (!devices.authorized) {
    return status('neutral', 'No authorized devices', 'There are no Companion or legacy devices with current access.');
  }
  const recent = `${count(devices.recently_connected, 'Companion device')} contacted Market in the last ${devices.recent_window_minutes ?? 15} minutes.`;
  return devices.recently_connected
    ? status('success', 'Recent activity', recent, `${authorized}.`)
    : status('neutral', 'No recent activity', recent, `${authorized}.`);
}

function ModuleCard({ module }: { module: Module }) {
  return <article className="overview-module" data-tone={module.tone} aria-labelledby={`overview-${module.id}`}>
    <div className="overview-module-heading">
      <span className="overview-signal" aria-hidden="true">{signals[module.tone]}</span>
      <div>
        <h4 id={`overview-${module.id}`}>{module.title}</h4>
        <span className="overview-module-status">{module.label}</span>
      </div>
    </div>
    <p className="overview-module-reason">{module.reason}</p>
    {module.detail && <p className="overview-module-detail">{module.detail}</p>}
    <div className="overview-module-links">
      {module.links.map(link => <a href={link.href} onClick={followItem} key={link.href}>
        {link.label}<span aria-hidden="true"> →</span>
      </a>)}
    </div>
  </article>;
}

function StatusSummary({ modules }: { modules: Module[] }) {
  const total = (tone: Tone) => modules.filter(module => module.tone === tone).length;
  const problems = total('error'), warnings = total('warning'), unavailable = total('unavailable'), loading = total('loading');
  const issueCount = problems + warnings;
  const parts = [
    problems && count(problems, 'problem'),
    warnings && `${warnings} to review`,
    unavailable && `${unavailable} unavailable`,
    loading && `${loading} checking`,
    total('success') > 0 && `${total('success')} passing`,
  ].filter(Boolean).join(' · ');
  const tone = problems ? 'error' : warnings ? 'warning' : unavailable ? 'unavailable' : loading ? 'loading' : 'neutral';
  const summary = issueCount ? `${count(issueCount, 'module')} need${issueCount === 1 ? 's' : ''} attention`
    : unavailable ? 'Some checks are unavailable' : loading ? 'Checks in progress' : 'No problems reported by available checks';
  return <div className="overview-summary" data-tone={tone} role="status">
    <span className="overview-signal" aria-hidden="true">{signals[tone]}</span>
    <div><strong>{summary}</strong>{parts && <p>{parts}</p>}</div>
  </div>;
}

export function AdministrationOverview({
  access, storage, backups, coverage, coverageMarket, devices, markets, marketStatus, sources, pending, errors,
}: OverviewProps) {
  const now = Date.now();
  const checks = marketStatusCards(markets, marketStatus, now);
  const result = <T,>(key: Check, data: T | undefined, subject: string, render: (data: T) => Status) =>
    data !== undefined && !errors?.[key] ? render(data) : waiting(!errors?.[key] && Boolean(pending?.[key]), subject);
  const coverageCheck = marketStatus && marketStatus !== 'available'
    ? waiting(marketStatus === 'loading', 'the market for item coverage')
    : !coverageMarket && !coverage && !markets.length
      ? status('neutral', 'No market configured', 'Item coverage needs a market with observed catalogue items.')
      : result('coverage', coverage, 'item coverage', value => coverageStatus(value, coverageMarket));
  const metadataLink = sectionLink('metadata', 'Review item coverage');
  if (coverageMarket) metadataLink.href += `&market_id=${coverageMarket.id}`;
  const marketModules: Module[] = [
    { id: 'collection', title: 'Collection', ...checks.collection, links: [sectionLink('collection', 'Review collection checks')] },
    { id: 'markets', title: 'Markets & schedules', ...checks.schedules, links: [sectionLink('markets', 'Manage market schedules')] },
    { id: 'metadata', title: 'Item Metadata', ...coverageCheck, links: [metadataLink] },
    { id: 'sources', title: 'Data Sources', ...result('sources', sources, 'metadata sources', sourceStatus), links: [sectionLink('sources', 'Review data sources')] },
    { id: 'storage', title: 'Storage capacity', ...result('storage', storage, 'database storage measurements', capacityStatus), links: [{ href: storageUrl('maintenance'), label: 'Review storage safeguards' }] },
    { id: 'backups', title: 'Backups', ...result('backups', backups, 'the backup inventory', value => backupStatus(value, now)), links: [{ href: storageUrl('backups'), label: 'Review backups' }] },
  ];
  const accessModules: Module[] = [
    { id: 'members', title: 'Members & invitations',
      ...result('access', access, 'member and invitation counts', value => status(
        value.active_admins ? 'success' : 'error', value.active_admins ? 'Administrator access available' : 'No active administrator',
        `${count(value.active_members, 'active account')}, including ${count(value.active_admins, 'administrator')}.`,
        `${count(value.pending_invitations, 'open invitation')}.`)),
      links: [sectionLink('members', 'Manage members'), sectionLink('invitations', 'View invitations')] },
    { id: 'devices', title: 'Devices', ...result('devices', devices, 'device activity', deviceStatus), links: [sectionLink('devices', 'Manage devices')] },
    { id: 'security', title: 'Security events',
      ...result('access', access, 'security activity', value => status('neutral', 'Activity log',
        value.latest_security_event ? <>Last recorded event <LocalTime value={value.latest_security_event}/></> : 'No security events recorded.')),
      links: [sectionLink('security', 'Review security events')] },
  ];

  return <section className="administration-overview" aria-label="Operational overview">
    <h2>System status</h2>
    <StatusSummary modules={[...marketModules, ...accessModules]}/>
    <section className="overview-module-group" aria-label="Market data and recovery">
      <h3 className="overview-group-title">Market data &amp; recovery</h3>
      <div className="overview-module-grid">{marketModules.map(module => <ModuleCard key={module.id} module={module}/>)}</div>
    </section>
    <section className="overview-module-group" aria-label="Account access">
      <h3 className="overview-group-title">Account access</h3>
      <div className="overview-module-grid">{accessModules.map(module => <ModuleCard key={module.id} module={module}/>)}</div>
    </section>
  </section>;
}
