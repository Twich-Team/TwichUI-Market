export interface InstallerDownload {
  ready: boolean;
  version: string | null;
  download_url: string | null;
}
export function companionDownloadUrl(
  release: InstallerDownload | null | undefined,
  channel: "stable" | "private-beta" = "stable",
  origin = location.origin,
): string | null {
  if (!release?.ready || !release.version || !release.download_url) return null;
  const version = channel === "stable"
    ? /^2\.(?:0|[1-9][0-9]{0,3})\.(?:0|[1-9][0-9]{0,3})$/
    : /^2\.(?:0|[1-9][0-9]{0,3})\.(?:0|[1-9][0-9]{0,3})-beta\.[1-9][0-9]{0,3}$/;
  if (!version.test(release.version)) return null;
  try {
    const uri = new URL(release.download_url, origin);
    const prefix = channel === "stable" ? "releases" : "private-beta";
    return uri.origin === origin && !uri.username && !uri.password && !uri.hash && !uri.search &&
      uri.pathname === `/api/v1/companion/${prefix}/${release.version}/windows-x64`
      ? uri.pathname : null;
  } catch { return null; }
}
