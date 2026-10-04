"""Run the extract and classify layers on one invented paragraph.

Offline and deterministic: reads only pipeline/ and decisions/, no corpus needed.

    python scripts/demo.py
"""
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
os.chdir(ROOT)

import classify  # noqa: E402
import extract  # noqa: E402

TEXT = ("[12] The standard of review was settled in Housen v. Nikolaisen, 2002 SCC 33, "
        "[2002] 2 S.C.R. 235. The English rule in Donoghue v. Stevenson, [1932] A.C. 562 (H.L.), "
        "was applied. See also R. v. Oakes, [1986] 1 S.C.R. 103, and section 7 of the Act, "
        "R.S.C. 1985, c. C-46.")


def main():
    cands, _ = extract.extract_candidates(TEXT, "ONCA_2020onca1", "2020", 0, "ONCA")
    tables = {n: classify.load_table(n + ".csv") for n in
              ("neutral_court_codes", "reporter_jurisdiction", "series_prefix", "case_origin")}
    tables["identifier_systems"] = classify.load_identifier_systems()
    tables["id_prefixes"] = classify.load_id_prefixes()
    tables["non_citation_words"] = classify.load_non_citation_words()
    tables["volume_system"] = classify.load_volume_systems()
    tables["court_designations"] = classify.load_court_designations()
    clf = classify.Classifier(tables, Counter())

    cols = ("raw_string", "shape_name", "match_start_offset", "citation_kind",
            "jurisdiction", "parse_status", "court_designation_raw")
    widths = (20, 20, 7, 9, 12, 19, 5)
    heads = ("raw_string", "shape", "offset", "kind", "jurisdiction", "parse_status", "court")
    print("  ".join("%-*s" % (w, h) for w, h in zip(widths, heads)).rstrip())
    rows = [clf.run_row({k: "" if v is None else str(v) for k, v in c.items()}) for c in cands]
    for r in sorted(rows, key=lambda r: int(r["match_start_offset"])):
        vals = [r[c] or "-" for c in cols]
        vals[1] = vals[1].replace("shape_", "")
        print("  ".join("%-*s" % (w, v) for w, v in zip(widths, vals)).rstrip())


if __name__ == "__main__":
    main()
