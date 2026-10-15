"""Offline identity queue, stratified review samples, manual labels and evaluation."""
import argparse
import json
from pathlib import Path
import sys

from common import open_source, write_bounded_json, read_bounded_json
from identity_queue import review_queue
from sample import stratified_sample


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('queue', 'sample', 'sample-french'):
        command = sub.add_parser(name)
        source = command.add_mutually_exclusive_group(required=True)
        source.add_argument('--run', help='Stream complete CSV/CSV.gz artifacts in place')
        source.add_argument('--db', help='Use an existing formal DB in read-only mode')
        command.add_argument('--run-id', help='Required when a DB has several ready runs')
        command.add_argument('--corpus-dir')
        command.add_argument('--documents', help='Fixture metadata CSV; explicitly recorded as caller-supplied')
        command.add_argument('--with-text', action='store_true', help='Verify source parquet and include bounded original context')
        command.add_argument('--output', required=True, help='JSON output, maximum 2 MiB, outside source directories')
        if name == 'queue':
            command.add_argument('--limit', type=int, default=500)
            command.add_argument('--min-impact-dd', type=int, default=20)
        else:
            command.add_argument('--seed', type=int, default=20261015 if name == 'sample-french' else 20261014)
            if name == 'sample-french':
                command.add_argument('--base-samples', required=True, help='Preserved main sample; source folds and parent hash are inherited')
    template = sub.add_parser('template')
    template.add_argument('--samples', required=True)
    template.add_argument('--output', required=True)
    import_command = sub.add_parser('import-labels')
    import_command.add_argument('--samples', required=True)
    import_command.add_argument('--labels', required=True)
    import_command.add_argument('--output', required=True)
    evaluate = sub.add_parser('evaluate')
    evaluate.add_argument('--samples', required=True)
    evaluate.add_argument('--labels', required=True)
    evaluate.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    source = None
    try:
        if args.command in ('queue', 'sample', 'sample-french'):
            source = open_source(run=args.run, db=args.db, run_id=args.run_id,
                                 corpus_dir=args.corpus_dir, documents=args.documents)
            inputs = []
            if args.command == 'sample-french':
                from language_sample import french_supplement
                target = Path(args.output).resolve()
                parent_directory = Path(args.base_samples).resolve().parent
                if target == parent_directory or parent_directory in target.parents:
                    raise ValueError('French supplement outputs must be outside the preserved parent quality directory')
                if target.exists():
                    raise ValueError('French supplement output already exists; choose a new review packet path')
                result = french_supplement(source, args.base_samples, args.seed)
                inputs = [args.base_samples]
            else:
                result = review_queue(source, args.limit, args.min_impact_dd, args.with_text) if args.command == 'queue' \
                    else stratified_sample(source, args.seed, with_text=args.with_text)
            write_bounded_json(args.output, result, source=source, inputs=inputs)
            print(json.dumps({'output': str(Path(args.output).resolve()), 'schema': result['schema'],
                              'records': len(result['records']), 'frame_id': result['frame_id']}, ensure_ascii=False))
        else:
            from labels import template, import_labels, evaluate, _protected
            if args.command == 'template':
                result = template(args.samples, args.output)
            elif args.command == 'import-labels':
                result = import_labels(args.samples, args.labels, args.output)
            else:
                result = evaluate(args.samples, args.labels)
                target = _protected(args.output, read_bounded_json(args.samples), [args.samples, args.labels])
                write_bounded_json(target, result, inputs=[args.samples, args.labels])
            summary = {k: result[k] for k in ('schema', 'run_id', 'frame_id', 'rows',
                       'sampled_records', 'labelled_records', 'frame_N', 'sampled_n', 'labelled_n',
                       'population_calibration_status') if k in result}
            summary['output'] = str(Path(args.output).resolve())
            print(json.dumps(summary, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        if source:
            source.close()


if __name__ == '__main__':
    raise SystemExit(main())
