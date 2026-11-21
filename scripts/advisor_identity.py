"""Inactive U2 exact identity resolver; no game calls, UI, prices or runtime hooks.

Trust is injected explicitly: a pinned U1 context, pinned per-item candidate
bundle and independently approved descriptor-equivalence evidence. No built-in
native equivalences exist. A caller's untrusted 'verified' flag is never evidence.
"""
import hashlib
import json
import re

import jsonschema
import advisor_summary as u1

MAX_ITEM_CANDIDATES = 128
MAX_EQUIVALENCES = 32
MAX_BUNDLE_BYTES = 64 * 1024
MAX_IDENTITY_BYTES = 4096
MAX_LINK_BYTES = 1000
MAX_LINK_FIELDS = 64
CONTEXT_FIELDS = ('generation_id', 'issuer_id', 'market', 'pricing_algorithm',
                  'history_basis', 'source_kind', 'confidence_ceiling', 'can_satisfy_local_competition')
ATTRIBUTES = {'link_fields', 'item_key', 'suffix_id', 'random_property_id', 'bonus_ids', 'modifiers'}
KEY_FIELDS = {'itemID', 'itemLevel', 'itemSuffix', 'battlePetSpeciesID'}


class Refusal(ValueError):
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status, self.reason = status, reason


def require(ok, reason, status='invalid_input'):
    if not ok:
        raise Refusal(status, reason)


def integer(value, low=0, high=2**31 - 1):
    require(type(value) is int and low <= value <= high, 'integer_range')


def sha(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None, 'invalid_hash')


def closed(value, fields):
    require(type(value) is dict and set(value) == set(fields), 'object_fields')


def bounded_copy(value, limit):
    # Fixed-depth canonical serializer rejects floats/unsupported JSON. Size bounds
    # apply to serialized input; callers must also bound decoding before this API.
    try:
        raw = u1.canonical(value)
        require(len(raw) <= limit, 'input_byte_limit')
        return json.loads(raw)
    except (TypeError, ValueError, RecursionError, OverflowError) as error:
        if isinstance(error, Refusal):
            raise
        raise Refusal('invalid_input', 'malformed_value') from error


def context(manifest):
    """Project established fields without inventing another market representation."""
    return {key: manifest[key] for key in CONTEXT_FIELDS}


def validate_context(value):
    closed(value, CONTEXT_FIELDS)
    for key, field in value.items():
        schema = u1.OLD_SCHEMA['properties'][key]
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(field)
    sha(value['generation_id'])
    market = value['market']
    for key in ('house_id', 'server_market_id', 'transport_ruleset_id'):
        integer(market[key], 1)
    require(market['mapping_verified'] is True and market['player_ruleset'] is not None,
            'mapping_unverified', 'unverified_market')
    require(market['mapping_evidence_sha256'] is not None, 'mapping_evidence_missing', 'unverified_market')
    sha(market['mapping_evidence_sha256'])


def validate_identity(value):
    closed(value, ('item_id', 'attributes'))
    integer(value['item_id'], 1)
    attrs = value['attributes']
    require(type(attrs) is dict, 'attributes_object')
    require(not set(attrs) - ATTRIBUTES, 'unknown_attribute', 'unsupported')
    for key, data in attrs.items():
        if data is None:  # Unknown stays unknown, never a fabricated zero/default.
            continue
        if key in ('suffix_id', 'random_property_id'):
            integer(data, -(2**31 - 1))
        elif key == 'item_key':
            closed(data, KEY_FIELDS)
            for name, number in data.items():
                integer(number, -(2**31 - 1) if name == 'itemSuffix' else 0)
            require(data['itemID'] == value['item_id'], 'contradictory_item_id')
        elif key == 'link_fields':
            require(type(data) is list and 1 <= len(data) <= MAX_LINK_FIELDS, 'link_field_count')
            for token in data:
                require(type(token) is str and len(token) <= 11 and
                        re.fullmatch(r'(?:-?[0-9]+)?', token) is not None, 'link_field_syntax')
            require(data[0] == str(value['item_id']), 'contradictory_item_id')
        elif key == 'bonus_ids':
            require(type(data) is list and len(data) <= 32, 'bonus_count')
            for number in data:
                integer(number, 1)
        elif key == 'modifiers':
            require(type(data) is list and len(data) <= 16, 'modifier_count')
            seen = set()
            for modifier in data:
                closed(modifier, ('type', 'value'))
                integer(modifier['type'], 1)
                integer(modifier['value'], -(2**31 - 1))
                require(modifier['type'] not in seen, 'duplicate_modifier')
                seen.add(modifier['type'])
    # Cross-check only names whose equivalence is explicit within this input model.
    if attrs.get('item_key') is not None and attrs.get('suffix_id') is not None:
        require(attrs['item_key']['itemSuffix'] == attrs['suffix_id'], 'contradictory_suffix')


