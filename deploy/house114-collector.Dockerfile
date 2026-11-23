# The operator must verify this retained local alias resolves to exact image
# sha256:aab0d6585115da68811f6c3ecebde4233d8e1a73306b2fc8f2d5ba6b1daad50b.
# No dependency, collector-loop, credential, configuration or schema changes.
FROM twichui-market-collector-base:house114-aab0d6585115
COPY backend/market/ingest.py backend/market/feed_collection.py /app/market/
COPY backend/market/ingest.py backend/market/feed_collection.py /usr/local/lib/python3.12/site-packages/market/
ARG REPAIR_SOURCE
LABEL gg.twich.market.collector-repair-source="${REPAIR_SOURCE}"
