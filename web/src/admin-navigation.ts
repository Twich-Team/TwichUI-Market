export const administrationGroups = [
  { label: 'Administration', sections: [{ id: 'overview', label: 'Overview' }] },
  { label: 'Market data', sections: [
    { id: 'markets', label: 'Markets & schedules' },
    { id: 'collection', label: 'Collection' },
    { id: 'metadata', label: 'Item Metadata' },
    { id: 'sources', label: 'Data Sources' },
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
  const params = new URLSearchParams(url.split('?')[1]);
  const section = params.get('admin_tab');
  return administrationGroups.some(group => group.sections.some(item => item.id === section))
    ? section!
    : params.get('metadata_view') === 'tracker' ? 'metadata' : 'overview';
}
