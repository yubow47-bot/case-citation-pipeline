# Audit output retention

Code and final evidence belong in Git. Databases, raw run outputs, caches, progress logs and duplicate snapshots stay local. The patterns in the root `.gitignore` make these decisions explicit.

| Folder | Published | Local only |
| --- | ---: | ---: |
| `project_review_20261014` | 17 | 26 |
| `project_review_20261015` | 9 | 9 |
| `quality_20261014` | 0 | 12 |
| `quality_20261015` | 7 | 4 |
| `quality_20261015_fr` | 5 | 2 |
| `receipts_20261015` | 6 | 1 |
| `research` | 10 | 2 |
| `research_20261015` | 15 | 0 |
| `storage_20261014` | 9 | 21 |

Current main and French quality samples, label templates and evaluations are published as separate frames. Prior samples and identity-priority queues stay local. Research reports keep their run IDs and query parameters; names such as `current` do not make an older report current.

The two CanLII comparison files and two small NSCA coverage/sampling files are retained as audit evidence. Machine-specific `project_status*.json` files are regenerated with `tools/status.py`. Internal Chinese working notes live under ignored `implementation/`.

See [the per-file inventory](repository_cleanup_20261015/artifact_inventory.json) and [the retired-run receipts](repository_cleanup_20261015/retired_runs.json). Retired runs cannot be replayed from their receipts alone.

Do not use broad `git add -f` on this directory. Publish a new result only after checking its contents, scope and provenance.
