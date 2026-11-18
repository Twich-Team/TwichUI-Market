FROM twichui-market-backend:retention-activation-base-fe92999
COPY backend/market/retention.py backend/market/retention_worker.py /app/market/
COPY backend/market/retention.py backend/market/retention_worker.py /usr/local/lib/python3.12/site-packages/market/
LABEL gg.twich.market.base-source="fe92999cc969a23684f3023638673c656efb3bce" gg.twich.market.patch-source="3ebd8b3c8b613ca8ed42a85614679a824ff85033"
