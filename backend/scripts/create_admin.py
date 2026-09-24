"""One-off bootstrap script: creates the very first admin user in a fresh
database. Nothing else can — every other account-creation path in this app
(admin_management.py) requires an already-authenticated admin, which is
exactly the chicken-and-egg problem a brand new deployment has.

Usage:
    python -m scripts.create_admin <username> <password> "<Full Name>"
"""

import sys

from app.core.security import hash_password
from app.db.base import SessionLocal
from app.models.user import User, UserRole


def main() -> None:
    if len(sys.argv) != 4:
        print('Usage: python -m scripts.create_admin <username> <password> "<Full Name>"')
        sys.exit(1)
    username, password, full_name = sys.argv[1], sys.argv[2], sys.argv[3]

    db = SessionLocal()
    try:
        if db.query(User).filter_by(username=username).first():
            print(f"User '{username}' already exists.")
            sys.exit(1)
        user = User(
            username=username,
            password_hash=hash_password(password),
            role=UserRole.admin,
            full_name=full_name,
        )
        db.add(user)
        db.commit()
        print(f"Admin '{username}' created (id={user.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