def parse_link(link, *, item_id=None, item_key=None):
    """Extract ID and retain ALL raw numeric fields, without assigning a layout.

    Mirrors native LinkUtil's item-body extraction and Workshop's raw-item form;
    adds strict framing/size/grammar checks. It does not interpret suffix/bonus
    positions or certify that a link is a complete native variant identity.
    """
    require(type(link) is str and len(link.encode('utf-8')) <= MAX_LINK_BYTES, 'link_size_or_type')
    match = re.fullmatch(r'item:([^|]+)', link) or re.fullmatch(
        r'(?:\|c[0-9a-fA-F]{8})?\|Hitem:([^|]+)\|h\[[^|\r\n]*\]\|h(?:\|r)?', link)
    require(match is not None, 'malformed_item_link')
    fields = match[1].split(':')
    require(re.fullmatch('[1-9][0-9]{0,9}', fields[0]) is not None, 'item_id_syntax')
    found = int(fields[0])
    require(item_id is None or (type(item_id) is int and item_id == found), 'contradictory_item_id')
    attrs = {'link_fields': fields}
    if item_key is not None:
        attrs['item_key'] = item_key
    value = bounded_copy({'item_id': found, 'attributes': attrs}, MAX_IDENTITY_BYTES)
    validate_identity(value)
    return value


def descriptor(text, item):
    require(type(text) is str and 1 <= len(text.encode('utf-8')) <= 4096, 'descriptor_size_or_type')
    try:
        value = json.loads(text)
        require(type(value) is dict and type(value.get('id')) is int and value['id'] == item,
                'descriptor_item_id')
        require(u1.canonical(value).decode() == text, 'descriptor_noncanonical')
    except (ValueError, TypeError, RecursionError) as error:
        if isinstance(error, Refusal):
            raise
        raise Refusal('invalid_input', 'malformed_descriptor') from error
    return value


def validate_equivalence(proof, item):
    closed(proof, ('format', 'issuer_id', 'market', 'game_identity', 'variant_json',
                   'identity_complete', 'provenance'))
    require(proof['format'] == 'twichui-item-equivalence-u2', 'equivalence_format')
    require(proof['identity_complete'] is True, 'equivalence_incomplete', 'insufficient_identity')
    validate_identity(proof['game_identity'])
    require(proof['game_identity']['item_id'] == item, 'equivalence_item_id')
    attrs = proof['game_identity']['attributes']
    require(bool(attrs) and all(v is not None for v in attrs.values()), 'equivalence_missing_attributes')
    descriptor(proof['variant_json'], item)
    closed(proof['provenance'], ('classification', 'reference'))
    require(proof['provenance']['classification'] in
            ('source_verified', 'recorded_upstream', 'repository_fixture', 'synthetic_control'), 'evidence_class')
    require(type(proof['provenance']['reference']) is str and
            1 <= len(proof['provenance']['reference']) <= 256, 'evidence_reference')


