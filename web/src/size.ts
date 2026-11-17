/** IEC binary units; input stays in bytes. */
export function formatBytes(value: number | null | undefined, digits=1): string {
  if (value == null || !Number.isFinite(value)) return 'Unavailable';
  const magnitude=Math.abs(value);
  const index=Math.min(4, magnitude < 1 ? 0 : Math.floor(Math.log(magnitude)/Math.log(1024)));
  const units=['B','KiB','MiB','GiB','TiB'];
  return `${(value/1024**index).toFixed(index===0 ? 0 : digits)} ${units[index]}`;
}
