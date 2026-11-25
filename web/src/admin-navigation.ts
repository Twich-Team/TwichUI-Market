export const administrationGroups = [
  { label: 'Administration', sections: [{ id: 'overview', label: 'Overview' }] },
  { label: 'Market data', sections: [
    { id: 'markets', label: 'Markets & schedules' },
    { id: 'collection', label: 'Collection' },
    { id: 'metadata', label: 'Item Metadata' },
    { id: 'sources', label: 'Data Sources' },
    { id: 'waylaid-crates', label: 'Waylaid Crates' },
    { id: 'crafting-writs', label: 'Crafting Writs' },
    { id: 'storage', label: 'Storage & Backups' },
  ] },
  { label: 'Account access', sections: [
    { id: 'members', label: 'Members' },
    { id: 'invitations', label: 'Invitations' },
    { id: 'devices', label: 'Devices' },
    { id: 'security', label: 'Security events' },
  ] },
];

export function administrationSection(url: string) {
  const [path, search] = url.split('?');
  if (path === '/admin/crafting-writs') return 'crafting-writs';
  if (path === '/admin/waylaid-crates') return 'waylaid-crates';
  const params = new URLSearchParams(search);
  const section = params.get('admin_tab');
  return administrationGroups.some(group => group.sections.some(item => item.id === section))
    ? section!
    : params.get('metadata_view') === 'tracker' ? 'metadata' : 'overview';
}

export function administrationUrl(section: string) {
  if (section === 'overview') return '/administration';
  if (section === 'crafting-writs') return '/admin/crafting-writs';
  if (section === 'waylaid-crates') return '/admin/waylaid-crates';
  return `/administration?admin_tab=${section}`;
}
