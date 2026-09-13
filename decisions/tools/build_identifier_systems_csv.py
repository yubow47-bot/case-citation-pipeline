# -*- coding: utf-8 -*-
"""重建 decisions/identifier_systems.csv（程序化引号，杜绝手写列错位）。
证据来自三个只读研究子代理（2026-09-13）：CanLII/IIJCan/CanLIIDocs、
Carswell/WL/DTC、QCTAQ（QCTAQ 走 neutral_court_codes，不入本表）。
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "identifier_systems.csv")

FIELDS = ["printed_token", "system_name", "issuer", "identifier_kind",
          "identifies", "jurisdiction_scope", "bilingual_equivalent",
          "year_is_volume", "valid_from", "valid_to", "source",
          "source_locator", "verification_status", "notes", "reviewer",
          "reviewed_at"]

MCGILL = ("McGill Guide 9e §3.8（在线数据库引证，例 Almad Investments "
          "1996 CarswellOnt 4402 (WL Can)）+ Appendix E 缩写表；Queen's "
          "University McGill-10th 指南（CarswellNat 作 SCC 判决并列引证实例）")
MCGILL_LOC = ("https://guides.library.queensu.ca/legalcitation-mcgill-10th/"
              "choosing-a-citation-pattern ; "
              "https://dokumen.pub/manuel-canadien-de-la-reference-juridique-"
              "9e-ednbsped-9780459551490-0459551493-9780459551513-0459551515.html")
CARSWELL_NOTE = ("权威引证手册（McGill）+ 使用佐证（2016 SCC 8 引 CarswellQue）；"
                 "同一判决可携多库编号；尾缀字母（如 85F headnote）为同判决变体，"
                 "键层不展开")

rows = [
    ["CanLII", "CanLII", "CanLII (Federation of Law Societies of Canada; operated by Lexum)",
     "database_decision_id", "single_decision", "CA", "IIJCan", "", "", "",
     "CanLII API 官方文档（citation 字段示例 1998 CanLII 2237 (ON CA)）；官方 FAQ（Wayback 存档 2025-06-02）2.6 条；官方博客 coverage 声明",
     "https://github.com/canlii/API_documentation/blob/master/EN.md ; "
     "https://web.archive.org/web/20250602103303/https://www.canlii.org/info/faq.html ; "
     "https://blog.canlii.org/2018/07/03/canlii-passes-2000000-cases/",
     "verified_official_source",
     "标识符空间含 ukjcpc 库（JCPC 上诉自加拿大法院的判决，官方博客 2016-12-22 明言这是其首个非加拿大法院内容）——这些案件按「上诉来自加拿大法院」语义 origin=CA，与本行 scope 相容。编号回溯性赋给历史判决（1957 CanLII 73），故不设年代闸。bilingual_equivalent=IIJCan（法语旧称，2007 年弃用）",
     "engineering lead (autonomous demo round)", "2026-09-13"],
    ["IIJCan", "IIJCan (ancien acronyme francophone de CanLII)",
     "CanLII (Federation of Law Societies of Canada; operated by Lexum)",
     "database_decision_id", "single_decision", "CA", "CanLII", "", "", "",
     "CanLII 官方托管页同编号双 token 引证：2005 IIJCan 24709 (CanLII) (QC CS)（Sedona Canada Principles）；Lexum 2013 论文：IIJCan 为 CanLII 法语旧称（2007 年弃用）",
     "https://www.canlii.org/en/commentary/doc/2008CanLIIDocs1 ; "
     "https://lexum.com/wp-content/uploads/2016/10/2013-canlii-genevieve-leger-lexum.pdf ; "
     "https://lexum.com/conf/conf2002/actes/salvas.pdf",
     "verified_official_source",
     "语料未见 IIJCan 引证（行休眠）；双语对 CanLII↔IIJCan 经 bilingual_neutral_codes.csv 显式登记后方可用于身份等价",
     "engineering lead (autonomous demo round)", "2026-09-13"],
]
for tok, jur in (("CarswellOnt", "ON"), ("CarswellQue", "QC"),
                 ("CarswellBC", "BC"), ("CarswellNat", "CA"),
                 ("CarswellAlta", "AB"), ("CarswellSask", "SK"),
                 ("CarswellNS", "NS"), ("CarswellNfld", "NL"),
                 ("CarswellMan", "MB"), ("CarswellNB", "NB")):
    rows.append([tok, "Carswell %s (Westlaw Canada)" % tok.replace("Carswell", ""),
                 "Thomson Reuters (Carswell)", "vendor_decision_id",
                 "single_decision", jur, "", "", "", "",
                 MCGILL, MCGILL_LOC, "verified_authoritative_manual",
                 CARSWELL_NOTE, "engineering lead (autonomous demo round)",
                 "2026-09-13"])
rows.append(["Carswell", "Carswell (Westlaw Canada; database not subdivided)",
             "Thomson Reuters (Carswell)", "vendor_decision_id",
             "single_decision", "CA", "", "", "", "",
             MCGILL, MCGILL_LOC, "verified_authoritative_manual",
             "裸 Carswell 形态=未带省缩写的库引证；scope=CA（厂商全库，非排他省级）——origin 推断仅到 CA 级",
             "engineering lead (autonomous demo round)", "2026-09-13"])
rows.append(["DTC", "Dominion Tax Cases",
             "CCH Canadian Ltd. (Toronto, 1940–), now Wolters Kluwer",
             "year_volume_reporter", "reporter_volume_page", "CA", "", "yes",
             "", "",
             "Bluebook T2.6 (Canada)「Dominion Tax Cases, 1920–date, D.T.C.」；IBFD 馆藏目录显式年份=卷（vol 41:1987 cited 87 DTC；vol 46:1992 cited 92 DTC）；York University 图书馆报告页",
             "https://www.legalbluebook.com/bluebook/v21/tables/t2-foreign-jurisdictions/t2-6-canada ; "
             "https://link.library.ibfd.org/ru/resource/zMqMbrRKNU4 ; "
             "https://www.yorku.ca/jdavis/2017/w08t1_1_court_reporters.html",
             "verified_authoritative_manual",
             "【出版方更正】CCH Canadian/Wolters Kluwer，非 Carswell/Thomson（Carswell 的税务报告是 C.T.C.）。year_is_volume=yes：年读法（YYYY DTC 页）即正确读法，仲裁按既有支持分级将年读法判 counted",
             "engineering lead (autonomous demo round)", "2026-09-13"])
rows.append(["WL", "Westlaw (Thomson West) database ID", "Thomson West (Westlaw)",
             "vendor_decision_id", "single_decision", "", "", "", "", "",
             "Bluebook Rule 10.8.1(a)/18 经 Georgetown 引证指南（例 2005 WL 2709572, W.D.N.Y.）；Wikipedia Case citation 条目同述",
             "https://guides.ll.georgetown.edu/c.php?g=261289&p=2339386 ; "
             "https://en.wikipedia.org/wiki/Case_citation",
             "verified_authoritative_manual",
             "coverage 非加拿大专属（文档实例为美国法院；加拿大 Westlaw 用 WL Can/Carswell 系）——jurisdiction_scope 留空：不做任何来源地推断，FOREIGN/DOMESTIC 均不产生",
             "engineering lead (autonomous demo round)", "2026-09-13"])
rows.append(["CanLIIDocs", "CanLII secondary commentary",
             "CanLII (Federation of Law Societies of Canada)",
             "secondary_source", "not_a_decision", "CA", "", "", "", "",
             "CanLII 官方博客：CanLIIDocs 为评论/二手资料平台（非判决）；COAL 引证指南本身以 2024 CanLIIDocs 830 发布于评论栏",
             "https://blog.canlii.org/2018/11/22/academic-authors/ ; "
             "https://www.canlii.org/en/commentary/doc/2024CanLIIDocs830",
             "verified_official_source",
             "分类层行级拒绝 rejected_reason=not_a_decision（保留不计数）",
             "engineering lead (autonomous demo round)", "2026-09-13"])

with open(OUT + ".tmp", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(FIELDS)
    w.writerows(rows)
os.replace(OUT + ".tmp", OUT)
print("written", OUT, "rows:", len(rows))
