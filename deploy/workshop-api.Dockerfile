# Preserve the exact live retention recovery/selector patch and installed deps.
FROM twichui-market-backend:retention-local-only-selector-3ebd8b3-final
COPY backend/market/app.py backend/market/security.py backend/market/bridge_api.py backend/market/workshop_summary.py /app/market/
COPY backend/market/app.py backend/market/security.py backend/market/bridge_api.py backend/market/workshop_summary.py /usr/local/lib/python3.12/site-packages/market/
COPY contracts/workshop-summary/v1 /contracts/workshop-summary/v1
LABEL gg.twich.market.workshop-source="47ab3cf52b58cafb3006523fc4e96e11943d2c9d"
