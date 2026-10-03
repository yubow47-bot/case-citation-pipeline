"""借名影响（只读）：把 name_borrow_rows.csv 的行追到 merge_key → 跨院组，看错名走到了哪一步。

问题分三级：
  L1 行级：这一行的 candidate_case_name 是借来的（已由 name_borrow_audit 计数）
  L2 组名：该行所在跨院组的 case_name_modal 恰好等于借来的名字（错名赢了投票）
  L3 身份：该组 identity_basis 依赖案名（非 singleton / 非锚），借名可能让它并错或拆开
并报：受影响组中过门槛（dd>=5）的数量。
"""
import csv, os, re, collections, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(10 ** 9)
R = os.path.join(ROOT, "data", "run_20260918_scc_onca_bcca")


def nn(s):
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).split())


rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "data", "audit", "name_borrow_rows.csv"), encoding="utf-8"))
        if not r["connector_bucket"].startswith("history")]
want = {r["candidate_id"]: r for r in rows}
key_of = {}
for court in ("SCC", "ONCA", "BCCA"):
    for r in csv.DictReader(open(os.path.join(R, "merge_out", court, "mentions_candidates.csv"), encoding="utf-8")):
        if r["candidate_id"] in want:
            key_of[r["candidate_id"]] = (court, r["merge_key"], r["arbitration_status"])
grp = {}
for r in csv.DictReader(open(os.path.join(R, "decide_out", "cross_court", "decided.csv"), encoding="utf-8")):
    grp[(r["court"], r["merge_key"])] = (r["merged_group_id"], r["case_name_modal"], r["identity_basis"],
                                        int(r["distinct_decisions_count"] or 0))
agg = collections.Counter()
groups_l2, groups_l2_kept, groups_touched, groups_kept = set(), set(), set(), set()
basis = collections.Counter()
ex = []
for cid, r in want.items():
    agg["rows"] += 1
    k = key_of.get(cid)
    if not k:
        agg["no_merge_row"] += 1
        continue
    g = grp.get((k[0], k[1]))
    if not g:
        agg["key_not_in_decided(" + k[2] + ")"] += 1
        continue
    gid, modal, ib, dd = g
    groups_touched.add(gid)
    basis[ib] += 1
    if dd >= 5:
        groups_kept.add(gid)
    if nn(modal) and nn(modal) == nn(r["given_name"]):
        agg["L2_modal_is_borrowed"] += 1
        groups_l2.add(gid)
        if dd >= 5:
            groups_l2_kept.add(gid)
            if len(ex) < 15:
                ex.append((gid, dd, modal, r["raw_string"], r["candidate_segment"][-150:].replace("\n", " ")))
print(dict(agg))
print("groups touched:", len(groups_touched), "| of which dd>=5:", len(groups_kept))
print("groups whose modal name IS a borrowed name:", len(groups_l2), "| of which dd>=5:", len(groups_l2_kept))
print("identity_basis of touched rows:", basis.most_common())
for e in ex:
    print(e)
