import os
from pathlib import Path
import subprocess
import sys
import pytest
from sqlalchemy import create_engine,text


def test_legacy_statistics_backfill_round_trip_and_compaction_guard(database):
    with database() as db:
        if db.bind.dialect.name!='postgresql': pytest.skip('PostgreSQL migration arithmetic')
        source=db.bind.url
    owner=create_engine(source,isolation_level='AUTOCOMMIT')
    with owner.connect() as connection:
        connection.execute(text('CREATE DATABASE market_migration_test'))
    target=create_engine(source.set(database='market_migration_test'))
    env={**os.environ,'DATABASE_URL':target.url.render_as_string(hide_password=False)}
    def migration(*arguments,success=True):
        result=subprocess.run([sys.executable,'-m','alembic',*arguments],cwd=Path(__file__).resolve().parents[1],
            env=env,capture_output=True,text=True)
        assert (result.returncode==0)==success,result.stdout+result.stderr
        return result
    try:
        migration('upgrade','2541add7d379')
        with target.begin() as db:
            db.execute(text("""INSERT INTO markets(id,region,ruleset_id,house_id,source_kind,label,enabled,verified,interval_seconds,next_check,failures)
                VALUES(1,'eu',2,113,'auctions','Synthetic legacy fixture',false,false,1800,now(),0)"""))
            db.execute(text("INSERT INTO snapshots(id,market_id,content_hash,created_at,listing_count) VALUES(1,1,:hash,now(),3)"),{'hash':'a'*64})
            for auction,item,quantity,buyout,bid in [(1,1,2,201,None),(2,1,8,1600,None),(3,2,9,None,100)]:
                db.execute(text('''INSERT INTO listings(snapshot_id,auction_id,item_id,variant,variant_key,quantity,buyout,bid)
                    VALUES(1,:auction,:item,:variant,:key,:quantity,:buyout,:bid)'''),
                    {'auction':auction,'item':item,'variant':'{"id":'+str(item)+'}','key':str(item)*64,
                     'quantity':quantity,'buyout':buyout,'bid':bid})
            db.execute(text('''INSERT INTO observations(market_id,snapshot_id,request_key,retrieved_at,namespace,payload_hash,payload_bytes,synthetic)
                VALUES(1,1,'legacy',now(),'dynamic-forever-eu',:hash,100,true)'''),{'hash':'b'*64})
        for _ in range(2):
            migration('upgrade','head')
            migration('check')
            with target.connect() as db:
                row=db.execute(text('SELECT recent_price,lowest_buyout,supply,priced_supply FROM snapshot_statistics WHERE item_id=1')).one()
                assert tuple(row)==(180,101,10,10)
                assert tuple(db.execute(text('SELECT recent_price,supply,priced_supply FROM snapshot_statistics WHERE item_id=2')).one())==(None,9,0)
                assert db.scalar(text('SELECT count(*) FROM daily_observations'))==1
            if _==0: migration('downgrade','2541add7d379')
        with target.begin() as db:
            db.execute(text('DELETE FROM listings'))
            db.execute(text('UPDATE snapshots SET raw_retained=false'))
        rejected=migration('downgrade','2541add7d379',success=False)
        assert 'Cannot downgrade after raw compaction' in rejected.stderr
    finally:
        target.dispose()
        with owner.connect() as connection:
            connection.execute(text('DROP DATABASE market_migration_test WITH (FORCE)'))
        owner.dispose()
