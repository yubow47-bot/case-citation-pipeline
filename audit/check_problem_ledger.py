# -*- coding: utf-8 -*-
"""Check the human problem ledger offline; never provide pipeline configuration.

Default: read PROBLEMS.md and print structural errors and historical-path warnings.
Use --ledger PATH for a fixture and --json PATH to save an explicit review report.
Link existence proves only that evidence can be opened, not that its claims hold.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "PROBLEMS.md"
STATES = frozenset({"OPEN", "PARTIAL", "SOURCE_ONLY", "IMPLEMENTED",
                    "LIMITATION", "RECHECK", "HISTORICAL", "PROCESS"})
MARKERS = {name: ("<!-- ledger-%s:start -->" % name,
                  "<!-- ledger-%s:end -->" % name)
           for name in ("current", "history")}
ID_ROW = re.compile(r"^\|\s*(\d+)\s*\|")


class LedgerError(ValueError):
    """Invalid ledger or proposed edit; no write should have occurred."""


def table_boundaries(line):
    """Find Markdown delimiters outside code spans and escaped pipes."""
    text = line.strip()
    if not text.startswith("|") or not text.endswith("|"):
        raise LedgerError("expected a complete Markdown table row")
    cuts, code_ticks, pos = [], 0, 0
    while pos < len(text):
        char = text[pos]
        if char == "\\" and not code_ticks:
            pos += 2
            continue
        if char == "`":
            end = pos + 1
            while end < len(text) and text[end] == "`":
                end += 1
            run = end - pos
            if not code_ticks:
                code_ticks = run
            elif code_ticks == run:
                code_ticks = 0
            pos = end
            continue
        if char == "|" and not code_ticks:
            cuts.append(pos)
        pos += 1
    if code_ticks or not cuts or cuts[0] != 0 or cuts[-1] != len(text) - 1:
        raise LedgerError("unclosed code span or missing table delimiter")
    return text, cuts


def table_cells(line):
    text, cuts = table_boundaries(line)
    return [text[a + 1:b].strip() for a, b in zip(cuts, cuts[1:])]


def sections(lines):
    spans = {}
    for name, (start, end) in MARKERS.items():
        starts = [i for i, line in enumerate(lines) if line.strip() == start]
        ends = [i for i, line in enumerate(lines) if line.strip() == end]
        if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
            raise LedgerError("%s requires exactly one ordered start/end marker" % name)
        spans[name] = (starts[0], ends[0])
    if spans["current"][1] >= spans["history"][0]:
        raise LedgerError("current index must precede the separate history table")
    return spans


def ledger_rows(lines, spans):
    rows, errors = {}, []
    for name, (start, end) in spans.items():
        found, headers, separators = [], 0, 0
        expected = 4 if name == "current" else 3
        for i in range(start + 1, end):
            line = lines[i]
            if not line.strip():
                continue
            if not line.lstrip().startswith("|"):
                errors.append("line %d: non-table text inside %s table" % (i + 1, name))
                continue
            match = ID_ROW.match(line.strip())
            if not match:
                try:
                    cells = table_cells(line)
                except LedgerError as exc:
                    errors.append("line %d: %s" % (i + 1, exc))
                    continue
                header = (["#", "状态", "当前结论与证据", "下一步 / 关闭条件"] if name == "current"
                          else ["#", "Problem", "Current handling"])
                if cells == header:
                    headers += 1
                elif len(cells) == expected and all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    separators += 1
                else:
                    errors.append("line %d: invalid %s header or row ID" % (i + 1, name))
                continue
            number = int(match.group(1))
            try:
                cells = table_cells(line)
            except LedgerError as exc:
                errors.append("line %d: #%d %s" % (i + 1, number, exc))
                cells = []
            if len(cells) != expected:
                errors.append("line %d: #%d %s row requires %d cells (found %d)" %
                              (i + 1, number, name, expected, len(cells)))
            elif any(not cell for cell in cells):
                errors.append("line %d: #%d has an empty required cell" % (i + 1, number))
            elif name == "current" and cells[1] not in STATES:
                errors.append("line %d: #%d unknown status %r" % (i + 1, number, cells[1]))
            found.append({"id": number, "line": i + 1, "cells": cells, "text": line})
        if headers != 1 or separators != 1:
            errors.append("%s table requires exactly one header and one alignment row" % name)
        ids = [row["id"] for row in found]
        for number, count in Counter(ids).items():
            if count != 1:
                errors.append("%s: #%d occurs %d times" % (name, number, count))
        if not ids:
            errors.append("%s table has no numbered entries" % name)
        elif ids != list(range(1, max(ids) + 1)):
            missing = sorted(set(range(1, max(ids) + 1)) - set(ids))
            errors.append("%s IDs must be unique and ordered continuously from 1; missing=%s" %
                          (name, missing))
        rows[name] = found
    if [r["id"] for r in rows["current"]] != [r["id"] for r in rows["history"]]:
        errors.append("current index and history must cover exactly the same IDs in order")
    for i, line in enumerate(lines):
        if ID_ROW.match(line.strip()) and not any(a < i < b for a, b in spans.values()):
            errors.append("line %d: numbered ledger row outside marked tables" % (i + 1))
    return rows, errors


def markdown_targets(text):
    """Read inline link destinations, including balanced path parentheses."""
    for match in re.finditer(r"!?\[[^\]\n]*\]\(", text):
        start = match.end()
        depth, escaped, angle = 1, False, False
        for end in range(start, len(text)):
            char = text[end]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == "<" and end == start:
                angle = True
            elif char == ">" and angle:
                angle = False
            elif not angle:
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        target = text[start:end].strip()
                        if target.startswith("<") and ">" in target:
                            target = target[1:target.index(">")]
                        else:
                            target = re.split(r'\s+["\']', target, maxsplit=1)[0]
                        yield target
                        break


def local_link(target, ledger_path, root):
    # URI schemes are external evidence. Anchors are stripped, not validated.
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
        if not re.match(r"^[A-Za-z]:[/\\]", target):
            return None, None
    if target.startswith("//"):
        return None, None
    value = unquote(target.split("#", 1)[0].split("?", 1)[0])
    if not value:
        return ledger_path, None
    path = (ledger_path.parent / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return path, "local evidence link escapes repository: %s" % target
    return path, None


def check_lines(lines, ledger_path=LEDGER, root=ROOT):
    """Return JSON-safe review data without modifying files or judging claims."""
    ledger_path, root = Path(ledger_path).resolve(), Path(root).resolve()
    result = {"ledger": str(ledger_path), "status": "failed", "errors": [],
              "warnings": [], "counts": {}, "scope": "structure and local link existence only"}
    try:
        spans = sections(lines)
    except LedgerError as exc:
        result["errors"].append(str(exc))
        return result
    rows, errors = ledger_rows(lines, spans)
    result["errors"].extend(errors)
    for name, entries in rows.items():
        result["counts"][name] = len(entries)
    result["counts"]["statuses"] = dict(Counter(
        r["cells"][1] for r in rows["current"] if len(r["cells"]) == 4))
    for row in rows["current"]:
        for target in markdown_targets(row["text"]):
            path, error = local_link(target, ledger_path, root)
            if error or (path is not None and not path.exists()):
                result["errors"].append("line %d: #%d %s" % (row["line"], row["id"],
                    error or "missing local evidence link: %s" % target))
    seen = set()
    for row in rows["history"]:
        for code in re.findall(r"`([^`\r\n]+)`", row["text"]):
            # Keep historical text: only clear literal paths get warnings.
            if not re.fullmatch(r"(?:audit|decisions|docs|pipeline|implementation|scripts|tools|data|corpus)[/\\][^\s<>*?={}|]+", code):
                continue
            target = re.sub(r":\d+$", "", code).rstrip("/\\")
            path, error = local_link(target, ledger_path, root)
            if (error or (path is not None and not path.exists())) and (row["id"], target) not in seen:
                seen.add((row["id"], target))
                result["warnings"].append("line %d: historical #%d path unavailable: %s" %
                                           (row["line"], row["id"], target))
    result["status"] = "passed" if not result["errors"] else "failed"
    return result


def check_ledger(path=LEDGER, root=ROOT):
    path = Path(path)
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        return {"ledger": str(path), "status": "failed", "errors": [str(exc)],
                "warnings": [], "counts": {}}
    result = check_lines(text.splitlines(), path, root)
    remainder = raw.replace(b"\r\n", b"")
    if b"\n" in remainder or b"\r" in remainder:
        result["errors"].append("ledger must use pure CRLF line endings")
        result["status"] = "failed"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--json", type=Path, dest="report", help="save the explicit review report")
    args = parser.parse_args(argv)
    result = check_ledger(args.ledger)
    if args.report:
        if args.report.resolve() == args.ledger.resolve():
            parser.error("JSON report must not overwrite the ledger")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for error in result["errors"]:
        print("ERROR:", error)
    for warning in result["warnings"]:
        print("WARNING:", warning)
    print("ledger:", result["status"], "(%d current, %d history, %d warnings)" %
          (result["counts"].get("current", 0), result["counts"].get("history", 0), len(result["warnings"])))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
