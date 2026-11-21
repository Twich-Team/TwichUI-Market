"""Read-only bounded configuration/history guard for the approved API-only rollout.

Run inside the existing API with optional baseline JSON on stdin. Outputs hashes,
counts and public collection identity only; never credentials or raw records.
"""
import hashlib, json, sys
from sqlalchemy import select, text
from market.db import Base, engine
from market import models

baseline = json.load(sys.stdin) if '--verify' in sys.argv else None
tables = ['users','credentials','user_preferences','player_market_mappings',
          'market_verifications','retention_policy','retention_automation']
tables += sorted(n for n in Base.metadata.tables if ('provider' in n or 'keyring' in n)
                 and not any(x in n for x in ['usage','event','attempt','request','run']))
with engine.connect() as db:
    db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
    db.execute(text("SET LOCAL statement_timeout='3s'"))
    db.execute(text("SET LOCAL lock_timeout='250ms'"))
    cutoffs = baseline['cutoffs'] if baseline else {
        'snapshots': db.scalar(text('SELECT coalesce(max(id),0) FROM snapshots')),
        'observations': db.scalar(text('SELECT coalesce(max(id),0) FROM observations')),
        'credentials':db.scalar(text('SELECT coalesce(max(id),0) FROM credentials'))}
    hashes = {}
    for name in tables + ['snapshots','observations']:
        table=Base.metadata.tables[name]
        query=select(table)
        if name in cutoffs: query=query.where(table.c.id<=cutoffs[name])
        query=query.order_by(*table.primary_key.columns)
        digest=hashlib.sha256(); count=0
        for row in db.execute(query).mappings():
            digest.update(json.dumps(dict(row),sort_keys=True,default=str,separators=(',',':')).encode()+b'\n')
            count+=1
            if count>10000:raise ValueError('Bounded guard row limit exceeded')
        hashes[name]={'rows':count,'sha256':digest.hexdigest()}
    markets=[dict(r) for r in db.execute(text('SELECT id,region,ruleset_id,house_id,source_kind,enabled,verified,interval_seconds FROM markets ORDER BY id')).mappings()]
    assert [(m['id'],m['house_id'],m['interval_seconds']) for m in markets if m['enabled']]==[(2,114,300)]
    schema=db.scalar(text('SELECT version_num FROM alembic_version'))
    assert schema=='retention_20261118'
    if baseline:
        assert hashes==baseline['hashes'],'Original protected rows changed; inspect concurrent owner activity'
        assert markets==baseline['markets']
    print(json.dumps({'schema':schema,'cutoffs':cutoffs,'hashes':hashes,'markets':markets,
                      'all_guarded_original_rows_identical':bool(baseline)}))
    db.rollback()
