# -*- coding: utf-8 -*-
"""corpus_counts.py — 语料级诊断计数的唯一产生脚本（规格 §13.1）

规格与 PROBLEMS.md 引用的全部语料级数字必须能由本脚本重放（约束九）：
模式字典逐字记录每个数字的口径；PATTERN_ASSERTIONS 在扫描前钉住每个模式的
正反样例——测量正则本身必须先被测过（v1.2 的 O.R. 124 事故：模式 \bO\.R\.\b
在真实写法上永不命中，124 恰为该坏模式对内嵌缩写片段的计数）。

读取遵守 §7.5：pyarrow iter_batches + 列投影；禁用 pd.read_parquet。
语料只读；本脚本唯一写仓库文件的动作是 --gen-sample 生成 prose_sample.py
（受控生成，重跑应逐字节一致）。

用法：
    python corpus_counts.py                  # 默认：全语料计数（含 S.C.R. 分解与恒等式断言）
    python corpus_counts.py --dedup          # 全语料 v1/v2 抽取+去重，按形状行数
    python corpus_counts.py --prose-sample   # 冻结散文样本上的锚基线（PROBLEMS #16）
    python corpus_counts.py --gen-sample     # 生成 prose_sample.py

口径约定（v1.3 定）：
- occurrence 计 = 非重叠匹配数；doc 计 = 至少一次命中的判决数。
- 语料 = corpus/SCC.parquet + corpus/ONCA.parquet（2026-08-30 快照，SHA-256 见 §1.3）。
- reporter 模式统一左锚 (?<![A-Za-z0-9])，只为排除更长 token 的片段
  （O.R.C.C.、C.O.R.P.I.Q.、1S.C.R. 类）；右锚见各行注释。
- S.C.R. 家族按印刷形式分解（模式名与行为一一对应）：
    scr_dotted_full  S.C.R.   尾点在（= 字面量 "S.C.R." 的锚定版）
    scr_dotless      S.C.R    缺尾点，后随非词非点（后随数字/字母的粘连不计，dots_any 同样不计）
    scr_bare         SCR      无点（后随句点算：句点是排版符号）
    scr_halfdot1/2   S.CR / SC.R  缺点半写法
    scr_spaced       S. C. R. 段内空格排版（19 世纪印刷惯例），尾点在，段间单空格
  恒等式（扫描时逐语料与合计硬断言）：
    scr_dots_any == dotted_full + dotless + bare + halfdot1 + halfdot2
  家族排名总数 = dots_any + spaced（裸 SCR 与段内空格都是该 reporter 的真实印刷形式；
  夹具 citation_en "(1883) 8 SCR 579" 即无点形式的实例）。
- 其他 reporter 的段内空格变体（D. L. R. 类）未单列——如需，扩本字典并补断言。
"""
import argparse
import hashlib
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.dirname(HERE)
ROOT = os.path.dirname(PIPE)
COLUMNS = ["citation_en", "document_date_en", "unofficial_text_en"]
COURTS = ["SCC", "ONCA"]
SNAPSHOT_SHA = {
    "SCC": "8e79cd406e302d9586ae2235e3c6c34b2797e2dbf6733872536fd2307ace6da6",
    "ONCA": "58c31f93063c6bcc83cb2014310737932ea4396443e3015213a923528d993775",
}

G = r"(?<![A-Za-z0-9])"  # 左锚：前邻不得是字母或数字

# ---- S.C.R. 家族（分解 + 恒等式） ------------------------------------------------
SCR_FAMILY = [
    ("scr_dotted_full", re.compile(G + r"S\.C\.R\.")),
    ("scr_dotless",     re.compile(G + r"S\.C\.R(?![\w.])")),
    ("scr_bare",        re.compile(G + r"SCR(?![\w])")),
    ("scr_halfdot1",    re.compile(G + r"S\.CR(?![\w])")),
    ("scr_halfdot2",    re.compile(G + r"SC\.R(?![\w])")),
]
RX_SCR_DOTS_ANY = re.compile(r"\bS\.?C\.?R\.?\b")        # 任意点子集、无段内空格（历史口径）
RX_SCR_SPACED = re.compile(G + r"S\. C\. R\.(?![A-Za-z])")

