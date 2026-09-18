# -*- coding: utf-8 -*-
"""registry_report.py — 天花板监测仪（PROBLEMS #88/#89，规格 2.4）

产出 `<run>/registry/ceiling.json`：

    {"typo_merges_total": N,
     "by_court_family": {"canadian": N1, "foreign": N2, "unclassified": N3},
     "foreign_examples": [...]}

**它量的是什么**：裁定层把「号码/年份差一点」的键当笔误并进另一组的次数，
按**被并掉那个键的法院代码法域**分档。分类依据只来自
`decisions/neutral_court_codes.csv` 的 `jurisdiction` 列（人工核实表）：
非加拿大法域 → `foreign`，代码不在表里 → `unclassified`，其余 → `canadian`。

**为什么必须有这个仪器**：全局登记簿只能覆盖我们有语料的法院。外国法院的
判决原文在 a2aj 数据集里根本不存在——**再加多少加拿大语料也补不出那一页**。
所以「笔误规则本身够不够好」不能靠登记簿回答；foreign 计数是那条数据驱动
路径的边界指示器：一旦 foreign > 0，说明出现的是「两侧都说不出身份」的并组，
必须回头重新校准笔误判据本身（收紧判据、不再单靠数量悬殊），而不是继续喂语料。
当前实测 foreign = 0（主线 33 起、实验线 46 起全部是加拿大法院）。

本脚本只读裁定层产物，不写任何上游文件（约束六）。
"""
import argparse
import collections
import csv
import io
import json
import os
import sys

PIPE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PIPE)
sys.path.insert(0, PIPE)

import classify                                               # noqa: E402
from normalize import nk                                      # noqa: E402

# 加拿大法域代码（`neutral_court_codes.csv` 的 jurisdiction 列取值，已核实）：
# CA=联邦、其余为省/地区代码。表里出现新代码时它**不会**被静默归到 canadian
# ——见 classify()：不在这两个集合里的一律 unclassified。
CANADIAN = frozenset((
    "CA", "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YK",
))
TYPO_BASES = ("anchor_variant_typo_number", "anchor_variant_typo_year")


def load_jurisdiction():
    """neutral_court_codes.csv → {nk(court_code): jurisdiction}。"""
    rows = classify.load_table("neutral_court_codes.csv")
    return {nk(r.get("court_code") or ""): (r.get("jurisdiction") or "").strip()
            for r in rows if (r.get("court_code") or "").strip()}


def court_family(code, jur_idx):
    if not code:
        return "unclassified"
    j = jur_idx.get(nk(code))
    if not j:
        return "unclassified"
    return "canadian" if j in CANADIAN else "foreign"


def collect(run_dir, scopes, jur_idx, registry=None):
    """裁定层各 scope 的 decided.csv → 笔误并组清单。"""
    rows, per_scope = [], collections.Counter()
    for scope in scopes:
        path = os.path.join(run_dir, "decide_out", scope, "decided.csv")
        if not os.path.exists(path):
            continue
        with io.open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("identity_basis") or "") not in TYPO_BASES:
                    continue
                key = r["merge_key"]
                code = key.split("|")[2] if len(key.split("|")) > 2 else ""
                reg = (registry or {}).get(key, "")
                rows.append({"scope": scope, "merge_key": key,
                             "typo_kind": r["identity_basis"],
                             "citation_kind": r.get("citation_kind") or "",
                             "jurisdiction": r.get("jurisdiction") or "",
                             "court_code": code,
                             "court_code_jurisdiction": jur_idx.get(nk(code), ""),
                             "family": court_family(code, jur_idx),
                             "case_name_modal": r.get("case_name_modal") or "",
                             "self_citation_of": r.get("self_citation_of") or "",
                             "registry_decision_id": reg})
                per_scope[scope] += 1
    # 同一键在多个 scope 出现只算一次；并组次数按 (scope, key) 计
    return rows, per_scope


def build(run_dir, scopes=("cross_court",), verbose=True):
    jur_idx = load_jurisdiction()
    reg_path = os.path.join(run_dir, "registry", "decision_registry.csv")
    registry = {}
    if os.path.exists(reg_path):
        with io.open(reg_path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                registry.setdefault(r["merge_key"], r.get("decision_id") or "")
    rows, per_scope = collect(run_dir, scopes, jur_idx, registry)
    by_family = collections.Counter(r["family"] for r in rows)
    by_kind = collections.Counter(r["typo_kind"] for r in rows)
    by_code = collections.Counter(r["court_code"] for r in rows)
    foreign = [r for r in rows if r["family"] == "foreign"]
    unclassified = [r for r in rows if r["family"] == "unclassified"]
    out = {
        "typo_merges_total": len(rows),
        "typo_merge_keys": len({r["merge_key"] for r in rows}),
        "typo_merge_keys_without_self_citation": len(
            {r["merge_key"] for r in rows if not r["self_citation_of"]}),
        "by_court_family": {k: by_family.get(k, 0)
                            for k in ("canadian", "foreign", "unclassified")},
        "foreign_examples": foreign[:50],
        "unclassified_examples": unclassified[:50],
        "by_typo_kind": dict(sorted(by_kind.items())),
        "by_court_code": dict(sorted(by_code.items())),
        "by_scope": dict(sorted(per_scope.items())),
        "rows": rows,
        "note": ("登记簿只覆盖我们有语料的法院；外国法院判决原文在 a2aj 里不存在，"
                 "再加加拿大语料也补不出。foreign > 0 是「必须重新校准笔误规则本身"
                 "（收紧判据、不再单靠数量悬殊）」的信号，到那时以这里的"
                 "foreign_examples 为具体案例。"),
    }
    path = os.path.join(run_dir, "registry", "ceiling.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    if verbose:
        print("ceiling: typo_merges_total=%d family=%s -> %s"
              % (out["typo_merges_total"], out["by_court_family"], path))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--scope", action="append", default=None,
                    help="裁定层 scope 目录名（可重复；默认 cross_court）")
    a = ap.parse_args()
    build(a.run_dir, scopes=tuple(a.scope) if a.scope else ("cross_court",))


if __name__ == "__main__":
    main()
