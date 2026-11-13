"""Create the first administrator from environment; refuses existing users."""
import os
import re
from sqlalchemy import select, text
from .db import Session
from .models import User
from .security import audit, hasher


def main():
    username = os.environ.get("MARKET_ADMIN_USERNAME", "").lower()
    password = os.environ.get("MARKET_ADMIN_PASSWORD", "")
    if not re.fullmatch(r"[a-z0-9_]{3,64}", username) or not 12 <= len(password) <= 128:
        raise SystemExit("Set a valid MARKET_ADMIN_USERNAME and a 12–128 character MARKET_ADMIN_PASSWORD")
    with Session.begin() as db:
        if db.bind.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(7140231)"))
        if db.scalar(select(User.id).limit(1)):
            raise SystemExit("Bootstrap refused: users already exist")
        user = User(username=username, password_hash=hasher.hash(password), role="admin")
        db.add(user)
        db.flush()
        audit(db, user.id, "admin.bootstrapped")
    print("Administrator created")


if __name__ == "__main__":
    main()
