# -*- coding: utf-8 -*-
"""重建 decisions/non_citation_words.csv（程序化引号；观测计数现场重算）。

分类层 step2 的「被误当成报告集缩写的普通词」拒收表（rejected_reason=non_citation_word）。
来源：2026-10-03 边缘四法庭（TCC/SST/FPSLREB/CITT）edge4c 与主线 v16e 的 classify 输出（第一批词在 edge4/v16c 上建，第二批在 round-one 之后的 edge4c/v16e 上补）——
shape_vol_abbr_page 抽出的「卷 缩写 页」里，缩写位是结构词/日历词/案名片段而不是汇编。
典型：`Footnote 7 Section 69 of the Act` 的脚注号 + Section + 条号被读成「7 Section 69」。

三种匹配（对缩写串逐词做 nk 归一后比较）：
  whole       整个缩写串等于该词（Footnote、Section、X、May…）
  first_word  多词缩写的首词等于该词（`See Villani v`、`On November`、`INTRODUCTION On July`）
  last_word   多词缩写的末词等于该词（`Ontario Inc. v`、`Villani v`——案名被当缩写）
安全阀（在 classify 里，不在表里）：缩写已登记在 reporter_jurisdiction 的，绝不拒收。
每行 observed_count = 在两批 classify 输出里「未被其他理由拒绝、法域 UNSUPPORTED」的行数。
"""
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(os.path.dirname(HERE), "non_citation_words.csv")
csv.field_size_limit(10 ** 9)

FIELDS = ["word", "match_type", "category", "observed_count", "example",
          "source", "source_locator", "verification_status", "notes",
          "reviewer", "reviewed_at"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]

SPEC = (
    [(w, "whole", "structure_word") for w in
     ("Footnote", "Footnotes", "Section", "Sections", "Subsection", "Subsections",
      "Paragraph", "Paragraphs", "Clause", "Issue", "Citation", "File Number", "Appeal",
      "No", "In", "Canada", "GD",
      # 第二批（2026-10-03，边缘四法庭 round-one 之后的剩余噪声）
      "Article", "Articles", "Subparagraph", "Subparagraphs", "S", "At", "The", "Total", "Tab", "From", "See")]
    + [("X", "whole", "table_label")]
    + [(w, "whole", "document_heading") for w in ("DECISION", "Decision", "CONCLUSION", "Conclusion",
                                                   "INTRODUCTION", "Introduction")]
    + [(m, "whole", "calendar") for m in MONTHS]
    # `The December 12`：整词形式。不能用首词 The——真期刊/汇编以 The 开头（The Times L.R.、
    # The Advocate、The Reports=Browne v. Dunn 的 (1893) 6 The Reports 67，2026-10-03 差分抓到误杀）
    + [("The " + m, "whole", "calendar") for m in MONTHS]
    + [(m, "whole", "calendar_abbr") for m in ("Jan", "Feb", "Mar", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec")]
    + [("See", "first_word", "citation_signal"), ("On", "first_word", "calendar_lead"),
       ("In", "first_word", "calendar_lead"), ("At", "first_word", "document_label"),
       ("From", "first_word", "document_label"),
       ("INTRODUCTION", "first_word", "document_heading")]
    + [("v", "last_word", "party_marker"), ("c", "last_word", "party_marker")]
)


def nk(s):
    return re.sub(r"[^A-Za-z0-9]", "", s or "").lower()


def ck(s):
    """区分大小写的 key（只去标点）：ON CA（安省上诉法院标注）≠ On November；
    末词大写 C（`Cl. C`）≠ 案名分隔符 c.。"""
    return re.sub(r"[^A-Za-z0-9]", "", s or "")


def matches(mt, key, abbr):
    words = [ck(w) for w in re.split(r"\s+", abbr.strip()) if ck(w)]
    if not words:
        return False
    if mt == "whole":
        return ck(abbr) == key
    if len(words) < 2:
        return False
    return words[0] == key if mt == "first_word" else words[-1] == key


def main():
    reps = {r["normalized_key"] for r in csv.DictReader(
        open(os.path.join(os.path.dirname(HERE), "reporter_jurisdiction.csv"), encoding="utf-8"))}
    clash = [w for w, mt, _ in SPEC if mt == "whole" and nk(w) in reps]
    assert not clash, "拒收词与已登记汇编撞键：%r" % clash

    counts = {(w, mt): 0 for w, mt, _ in SPEC}
    collisions = []
    ex = {}
    for run, courts in (("edge4c", ("TCC", "SST", "FPSLREB", "CITT")),
                        ("v16e", ("SCC", "ONCA", "BCCA"))):
        for c in courts:
            p = os.path.join(ROOT, "data", "run_20261003_" + run, "classify_out", c, "classified.csv")
            for r in csv.DictReader(open(p, encoding="utf-8", newline="")):
                if r["citation_kind"] == "reporter" and r["jurisdiction"] not in ("", "UNSUPPORTED")                         and "non_citation_word" not in (r["rejected_reason"] or "") and not r["rejected_reason"]:
                    for w, mt, _ in SPEC:
                        if matches(mt, ck(w), r["abbreviation"]) and nk(r["abbreviation"]) not in reps:
                            collisions.append((w, mt, r["abbreviation"], r["raw_string"]))
                # 被本规则自己拒收的行也算观测（否则规则生效后的输出里计数归零、行被丢掉）
                other = [x for x in (r["rejected_reason"] or "").split("|") if x and x != "non_citation_word"]
                if r["citation_kind"] != "reporter" or r["jurisdiction"] != "UNSUPPORTED" or other:
                    continue
                ab = r["abbreviation"]
                if nk(ab) in reps:
                    continue
                for w, mt, _ in SPEC:
                    if matches(mt, ck(w), ab):
                        counts[(w, mt)] += 1
                        ex.setdefault((w, mt), r["raw_string"][:40])
    assert not collisions, "拒收规则会误伤已解析的行：%r" % collisions[:5]
    rows = []
    for w, mt, cat in SPEC:
        n = counts[(w, mt)]
        if n == 0:
            continue                      # 没有观测就不入表（约束八：无出处不入表）
        rows.append([w, mt, cat, n, ex[(w, mt)],
                     "语料实测：edge4 基线 run 与主线 v16c 的 classify 输出（shape 抽出的缩写位不是汇编）",
                     "data/run_20261003_edge4c/classify_out/*/classified.csv; "
                     "data/run_20261003_v16e/classify_out/*/classified.csv",
                     "observed_closed_word",
                     "封闭的结构词/日历词/案名片段，不是汇编缩写；已登记汇编永不拒收（classify 安全阀）",
                     "engineering lead (edge-court round)", "2026-10-03"])
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        w.writerows(rows)
    print("wrote", OUT, len(rows), "rows;", "total observed", sum(r[3] for r in rows))
    for r in rows:
        print("  %-14s %-10s %7d  %s" % (r[0], r[1], r[3], r[4]))


if __name__ == "__main__":
    main()
