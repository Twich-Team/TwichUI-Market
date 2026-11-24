ARG MARKET_BASE_IMAGE=twichui-market-backend:nas-production-base-cae89b4d
FROM ${MARKET_BASE_IMAGE}
ARG MARKET_SOURCE_COMMIT
LABEL org.opencontainers.image.revision=$MARKET_SOURCE_COMMIT
COPY backend/market/bridge_api.py backend/market/maintenance.py backend/market/app.py backend/market/backup_management.py backend/market/retention.py backend/market/retention_worker.py backend/market/compaction_safety.py backend/market/maintenance_health.py backend/market/maintenance_resources.py /app/market/
