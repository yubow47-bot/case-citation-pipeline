"""Exact research reports and auditable offline answer packets (no network/API)."""
import argparse
import csv
import hashlib
import io
import json
import shutil
import sqlite3
import sys
from pathlib import Path

from core import (ROOT, Filters, ResearchSource, make_packet, make_lookup_packet,
                  route_question, unsupported_packet)

MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_POINTER_BYTES = 64 * 1024


def open_source(args):
    """Default to the published pointer; explicit DB/stream inputs are separate."""
    if args.stream_run:
        return ResearchSource.stream(args.stream_run, args.corpus_dir, args.documents)
    if args.db:
        source = ResearchSource.sqlite(args.db, args.run_id, args.run_dir)
        source.provenance['selection'] = {'mode': 'explicit_db'}
        return source
    root = Path(ROOT).resolve()
    pointer_path = root / 'data/active_run.json'
    if not pointer_path.exists():
        source = ResearchSource.sqlite(root / 'data/foundation/research.db', args.run_id, args.run_dir)
        source.provenance['selection'] = {'mode': 'default_foundation_db',
            'pointer_path': str(pointer_path), 'pointer_status': 'missing'}
        return source
    if pointer_path.stat().st_size > MAX_POINTER_BYTES:
        raise ValueError('Active run pointer exceeds 64 KiB; refusing to guess a fallback run')
    raw = pointer_path.read_bytes()
    if len(raw) > MAX_POINTER_BYTES:
        raise ValueError('Active run pointer exceeds 64 KiB')
    try:
        pointer = json.loads(raw.decode('utf-8-sig'))
    except (UnicodeError, ValueError) as exc:
        raise ValueError('Active run pointer is invalid; no fallback database was selected') from exc
    if not isinstance(pointer, dict):
        raise ValueError('Active run pointer must be an object')
    fields = {name: pointer.get(name) for name in ('run_id', 'run_directory', 'input_fingerprint')}
    fields['db_path'] = pointer.get('db_path') or pointer.get('db')
    if any(not isinstance(value, str) or not value.strip() for value in fields.values()):
        raise ValueError('Active run pointer requires run_id, run_directory, db_path and input_fingerprint')
    if args.run_id and args.run_id != fields['run_id']:
        raise ValueError('--run-id disagrees with active pointer; specify --db for an independent historical run')
    def absolute(path):
        path = Path(path)
        return (path if path.is_absolute() else root / path).resolve()
    directory = absolute(fields['run_directory'])
    if args.run_dir and Path(args.run_dir).resolve() != directory:
        raise ValueError('--run-dir disagrees with active pointer; specify --db for deliberate relocation')
    source = None
    try:
        source = ResearchSource.sqlite(absolute(fields['db_path']), fields['run_id'], directory)
        stored = source.db.execute('SELECT source_directory FROM runs WHERE run_id=?', (source.run_id,)).fetchone()[0]
        if source.manifest['input_identity']['fingerprint'] != fields['input_fingerprint'] or absolute(stored) != directory:
            raise ValueError('Active pointer disagrees with the database run fingerprint/source directory')
        if pointer_path.read_bytes() != raw:
            raise ValueError('Active pointer changed during selection; retry the query')
        source.provenance['selection'] = {'mode': 'active_pointer', 'pointer_path': str(pointer_path),
            'pointer_sha256': hashlib.sha256(raw).hexdigest(), 'pointer_bytes': len(raw),
            'run_id_verified': True, 'input_fingerprint_verified': True, 'source_directory_verified': True}
        return source
    except Exception:
        if source:
            source.close()
        raise


def bounded_write(path, content):
    """Fixed small files, atomic overwrite, no report history or cache expansion."""
    payload = content.encode("utf-8")
    if len(payload) > MAX_OUTPUT_BYTES:
        raise ValueError("Report exceeds 2 MiB output budget; lower evidence/top or select a narrower scope")
    path = Path(path).resolve()
    existing = path
    while not existing.exists():
        existing = existing.parent
    if shutil.disk_usage(existing).free < len(payload) + 1024 * 1024:
        raise ValueError("Insufficient free space for bounded report output")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(path)
    finally:
        if temporary.is_file():
            temporary.unlink()


