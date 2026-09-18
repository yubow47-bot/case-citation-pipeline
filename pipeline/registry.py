# -*- coding: utf-8 -*-
"""registry.py — 全局判决登记簿（PROBLEMS #88/#89，规格见
`implementation/prompt_88_89_registry.md`）

**要治的病**：裁定层 `decide.py:570` 的笔误闸只认「这一行自己带的
`self_citation_of`」，而那个标记**只在判决自己所属法院那一轮**产生
（`merge.py:875`）。于是：

  * #88 跨院失明：ONCA 那一轮不知道 `2002 SCC 3` 是语料里的真判决
    （Chieu v. Canada），把它当 `2002 SCC 33` Housen 的号码笔误并了进去；
  * #89 语料缺席：跑 BCCA/CITT 时 SCC 语料不在场，SCC 判决全部无锚。

**本模块只做一件事**：在**所有法院的归并层跑完后、第一个裁定层开跑前**，
把所有已知真判决的「自己印的引证」归一成 merge_key 形式，落成一张 run 级
产物 `<run>/registry/decision_registry.csv`，供**每一轮**裁定层查询。

两个来源（union）：

  * `source=self_citation` —— 各法院 `merge_out/<court>/merged.csv` 中
    `self_citation_of` 非空的行（判决在自己头部印的引证）。这是现状的
    「法院作用域登记簿」的并集，一字不改地搬进全局表。
  * `source=corpus_citation` —— 锚语料（`--anchor-corpus`）的 `citation_en`
    逐条归一构键。**只生成登记簿，不抽取、不分类、不计数**（否则 dd 口径被
    污染，见 PROBLEMS #89 的技术难点）。

**边界（不许越）**：

  * 本模块**不回写**上游任何产物，也不改上游任何一行（约束六、铁律二）。
  * 构键**复用既有归一函数**（`merge.build_merge_key_v2`、`normalize.nk`）、
    **复用抽取层的形状匹配与分类层**，不新写任何正则、不新写任何缩写清单
    （铁律二）。
  * 读语料只用 `pyarrow.parquet.ParquetFile.iter_batches` 按列投影，
    语料一律只读（规格 §7.5）。
  * `citation_en` 不是引证的（案卷号）→ 构不出键 → **如实跳过并计数**，
    绝不填默认值（铁律四：无证据不给判定）。

**为什么键的缩写槽必须落在 `neutral_court_codes` 里**：登记簿唯一的用途是
回答「这个键是不是某件真判决自己印的引证」。缩写槽不是法院代码的键（供应商
序列号、案卷号、汇编缩写）解答不了这个问题；进表的代价是让一个跟判决身份无关
的串获得「真判决」的豁免。实测（`implementation/_probe_registry_keys.py`）：
SCC 语料 10891 行里，9119 行的缩写槽不是法院代码（全是 `S.C.R.` 类汇编写法），
进表只增加噪声、不改变任何判定的可得信息——因为裁定层 `neu[k]` 只对
`citation_kind=neutral` 的键开放笔误闸，而那些键在归并表里一律是 reporter。

自校验闸：同一法院若既被抽取、又能从语料构键（主线的 SCC/ONCA），两条路径
的键集合必须比对，差集逐条落 `<run>/registry/registry_crosscheck.csv` 并归类
（见 `crosscheck()` 与 manifest 的 `crosscheck_unclassified`）。
"""
import argparse
import collections
import csv
import hashlib
import io
import json
import os
import sys

PIPE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PIPE)
sys.path.insert(0, PIPE)

import pyarrow.parquet as pq                                  # noqa: E402
import classify                                               # noqa: E402
import extract                                                # noqa: E402
import merge as merge_mod                                     # noqa: E402
from normalize import nk                                      # noqa: E402

REGISTRY_FIELDS = ["merge_key", "decision_id", "source_court", "source"]
CROSSCHECK_FIELDS = ["court", "category", "merge_key", "detail"]
CORPUS_COL = "citation_en"
SOURCE_SELF = "self_citation"
SOURCE_CORPUS = "corpus_citation"
BATCH = 2000


