# -*- coding: utf-8 -*-
"""Safely maintain the human problem ledger and its current index together.

Usage (UTF-8 fragments, one complete Markdown row per line):
  python audit/append_problems_entry.py --fragment history.txt --current-fragment current.txt
  python audit/append_problems_entry.py --fragment history.txt --current-fragment current.txt --dry-run
  python audit/append_problems_entry.py --fragment history.txt --current-fragment current.txt --replace-row 58
  python audit/append_problems_entry.py --fragment disposition.txt --current-fragment current.txt --set-disposition 58

The last mode takes one disposition cell, without surrounding table delimiters.
Every edit requires an explicitly reviewed current row for the same ID(s).
Append inserts before ledger-history:end and ledger-current:end. All IDs, table
structure and current evidence links are validated before an atomic CRLF write.
This maintenance tool supplies no rules or configuration to the pipeline.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile

try:
    from .check_problem_ledger import (ID_ROW, LEDGER, ROOT, LedgerError,
                                       check_lines, ledger_rows, sections, table_boundaries, table_cells)
except ImportError:  # Direct script invocation.
    from check_problem_ledger import (ID_ROW, LEDGER, ROOT, LedgerError,
                                      check_lines, ledger_rows, sections, table_boundaries, table_cells)


def load_crlf(path):
    raw = Path(path).read_bytes()
    remainder = raw.replace(b"\r\n", b"")
    if b"\n" in remainder or b"\r" in remainder:
        raise LedgerError("ledger must use pure CRLF; refusing to rewrite it")
    return raw.decode("utf-8").split("\r\n")


def fragment_lines(path):
    text = Path(path).read_bytes().decode("utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise LedgerError("fragment is empty")
    return lines


def fragment_rows(lines, columns):
    numbers = []
    for line in lines:
        match = ID_ROW.match(line)
        if not match or len(table_cells(line)) != columns:
            raise LedgerError("fragment requires complete %d-cell numbered table rows" % columns)
        if any(not cell for cell in table_cells(line)):
            raise LedgerError("fragment has an empty required cell")
        numbers.append(int(match.group(1)))
    if len(set(numbers)) != len(numbers):
        raise LedgerError("fragment contains duplicate IDs")
    return numbers


def apply_change(ledger, fragment, current_fragment, *, replace_row=None,
                 set_disposition=None, dry_run=False, root=ROOT):
    """Validate the whole proposal first; malformed input leaves bytes unchanged."""
    ledger = Path(ledger)
    if replace_row is not None and set_disposition is not None:
        raise LedgerError("--replace-row and --set-disposition are mutually exclusive")
    if not current_fragment:
        raise LedgerError("--current-fragment is required for every edit")
    original = ledger.read_bytes()
    lines = load_crlf(ledger)
    spans = sections(lines)
    rows, errors = ledger_rows(lines, spans)
    if errors:
        raise LedgerError("existing ledger structure is invalid: " + "; ".join(errors))
    history_lines = fragment_lines(fragment)
    current_lines = fragment_lines(current_fragment)
    current_ids = fragment_rows(current_lines, 4)
    target = replace_row if replace_row is not None else set_disposition
    if target is not None:
        if current_ids != [target] or len(history_lines) != 1:
            raise LedgerError("replacement requires exactly one history/current row with the target ID")
        matches = {name: [row for row in entries if row["id"] == target]
                   for name, entries in rows.items()}
        if any(len(found) != 1 for found in matches.values()):
            raise LedgerError("target ID must occur exactly once in both tables")
        old_history = matches["history"][0]
        if set_disposition is not None:
            if len(table_cells("| " + history_lines[0] + " |")) != 1:
                raise LedgerError("disposition contains an unescaped table delimiter")
            text, cuts = table_boundaries(old_history["text"])
            history_lines = [text[:cuts[-2] + 1] + " " + history_lines[0] + " |"]
        elif fragment_rows(history_lines, 3) != [target]:
            raise LedgerError("replacement history row must retain the target ID")
        lines[old_history["line"] - 1] = history_lines[0]
        lines[matches["current"][0]["line"] - 1] = current_lines[0]
    else:
        history_ids = fragment_rows(history_lines, 3)
        last = rows["history"][-1]["id"]
        expected = list(range(last + 1, last + 1 + len(history_ids)))
        if history_ids != expected or current_ids != expected:
            raise LedgerError("append IDs must be consecutive from #%d in both fragments" % (last + 1))
        # Insert later section first so earlier offsets remain valid.
        lines[spans["history"][1]:spans["history"][1]] = history_lines
        lines[spans["current"][1]:spans["current"][1]] = current_lines
    result = check_lines(lines, ledger, root)
    if result["errors"]:
        raise LedgerError("proposed ledger is invalid: " + "; ".join(result["errors"]))
    data = "\r\n".join(lines).encode("utf-8")
    if dry_run:
        print("dry-run: valid proposal; ledger unchanged")
        return result
    temporary = None
    try:
        # Unique sibling, closed before replacement for Windows compatibility.
        with tempfile.NamedTemporaryFile(prefix=ledger.name + ".", suffix=".tmp",
                                         dir=ledger.parent, delete=False) as out:
            temporary = Path(out.name)
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        if ledger.read_bytes() != original:
            raise LedgerError("ledger changed during maintenance; refusing to overwrite another edit")
        os.replace(temporary, ledger)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print("updated %s: %d current/history entries; pure CRLF" %
          (ledger, result["counts"]["history"]))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fragment", type=Path, required=True)
    parser.add_argument("--current-fragment", type=Path, required=True,
                        help="reviewed current-index row(s) for the same ID(s)")
    parser.add_argument("--dry-run", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--replace-row", type=int)
    mode.add_argument("--set-disposition", type=int)
    args = parser.parse_args(argv)
    try:
        apply_change(LEDGER, args.fragment, args.current_fragment,
                     replace_row=args.replace_row, set_disposition=args.set_disposition,
                     dry_run=args.dry_run)
    except (LedgerError, OSError, UnicodeError) as exc:
        parser.exit(1, "ERROR: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
