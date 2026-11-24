ARG MARKET_ASSET_IMAGE=twichui-market-web:nas-candidate
FROM ${MARKET_ASSET_IMAGE} AS assets
FROM twichui-market-web:nas-proxy-base-f48f8f1a
ARG MARKET_SOURCE_COMMIT
LABEL org.opencontainers.image.revision=$MARKET_SOURCE_COMMIT
# Preserve the deployed Caddy runtime and bind-mounted ingress configuration.
COPY --from=assets /srv/ /srv/
