"""Configurable operational retention. Market history is always preserved."""
import argparse
import json
import os
from datetime import timedelta
from sqlalchemy import delete, func, select, text
from .db import Session, now
from .models import CollectionRun, Credential, Invitation, LoginAttempt, SecurityEvent


def maintain(factory=Session, *, apply=False, at=None):
    at=at or now()
    collection_days=int(os.environ.get('COLLECTION_LOG_DAYS','90'))
    security_days=int(os.environ.get('SECURITY_EVENT_DAYS','365'))
    if not 7<=collection_days<=3650 or not 30<=security_days<=3650:
        raise ValueError('Retention outside safe operational bounds')
    predicates=[(CollectionRun,CollectionRun.checked_at<at-timedelta(days=collection_days)),
                (SecurityEvent,SecurityEvent.created_at<at-timedelta(days=security_days)),
                (LoginAttempt,LoginAttempt.window_start<at-timedelta(days=1)),
                (Credential,Credential.expires_at<at-timedelta(days=30)),
                (Invitation,Invitation.expires_at<at-timedelta(days=30))]
    with factory.begin() as db:
        if db.bind.dialect.name=='postgresql' and not db.scalar(text('SELECT pg_try_advisory_xact_lock(7140233)')):
            return {'status':'busy'}
        result={'status':'applied' if apply else 'dry_run','historical_observations':'preserved_indefinitely','deleted':{}}
        for model,predicate in predicates:
            count=db.scalar(select(func.count()).select_from(model).where(predicate))
            result['deleted'][model.__tablename__]=count
            if apply:
                db.execute(delete(model).where(predicate))
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(json.dumps(maintain(apply=args.apply)))


if __name__=='__main__':
    main()
