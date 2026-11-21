"""Quality-rendering fixtures; metadata only in isolated market_test."""
import json
from market.db import Session,engine
from market.metadata import store_metadata
assert engine.url.database=='market_test','Refusing quality fixtures outside market_test'
with Session.begin() as db:
    for ident,quality in [(20003,'COMMON'),(20004,'EPIC'),(20005,'POOR'),(20006,'LEGENDARY'),(20007,'ARTIFACT')]:
        store_metadata(db,'eu',ident,json.dumps({'id':ident,'name':f'Synthetic {quality.title()} Item','quality':{'type':quality}}).encode(),synthetic=True,resolved_namespace='static-1.60.1_70532-forever-eu')
print('Synthetic quality metadata seeded; no auction or provider changes')
