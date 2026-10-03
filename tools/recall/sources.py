# -*- coding: utf-8 -*-
"""sources.py -- cut every project text source into chunks for the experience library.

A chunk is a dict: source, locator, date, title, text. `locator` always lets a human
jump back to the original (1-based line numbers of the ORIGINAL file).
Nothing here talks to a model or a database.
"""
import csv
import glob
import io
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLAUDE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects", "D--cases-data-analisis")

MAX_CHARS = 1500
OVERLAP = 200
MIN_CHARS = 40

SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
csv.field_size_limit(10 ** 9)


def _rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def _read_lines(path):
    with io.open(path, encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def _split_long(text):
    """Split an over-long text on paragraph boundaries, ~OVERLAP chars of overlap."""
    if len(text) <= MAX_CHARS:
        return [text]
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n|\n", text):
        while len(para) > MAX_CHARS:  # one giant line: hard cut
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(para[:MAX_CHARS])
            para = para[MAX_CHARS - OVERLAP:]
        if len(cur) + len(para) + 1 > MAX_CHARS and cur:
            parts.append(cur)
            cur = cur[-OVERLAP:] + "\n" + para
        else:
            cur = (cur + "\n" + para) if cur else para
    if cur:
        parts.append(cur)
    return parts


def _emit(source, locator, title, text, date=""):
    text = text.strip()
    if len(text) < MIN_CHARS:
        return
    for i, piece in enumerate(_split_long(text)):
        piece = piece.strip()
        if len(piece) < MIN_CHARS:
            continue
        loc = locator if i == 0 else "%s~%d" % (locator, i + 1)
        yield {"source": source, "locator": loc, "date": date, "title": title, "text": piece}


def chunk_markdown(path, source):
    """Split on #/##/### headings. Locator = file:first-line-of-section."""
    lines = _read_lines(path)
    rel = _rel(path)
    starts = [i for i, l in enumerate(lines) if re.match(r"#{1,3}\s", l)]
    if not starts or starts[0] != 0:
        starts = [0] + starts
    starts.append(len(lines))
    for a, b in zip(starts, starts[1:]):
        body = "\n".join(lines[a:b])
        title = lines[a].lstrip("# ").strip()[:120] if a < len(lines) else rel
        yield from _emit(source, "%s:%d" % (rel, a + 1), title, body)


def chunk_debt():
    path = os.path.join(ROOT, "DEBT_LEDGER.md")
    lines = _read_lines(path)
    cur_head, buf, buf_start = "DEBT_LEDGER", [], 1

    def flush():
        if buf:
            yield from _emit("debt", "DEBT_LEDGER.md:%d" % buf_start, cur_head, "\n".join(buf))

    for i, l in enumerate(lines, 1):
        if re.match(r"#{1,3}\s", l):
            yield from flush()
            cur_head, buf, buf_start = l.lstrip("# ").strip()[:120], [l], i
        elif l.startswith("|") and not re.match(r"\|[\s\-:|]+\|$", l):
            yield from _emit("debt", "DEBT_LEDGER.md:%d" % i, cur_head, cur_head + "\n" + l)
        else:
            buf.append(l)
    yield from flush()


def chunk_csv(path):
    rel = _rel(path)
    with io.open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            text = "; ".join("%s=%s" % (h, v) for h, v in zip(header, row) if v != "")
            yield from _emit("decisions", "%s:%d" % (rel, reader.line_num), os.path.basename(path), text)


def chunk_git():
    out = subprocess.run(
        ["git", "log", "master", "--format=%x1e%h%x1f%ad%x1f%B", "--date=short"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    for rec in out.split("\x1e"):
        if not rec.strip():
            continue
        h, date, body = (rec.split("\x1f", 2) + ["", ""])[:3]
        h = h.strip()
        body = re.sub(r"\n+Co-Authored-By:.*", "", body.strip(), flags=re.S | re.I)
        title = body.splitlines()[0][:120] if body else h
        yield from _emit("git", "git:" + h, title, "%s %s\n%s" % (h, date, body), date)


def _visible_text(content):
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    else:
        text = ""
    return SYSTEM_REMINDER.sub("", text).strip()


def chunk_chat(stats):
    """One chunk per (user message + the assistant text that follows it).

    stats: dict counter filled with drop reasons (reported by build.py).
    """
    files = sorted(glob.glob(os.path.join(CLAUDE_DIR, "*.jsonl")))
    for path in files:
        sid = os.path.basename(path)[:8]
        pending = None  # [timestamp, user_text, [assistant texts]]

        def close(p):
            if p and p[1]:
                body = "USER: %s\n\nASSISTANT: %s" % (p[1], "\n".join(p[2]).strip())
                yield from _emit("chat", "chat:%s@%s" % (sid, p[0]), p[1][:80].replace("\n", " "),
                                 body, p[0][:10])

        with io.open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    stats["bad_json"] = stats.get("bad_json", 0) + 1
                    continue
                t = d.get("type")
                if t not in ("user", "assistant"):
                    stats["other_type"] = stats.get("other_type", 0) + 1
                    continue
                msg = d.get("message") or {}
                content = msg.get("content")
                if t == "user" and isinstance(content, list) and all(
                        isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                    stats["tool_result_only"] = stats.get("tool_result_only", 0) + 1
                    continue
                text = _visible_text(content)
                if not text:
                    stats["empty_after_strip"] = stats.get("empty_after_strip", 0) + 1
                    continue
                if t == "user":
                    yield from close(pending)
                    pending = [d.get("timestamp", ""), text, []]
                elif pending is not None:
                    pending[2].append(text)
        yield from close(pending)


def chunk_memory():
    for path in sorted(glob.glob(os.path.join(CLAUDE_DIR, "memory", "*.md"))):
        if os.path.basename(path) == "MEMORY.md":
            continue
        text = "\n".join(_read_lines(path))
        yield from _emit("memory", "memory:" + os.path.basename(path), os.path.basename(path), text)


def _globs(patterns):
    seen = []
    for p in patterns:
        for f in sorted(glob.glob(os.path.join(ROOT, p), recursive=True)):
            if f not in seen:
                seen.append(f)
    return seen


def all_sources(stats=None):
    """Return {source_name: generator-factory}."""
    stats = stats if stats is not None else {}
    def md(patterns, name):
        return lambda: (c for f in _globs(patterns) for c in chunk_markdown(f, name))
    # the ledger itself is chunked in build.py -- the only file allowed to read it (PROBLEMS #101)
    return {
        "debt": chunk_debt,
        "findings": md(["audit/findings/**/*.md"], "findings"),
        "decisions": lambda: (c for f in _globs(["decisions/*.csv"]) for c in chunk_csv(f)),
        "decisions_doc": md(["decisions/README.md"], "decisions"),
        "worknotes": md(["implementation/*.md"], "worknotes"),
        "docs": md(["docs/*.md", "README.md", "audit/README.md"], "docs"),
        "zcode": md([".zcode/plans/*.md"], "zcode"),
        "git": chunk_git,
        "chat": lambda: chunk_chat(stats),
        "memory": chunk_memory,
    }