# ---- 五 reporter（左锚 + 右锚排除 O.R.C.C./C.C.C.P. 类更长缩写的片段） -------------
REPORTERS = [
    ("or_strict",  re.compile(G + r"O\.R\.(?![A-Za-z])")),
    ("ccc_strict", re.compile(G + r"C\.C\.C\.(?![A-Za-z])")),
    ("dlr_strict", re.compile(G + r"D\.L\.R\.(?![A-Za-z])")),
    ("wwr_strict", re.compile(G + r"W\.W\.R\.(?![A-Za-z])")),
]

# ---- 中立引用 / 内联标记 --------------------------------------------------------
RX_NEUTRAL = re.compile(r"(?<![\dA-Za-z])(?:19|20)\d{2}\s+SCC\s+\d+(?![\dA-Za-z])")
# 当事人名 ≤4 词（N=4：当事人名 1–4 词为主流写法，如 The Queen / Peguis Indian Band）
RX_VXN = re.compile(r"v\.\s+[A-Z][A-Za-z'\-]*(?:\s+[A-Za-z'\-]+){0,4}\s*\[\d+\]")
RX_VXPAR = re.compile(r"v\.\s+[A-Z][A-Za-z'\-]*(?:\s+[A-Za-z'\-]+){0,4}\s*\(\d{1,3}\)")

# ---- 字面量（§7.1 / PROBLEMS #11 #12 的 occurrence 计） ---------------------------
LITERALS = ["(2d)", "(3d)", "(N.S.)", "(Mass.)", "(Q. B.)",
            "H. of L.", "R. de J.", "C. de D.", "U, S. R.", "C.B., N.S."]

PATTERNS = dict(
    [("scr_dots_any", RX_SCR_DOTS_ANY), ("scr_spaced", RX_SCR_SPACED),
     ("neutral", RX_NEUTRAL), ("vxn", RX_VXN), ("vxparen", RX_VXPAR)]
    + SCR_FAMILY + REPORTERS
)
DOC_PATTERNS = {"neutral", "vxn", "vxparen"}  # doc 计；其余为 occ 计

# ---- 模式断言（P0）：测量正则本身必须先被测过 --------------------------------------
# (模式名, 样本, 期望命中数)。启动即断言，任一失败 exit 1，不进扫描。
PATTERN_ASSERTIONS = [
    ("scr_dotted_full", "[1935] S.C.R. 441", 1),
    ("scr_dotted_full", "S.C.R 572", 0),          # 缺尾点不属本模式
    ("scr_dotted_full", "S. C. R. 572", 0),       # 段内空格不属本模式（名实一致的锚）
    ("scr_dotless",     "S.C.R 572", 1),
    ("scr_dotless",     "S.C.R. 572", 0),         # 不得重复计入点式
    ("scr_dotless",     "S.C.R572", 0),           # 数字粘连：dots_any 同样不计
    ("scr_bare",        "(1883) 8 SCR 579", 1),
    ("scr_bare",        "S.C.R. 572", 0),
    ("scr_bare",        "SCREEN", 0),
    ("scr_halfdot1",    "S.CR 12", 1),
    ("scr_halfdot2",    "SC.R 12", 1),
    ("scr_spaced",      "S. C. R. 572", 1),
    ("scr_spaced",      "S.C.R. 572", 0),
    ("scr_dots_any",    "[1935] S.C.R. 441", 1),
    ("scr_dots_any",    "(1883) 8 SCR 579", 1),
    ("scr_dots_any",    "S. C. R. 572", 0),
    ("or_strict",       "[1962] O.R. 572", 1),
    ("or_strict",       "[2015] O.R.B.D. No. 1168", 0),   # 内嵌片段不计（v1.2 的 124 事故来源）
    ("or_strict",       "120 O.R. (3d) 572", 1),
    ("ccc_strict",      "107 C.C.C. 183", 1),
    ("dlr_strict",      "34 D.L.R. (2d) 451", 1),
    ("wwr_strict",      "[1928] 1 W.W.R. 40", 1),
    ("neutral",         "2019 SCC 65", 1),
    ("neutral",         "12019 SCC 65", 0),       # 左守卫：数字紧贴不计
    ("vxn",             "Brook v. Hook[11]", 1),
    ("vxn",             "Mitchell v. Peguis Indian Band, [1990] 2 S.C.R. 85", 0),
    ("vxn",             "Nowegijick v. The Queen, [1983] 1 S.C.R. 29", 0),
    ("vxparen",         "B-n v. B-n (1)", 1),
    ("vxparen",         "Breakey v. Carter (1881) 7 Q.L.R. 286", 0),  # 括号年份非页标记
]