def result_csv(packet):
    result = packet.get("exact_results")
    if not result:
        raise ValueError("Unsupported answer has no CSV result")
    data = result["rows"] if packet["intent"] != "count" else [result["summary"]]
    if not data:
        if packet['intent'] == 'group_lookup':
            data = [{}]  # Preserve a detached CSV's explicit zero-match scope.
        else:
            return ""
    # Repeat identity/scope per CSV row so a detached CSV retains its denominator context.
    scope = {"run_id": packet["run_identity"]["run_id"],
             "input_fingerprint": packet["run_identity"]["input_fingerprint"],
             "intent": packet["intent"],
             "parameters_json": json.dumps(packet["parameters"], ensure_ascii=False, sort_keys=True),
             "packet_sha256": packet["packet_sha256"]}
    if result.get('origin_coverage_context'):
        scope['origin_coverage_context_json'] = json.dumps(result['origin_coverage_context'], ensure_ascii=False, sort_keys=True)
    if 'matching_groups' in result:
        scope['matching_groups'] = result['matching_groups']
    out = io.StringIO(newline="")
    fields = list(scope) + list(data[0])
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in data:
        writer.writerow({**scope, **{key: json.dumps(value, ensure_ascii=False, sort_keys=True)
            if isinstance(value, (list, dict)) else value for key, value in row.items()}})
    return out.getvalue()


def validate_outputs(args, source):
    targets = []
    for name, suffix in (("output", ".json"), ("csv", ".csv")):
        value = getattr(args, name)
        if value:
            path = Path(value).resolve()
            if path.suffix.lower() != suffix:
                raise ValueError(f"--{name} must use a {suffix} filename")
            targets.append(path)
    if len(targets) != len(set(targets)):
        raise ValueError("JSON and CSV outputs must use different paths")
    if (Path(ROOT) / 'data/active_run.json').resolve() in targets:
        raise ValueError('Report target is the active run pointer')
    if source:
        protected = [source.run_dir] if source.run_dir else []
        corpus = args.corpus_dir or source.manifest["params"].get("corpus_dir")
        if corpus:
            protected.append(Path(corpus).resolve())
        for path in targets:
            if path == Path(source.provenance.get('db_path', '/not-a-database')).resolve():
                raise ValueError('Report target is the source database')
            if any(path == parent or parent in path.parents for parent in protected):
                raise ValueError("Reports must not overwrite files inside a source run/corpus directory")
            if args.documents and path == Path(args.documents).resolve():
                raise ValueError("Report target is an input document metadata artifact")


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("stats", "ask", "find"):
        command = sub.add_parser(name)
        inputs = command.add_mutually_exclusive_group()
        inputs.add_argument("--db", help="Independent existing SQLite DB; otherwise follow data/active_run.json")
        inputs.add_argument("--stream-run", help="Stream CSV/CSV.gz into compact in-memory tables; no persistent cache")
        command.add_argument("--run-id", help="Exact SQLite run ID; required if multiple ready runs exist")
        command.add_argument("--run-dir", help="SQLite source artifacts relocated with the exact same manifest")
        command.add_argument("--corpus-dir", help="Original parquet directory; hashes must match the run to extract text")
        command.add_argument("--documents", help="Streaming mode only: small CSV/CSV.gz metadata, explicitly marked caller-supplied")
        command.add_argument("--output", help="JSON packet, at most 2 MiB; overwrite rather than keep histories")
        command.add_argument("--csv", help="Exact result CSV, at most 2 MiB")
        command.add_argument("--language", choices=("zh", "en"), default="zh")
        command.add_argument("--top", type=int, default=10)
        if name == 'find':
            command.add_argument('name', help='Literal recorded case-name fragment; returns separate group candidates')
            continue
        command.add_argument("--evidence-limit", type=int, default=3, help="Deterministic evidence preview, 0..10; not used for counts")
        command.add_argument("--with-text", action="store_true", help="Verify corpus hashes and return original-text windows (no API)")
        command.add_argument("--court")
        command.add_argument("--year-from", type=int)
        command.add_argument("--year-to", type=int)
        command.add_argument("--origin", choices=("FOREIGN", "DOMESTIC_CA", "UNDETERMINED", "CONFLICT"))
        command.add_argument("--min-dd", type=int, default=0)
        command.add_argument("--kept-only", action="store_true")
        command.add_argument("--group-id")
        if name == "ask":
            command.add_argument("question", nargs="?")
            command.add_argument("--intent", choices=("count", "court_decade", "ranking", "case_citations"),
                                 help="Explicit fixed query if question wording is outside the small grammar")
            command.add_argument("--answer-mode", choices=("offline", "model"), default="offline")
    return p


