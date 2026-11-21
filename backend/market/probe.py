"""Bounded, read-only Blizzard feasibility probes. No credentials in output."""
import argparse
import base64
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BYTES = 32 * 1024 * 1024
REGIONS = ("us", "eu", "kr", "tw")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


opener=build_opener(NoRedirect())


def request(url, *, token=None, data=None, authorization=None, conditional=None,timeout=45,max_bytes=MAX_BYTES):
    headers = {"Accept": "application/json", "User-Agent": "TwichUI-Market/0.1 feasibility"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if authorization:
        headers["Authorization"] = authorization
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    for name in ("If-None-Match", "If-Modified-Since"):
        if conditional and conditional.get(name):
            headers[name] = conditional[name]
    started = time.monotonic()
    try:
        response = opener.open(Request(url, data=data, headers=headers), timeout=timeout)
    except HTTPError as exc:
        response = exc
    with response:
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError("Response exceeds configured safety limit")
        metadata = {
            "url": url, "status": response.status,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(time.monotonic() - started, 3),
            "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
            "headers": {key: response.headers.get(key) for key in (
                "Last-Modified", "ETag", "Date", "Cache-Control", "Retry-After", "Battlenet-Namespace",
                "RateLimit-Limit", "RateLimit-Remaining", "RateLimit-Reset", "X-RateLimit-Remaining"
            )},
        }
    return metadata, body


def targets(ruleset, house):
    paths = ["/data/wow/ruleset/index", f"/data/wow/ruleset/{ruleset}",
             f"/data/wow/ruleset/{ruleset}/auctions/",
             f"/data/wow/ruleset/{ruleset}/auctions/{house}",
             f"/data/wow/ruleset/{ruleset}/auctions/{house}/commodities"]
    return paths


def summarize(body):
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object")
    result = {"keys": sorted(payload)}
    for key in ("auctions", "rulesets"):
        if isinstance(payload.get(key), list):
            result[f"{key}_count"] = len(payload[key])
    # Structural evidence only: do not print upstream error text or arbitrary links.
    if isinstance(payload.get("auctions"), list) and payload["auctions"]:
        first = payload["auctions"][0]
        if isinstance(first, dict):
            result["auction_fields"] = sorted(first)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", choices=REGIONS, required=True)
    parser.add_argument("--ruleset", type=int, required=True)
    parser.add_argument("--house", type=int, required=True)
    args = parser.parse_args()
    client_id = os.environ.get("BLIZZARD_CLIENT_ID")
    secret = os.environ.get("BLIZZARD_CLIENT_SECRET")
    if not client_id or not secret:
        parser.exit(2, "Live verification blocked: set BLIZZARD_CLIENT_ID and BLIZZARD_CLIENT_SECRET.\n")
    if args.ruleset <= 0 or args.house <= 0:
        parser.error("ruleset and house must be positive")
    try:
        basic = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
        meta, body = request("https://oauth.battle.net/token", data=b"grant_type=client_credentials",
                             authorization=f"Basic {basic}")
        # OAuth metadata body hash is deliberately excluded to avoid token fingerprints.
        if meta["status"] != 200:
            parser.exit(1, f"OAuth failed with HTTP {meta['status']}; no response body logged.\n")
        token = json.loads(body)["access_token"]
        for path in targets(args.ruleset, args.house):
            url = f"https://{args.region}.api.blizzard.com{path}?" + urlencode({
                "namespace": f"dynamic-forever-{args.region}", "locale": "en_US"})
            meta, body = request(url, token=token)
            try:
                meta["structure"] = summarize(body)
            except (ValueError, UnicodeDecodeError):
                meta["structure"] = {"invalid_json": True}
            print(json.dumps(meta), flush=True)
            if meta["status"] in (401, 403, 429) or meta["status"] >= 500:
                return 1
            time.sleep(1)
    except (URLError, TimeoutError, ValueError, KeyError):
        parser.exit(1, "Probe failed: transport or malformed response; details suppressed to protect credentials.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