def run_assertions():
    bad = []
    for name, sample, want in PATTERN_ASSERTIONS:
        got = len(PATTERNS[name].findall(sample))
        if got != want:
            bad.append((name, sample, want, got))
    if bad:
        for name, sample, want, got in bad:
            print(f"ASSERTION FAILED: {name} on {sample!r}: want {want}, got {got}")
        sys.exit(1)


def nk(s):
    return re.sub(r"[^A-Za-z0-9]", "", s).lower()


def iter_texts(court):
    import pyarrow.parquet as pq
    path = os.path.join(ROOT, "corpus", court + ".parquet")
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=500, columns=COLUMNS):
        d = batch.to_pydict()
        for cite, date, text in zip(d["citation_en"], d["document_date_en"],
                                    d["unofficial_text_en"]):
            yield cite, date, text


def default_mode():
    run_assertions()
    out = {}
    for court in COURTS:
        rows = nonempty = 0
        chars = 0
        occ = {k: 0 for k in PATTERNS}
        occ["scr_literal_recon"] = 0   # 对账用：无锚定字面量 str.count("S.C.R.")
        occ_lit = {k: 0 for k in LITERALS}
        docs = {k: 0 for k in DOC_PATTERNS}
        docs["self_citation_head3000"] = 0
        for cite, date, text in iter_texts(court):
            rows += 1
            if not text:
                continue
            nonempty += 1
            chars += len(text)
            for lit in LITERALS:
                if lit in text:
                    occ_lit[lit] += text.count(lit)
            if "S.C.R." in text:
                occ["scr_literal_recon"] += text.count("S.C.R.")
            for k, rx in PATTERNS.items():
                if k.startswith("scr"):
                    need = ("S.C.R", "SCR", "SC.R", "S.CR", "S. C. R")
                elif k == "or_strict":
                    need = ("O.R.",)
                elif k == "ccc_strict":
                    need = ("C.C.C.",)
                elif k == "dlr_strict":
                    need = ("D.L.R.",)
                elif k == "wwr_strict":
                    need = ("W.W.R.",)
                elif k == "neutral":
                    need = ("SCC",)
                else:  # vxn / vxparen
                    need = ("v.",)
                if not any(lit in text for lit in need):
                    continue
                n = len(rx.findall(text))
                occ[k] += n
                if k in DOC_PATTERNS and n:
                    docs[k] += 1
            if cite:
                target = nk(cite)
                if target and target in nk(text[:3000]):
                    docs["self_citation_head3000"] += 1
        out[court] = {"rows": rows, "nonempty_docs": nonempty, "text_chars": chars,
                      "literal_counts": occ_lit, "regex_occ": occ, "regex_docs": docs}
    both = {}
    for k in PATTERNS:
        both[k] = out["SCC"]["regex_occ"][k] + out["ONCA"]["regex_occ"][k]
    both["scr_literal_recon"] = (out["SCC"]["regex_occ"]["scr_literal_recon"]
                                 + out["ONCA"]["regex_occ"]["scr_literal_recon"])
    for lit in LITERALS:
        both["lit:" + lit] = out["SCC"]["literal_counts"][lit] + out["ONCA"]["literal_counts"][lit]
    for k in ("neutral", "vxn", "vxparen", "self_citation_head3000"):
        both["docs:" + k] = out["SCC"]["regex_docs"][k] + out["ONCA"]["regex_docs"][k]
    # S.C.R. 恒等式：逐语料与合计
    ident = {}
    ok_all = True
    for c in COURTS + ["BOTH"]:
        o = both if c == "BOTH" else out[c]["regex_occ"]
        total = (o["scr_dotted_full"] + o["scr_dotless"] + o["scr_bare"]
                 + o["scr_halfdot1"] + o["scr_halfdot2"])
        ok = o["scr_dots_any"] == total
        ok_all = ok_all and ok
        ident[c] = {"dots_any": o["scr_dots_any"], "sum_of_forms": total, "ok": ok}
    result = {"SCC": out["SCC"], "ONCA": out["ONCA"], "BOTH": both,
              "scr_identity": ident, "scr_family_ranking_total":
                  {"dots_any_plus_spaced": both["scr_dots_any"] + both["scr_spaced"]},
              "note": "occurrence 计=非重叠匹配；doc 计=至少一次命中；口径见本文件模式字典"}
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if not ok_all:
        sys.exit(1)


