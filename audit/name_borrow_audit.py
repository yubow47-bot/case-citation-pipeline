"""借名审计（只读）：#45 剥尾把「A v. B, 引证, <连接> C v. D, [本行]」剪成 A v. B。

对每个已给出案名的行，按生产代码 split_case_name 的同一路径重算：
  cand = 最后一个 v. 所在段（前一个 ; : 换行 之后）
  若 #45 剥尾触发、且被剪掉的尾巴里还有 v.（另一个案名）-> 可疑借名
再按尾巴里最后那个案名前的连接词分类；_HISTORY_RE（aff'd/rev'd/var'd/leave）是同案沿革，
借名在那里是**正确**的，单列。
只读 run 与 pipeline；输出 audit/findings/name_borrow_audit.md 与 data/audit/name_borrow_rows.csv。
"""
import csv, os, re, sys, collections, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import classify as K

csv.field_size_limit(10 ** 9)
R = os.path.join(ROOT, "data", "run_20260918_scc_onca_bcca")
CONN = re.compile(r"([A-Za-z’'.]+(?:\s+[a-z’'.]+){0,2})\s*$")


def analyse(pre):
    last = None
    for m in K.V_RE.finditer(pre):
        last = m
    if last is None:
        return None
    sep = max(pre.rfind(";", 0, last.start()), pre.rfind(":", 0, last.start()), pre.rfind("\n", 0, last.start()))
    if sep == -1:
        return None
    cand = pre[sep + 1:].strip().rstrip(",").strip()
    m = K._ADMIT_CITE_TAIL_RE.search(cand)
    if not m:
        return None
    tail = cand[m.start():]
    vs = list(K.V_RE.finditer(tail))
    if not vs:
        return None
    # 尾巴里最后一个案名起点：最后一个 v. 之前，往回找到最近的「, 」或「 小写连接词 」
    head = tail[:vs[-1].start()]
    # 去掉最后案名的首段（大写词序列），剩下的末尾就是连接词
    h = re.sub(r"(?:\b[A-Z][\w’'().&-]*\.?\s*)+$", "", head.rstrip())
    h = h.rstrip(" ,")
    c = CONN.search(h)
    conn = c.group(1).lower() if c else ""
    return cand, tail, conn


def bucket(conn):
    if K._HISTORY_RE.search(conn):
        return "history(同案沿革，借名正确)"
    for k, pat in [("foll'g/following", r"foll|follow"), ("citing", r"\bcit"), ("quoting", r"quot"),
                   ("applying/applied", r"appl"), ("adopting/approving", r"adopt|approv"),
                   ("and", r"^and$|\band$"), ("in", r"\bin$"), ("see/see also/cf", r"\bsee\b|\bcf\b"),
                   ("per", r"\bper$"), ("referring to/relying on", r"refer|rely|relied"),
                   ("considering/discussing", r"consid|discuss|explain|distinguish")]:
        if re.search(pat, conn):
            return k
    return "other:" + conn[:25]


def main():
    agg = collections.Counter()
    by_court = collections.defaultdict(collections.Counter)
    rows_out = []
    named = 0
    for court in ("SCC", "ONCA", "BCCA"):
        for r in csv.DictReader(open(os.path.join(R, "classify_out", court, "classified.csv"), encoding="utf-8")):
            if not r["candidate_case_name"]:
                continue
            named += 1
            res = analyse(r["preceding_text"] or "")
            if not res:
                continue
            cand, tail, conn = res
            # 收紧：尾巴里最后那个 v. 左边的当事人词若已出现在给出的案名里，说明生产代码的
            # 后续清洗已救回真名（非借名），不计
            lw = re.findall(r"([A-Za-z][\w’'-]*)\.?\s*$", tail[:list(K.V_RE.finditer(tail))[-1].start()])
            if lw and lw[-1].lower() in r["candidate_case_name"].lower():
                continue
            b = bucket(conn)
            agg[b] += 1
            by_court[court][b] += 1
            rows_out.append([court, r["candidate_id"], r["source_decision_citation"], r["raw_string"],
                             r["candidate_case_name"], b, cand[-220:]])
    os.makedirs(os.path.join(ROOT, "data", "audit"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "audit", "name_borrow_rows.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["court", "candidate_id", "source", "raw_string", "given_name", "connector_bucket", "candidate_segment"])
        w.writerows(rows_out)
    tot = sum(agg.values())
    print("named rows:", named, "| suspect borrowed:", tot)
    for k, v in agg.most_common():
        print("%6d  %s" % (v, k))
    print({c: sum(v.values()) for c, v in by_court.items()})
    random.Random(1).shuffle(rows_out)
    for r in rows_out[:12]:
        print("--", r[5], "| given:", r[4], "| cite:", r[3], "\n   ", r[6].replace("\n", " ")[-200:])


if __name__ == "__main__":
    main()
