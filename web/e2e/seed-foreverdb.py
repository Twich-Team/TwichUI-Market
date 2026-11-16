"""Authentic provider metadata with explicitly synthetic isolated AH observations."""
import json
from pathlib import Path
from market.db import Session,engine,now
from market.foreverdb import item
from market.metadata_catalog import store_source,import_foreverdb_resource
from market.ingest import ingest
assert engine.url.database=='market_test','Refusing ForeverDB fixtures outside market_test'
fixtures=Path('/app/tests/fixtures/foreverdb')
with Session.begin() as db:
    for ident in (8188,10098,2589,19019):
        fields,origin=item((fixtures/f'items-{ident}.json').read_bytes(),ident)
        store_source(db,'eu',ident,'foreverdb',fields,origin)
    for resource,name in [('professions/alchemy','professions-alchemy.json'),('vendors/54','vendors-54.json'),('itemsets/1','itemsets-1.json')]:
        import_foreverdb_resource(db,'eu',resource,(fixtures/name).read_bytes())
    rows=[{'id':800000+i,'item':{'id':ident},'quantity':2,'buyout':10000} for i,ident in enumerate((8188,10098,2589,19019,765,2488,11729))]
    ingest(db,1,json.dumps({'auctions':rows}).encode(),request_key='foreverdb-synthetic-browser',retrieved_at=now(),synthetic=True)
print('Authentic provider metadata seeded with synthetic market_test observations; no live provider calls')