def query_packet(args, source):
    if args.command == 'find':
        return make_lookup_packet(source, args.name, args.top, args.language)
    filters = Filters(args.court.upper() if args.court else None, args.year_from, args.year_to,
                      args.origin, args.min_dd, args.kept_only, args.group_id)
    intent, top = ("court_decade", args.top) if args.command == "stats" else (args.intent, args.top)
    question = getattr(args, "question", None)
    if args.command == "ask" and question and not intent:
        route = route_question(question, source.manifest["params"]["courts"])
        if route is None:
            return unsupported_packet(question, "Question is outside the supported count/ranking/trend/explicit group-citation grammar. Specify --intent and filters to make the query unambiguous.", source.identity())
        intent, inferred, inferred_top = route
        values = {}
        for name in filters.__dataclass_fields__:
            explicit, parsed = getattr(filters, name), getattr(inferred, name)
            default = Filters.__dataclass_fields__[name].default
            if explicit != default and parsed != default and explicit != parsed:
                raise ValueError("Question and CLI filter disagree: " + name)
            values[name] = explicit if explicit != default else parsed
        filters = Filters(**values)
        if args.top != 10 and inferred_top != 10 and args.top != inferred_top:
            raise ValueError("Question and --top disagree")
        top = args.top if args.top != 10 else inferred_top
    elif args.command == "ask" and not intent:
        raise ValueError("Supply a question or --intent")
    return make_packet(source, intent, filters, top, args.evidence_limit,
                       args.with_text, args.corpus_dir, args.language, question,
                       "explicit_fixed_intent" if getattr(args, "intent", None) or args.command == "stats" else "controlled_question_grammar")


def main(argv=None):
    # Windows redirected stdout may otherwise use a legacy code page; artifacts and CLI are UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    source = None
    try:
        if args.documents and not args.stream_run:
            raise ValueError("--documents is only supported with --stream-run")
        if args.stream_run and (args.run_id or args.run_dir):
            raise ValueError("--stream-run already defines the complete run path and identity")
        if args.command == "ask" and args.answer_mode == "model":
            # Deliberate capability boundary: do not load a key or silently call a model.
            packet = unsupported_packet(args.question, "Model-generated answers are not implemented by this offline tool. Use --answer-mode offline.")
        else:
            source = open_source(args)
            packet = query_packet(args, source)
        validate_outputs(args, source)
        if args.output:
            bounded_write(args.output, json.dumps(packet, ensure_ascii=False, indent=2) + "\n")
        if args.csv:
            bounded_write(args.csv, result_csv(packet))
        if args.output:
            print(json.dumps({"status": packet["status"], "answer": packet.get("answer"),
                              "reason": packet.get("reason"), "packet": str(Path(args.output).resolve()),
                              "packet_sha256": packet["packet_sha256"]}, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(packet, ensure_ascii=False, indent=2))
        return 0 if packet["status"] == "supported" else 2
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        if source:
            source.close()


if __name__ == "__main__":
    sys.exit(main())
