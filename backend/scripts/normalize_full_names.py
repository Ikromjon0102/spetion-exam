"""One-off data cleanup: collapses internal whitespace runs (tabs, double
spaces — an Excel-paste artifact) in existing users.full_name values.

Both the bulk-import endpoint (admin_management.py) and
scripts/seed_school_data.py used to store full_name with only .strip()
applied, which trims the ends but leaves an internal tab/double-space
intact (e.g. "Abdukarimova\tShahnoza" — a huge visible gap wherever the
name is displayed). Both are now fixed at the source (a Pydantic
field_validator on the admin_management.py schemas; a direct re.sub in the
seed script), but that only prevents the bug going forward — any row
already created before this fix still has the raw whitespace. Run this
once per environment (including production, since the real 48-teacher
roster was seeded through the exact code path that had this bug) to fix
already-existing rows.

Usage:
    python -m scripts.normalize_full_names          # apply
    python -m scripts.normalize_full_names --dry-run  # preview only
"""

import re
import sys

from app.db.base import SessionLocal
from app.models.user import User


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    db = SessionLocal()
    try:
        changed = 0
        for user in db.query(User).all():
            cleaned = re.sub(r"\s+", " ", user.full_name.strip())
            if cleaned != user.full_name:
                changed += 1
                print(f"  id={user.id:<6} {user.full_name!r} -> {cleaned!r}")
                if not dry_run:
                    user.full_name = cleaned
        if changed == 0:
            print("No full_name values needed cleaning.")
        elif dry_run:
            print(f"\n{changed} row(s) would be updated (dry run, nothing written).")
        else:
            db.commit()
            print(f"\n{changed} row(s) updated.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
