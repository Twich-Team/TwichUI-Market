"""Deterministic SYNTHETIC scale inputs; no production database or observations.

Prices are constant 100 copper when listed, making all supported medians/means
independently known. Missing/absent/unknown dates are never filled with prices.
No contract limits are changed and oversized workloads are not truncated.
"""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 32 * 1024 * 1024
PROFILES = ("one", "two-gap", "fourteen", "sixty", "sparse-sixty", "mixed", "mixed-provisional", "historical-only", "injection")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def header(profile):
    assert profile in PROFILES
    provisional = profile == "mixed-provisional"
    name = "source-provisional-generation.json" if provisional else "source-canonical-generation.json"
    original = json.loads((ROOT / "contracts/bridge/v1" / name).read_text())
    template = original["records"][-1]
    h = {k: deepcopy(v) for k, v in original.items() if k not in ("records", "integrity", "generation_id")}
    offsets = {
        "one": [0], "two-gap": [0, 2], "fourteen": list(range(14)),
        "sixty": list(range(60)), "sparse-sixty": [0, 29, 55, 59],
        "mixed": list(range(0, 60, 5)) + [59],
        "mixed-provisional": list(range(0, 60, 5)) + [59],
        "historical-only": [0, 2],
        "injection": [0, 2],
    }[profile]
    first = date(2026, 11, 15) - timedelta(days=offsets[-1])
    prototype = original["observations"][0]
    h["observations"] = []
    for i, offset in enumerate(offsets):
        day = (first + timedelta(days=offset)).isoformat()
        o = deepcopy(prototype)
        o.update(observation_id=str(1000+i), snapshot_id=str(2000+i), utc_day=day,
                 observed_at=day+"T12:00:00.123456Z", upstream_updated_at=day+"T11:00:00Z",
                 synthetic=True, scope_complete=not (profile.startswith("mixed") and (i % 4 == 1 or i == len(offsets)-1)))
        o["payload_sha256"] = sha({"synthetic": True, "observation": i, "profile": profile})
        o["snapshot_content_sha256"] = sha({"synthetic": True, "snapshot": i, "profile": profile})
        h["observations"].append(o)
    h["watermark_observation_id"] = h["observations"][-1]["observation_id"]
    h["current_observation_ref"] = len(offsets)-1
    h["coverage"].update(history_from_day=first.isoformat(), history_through_day="2026-11-15",
        available_observed_days=len(offsets), delivered_observed_days=len(offsets),
        current_complete=h["observations"][-1]["scope_complete"])
    return h, template


def record(h, template, index, profile):
    r = deepcopy(template)
    item = 10000 + index
    r.update(item_id=item, variant_json=canonical({"id": item}).decode())
    r["variant_key"] = hashlib.sha256(r["variant_json"].encode()).hexdigest()
    if profile == "injection":
        r["variant_json"] = canonical({"id":item,"text":'"; M15_EXECUTED=true; os.execute("bad"); --\n\\\0😀'}).decode()
        r["variant_key"] = hashlib.sha256(r["variant_json"].encode()).hexdigest()
    model = h["pricing_algorithm"] == "twichui-pricing-v1"
    historical_only = profile == "historical-only" or profile != "one" and index % 17 == 0
    latest = len(h["observations"])-1
    daily = []
    for i, o in enumerate(h["observations"]):
        if model and not o["scope_complete"]:
            continue
        state = "unknown" if not o["scope_complete"] else "absent" if historical_only and i == latest else "listed"
        d = deepcopy(template["daily"][0])
        d.update(observation_ref=i, state=state, minimum_copper="100" if state == "listed" else None,
                 recent_copper="100" if state == "listed" else None,
                 supply=10 if state == "listed" else 0 if state == "absent" else None,
                 priced_supply=10 if state == "listed" else 0 if state == "absent" else None,
                 listing_count=3 if state == "listed" else 0 if state == "absent" else None)
        daily.append(d)
    r["daily"] = daily
    state = "unknown" if not h["coverage"]["current_complete"] else "absent" if historical_only else "listed"
    c = r["current"]
    c.update(state=state, observation_ref=latest, complete=h["coverage"]["current_complete"],
             supply=10 if state == "listed" else 0 if state == "absent" else None,
             priced_supply=10 if state == "listed" else 0 if state == "absent" else None,
             listing_count=3 if state == "listed" else 0 if state == "absent" else None)
    priced = [d for d in daily if d["state"] == "listed"]
    recent = sum(h["observations"][d["observation_ref"]]["utc_day"] >= "2026-11-02" for d in priced)
    c["metrics"].update(minimum_copper="100" if state == "listed" else None,
                        recent_copper="100" if state == "listed" else None,
                        quantity_weighted_ask_copper="100" if state == "listed" else None,
                        market_value_copper="100" if recent else None,
                        historical_value_copper="100" if len(priced) >= 3 else None)
    c["coverage"].update(priced_days_14=recent, priced_days_60=len(priced), observed_days_60=len(daily))
    if state != "listed":
        r["distribution"], r["distribution_status"] = None, "unavailable"
    else:
        d = r["distribution"]
        if model:
            for k in d["quartiles"]:
                d["quartiles"][k] = "100"
            d["tiers"][0]["unit_copper"] = "100"
        else:
            for band in d["bands"]:
                band["minimum_copper"] = band["maximum_copper"] = "100"
    return r


def generate(count, profile):
    """Bound retained generator input; report exact full size even on refusal."""
    assert 1 <= count <= 100000
    h, template = header(profile)
    h["record_count"] = count
    records = []
    total = 2
    hasher = hashlib.sha256(b"[")
    for i in range(count):
        r = record(h, template, i, profile)
        text = canonical(r)
        assert len(text) <= 65536
        piece = (b"," if i else b"") + text
        total += len(piece)
        hasher.update(piece)
        if total <= MAX_BYTES:
            records.append(r)
        elif records:
            records.clear()
    hasher.update(b"]")
    h["generation_id"] = "0"*64
    h["integrity"] = dict(records_bytes=total, records_sha256=hasher.hexdigest(), manifest_sha256=sha({k:v for k,v in h.items() if k not in ("generation_id", "integrity")}))
    size = len(canonical(h)) + total + 11
    metadata = dict(origin="synthetic", eligible_records=count, profile=profile,
                    observation_dates=[o["utc_day"] for o in h["observations"]],
                    daily_dates_per_listed_variant=len(records[-1]["daily"]) if records else
                        sum(not (h["pricing_algorithm"]=="twichui-pricing-v1" and not o["scope_complete"]) for o in h["observations"]),
                    canonical_bytes=size, materialized_export_records=count if size <= MAX_BYTES else 0,
                    status="eligible" if size <= MAX_BYTES else "refused_contract_bytes")
    if size > MAX_BYTES:
        return None, metadata
    body = {k:v for k,v in h.items() if k not in ("generation_id", "integrity")}
    body["records"] = records
    h["generation_id"] = sha(body)
    h["records"] = records
    assert len(canonical(h)) == size
    metadata["generation_id"] = h["generation_id"]
    return h, metadata
