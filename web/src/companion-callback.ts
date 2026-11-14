/** Accept only the exact native loopback navigation shape; never a general redirect. */
export function companionCallback(value: string): string {
  if (value.length > 2048)
    throw new Error(
      "The companion return address is invalid. Start again in the companion.",
    );
  const uri = new URL(value);
  const port = Number(uri.port);
  const state = uri.searchParams.get("state") || "";
  const code = uri.searchParams.get("code");
  const denied = uri.searchParams.get("error");
  const pairs = [...uri.searchParams];
  if (
    uri.protocol !== "http:" ||
    uri.hostname !== "127.0.0.1" ||
    port < 1024 ||
    port > 65535 ||
    !Number.isInteger(port) ||
    uri.username ||
    uri.password ||
    uri.hash ||
    uri.pathname !== "/companion/callback" ||
    !value.startsWith(`http://127.0.0.1:${port}/companion/callback?`) ||
    pairs.length !== 2 ||
    uri.searchParams.getAll("state").length !== 1 ||
    !/^[A-Za-z0-9_-]{43,128}$/.test(state) ||
    !(
      (code && /^[A-Za-z0-9_-]{43}$/.test(code) && !denied) ||
      (denied === "access_denied" && !code)
    )
  ) {
    throw new Error(
      "The companion return address is invalid. Start again in the companion.",
    );
  }
  return uri.href;
}
