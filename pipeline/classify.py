# -*- coding: utf-8 -*-
"""classify.py — 分类层（规格 §8）

逐行独立判定：确定 citation_kind 与 abbreviation、剔除非案例引证、查表定法域、
同形异义消歧、切分案名候选。**不读其他行，不做跨行统计**（那是归并层）。

用法
    python pipeline/classify.py --court SCC  --input data/extract_out/extracted.csv --output data/classify_out/SCC
    python pipeline/classify.py --court ONCA --input data/extract_out/extracted.csv --output data/classify_out/ONCA

输出
    <output>/classified.csv   抽取层全部字段 + §8.9 的十个新列
    <output>/manifest.json    参数、决策表行数、各档计数（约束九：数字须可重放）

不删行（约束五）：任何拒绝都只写 rejected_reason / name_rejected_reason 两个
字段之一，行本身照常输出并填满其余字段。

三处实现决定（规格未写明或明确留待裁决，均已实测，见 PROBLEMS）：
  1. §8.2 首行 normalize_code 的裁决（PROBLEMS #33）——加结构闸：仅当本行
     无卷号（中立引用的结构签名）时才启用归一键退路；有卷号一律只精确匹配。
     实测：挡掉 2,382 行带卷号的汇编误命中（F.C. 2,358 等），保住无卷号的
     带点真中立引用。归一命中一律记 lookup_mode=normalized，按 §8.5 的原则
     不与精确命中混同。
  2. §8.4 两条正则的作用域，规格只写 s 未定义。实测：只看 raw_string 时
     两条规则命中数均为 0（死代码，正是 §7.3 警告的模式）。故 FED_STATUTE
     作用于 preceding_text + raw_string；PARTY_INITIALS 采精确口径——
     要求前文正好以 R. v. 结尾**且**本行 raw 以 X.Y. 起头（实测 92 行）。
     宽口径「前文任意位置出现 R. v. A.B.」命中 15,999 行，会把大量真引证
     误杀，正踩 §8.8 警告的「引用次数被系统性低估」。
  3. §8 无 shape_neutral_bare 的专节。其 token 结构上即裸代码，按 §8.2 的
     两表并查逻辑类推处理（两表都命中→table_conflict 交人裁），理由与 §8.2
     所述相同：中立码表可立即填满而 reporter 表长期为空，设优先级等于让
     填表进度决定判定结果。此处为**补充规格的实现决定**，须人复核。
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import nk, normalize_code                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISIONS = os.path.join(ROOT, "decisions")

NEW_COLUMNS = ["citation_kind", "abbreviation", "jurisdiction",
               "jurisdiction_confidence", "lookup_mode", "vol_missing",
               "series_prefix", "candidate_case_name",
               "rejected_reason", "name_rejected_reason"]

# ---------------------------------------------------------------- §8.4 Step 2
FED_STATUTE = re.compile(r"(?:^|[\s(\[])(?:R\.S\.C\.|S\.C\.)\s*(?:18|19|20)\d{2}")
CHAPTER = re.compile(r"\bc\.\s*(?:[A-Z]|\d)")
PARTY_TAIL = re.compile(r"\bR\.\s*v\.\s*$")        # 前文正好以 R. v. 结尾
PARTY_HEAD = re.compile(r"^[A-Z]\.\s*[A-Z]\.")     # 本行 raw 以缩写型姓名起头

# ---------------------------------------------------------------- §8.7 Step 5
V_RE = re.compile(r"\bv\.?(?=\s)")
_ADMIT_LEAD_CHARS = set("[(«\"'‘“….")
_ADMIT_VERB_RE = re.compile(
    r"(?:citing|see also|see|per|applied|considered|referred to|"
    r"following|approving|distinguished|overruled|cf)\s+", re.IGNORECASE)
_ADMIT_IN_RE = re.compile(r"in\s+(?!re\s)", re.IGNORECASE)

# 形状 → 主缩写取自哪个字段（规格 §7.3）
TOKEN_SHAPES = {"shape_bracket", "shape_neutral_bare"}


# ------------------------------------------------------------------- 决策表 IO
def load_table(name):
    """读一张决策表。空表（只有表头）返回空列表——空表不是故障（§13.4）。"""
    path = os.path.join(DECISIONS, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f)
                if any((v or "").strip() for v in r.values())]


def build_index(rows, field):
    idx = {}
    for r in rows:
        k = (r.get(field) or "").strip()
        if k:
            idx.setdefault(k, []).append(r)
    return idx


def lookup_all(key, idx):
    return idx.get((key or "").strip(), [])


def lookup_one(key, idx):
    """唯一命中才返回；同键多行属建表缺陷，不猜。"""
    hits = lookup_all(key, idx)
    return hits[0] if len(hits) == 1 else None


def append_reason(row, field, reason):
    cur = row.get(field) or ""
    row[field] = (cur + "|" + reason) if cur else reason


# --------------------------------------------------------------- §8.7 案名清洗
def admit_candidate(cand):
    s = cand
    while True:
        before = s
        i = 0
        while i < len(s) and (s[i].isspace() or s[i] in _ADMIT_LEAD_CHARS):
            i += 1
        s = s[i:]
        m = _ADMIT_VERB_RE.match(s)
        if m:
            s = s[m.end():]
        m = _ADMIT_IN_RE.match(s)
        if m:
            s = s[m.end():]
        if s == before:
            break
    s = re.sub(r"[,;:.\s]+$", "", s)

    if len(s) > 120:
        return None, "too_long"
    if re.search(r"\[(?:18|19|20)\d{2}\]", s):
        return None, "has_bracketed_year"
    if sum(1 for _ in V_RE.finditer(s)) >= 2:
        return None, "multi_v"
    if not s:
        return None, "empty_after_clean"
    return s, None


def split_case_name(row):
    """§8.7：取**最后一个** v.；候选取到 preceding_text 末尾（不截到 v.）；
    找不到分隔符即放弃（不退化为从位置 0 取）。"""
    pre = row.get("preceding_text") or ""
    last = None
    for m in V_RE.finditer(pre):
        last = m

    if last is None:
        append_reason(row, "name_rejected_reason", "no_v_structure")
        row["candidate_case_name"] = ""
        return

    sep = max(pre.rfind(";", 0, last.start()),
              pre.rfind(":", 0, last.start()),
              pre.rfind("\n", 0, last.start()))
    if sep == -1:
        append_reason(row, "name_rejected_reason", "no_separator_before_v")
        row["candidate_case_name"] = ""
        return

    cand = pre[sep + 1:].strip().rstrip(",").strip()
    cleaned, reject = admit_candidate(cand)
    if reject:
        append_reason(row, "name_rejected_reason", reject)
        row["candidate_case_name"] = ""
    else:
        row["candidate_case_name"] = cleaned


# ---------------------------------------------------------------- §8.6 Step 4
def disambiguate_by_structure(row, candidates):
    """只用本行自带的卷号与年份，与候选法域的取值区间比对（§8.6）。
    零命中或多命中一律 UNSUPPORTED —— 多个候选吻合就不猜。"""
    vol, year = row.get("vol"), row.get("year_start")
    if not vol or not year:
        return "UNSUPPORTED"
    try:
        vol, year = int(vol), int(year)
    except ValueError:
        return "UNSUPPORTED"

    matching = []
    for c in candidates:
        try:
            vs = int(c.get("vol_range_start") or 0)
            ve = int(c.get("vol_range_end") or 99999)
            ys = int(c.get("year_range_start") or 0)
            ye = int(c.get("year_range_end") or 9999)
        except ValueError:
            continue
        if vs <= vol <= ve and ys <= year <= ye:
            matching.append(c)

    return matching[0]["jurisdiction"] if len(matching) == 1 else "UNSUPPORTED"


# --------------------------------------------------------------------- 主流程
class Classifier(object):
    def __init__(self, tables, stats):
        self.court_exact = build_index(tables["neutral_court_codes"], "court_code")
        self.court_norm = build_index(tables["neutral_court_codes"], "normalized_key")
        self.rep_exact = build_index(tables["reporter_jurisdiction"], "abbreviation")
        self.rep_norm = build_index(tables["reporter_jurisdiction"], "normalized_key")
        self.prefix_norm = build_index(tables["series_prefix"], "normalized_key")
        self.stats = stats

    def _court_lookup(self, printed_token, has_vol):
        """中立码表查询。PROBLEMS #33 的结构闸在此：有卷号即印刷汇编的结构
        签名，不启用归一键退路。"""
        hit = lookup_one(printed_token, self.court_exact)
        if hit:
            return hit, "exact"
        if has_vol:
            # 只统计「闸门真的挡下了一次归一命中」，不统计「闸门被应用」——
            # 后者含大量本来就不会命中的行，会把闸门的功劳夸大两个数量级
            if lookup_one(normalize_code(printed_token), self.court_norm):
                self.stats["court_false_hit_blocked_by_vol_gate"] += 1
            return None, ""
        hit = lookup_one(normalize_code(printed_token), self.court_norm)
        if hit:
            self.stats["court_hit_via_normalized"] += 1
            return hit, "normalized"
        return None, ""

    def _two_table(self, row, printed_token):
        """§8.2 两表并查：都命中即 table_conflict 交人裁，不设优先级。"""
        has_vol = bool((row.get("vol") or "").strip())
        court_hit, court_mode = self._court_lookup(printed_token, has_vol)

        reporter_hits = lookup_all(printed_token, self.rep_exact)
        rep_mode = "exact" if reporter_hits else ""
        if not reporter_hits:
            reporter_hits = lookup_all(nk(printed_token), self.rep_norm)
            rep_mode = "normalized" if reporter_hits else ""

        # 两表都命中，但**匹配成色不同档**时，精确的一方胜出——印刷串精确等于
        # 哪张表的键，就归哪张。这不是给冲突开优先级（§8.2 禁的是那个），而是
        # 认定「同档才算冲突」：FC 精确等于中立码、只在去标点后才碰到 reporter
        # 的 F.C.，两者不是同一个印刷事实。与 #33 的裁决同源（精确 > 模糊），
        # 方向相反：那次挡的是归一查法院表造假命中，这次挡的是归一查汇编表造假冲突。
        if court_hit and reporter_hits and court_mode != rep_mode:
            if court_mode == "exact":
                reporter_hits = []          # 中立码胜出，按下方 neutral 分支定案
            else:
                court_hit = None            # 汇编胜出，落 Step 3 查法域
            self.stats["conflict_resolved_by_match_grade"] += 1

        if court_hit and not reporter_hits:
            if court_mode == "normalized":
                # 归一命中不是印刷事实：判决上印的是 F.C.，与代码 FC 只是「去
                # 标点后同形」，这是一次推断。按约束四不给判定——给它打
                # confirmed 等于拿模糊匹配当确证，正是「inferred 标签只是给猜测
                # 发许可证」所禁。lookup_mode 已留痕，表填好后可回溯重判。
                row["citation_kind"] = "ambiguous"
                row["abbreviation"] = printed_token
                row["jurisdiction"] = "UNSUPPORTED"
                row["jurisdiction_confidence"] = "unsupported"
                row["lookup_mode"] = "normalized"
                self.stats["neutral_withheld_fuzzy_only"] += 1
                return True
            row["citation_kind"] = "neutral"
            row["abbreviation"] = court_hit["court_code"]
            row["jurisdiction"] = court_hit["jurisdiction"]
            row["jurisdiction_confidence"] = "confirmed"
            row["lookup_mode"] = court_mode
            return True                      # 已定案，不进 Step 3
        if court_hit and reporter_hits:
            row["citation_kind"] = "ambiguous"
            row["abbreviation"] = printed_token
            row["jurisdiction"] = "UNSUPPORTED"
            row["jurisdiction_confidence"] = "unsupported"
            append_reason(row, "rejected_reason", "table_conflict")
            return True
        row["citation_kind"] = "reporter"
        row["abbreviation"] = printed_token
        return False                         # 落入 Step 3

    def step1(self, row):
        shape = row["shape_name"]
        if shape == "shape_leading_abbr":
            # §8.3：前缀校验。leading_abbr 不参与法域判定，主缩写只取 abbr
            norm_prefix = normalize_code(row.get("leading_abbr") or "")
            if not lookup_one(norm_prefix, self.prefix_norm):
                append_reason(row, "rejected_reason", "unrecognized_series_prefix")
            else:
                row["series_prefix"] = row.get("leading_abbr") or ""
            row["citation_kind"] = "reporter"
            row["abbreviation"] = row.get("abbr") or ""
            return False
        if shape in TOKEN_SHAPES:
            return self._two_table(row, row.get("token") or "")
        row["citation_kind"] = "reporter"
        row["abbreviation"] = row.get("abbr") or ""
        return False

    def step2(self, row):
        """§8.4：剔除非案例引证。被标记的行继续填其余字段，不丢弃（约束五）。"""
        raw = row.get("raw_string") or ""
        pre = row.get("preceding_text") or ""
        window = pre + " " + raw
        if FED_STATUTE.search(window) and CHAPTER.search(window):
            append_reason(row, "rejected_reason", "federal_statute")
        if PARTY_TAIL.search(pre) and PARTY_HEAD.match(raw):
            append_reason(row, "rejected_reason", "party_initials")

    def step3(self, row):
        """§8.5：法域查表。精确优先、归一键作退路，lookup_mode 必须留痕。"""
        abbr = row.get("abbreviation") or ""
        mode = "exact"
        candidates = lookup_all(abbr, self.rep_exact)
        if not candidates:
            candidates = lookup_all(nk(abbr), self.rep_norm)
            mode = "normalized" if candidates else "exact"

        if len(candidates) == 1:
            row["jurisdiction"] = candidates[0].get("jurisdiction") or "UNSUPPORTED"
            row["jurisdiction_confidence"] = candidates[0].get("confidence") or ""
            row["lookup_mode"] = mode
        elif len(candidates) > 1:
            row["jurisdiction"] = disambiguate_by_structure(row, candidates)
            row["jurisdiction_confidence"] = "inferred"
            row["lookup_mode"] = mode
            # §8.6 补充规则：无卷号时消歧只能靠年份，误判风险显著更高，须留痕
            if not (row.get("vol") or "").strip():
                row["vol_missing"] = "true"
        else:
            row["jurisdiction"] = "UNSUPPORTED"
            row["jurisdiction_confidence"] = "unsupported"

    def run_row(self, row):
        for c in NEW_COLUMNS:
            row.setdefault(c, "")
        settled = self.step1(row)
        self.step2(row)
        if not settled:
            self.step3(row)
        split_case_name(row)

        self.stats["kind_" + (row["citation_kind"] or "none")] += 1
        for r in (row.get("rejected_reason") or "").split("|"):
            if r:
                self.stats["rejected_" + r] += 1
        for r in (row.get("name_rejected_reason") or "").split("|"):
            if r:
                self.stats["name_rejected_" + r] += 1
        if row["jurisdiction"] == "UNSUPPORTED":
            self.stats["jurisdiction_unsupported"] += 1
        elif row["jurisdiction"]:
            self.stats["jurisdiction_resolved"] += 1
        if row["candidate_case_name"]:
            self.stats["case_name_split"] += 1
        return row


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--court", required=True,
                    help="法院前缀，按 source_decision_citation 的 {COURT}_ 过滤（§7.3）")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    stats = Counter()
    tables = {n: load_table(n + ".csv") for n in
              ("neutral_court_codes", "reporter_jurisdiction",
               "series_prefix", "case_origin")}
    clf = Classifier(tables, stats)

    os.makedirs(args.output, exist_ok=True)
    out_path = os.path.join(args.output, "classified.csv")
    tmp = out_path + ".tmp"
    prefix = args.court + "_"

    with open(args.input, encoding="utf-8", newline="") as fin:
        reader = csv.DictReader(fin)
        fieldnames = list(reader.fieldnames) + NEW_COLUMNS
        with open(tmp, "w", encoding="utf-8", newline="") as fout:
            w = csv.DictWriter(fout, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for row in reader:
                stats["input_rows"] += 1
                if not (row.get("source_decision_citation") or "").startswith(prefix):
                    continue
                stats["court_rows"] += 1
                w.writerow(clf.run_row(row))
    os.replace(tmp, out_path)

    manifest = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "court": args.court,
        "input": os.path.relpath(args.input, ROOT).replace("\\", "/"),
        "spec_section": "8",
        "decision_table_rows": {k: len(v) for k, v in tables.items()},
        "stats": dict(sorted(stats.items())),
    }
    with open(os.path.join(args.output, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print("court=%s  input %d rows -> court %d rows -> %s"
          % (args.court, stats["input_rows"], stats["court_rows"], out_path))
    for k, v in sorted(stats.items()):
        print("   %-34s %d" % (k, v))


if __name__ == "__main__":
    main()