# ------------------------------------------------------------------ 工具
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_csv(path, fields, rows):
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    os.replace(tmp, path)


def build_classifier():
    """分类层的表与实例（与 `classify.main()` 同源，不另立一份表清单）。"""
    stats = collections.Counter()
    tables = {n: classify.load_table(n + ".csv") for n in
              ("neutral_court_codes", "reporter_jurisdiction",
               "series_prefix", "case_origin")}
    tables["identifier_systems"] = classify.load_identifier_systems()
    tables["volume_system"] = classify.load_volume_systems()
    tables["court_designations"] = classify.load_court_designations()
    return classify.Classifier(tables, stats), stats, tables


def court_code_set(neutral_rows):
    """法院代码封闭集合（`neutral_court_codes.court_code`，nk 后）。"""
    return frozenset(nk(r.get("court_code") or "") for r in neutral_rows)


# ------------------------------------------------------------------ 路径一：自引
def self_citation_entries(courts, run_dir):
    """各法院 merged.csv 的 `self_citation_of` 并集。键=逐行给，判决 id 原样。"""
    entries = set()
    per_court = collections.Counter()
    for court in courts:
        path = os.path.join(run_dir, "merge_out", court, "merged.csv")
        if not os.path.exists(path):
            continue
        with io.open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                for did in (r.get("self_citation_of") or "").split("|"):
                    if not did:
                        continue
                    entries.add((r["merge_key"], did, court, SOURCE_SELF))
                    per_court[court] += 1
    return entries, per_court


# ------------------------------------------------------------------ 路径二：锚语料
def one_key(clf, court, cite, court_codes):
    """`citation_en` 整串当**一件判决自己印的引证**构一个键。

    复用抽取层的形状匹配 + #21 兜底语义 + 重叠去重（`extract.process_text`），
    再走分类层（`Classifier.run_row`），最后用归并层的键函数构键。

    要求**恰好留下 1 条候选**。被压掉的候选不算问题——那正是抽取层在同一跨度上
    的常规行为（`2002 SCC 3` 同时命中 neutral_bare 与 vol_abbr_page，长者胜、
    短者进 superseded；`[1989] 2 S.C.R. 368` 压掉内嵌的 `2 S.C.R. 368`）。
    留下 0 条（案卷号 `C33725`、形状不认的串）或 ≥2 条（一串里印了两条互不重叠
    的引证）都说明这一串**不是「一条引证」**，如实返回原因、不入表（铁律四）。"""
    kept, removed = extract.process_text(
        cite, extract.source_decision_citation(court, cite), "")
    if not kept:
        return None, "shape_no_kept", "", 0
    if len(kept) != 1:
        return None, "shape_multiple_kept", "", 0
    row = clf.run_row(dict(kept[0]))
    if row.get("rejected_reason"):
        return None, "row_rejected", row["rejected_reason"], len(removed)
    key = merge_mod.build_merge_key_v2(row)
    code = key.split("|")[2] if len(key.split("|")) > 2 else ""
    if code not in court_codes:
        # 缩写槽不是法院代码：它不是任何判决的中立/汇编身份（供应商序列号、
        # 案卷号等）。无证据不给判定（铁律四）。
        return None, "abbreviation_not_a_court_code", code, len(removed)
    return key, "", "", len(removed)


