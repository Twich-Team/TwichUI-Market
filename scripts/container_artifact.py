"""Independent, non-executing inspection of the fixed DEV/production transport.

Only known generated Lua syntax is accepted. Host zlib is not Forever evidence.
"""
import base64
import re
import zlib
from pathlib import Path

BLOCK = 524288
LITERAL = r'"(?:[^"\\\r\n]|\\[0-9]{3})*"'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def literal(text):
    return re.sub(r'\\([0-9]{3})', lambda m: chr(int(m[1])), text[1:-1])


def stream(text, pos):
    need(text[pos:pos+1] == '{', 'container stream syntax')
    pos += 1
    out = []
    while not text.startswith(' }', pos):
        m = re.match(r'\{ bytes = ([0-9]+), payload = (' + LITERAL + r') \},', text[pos:])
        need(m, 'container block syntax')
        size = int(m[1]); encoded = literal(m[2])
        need(0 < size <= BLOCK and len(encoded) <= 700000 and len(out) < 8, 'container block bound')
        raw = base64.b64decode(encoded, validate=True)
        decoder = zlib.decompressobj(-15)
        value = decoder.decompress(raw, size + 1)
        need(len(value) == size and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail, 'raw Deflate boundary')
        out.append(value); pos += m.end()
    need(all(len(v) == BLOCK for v in out[:-1]), 'noncanonical block boundary')
    return b''.join(out), pos + 2


def read(addons, bank, generation):
    result = {}
    for kind, groups in [('Current', 2), ('History', 4)]:
        records = {}; result[kind] = records
        g = 'TwichUIMarketCompressed' + kind
        for group in range(groups):
            n = f'TwichUI_Market{kind}Container{bank}{group:02}'
            path = Path(addons) / n / 'Data.lua'
            need(path.stat().st_size <= 8 * 1024 * 1024, 'container file bound')
            text = path.read_text(encoding='ascii')
            prefix = f'{g} = {g} or {{}}\n'
            need(text.startswith(prefix), 'container global')
            pos = len(prefix)
            while pos < len(text):
                m = re.match(re.escape(g) + r'\["([AB])([0-9]{2})"\] = \{ version = 1, generation = (' + LITERAL + r'), content_id = (' + LITERAL + r'), data = ', text[pos:])
                need(m, 'container part syntax')
                bucket = int(m[2]); need(m[1] == bank and bucket // 16 == group and bucket not in records, 'container mapping')
                need(literal(m[3]) == generation, 'container generation')
                pos += m.end(); data, pos = stream(text, pos)
                proofs = None
                if kind == 'Current':
                    need(text.startswith(', proofs = ', pos), 'proof field'); pos += 11
                    proofs, pos = stream(text, pos)
                need(text.startswith(' }\n', pos), 'container closing syntax'); pos += 3
                records[bucket] = dict(content_id=literal(m[4]), data=data, proofs=proofs)
        need(kind != 'Current' or set(records) == set(range(32)), 'all current logical partitions')
    return result
