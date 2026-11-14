"""Explicit per-listener security settings; no arbitrary forwarded-header trust."""
import os
SESSION_ORIGIN=os.environ.get('APP_ORIGIN','https://localhost')
SESSION_COOKIE_NAME=os.environ.get('SESSION_COOKIE_NAME','market_session')
ALLOW_LEGACY_SESSIONS=os.environ.get('ALLOW_LEGACY_SESSIONS','false').lower()=='true'
READ_ONLY=os.environ.get('APP_READ_ONLY','false').lower()=='true'
INGRESS_TOKEN=os.environ.get('TRUSTED_INGRESS_TOKEN','')
if INGRESS_TOKEN and len(INGRESS_TOKEN)<32:raise RuntimeError('Ingress authentication token must contain at least 32 characters')