def corpus_citation_entries(courts, corpus_dir, clf, court_codes):
    """锚语料的 `citation_en` → 键。返回 (entries, stats, per_court)。"""
    entries = set()
    stats = collections.Counter()
    per_court = collections.Counter()
    samples = collections.defaultdict(list)
    for court in courts:
        path = os.path.join(corpus_dir, court + ".parquet")
        if not os.path.exists(path):
            raise SystemExit("锚语料不存在：%s" % path)
        pf = pq.ParquetFile(path)
        if CORPUS_COL not in list(pf.schema_arrow.names):
            raise SystemExit("锚语料 %s 缺 %s 列（列投影不可行）" % (path, CORPUS_COL))
        stats["corpus_sha256_" + court] = sha256_file(path)
        n = 0
        for batch in pf.iter_batches(batch_size=BATCH, columns=[CORPUS_COL]):
            for cite in batch.to_pydict()[CORPUS_COL]:
                n += 1
                if not cite:
                    stats["skipped_empty"] += 1
                    continue
                key, why, detail, removed = one_key(clf, court, cite, court_codes)
                if key is None:
                    stats["skipped_" + why] += 1
                    if len(samples[why]) < 5:
                        samples[why].append([court, cite, detail])
                    continue
                stats["keys_with_superseded_subspan"] += 1 if removed else 0
                entries.add((key, extract.source_decision_citation(court, cite),
                             court, SOURCE_CORPUS))
                per_court[court] += 1
        stats["corpus_rows_" + court] = n
    stats["corpus_keys"] = len({e[0] for e in entries})
    for why in sorted(samples):
        stats["sample_" + why] = samples[why]
    return entries, stats, per_court


# ------------------------------------------------------------------ 自校验
def crosscheck(entries, self_courts, corpus_courts):
    """两个来源的键集合比对。同一法院两边都在场时才比。

    差集**不为空不等于失败**（早年判决没有中立引证、案卷号类 `citation_en`、
    键形状差异都会造成差异），但每一类必须在报告里归类说明；归不了类的条目
    > 0 → 停手报告（规格 2.2）。"""
    rows = []
    summary = {}
    keys_self = collections.defaultdict(set)
    keys_corpus = collections.defaultdict(set)
    for key, _did, court, source in entries:
        if source == SOURCE_SELF:
            keys_self[court].add(key)
        else:
            keys_corpus[court].add(key)
    for court in sorted(set(self_courts) & set(corpus_courts)):
        s, c = keys_self.get(court, set()), keys_corpus.get(court, set())
        only_self, only_corpus = sorted(s - c), sorted(c - s)
        for k in only_self:
            rows.append({"court": court, "category": "self_not_in_corpus",
                         "merge_key": k, "detail": ""})
        for k in only_corpus:
            rows.append({"court": court, "category": "corpus_not_in_self",
                         "merge_key": k, "detail": ""})
        summary[court] = {"self_keys": len(s), "corpus_keys": len(c),
                          "self_not_in_corpus": len(only_self),
                          "corpus_not_in_self": len(only_corpus),
                          "both_sides": len(s & c)}
    rows.sort(key=lambda r: (r["court"], r["category"], r["merge_key"]))
    return rows, summary


