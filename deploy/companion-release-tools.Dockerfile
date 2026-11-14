# Build only the offline verifier; no GTK/WebView or private signing material.
ARG BACKEND_IMAGE
FROM rust:1.100.0-slim-bookworm AS verifier
WORKDIR /source
COPY desktop /source/desktop
RUN cargo build --manifest-path desktop/Cargo.toml --release --example verify_release --locked

# Supply the exact verified backend dependency image. This image is an operator
# tool only; it has no listener, collector, credentials or database dependency.
FROM ${BACKEND_IMAGE}
COPY --from=verifier /source/desktop/target/release/examples/verify_release /usr/local/bin/twichui-verify-release
COPY backend/market/companion_releases.py backend/market/release_publisher.py /app/market/
ENTRYPOINT ["python", "-m", "market.release_publisher"]
