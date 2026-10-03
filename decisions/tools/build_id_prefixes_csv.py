# -*- coding: utf-8 -*-
"""重建 decisions/id_prefixes.csv（程序化引号，杜绝手写列错位）。

第一层「已登记前缀 + 编号」形状（shape_registered_id）的驱动表。正则由本表生成，
新增前缀只加行、不动抽取代码。与 identifier_systems.csv 的区别：那张表登记
「年份+库名+编号」的数据库/出版商判决编号（有年份槽）；本表登记**无年份槽**的
前缀型标识——案卷号（docket）与出版社判决编号（decision）。

identifies：
  docket   案卷号：标识一场诉讼程序，下面可有多份文书，**对不上唯一一份判决**。
           第一层照抽（看得见），classify 打 citation_kind=docket 并写
           rejected_reason=docket_not_decision（保留不计数；不猜是哪一份，约束四）。
  decision 标识单份判决：按 citation_kind=identifier 正常计数。

verification_status：本批行**全部**是 unverified_*——前缀与编号格式来自语料残差挖掘
（audit/findings/residual_20261003_edge4/），发行方含义来自通用知识，尚未对照官方
来源逐行核实。classify 只在状态以 verified_ 开头时才套用 jurisdiction_scope；
未核实行法域一律 UNSUPPORTED（约束四：没有表证据就没有判定）。核实一行 =
补 source/source_locator 后把状态改为 verified_official_source。

body_regex / prefix_regex 里的连字符一律用 HY 字符类：语料实测 SST 印
A‑263‑78（U+2011）等变体。
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "id_prefixes.csv")

FIELDS = ["prefix_id", "prefix_regex", "body_regex", "canonical_token",
          "identifies", "jurisdiction_scope", "issuer", "example",
          "source", "source_locator", "verification_status", "notes",
          "reviewer", "reviewed_at"]

HY = "(?:[-‐‑‒–]|�C)"   # �C：语料里 en-dash 被错误解码的残片（实测 PSSRB/WTO 处）
OBS = "audit/findings/residual_20261003_edge4/ 与 anchor_20261003_edge4/（语料实测出现）"
UNV = "unverified_corpus_observed"      # 语料里见到，发行方含义未对官方来源核实
UNV_PK = "unverified_prior_knowledge"   # 语料里未见（无魁北克语料），仅凭通用知识
DATE = "2026-10-03"
WHO = "engineering lead (edge-court round)"

# 联邦案卷号：A-675-94 / T-1334-09 / IMM-1234-20
FED_BODY = HY + r"\d{1,5}" + HY + r"\d{2}"

rows = [
    ["FCA_A", "A", FED_BODY, "A-", "docket", "CA", "Federal Court of Appeal",
     "A-675-94", OBS, "", UNV,
     "SST 约 1.3 万次（9,311 次在案名之后）；FPSLREB 判决头「Court file: A-277-10」是上诉去向，"
     "不是引用——第一层照抽，由后续层分辨"],
    ["FC_T", "T", FED_BODY, "T-", "docket", "CA", "Federal Court (Trial Division)",
     "T-1334-09", OBS, "", UNV, ""],
    ["FC_IMM", "IMM", FED_BODY, "IMM-", "docket", "CA", "Federal Court (immigration)",
     "IMM-1234-20", OBS, "", UNV, "语料未见，按联邦法院移民案卷格式预登记"],
    ["PAB_CP", r"CP",
     r"\s?(?!(?:19|20)\d{2}(?!\d))\d{4,6}", "CP", "docket", "CA",
     "Pension Appeals Board",
     "CP 20466 (PAB)", OBS, "", UNV,
     "SST 1,546 次，案名之后命中率 95%。4 位纯年份（CP 2005）由负前瞻排除"],
    ["PAB_CP_YEARLIKE", r"(?:(?<=[,(;] )|(?<=Appeal ))CP", r"\s?(?:19|20)\d{2}(?!\d)", "CP",
     "docket", "CA", "Pension Appeals Board", "Vaughn v. Minister, CP 1971 (May 1992)", OBS, "", UNV,
     "CP 号恰好长得像年份（CP 1916/1971/2046）：只在逗号/括号/分号之后或 Appeal 之后才认，"
     "其余位置（CP 2005 results）仍被 PAB_CP 的负前瞻挡掉"],
    ["PSSRB_FILE", r"(?:PSSRB|PSLRB|PSLREB)\s+Files?(?:\s+Nos?\.?)?",
     r"\s*\d{1,3}" + HY + r"\d{1,2}(?:" + HY + r"\d{1,6})?", "PSSRB File No.", "docket", "CA",
     "Public Service Staff Relations Board (and successors)",
     "PSSRB File No. 168-02-37", OBS, "", UNV,
     "FPSLREB 3,097 次。PSSRB/PSLRB/PSLREB 三个机构名共用同一号段，规范 token 合一"],
    ["WTO_DS", r"WT/DS", r"\d{1,4}", "WT/DS", "docket", "",
     "World Trade Organization dispute settlement",
     "WT/DS135/AB/R", OBS, "", UNV,
     "一个争端号下有专家组报告、上诉机构报告多份文书，故为 docket；国际组织无加拿大法域码，留空"],
    ["CITT_FILE", r"(?:AP|PR|NQ|RR|GC|PI|TR|EP)",
     HY + r"\d{2,4}" + HY + r"\d{2,4}(?!/)", "{prefix}-", "docket", "CA",
     "Canadian International Trade Tribunal",
     "AP-2017-052", OBS, "", UNV,
     "尾部守卫排除证物号（PR-2009-080-09）与招标号（EP-803-183135/G）。前缀含义"
     "（AP 上诉/PR 采购投诉/NQ 调查/RR 到期复审…）未逐个核实"],
    ["SST_FILE", r"(?:AD|GE|GP)", HY + r"\d{2}" + HY + r"\d{1,5}", "{prefix}-", "docket", "CA",
     "Social Security Tribunal",
     "AD-16-785", OBS, "", UNV,
     "SST 判决头的 Reference number 也是这种号（自身编号），第一层照抽，自引由后续层处理。"
     "证据页码 GD2-11 类不在本表，故不会被抽"],
    ["CLRB_DI", r"\d{1,3}\s+di", r"\s+\d{1,4}", "{prefix}", "decision", "CA",
     "Canada Labour Relations Board Decisions", "61 di 77", OBS, "", UNV,
     "卷号在 token 里（50 DI），否则不同卷同页会撞键；FPSLREB 约 219 处"],
    # ---- 魁北克（语料内无魁北克法院，未实测，仅预登记）----
    ["QC_AZ", r"AZ", HY + r"\d{8}", "AZ-", "decision", "QC", "SOQUIJ",
     "AZ-50234567", "未实测；通用知识", "", UNV_PK, "SOQUIJ 文档号，每份判决一号"],
    ["QC_JE", r"J\.E\.", r"\s?\d{4}-\d{1,5}", "J.E.", "decision", "QC",
     "Jurisprudence Express (Éditions Yvon Blais)", "J.E. 2004-1234",
     "未实测；通用知识", "", UNV_PK, ""],
    ["QC_DTE", r"D\.T\.E\.", r"\s?\d{4}T-\d{1,4}", "D.T.E.", "decision", "QC",
     "Droit du travail Express (Éditions Yvon Blais)", "D.T.E. 2003T-123",
     "未实测；通用知识", "", UNV_PK, ""],
    ["QC_REJB", r"REJB", r"\s?\d{4}-\d{3,6}", "REJB", "decision", "QC",
     "Répertoire électronique de jurisprudence du Barreau", "REJB 1998-07890",
     "未实测；通用知识", "", UNV_PK, ""],
    ["QC_EYB", r"EYB", r"\s?\d{4}-\d{3,6}", "EYB", "decision", "QC",
     "Éditions Yvon Blais", "EYB 2004-12345", "未实测；通用知识", "", UNV_PK,
     "EYB2005DEV1234（Développements récents）是学术文章：编号体例带字母段，"
     "被本行 body 的纯数字约束结构性排除，不必另设排除表"],
]

# 约束八：每行必须有 source_locator。这里的定位是「在哪份测量结果里看到这个前缀」——
# 观测出处，不是发行方官方出处；发行方含义仍未核实，故状态仍是 unverified_*。
_RES = "audit/findings/residual_20261003_edge4/%s_residual.csv"
_ANC = "audit/findings/anchor_20261003_edge4/anchor_reconcile.json"
_MAIN = "data/run_20261003_v16/merge_out/%s/merged.csv（citation_kind=identifier 的 %s 键）"
LOCATORS = {
    "FCA_A": _ANC + " families.fed_docket（SST 13,530 / FPSLREB 653 / TCC 210 / CITT 308）",
    "FC_T": _ANC + " families.fed_docket（与 A- 同家族计数）；" + _RES % "FPSLREB" + " 模板 T-9-9（278 次）",
    "FC_IMM": "语料残差挖掘未见；按联邦法院移民案卷格式预登记（无观测出处，核实前不计数）",
    "PAB_CP": _ANC + " families.cp_pab（SST 1,546）",
    "PAB_CP_YEARLIKE": _ANC + " families.cp_pab 复查（SST 漏抓样例 CP 1916/CP 1971/CP2046）",
    "CLRB_DI": _ANC + " families.di_cite（FPSLREB 219）",
    "PSSRB_FILE": _ANC + " families.pssrb_file（FPSLREB 3,097）",
    "WTO_DS": _ANC + " families.wto_ds（CITT 609）",
    "CITT_FILE": _ANC + " families.citt_number（CITT 35,844）；" + _RES % "CITT",
    "SST_FILE": _ANC + " families.sst_decision（SST 37,661）；" + _RES % "SST",
    "QC_AZ": _MAIN % ("SCC", "AZ") + " 445 个",
    "QC_JE": _MAIN % ("SCC", "J.E.") + " 14 个；ONCA 1、BCCA 1",
    "QC_DTE": _MAIN % ("SCC", "D.T.E.") + " 4 个；ONCA 2",
    "QC_REJB": _MAIN % ("SCC", "REJB") + " 1 个",
    "QC_EYB": _MAIN % ("ONCA", "EYB") + " 3 个",
}
for r in rows:
    if not r[9]:
        r[9] = LOCATORS[r[0]]
    if r[0].startswith("QC_"):
        r[8] = "语料实测（SCC/ONCA/BCCA 判决正文）；发行方含义为通用知识，未对官方来源核实"

with open(OUT, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(FIELDS)
    for r in rows:
        r = list(r)
        assert len(r) == len(FIELDS) - 2, (r[0], len(r))
        w.writerow(r + [WHO, DATE])
print("wrote", OUT, len(rows), "rows")
