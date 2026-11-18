# Preserve the exact deployed Workshop/retention runtime and installed dependencies.
FROM twichui-market-backend:sync-performance-base-631c5e03
ARG SYNC_SOURCE
COPY backend/market/app.py backend/market/security.py backend/market/sync_api.py backend/market/sync_generation.py backend/market/sync_performance.py backend/market/workshop_summary.py /app/market/
COPY backend/market/app.py backend/market/security.py backend/market/sync_api.py backend/market/sync_generation.py backend/market/sync_performance.py backend/market/workshop_summary.py /usr/local/lib/python3.12/site-packages/market/
LABEL gg.twich.market.sync-source=$SYNC_SOURCE
