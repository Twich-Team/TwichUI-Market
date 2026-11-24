FROM node:24-bookworm-slim
WORKDIR /fixture
COPY deploy/review/backup-fixture.mjs web/e2e/storage-dashboard-fixtures.ts ./
USER node
CMD ["node", "backup-fixture.mjs"]