def explain_crosscheck(keys, merged_path):
    """把一类差集里的键对上归并表，给出可归类的证据（citation_kind / 法域 /
    出现次数），供报告把每一类差异说清楚。"""
    want = set(keys)
    kinds, jurisdictions, found = collections.Counter(), collections.Counter(), {}
    if os.path.exists(merged_path):
        with io.open(merged_path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["merge_key"] in want:
                    kinds[r.get("citation_kind") or ""] += 1
                    jurisdictions[r.get("jurisdiction") or ""] += 1
                    found[r["merge_key"]] = {
                        "citation_kind": r.get("citation_kind") or "",
                        "occurrence_count": r.get("occurrence_count") or "",
                        "distinct_decisions_count": r.get("distinct_decisions_count") or "",
                        "self_citation_of": r.get("self_citation_of") or ""}
    return {"rows": len(keys), "in_merged": len(found),
            "citation_kind": dict(sorted(kinds.items())),
            "jurisdiction": dict(sorted(jurisdictions.items())),
            "samples": [[k, found.get(k)] for k in sorted(keys)[:10]]}


# ------------------------------------------------------------------ 主流程
def build(run_dir, anchor_courts=(), corpus_dir=None, extracted_courts=(),
          verbose=True):
    """生成登记簿 + 自校验。返回 manifest 字典。"""
    corpus_dir = corpus_dir or os.path.join(ROOT, "corpus")
    reg_dir = os.path.join(run_dir, "registry")
    os.makedirs(reg_dir, exist_ok=True)

    neutral_rows = classify.load_table("neutral_court_codes.csv")
    court_codes = court_code_set(neutral_rows)
    clf, _cstats, _tables = build_classifier()

    entries, self_per_court = self_citation_entries(extracted_courts, run_dir)
    corpus_stats = collections.Counter()
    corpus_per_court = collections.Counter()
    if anchor_courts:
        centries, corpus_stats, corpus_per_court = corpus_citation_entries(
            tuple(anchor_courts), corpus_dir, clf, court_codes)
        entries |= centries

    rows = [{"merge_key": k, "decision_id": did, "source_court": court,
             "source": source} for k, did, court, source in sorted(entries)]
    _write_csv(os.path.join(reg_dir, "decision_registry.csv"),
               REGISTRY_FIELDS, rows)

    xc_rows, xc_summary = crosscheck(entries, set(extracted_courts),
                                     set(anchor_courts))
    if xc_rows:
        _write_csv(os.path.join(reg_dir, "registry_crosscheck.csv"),
                   CROSSCHECK_FIELDS, xc_rows)

    per_court, by_source = collections.Counter(), collections.Counter()
    for r in rows:
        per_court[r["source_court"]] += 1
        by_source[r["source"]] += 1

    # 差集的归类说明（不是「归不了类就失败」的自动判定：归不了类的条目要靠
    # 报告里的人复核，这里把每一类的可得证据都摆出来，绝不静默当 0）
    unclassified = {}
    for court in sorted(xc_summary):
        merged_path = os.path.join(run_dir, "merge_out", court, "merged.csv")
        for category in ("self_not_in_corpus", "corpus_not_in_self"):
            ks = [r["merge_key"] for r in xc_rows
                  if r["court"] == court and r["category"] == category]
            if ks:
                unclassified["%s/%s" % (court, category)] = explain_crosscheck(
                    ks, merged_path)

    manifest = {
        "registry_rows": len(rows),
        "registry_keys": len({r["merge_key"] for r in rows}),
        "by_source": dict(sorted(by_source.items())),
        "by_court": dict(sorted(per_court.items())),
        "anchor_courts": list(anchor_courts),
        "extracted_courts": list(extracted_courts),
        "corpus_dir": corpus_dir,
        "corpus_stats": {k: v for k, v in sorted(corpus_stats.items())},
        "self_citation_rows_by_court": dict(sorted(self_per_court.items())),
        "corpus_keys_by_court": dict(sorted(corpus_per_court.items())),
        "crosscheck": xc_summary,
        "crosscheck_explanations": unclassified,
        "crosscheck_note": ("差集不为空不等于失败（早年判决无中立引证、citation_en "
                            "是案卷号等）；每一类差异必须在报告里归类说明，"
                            "归不了类的条目 > 0 → 停手报告"),
    }
    with io.open(os.path.join(reg_dir, "manifest.json"), "w",
                 encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    if verbose:
        print("registry: %d 行 / %d 键 -> %s"
              % (manifest["registry_rows"], manifest["registry_keys"],
                 os.path.join(reg_dir, "decision_registry.csv")))
        print("  by_source %s" % manifest["by_source"])
        print("  by_court  %s" % manifest["by_court"])
        if anchor_courts:
            print("  crosscheck %s" % json.dumps(xc_summary, ensure_ascii=False))
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", required=True,
                    help="本次运行的输出目录（写 <run>/registry/）")
    ap.add_argument("--anchor-corpus", action="append", default=[],
                    help="锚语料法院码（可重复）；只生成登记簿，不抽取不计数")
    ap.add_argument("--corpus-dir", default=None,
                    help="语料目录（默认仓库 corpus/）；锚语料只读引用")
    ap.add_argument("--extracted-courts", action="append", default=[],
                    help="本次实际抽取的法院（可重复，也接受逗号分隔），"
                         "用于自引来源与自校验；不传 = 不读 self_citation 来源")
    a = ap.parse_args()
    extracted = tuple(c for item in a.extracted_courts
                      for c in item.split(",") if c)
    build(a.run_dir, anchor_courts=tuple(a.anchor_corpus),
          corpus_dir=a.corpus_dir, extracted_courts=extracted)


if __name__ == "__main__":
    main()
