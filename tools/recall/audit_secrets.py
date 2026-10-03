# -*- coding: utf-8 -*-
"""audit_secrets.py -- verify no key / email survived redaction in recall.db. Exit 0 = clean.
Reports counts and locators only; never prints matched content."""
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build  # noqa: E402


def main():
    if not os.path.exists(build.DB_PATH):
        sys.exit("no db -- run build.py first")
    secrets = build.load_secrets()
    db = sqlite3.connect(build.DB_PATH)
    hits = []
    for cid, loc, text in db.execute("SELECT id, locator, text FROM chunks"):
        why = None
        if any(s in text for s in secrets):
            why = "key"
        elif build.EMAIL in text:
            why = "email"
        elif re.search(r"api_key=(?!\[REDACTED_KEY\])\S", text):
            why = "api_key param"
        if why:
            hits.append((loc, why))
    print("secret audit: %d tokens loaded, %d chunks hit" % (len(secrets), len(hits)))
    for loc, why in hits[:50]:
        print("  HIT", why, loc)
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
