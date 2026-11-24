ARG MARKET_BASE_IMAGE=twichui-market-backend:nas-collector-base-ec94420d
FROM ${MARKET_BASE_IMAGE}
ARG MARKET_SOURCE_COMMIT
LABEL org.opencontainers.image.revision=$MARKET_SOURCE_COMMIT
# Preserve the exact live collector/ingestion modules and all runtime settings.
COPY backend/market/maintenance.py /app/market/maintenance.py
