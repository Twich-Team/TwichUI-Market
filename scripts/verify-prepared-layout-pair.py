#!/usr/bin/env python3
"""Read-only comparison of two CLOSED, private native publications; never runs Lua.

Usage: python verify_layout_pair.py SNAPSHOT16_ADDONS SNAPSHOT32_ADDONS
This supplements the production publisher's validation; it is not a replacement
for native admission, Merkle verification, or actual game acceptance.
"""
import hashlib
import json
import re
import sys
from pathlib import Path


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


LITERAL = r'"(?:[^"\\\r\n]|\\[0-9]{3})*"'


def literal(text):
    need(re.fullmatch(LITERAL, text), "unexpected Lua literal")
    return re.sub(r'\\([0-9]{3})', lambda m: chr(int(m[1])), text[1:-1])


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def read(addons, count):
    root = (addons / "TwichUI_MarketData/Data.lua").read_text(encoding="ascii")
    pattern = (r'TwichUIMarketData = \{ summary_version = 2, manifest = (' + LITERAL
               + r'), bank = (' + LITERAL + r'), receipt = (' + LITERAL
               + r'), prepared = (' + LITERAL + r') \}\n?')
    match = re.fullmatch(pattern, root)
    need(match, "not a supported prepared root (legacy fallback is not a layout trial)")
    manifest, bank, receipt, prepared = map(literal, match.groups())
    h, a = json.loads(manifest), json.loads(prepared)
    need(bank in ("A", "B"), "bank")
    need(h["contract_version"] == h["schema_version"] == 3, "source contract")
    need(a["version"] == 1 and a["partitions_count"] == count and a["record_width"] == 135, "layout")
    need(h["generation_id"] == a["source_generation_id"] == json.loads(receipt)["generation_id"], "generation")
    need(sha(canonical({k: v for k, v in h.items() if k != "generation_id"})) == h["generation_id"], "manifest digest")
    need(sha(canonical({k: v for k, v in a.items() if k != "attestation_id"})) == a["attestation_id"], "attestation digest")
    need({p["bucket"] for p in h["history_partitions"]} == set(range(64)), "expected all 64 history descriptors")
    histories = {}
    for p in h["history_partitions"]:
        bucket = p["bucket"]
        name = f"TwichUI_MarketHistoryPart{bank}{bucket:02}"
        text = (addons / name / "Data.lua").read_text(encoding="ascii")
        prefix = 'TwichUIMarketHistoryParts = TwichUIMarketHistoryParts or {}\n'
        prefix += f'TwichUIMarketHistoryParts["{bank}{bucket:02}"] = '
        need(text.startswith(prefix), "history identity")
        raw = literal(text[len(prefix):].rstrip("\n")).encode()
        need(len(raw) == p["bytes"] and sha(raw) == p["sha256"], "history integrity")
        histories[bucket] = sha(raw)
    rows = []
    need(len(a["partitions"]) == count, "prepared descriptor count")
    for p in a["partitions"]:
        bucket = p["bucket"]
        name = f"TwichUI_MarketCurrentPart{bank}{bucket:02}"
        text = (addons / name / "Data.lua").read_text(encoding="ascii")
        prefix = 'TwichUIMarketCurrentParts = TwichUIMarketCurrentParts or {}\n'
        prefix += f'TwichUIMarketCurrentParts["{bank}{bucket:02}"] = {{ version = 1, layout = {count}, content_id = "{p["sha256"]}", data = "'
        need(text.startswith(prefix), "current identity")
        match = re.fullmatch(r'([0-9a-fz]*)", proofs = "([0-9a-f]*)" \}\n?', text[len(prefix):])
        need(match, "current transport")
        data = match[1]
        need(len(data) == 135 * p["record_count"], "current record count")
        part_rows = [data[i:i + 135] for i in range(0, len(data), 135)]
        need(all(int(row[:8], 16) % count == bucket for row in part_rows), "current partition identity")
        rows.extend(part_rows)
    need(len(rows) == len({r[:72] for r in rows}) == h["record_count"] == a["record_count"], "identity/count")
    return h, histories, sorted(rows), a["attestation_id"]


def main():
    need(len(sys.argv) == 3, "usage: verify_layout_pair.py SNAPSHOT16_ADDONS SNAPSHOT32_ADDONS")
    x, y = read(Path(sys.argv[1]), 16), read(Path(sys.argv[2]), 32)
    need(x[0] == y[0], "different source generations/manifests: reject pair, recapture")
    need(x[1] == y[1], "different history bytes")
    need(x[2] == y[2], "different exact current tuples/prices/variants")
    print(json.dumps({"pair_matches": True, "generation": x[0]["generation_id"],
                      "history_partitions": 64, "current_records": len(x[2]),
                      "current_tuple_sha256": sha("".join(x[2]).encode()),
                      "attestation_16": x[3], "attestation_32": y[3]}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, UnicodeError, TypeError) as error:
        sys.exit("PAIR REFUSED: " + str(error))