# ---------------------------------------------------------------- --dedup
def dedup_mode():
    run_assertions()
    sys.path.insert(0, PIPE)
    from run_regression import (V1_SHAPES, V2_SHAPES, V1_ORDER, V2_ORDER,
                                dedup_v1, dedup_v2, extract as rx_extract)
    res = {}
    for court in COURTS:
        acc = {"v1": {}, "v2": {}}
        totals = {"v1": 0, "v2": 0}
        raws = {"v1": 0, "v2": 0}
        for cite, date, text in iter_texts(court):
            if not text:
                continue
            for ver, shapes, order, dd in (("v1", V1_SHAPES, V1_ORDER, dedup_v1),
                                           ("v2", V2_SHAPES, V2_ORDER, dedup_v2)):
                raw = rx_extract(text, shapes)
                raws[ver] += len(raw)
                kept = dd(raw, order)
                totals[ver] += len(kept)
                for k in kept:
                    acc[ver][k["shape_name"]] = acc[ver].get(k["shape_name"], 0) + 1
        res[court] = {"per_shape_kept": acc, "kept_total": totals, "raw_total": raws,
                      "note": "跨度重叠去重（dedup_v1=规格 §7.4 订正前口径，dedup_v2=订正后口径）"}
    print(json.dumps(res, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- --prose-sample
def prose_sample_mode():
    run_assertions()
    sys.path.insert(0, HERE)
    from prose_sample import SAMPLES, META
    sys.path.insert(0, PIPE)
    from run_regression import V2_SHAPES, V2_ORDER, dedup_v2
    from run_regression import extract as rx_extract
    # 快照指纹校验：语料一换，样本整份作废
    for court in COURTS:
        got = sha256_file(os.path.join(ROOT, "corpus", court + ".parquet"))
        if got != META["snapshot_sha256"][court]:
            print(f"SNAPSHOT MISMATCH for {court}: sample void, re-run --gen-sample")
            sys.exit(1)
    wanted = {}
    for s in SAMPLES:
        if s["row"] is not None:
            wanted.setdefault(s["court"], set()).add(s["row"])
    texts = {}
    for court, rows in wanted.items():
        i = -1
        remaining = set(rows)
        for cite, date, text in iter_texts(court):
            i += 1
            if i in remaining:
                texts[(court, i)] = (cite, text)
                remaining.discard(i)
                if not remaining:
                    break
    hits = []
    total_chars = 0
    for s in SAMPLES:
        if s["row"] is None:
            continue
        cite, text = texts[(s["court"], s["row"])]
        slice_ = text[s["corpus_start"]:s["corpus_end"]]
        total_chars += len(slice_)
        kept = dedup_v2(rx_extract(slice_, V2_SHAPES), V2_ORDER)
        for k in kept:
            ctx_s = max(0, k["start"] - 40)
            ctx_e = min(len(slice_), k["end"] + 40)
            hits.append({"court": s["court"], "row": s["row"], "shape": k["shape_name"],
                         "raw": k["raw"],
                         "context": slice_[ctx_s:ctx_e].replace("\n", "\\n")})
    m = len(hits)
    n = total_chars
    anchor = ("基线实测 0 事件（n=%d 字符）→ rule of three：同一样本上误报事件上限 3 条"
              "（3/n 的 95%% 上界）" % n) if m == 0 else (
        "基线实测 %d 事件 / %.1f 每百万字符 —— 待逐条人工归类（已知类见 PROBLEMS #16）后定锚"
        % (m, m / n * 1e6))
    print(json.dumps({"sample_chars": n, "docs": len(SAMPLES), "hit_count": m,
                      "hits": hits, "anchor": anchor, "meta": META},
                     ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- --gen-sample
FN = re.compile(r"^\[\d+\]")
HEADER = re.compile(r"^(Cases? Cited|Statutes( and Regulations)? Cited|Regulations? Cited|"
                    r"Authors? Cited|Authorities Cited)\s*$", re.I)
REFERRED = re.compile(r"^Referred to:", re.I)
SEED = 20260830
TARGET_MIN, TARGET_MAX = 1400, 2000
STRATA = [(1877, 1967), (1968, 1995), (1996, 9999)]
PER_STRATUM = 50


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_slice(text):
    """自 len(text)//2 起取正文散文切片：剔除 [n] 脚注行；撞上 Cases Cited/Statutes/
    Authors 类节头（含其后 Referred to 行）视为该判决中部不适合取散文，返回 None。
    累计整行至 TARGET_MIN–TARGET_MAX 字符；单行超长时截取。返回 (start, end) 或 None。"""
    n = len(text)
    line_offsets = []
    off = 0
    for ln in text.split("\n"):
        line_offsets.append((off, ln))
        off += len(ln) + 1
    seg_start = None
    total = 0
    prev_end = None
    for lo, ln in line_offsets:
        if lo < n // 2:
            continue
        if FN.match(ln):
            continue
        if HEADER.match(ln) or REFERRED.match(ln):
            return None  # 中部撞节头：该判决中部不适合取散文，弃
        if not ln.strip():
            if seg_start is None:
                continue
            if total >= TARGET_MIN:
                return (seg_start, prev_end)
            continue
        if seg_start is None:
            seg_start = lo
        if total + len(ln) > TARGET_MAX:
            if total >= TARGET_MIN:
                return (seg_start, prev_end)
            return (seg_start, seg_start + TARGET_MAX)  # 单行超长，截取
        total += len(ln) + 1
        prev_end = lo + len(ln)
        if total >= TARGET_MIN:
            return (seg_start, prev_end)
    return (seg_start, prev_end) if total >= TARGET_MIN else None


def gen_sample_mode():
    run_assertions()
    samples = []
    for court in COURTS:
        cands = []  # (row, date, start, end) 仅收可成功构建切片的判决
        i = -1
        for cite, date, text in iter_texts(court):
            i += 1
            if not text or len(text) < 8000 or not date:
                continue
            try:
                year = int(str(date)[:4])
            except ValueError:
                continue
            sl = build_slice(text)
            if sl is None:
                continue
            cands.append({"row": i, "year": year, "date": str(date),
                          "corpus_start": sl[0], "corpus_end": sl[1]})
        rng = random.Random("%s:%s" % (SEED, court))
        rng.shuffle(cands)
        for a, b in STRATA:
            got = 0
            for c in cands:
                if got >= PER_STRATUM:
                    break
                if a <= c["year"] <= b:
                    samples.append({"court": court, "stratum": "%d-%d" % (a, b),
                                    "row": c["row"], "date": c["date"],
                                    "corpus_start": c["corpus_start"],
                                    "corpus_end": c["corpus_end"]})
                    got += 1
            while got < PER_STRATUM:
                samples.append({"court": court, "stratum": "%d-%d" % (a, b),
                                "row": None, "date": None, "corpus_start": None,
                                "corpus_end": None,
                                "note": "该层可取散文判决不足（含 1877 前无判决的可能）"})
                got += 1
    filled = [s for s in samples if s["row"] is not None]
    total_chars = sum(s["corpus_end"] - s["corpus_start"] for s in filled)
    lines = []
    lines.append("# -*- coding: utf-8 -*-")
    lines.append('"""prose_sample.py — 冻结的散文锚样本（PROBLEMS #16）')
    lines.append("")
    lines.append("由 corpus_counts.py --gen-sample 生成（seed=%d，程序与口径见该文件头注），" % SEED)
    lines.append("重跑应逐字节一致；人工不得手改条目。")
    lines.append("用途：现行七形状在本样本上的去重后命中逐条人工核实为误报后，即为阈值锚基线。")
    lines.append("分层：%s，两语料各层 %d 份；切片自判决文本 len//2 起，剔除 [n] 脚注行，" % (STRATA, PER_STRATUM))
    lines.append("撞 Cases Cited/Statutes/Authors 类节头即弃，累计 %d–%d 字符。" % (TARGET_MIN, TARGET_MAX))
    lines.append("row 为 parquet 0 基行号（iter_batches 展平顺序）。快照指纹如下，")
    lines.append("语料一换本样本整份作废（--prose-sample 会校验）。")
    lines.append('"""')
    lines.append("META = %r" % ({"seed": SEED, "target_min": TARGET_MIN,
                              "target_max": TARGET_MAX, "per_stratum": PER_STRATUM,
                              "strata": STRATA, "snapshot_sha256": SNAPSHOT_SHA,
                              "filled_docs": len(filled), "total_chars": total_chars},))
    lines.append("SAMPLES = %r" % (samples,))
    out_path = os.path.join(HERE, "prose_sample.py")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("written", out_path, "| filled:", len(filled), "/", len(samples),
          "| chars:", total_chars)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dedup", action="store_true")
    ap.add_argument("--prose-sample", action="store_true")
    ap.add_argument("--gen-sample", action="store_true")
    args = ap.parse_args()
    if args.dedup:
        dedup_mode()
    elif args.prose_sample:
        prose_sample_mode()
    elif args.gen_sample:
        gen_sample_mode()
    else:
        default_mode()
