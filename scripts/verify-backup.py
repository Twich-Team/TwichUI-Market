"""Repeatable nonempty PostgreSQL restoration rehearsal, entirely in disposable projects."""
import json
import subprocess
from backups import ROOT, backup, compose, restore_check, run

SEED = '''
import json
from sqlalchemy import select
from market.db import Session, engine
from market.ingest import ingest
from market.models import Market, User
from market.security import hasher
assert engine.url.database == 'market_test'
with Session.begin() as db:
    db.add(User(username='restore_fixture', password_hash=hasher.hash('synthetic fixture password'), role='admin'))
    market=Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='Synthetic recovery fixture')
    db.add(market)
    db.flush()
    ingest(db,market.id,json.dumps({'auctions':[{'id':1,'item':{'id':12363},'quantity':10,'buyout':1200}]}).encode(),request_key='restore-fixture',synthetic=True)
print('Synthetic recovery fixture created in disposable test database')
'''


def main():
    command=compose('recovery')
    run(command+['down'],stdout=subprocess.DEVNULL)
    try:
        run(command+['run','--rm','test','alembic','upgrade','head'])
        run(command+['run','--rm','-T','test','python','-'],input=SEED.encode())
        archive=backup('recovery')
        result=restore_check(archive)
        assert result['users']==1 and result['markets']==1
        assert result['observations']==1 and result['listings']==1
        assert result['synthetic_observations']==1 and result['buyout_total']=='1200'
        # A damaged archive must fail integrity verification before PostgreSQL starts.
        content=archive.read_bytes()
        archive.write_bytes(content+b'corruption')
        try:
            restore_check(archive)
        except ValueError:
            pass
        else:
            raise AssertionError('Corrupted backup was accepted')
        finally:
            archive.write_bytes(content)
        print(json.dumps({'verified':True,'archive':archive.name,'restored':result,'corruption_rejected':True}))
    finally:
        run(command+['down'],stdout=subprocess.DEVNULL)


if __name__=='__main__':
    main()