class Resolver:
    """One item, one generation. No global cache or partition scans.

    expected_context, expected_bundle_sha256 and the digest->proof dictionary
    must come from a trusted caller boundary, separately from the supplied bundle.
    An empty proof registry (the default) can never produce an exact result.
    """
    def __init__(self, expected_context, candidate_bundle, *, expected_bundle_sha256,
                 trusted_equivalences=None):
        self.error = None
        self.generation = None
        self.item = None
        self.candidates, self.equivalences = {}, {}
        try:
            expected = bounded_copy(expected_context, MAX_BUNDLE_BYTES)
            validate_context(expected)
            self.generation = expected['generation_id']
            if candidate_bundle is None:
                raise Refusal('unavailable', 'candidate_evidence_unavailable')
            bundle = bounded_copy(candidate_bundle, MAX_BUNDLE_BYTES)
            sha(expected_bundle_sha256)
            require(u1.digest(bundle) == expected_bundle_sha256, 'candidate_bundle_integrity')
            closed(bundle, ('context', 'item_id', 'complete', 'candidates'))
            validate_context(bundle['context'])
            for key in CONTEXT_FIELDS:
                if bundle['context'][key] != expected[key]:
                    status = 'unverified_market' if key in ('market', 'issuer_id') else 'invalid_input'
                    raise Refusal(status, 'market_or_issuer_mismatch' if status == 'unverified_market'
                                  else 'source_generation_or_contract_mismatch')
            self.item = bundle['item_id']
            integer(self.item, 1)
            require(type(bundle['complete']) is bool, 'candidate_completeness')
            require(bundle['complete'], 'incomplete_candidate_set', 'insufficient_identity')
            candidates = bundle['candidates']
            require(type(candidates) is list and len(candidates) <= MAX_ITEM_CANDIDATES, 'candidate_count')
            for row in candidates:
                closed(row, ('variant_key', 'variant_json', 'identity_basis', 'evidence_status'))
                key = row['variant_key']
                sha(key)
                require(key not in self.candidates, 'duplicate_candidate_identity')
                require(row['evidence_status'] in ('supported', 'historical_only', 'unsupported', 'unavailable'),
                        'candidate_evidence_status')
                require(row['identity_basis'] in ('exact_upstream', 'hash_only'), 'identity_basis')
                if row['identity_basis'] == 'hash_only':
                    require(row['variant_json'] is None, 'hash_only_descriptor')
                else:
                    descriptor(row['variant_json'], self.item)
                    require(hashlib.sha256(row['variant_json'].encode()).hexdigest() == key, 'variant_hash_mismatch')
                self.candidates[key] = row
            proofs = bounded_copy({} if trusted_equivalences is None else trusted_equivalences, MAX_BUNDLE_BYTES)
            require(type(proofs) is dict and len(proofs) <= MAX_EQUIVALENCES, 'equivalence_count')
            for pin, proof in proofs.items():
                sha(pin)
                require(u1.digest(proof) == pin, 'equivalence_integrity')
                validate_equivalence(proof, self.item)
                validate_context(dict(expected, market=proof['market'], issuer_id=proof['issuer_id']))
                require(proof['issuer_id'] == expected['issuer_id'] and proof['market'] == expected['market'],
                        'equivalence_market_mismatch', 'unverified_market')
                signature = u1.canonical(proof['game_identity'])
                self.equivalences.setdefault(signature, []).append((pin, proof))
        except (Refusal, jsonschema.ValidationError, KeyError, TypeError, ValueError, RecursionError) as error:
            self.error = error if isinstance(error, Refusal) else Refusal('invalid_input', 'malformed_source_evidence')
            self.candidates, self.equivalences = {}, {}

    def result(self, status, reason, identity=None, evidence_ids=()):
        return {'status': status, 'reason': reason, 'identity': identity,
                'generation_id': self.generation, 'evidence_ids': sorted(evidence_ids)}

    def resolve(self, identity):
        if self.error is not None:
            return self.result(self.error.status, self.error.reason)
        try:
            identity = bounded_copy(identity, MAX_IDENTITY_BYTES)
            validate_identity(identity)
            if identity['item_id'] != self.item:
                return self.result('not_found', 'item_not_in_candidate_bundle')
            attrs = identity['attributes']
            if not attrs or any(v is None for v in attrs.values()):
                return self.result('insufficient_identity', 'missing_variant_attributes')
            if not self.candidates:
                return self.result('not_found', 'identity_not_delivered')
            proofs = self.equivalences.get(u1.canonical(identity), [])
            if not proofs:
                if len(self.candidates) > 1:
                    return self.result('ambiguous', 'unverified_variant_equivalence')
                if next(iter(self.candidates.values()))['identity_basis'] == 'hash_only':
                    return self.result('unsupported', 'hash_only_identity')
                return self.result('insufficient_identity', 'equivalence_unverified')
            variants = {proof['variant_json'] for _, proof in proofs}
            if len(variants) != 1:
                return self.result('ambiguous', 'conflicting_equivalence_evidence')
            text = next(iter(variants))
            # Hash only the proven UPSTREAM descriptor, never a game link or item ID.
            key = hashlib.sha256(text.encode()).hexdigest()
            candidate = self.candidates.get(key)
            if candidate is None:
                return self.result('not_found', 'identity_not_delivered')
            if candidate['identity_basis'] == 'hash_only':
                return self.result('unsupported', 'hash_only_identity')
            if candidate['evidence_status'] != 'supported':
                return self.result('unsupported', 'candidate_' + candidate['evidence_status'])
            require(candidate['variant_json'] == text, 'conflicting_descriptor')
            return self.result('exact', 'trusted_descriptor_equivalence',
                               {'item_id': self.item, 'variant_key': key}, (pin for pin, _ in proofs))
        except (Refusal, TypeError, ValueError, RecursionError) as error:
            if isinstance(error, Refusal):
                return self.result(error.status, error.reason)
            return self.result('invalid_input', 'malformed_identity')

    def resolve_link(self, link, **observed):
        try:
            return self.resolve(parse_link(link, **observed))
        except (Refusal, UnicodeError, TypeError) as error:
            if isinstance(error, Refusal):
                return self.result(error.status, error.reason)
            return self.result('invalid_input', 'malformed_item_link')
