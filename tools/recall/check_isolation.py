# -*- coding: utf-8 -*-
"""check_isolation.py -- enforce the three limits of the PROBLEMS #101 exception.
Exit 0 = ok, 1 = violation (printed). Anything it cannot classify is printed for a human.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALLOWED_READERS = {"audit/append_problems_entry.py", "tools/recall/build.py"}
GUARDED = ["pipeline", "decisions", "audit", "implementation"]
SKIP_DIRS = {".git", "__pycache__", "data", "corpus", ".claude", ".zcode", "node_modules"}


def py_files(base):
    for d, dirs, files in os.walk(base):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if f.endswith((".py", ".yaml", ".yml")):
                yield os.path.join(d, f)


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def read(p):
    return io.open(p, encoding="utf-8", errors="replace").read()


def main():
    bad, review = [], []
    # limit 2a: guarded code must not reference the library
    targets = [os.path.join(ROOT, g) for g in GUARDED] + [os.path.join(ROOT, "select_config.yaml")]
    for t in targets:
        files = [t] if os.path.isfile(t) else (py_files(t) if os.path.isdir(t) else [])
        for p in files:
            for n, line in enumerate(read(p).splitlines(), 1):
                if re.search(r"recall\.db|tools[/\\.]recall|import\s+recall|from\s+recall", line):
                    bad.append("%s:%d references the experience library: %s" % (rel(p), n, line.strip()[:100]))
    # limit 2b: only two files may mention PROBLEMS.md
    for p in py_files(ROOT):
        r = rel(p)
        if r in ALLOWED_READERS or r == "tools/recall/check_isolation.py":
            continue
        for n, line in enumerate(read(p).splitlines(), 1):
            if "PROBLEMS.md" in line:
                s = line.strip()
                reads = re.search(r"\b(open|read_text|read_bytes|Path|join|glob|load|read)\(", s) and not s.startswith("#")
                (bad if reads else review).append("%s:%d %s" % (r, n, s[:100]))
    # limit 3: query.py has no machine-readable output
    q = read(os.path.join(ROOT, "tools", "recall", "query.py"))
    code = "\n".join(l for l in q.splitlines() if not l.strip().startswith(("#", '"""')))
    for pat in (r'add_argument\(\s*["\']--(json|csv|out|output)', r"json\.dump", r"csv\.writer", r"open\([^)]*[\"']w"):
        if re.search(pat, code):
            bad.append("tools/recall/query.py has machine-readable output (%s)" % pat)

    for l in review:
        print("REVIEW (comment mention, not auto-passed):", l)
    for l in bad:
        print("VIOLATION:", l)
    print("isolation:", "FAIL" if bad else "ok", "(%d violations, %d to review)" % (len(bad), len(review)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
