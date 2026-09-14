# -*- coding: utf-8 -*-
"""R4 Stage 3：把逐案人工核验结果序列化为 decisions/case_origin_manual.csv。

本脚本**只做 CSV 序列化**（保证字段数与转义正确）——不做任何机器匹配或推断：
每行的印刷引证、决定法院、上诉来源、来源地均为研究核验所得，逐行带 source +
source_locator。status=verified_research_agent 表示四项证明齐备；未核验案不入表。
"""
import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "decisions", "case_origin_manual.csv")

COLS = ["printed_citation", "normalized_key", "case_name", "report_year",
        "decision_date_or_year", "proceeding_year_if_relevant", "deciding_court",
        "appeal_from_court", "appeal_from_jurisdiction", "origin_country",
        "origin_subdivision", "status", "source", "source_locator", "verified_on",
        "reviewer", "notes"]

V, D = "2026-09-14", "research agent；not human-reviewed"
S = "verified_research_agent"
B = "https://beta.bailii.org/uk/cases/UKPC/"
W = "https://en.wikipedia.org/wiki/"
J = "Judicial Committee of the Privy Council"
HL = "House of Lords"

# (printed, nk, name, report_year, decision, deciding_court, from_court,
#  from_juris, country, subdivision, source, locator, notes)
ROWS = [
 ("[1978] A.C. 728", "1978ac728", "Anns v. Merton London Borough Council", "1978",
  "1977-05-12", HL, "Court of Appeal", "England & Wales", "GB", "",
  "vLex UK；Wikipedia", "https://vlex.co.uk/vid/anns-v-merton-london-793653189；"
  + W + "Anns_v_Merton_London_Borough_Council",
  "报告年 1978 ≠ 判决年 1977（vLex 载判决日 1977-05-12）"),
 ("[1932] A.C. 562", "1932ac562",
  "Donoghue v. Stevenson（M'Alister or Donoghue）", "1932", "1932-05-26", HL,
  "Second Division of the Court of Session", "Scotland", "GB", "",
  "Scottish Council of Law Reporting 案例资源；Wikipedia",
  "https://www.scottishlawreports.org.uk/resources/donoghue-v-stevenson/case-report/；"
  + W + "Donoghue_v_Stevenson",
  "SCLR 载「No. 5. 26 May 1932 | HL」；苏格兰上诉→GB（来源地由案件级上诉来源证明）"),
 ("(1881), 7 App. Cas. 96", "18817appcas96",
  "Citizens Insurance Co. of Canada v. Parsons", "1881", "1881-11-26", J, "",
  "Canada", "CA", "",
  "BAILII UKPC；DPLA 判决原件",
  "http://www.bailii.org/uk/cases/UKPC/1881/1881_50.html；"
  "https://dp.la/item/7b409a3839793442e87788c29430e9ee",
  "BAILII 索引为 (Canada)→省别不写（只按 BAILII 明示省名填省）"),
 ("7 App. Cas. 96", "7appcas96", "Citizens Insurance Co. of Canada v. Parsons", "",
  "1881-11-26", J, "", "Canada", "CA", "",
  "同 (1881) 7 App. Cas. 96（无年印刷形）",
  "http://www.bailii.org/uk/cases/UKPC/1881/1881_50.html",
  "语料中的无年印刷形；与有年形同一判决"),
 ("(1883), 9 A.C. 117", "18839ac117", "Hodge v. The Queen", "1883", "1883-12-15",
  J, "", "Ontario", "CA", "Ontario", "BAILII UKPC 年度库；Wikipedia",
  B + "1883/；" + W + "Hodge_v_The_Queen",
  "安省酒类许可法（Crooks Act）案；上诉自安大略"),
 ("(1883), 9 App. Cas. 117", "18839appcas117", "Hodge v. The Queen", "1883",
  "1883-12-15", J, "", "Ontario", "CA", "Ontario",
  "同 (1883) 9 A.C. 117（App. Cas. 并行印刷形）", B + "1883/",
  "与 (1883) 9 A.C. 117 同一判决"),
 ("[1899] A.C. 580", "1899ac580",
  "Union Colliery Co. of British Columbia v. Bryden", "1899", "1899-07-28", J,
  "Supreme Court of British Columbia", "British Columbia", "CA",
  "British Columbia", "BAILII UKPC；Wikipedia",
  B + "1899/1899_58.html；" + W
  + "Union_Colliery_Co._of_British_Columbia_v._Bryden",
  "BAILII 标题含 (British Columbia)"),
 ("(1887) 12 A.C. 575", "188712ac575", "Bank of Toronto v. Lambe", "1887",
  "1887-07-09", J, "", "Quebec", "CA", "Quebec", "BAILII UKPC",
  B + "1887/1887_29.html", "BAILII 标题 (Quebec)"),
 ("(1887), 12 App. Cas. 575", "188712appcas575", "Bank of Toronto v. Lambe",
  "1887", "1887-07-09", J, "", "Quebec", "CA", "Quebec",
  "同 (1887) 12 A.C. 575（App. Cas. 并行印刷形）", B + "1887/1887_29.html",
  "与 (1887) 12 A.C. 575 同一判决"),
 ("12 App. Cas. 575", "12appcas575", "Bank of Toronto v. Lambe", "", "1887-07-09",
  J, "", "Quebec", "CA", "Quebec", "同 (1887) 12 A.C. 575（无年印刷形）",
  B + "1887/1887_29.html", "无年印刷形；同一判决"),
 ("[1903] A.C. 524", "1903ac524",
  "Attorney-General for Ontario v. Hamilton Street Railway", "1903",
  "1903-07-14", J, "", "Ontario", "CA", "Ontario", "BAILII UKPC；swarb.co.uk",
  B + "1903/1903_51.html；https://swarb.co.uk/"
  "attorney-general-for-ontario-v-hamilton-street-ry-co-pc-1903/",
  "BAILII 标题 (Ontario)"),
 ("[1894] A.C. 189", "1894ac189",
  "Attorney General of Ontario v. Attorney General for the Dominion of Canada",
  "1894", "1894-02-24", J, "", "Ontario", "CA", "Ontario",
  "BAILII UKPC（HTML + 判决原件 PDF）",
  B + "1894/1894_13.html；http://www.bailii.org/uk/cases/UKPC/1894/1894_13.pdf",
  "BAILII 标题 (Ontario)"),
 ("[1897] A.C. 22", "1897ac22", "Salomon v. A. Salomon & Co. Ltd.", "1897",
  "1896-11-16", HL, "Court of Appeal", "England & Wales", "GB", "",
  "ATO 法律数据库判例页；判例报告原件 PDF",
  "https://www.ato.gov.au/law/view/print?DocID=JUD%2F*1897*1AllER33%2F00001；"
  "https://corporations.ca/assets/Salomon%20v%20Salomon.pdf",
  "报告年 1897 ≠ 判决年 1896（1896-11-16）；两处均非 Wikipedia"),
 ("[1892] A.C. 437", "1892ac437",
  "The Liquidators of the Maritime Bank of Canada v. The Receiver General of "
  "New Brunswick", "1892", "1892-07-02", J, "", "Canada", "CA", "",
  "BAILII UKPC；CommonLII",
  B + "1892/1892_34.html；"
  "http://www.commonlii.org/uk/cases/UKLawRpAC/1892/31.html",
  "BAILII 索引 (Canada)→省别不写；案情涉新不伦瑞克"),
 ("[1894] A.C. 57", "1894ac57",
  "John Makin and Sarah Makin v. The Attorney General for New South Wales",
  "1894", "1893-12-12", J, "", "New South Wales", "AU", "New South Wales",
  "BAILII UKPC", B + "1893/1893_56.html",
  "BAILII 标题 (New South Wales)；报告年 1894 ≠ 判决年 1893"),
 ("[1905] A.C. 52", "1905ac52",
  "The Corporation of the City of Toronto v. The Bell Telephone Company of "
  "Canada", "1905", "1904-11-11", J, "", "Canada", "CA", "", "BAILII UKPC",
  B + "1904/1904_71.html",
  "BAILII 索引 (Canada)→省别不写；报告年 1905 ≠ 判决年 1904"),
 ("[1907] A.C. 65", "1907ac65",
  "The Grand Trunk Railway Company of Canada v. The Attorney General for the "
  "Dominion of Canada", "1907", "1906-11-05", J, "", "Canada", "CA", "",
  "BAILII UKPC", "https://knyvet.bailii.org/uk/cases/UKPC/1906/1906_72.html",
  "BAILII 索引 (Canada)；报告年 1907 ≠ 判决年 1906"),
 ("[1914] A.C. 599", "1914ac599", "Ibrahim v. The King", "1914", "1914", J, "",
  "Hong Kong", "HK", "", "McGill Law Journal 判例引注",
  "https://lawjournal.mcgill.ca/article/recent-developments-in-the-law-"
  "relating-to-confessions-engalnd-canada-and-australia/",
  "★语料案名「Boudreau v. The King」与本引证不符（案名携带错误）；本引证为 "
  "Ibrahim v. The King [1914] A.C. 599 (P.C.)——上诉自香港；精确判决日待补"),
 ("[1901] A.C. 495", "1901ac495", "Quinn v. Leathem", "1901", "1901-08-05", HL,
  "Court of Appeal in Ireland", "Ireland（1901 年属联合王国）", "GB", "",
  "BAILII UKHL", "http://beta.bailii.org/uk/cases/UKHL/1901/2.html",
  "上诉自爱尔兰上诉法院；1901 年爱尔兰属联合王国→GB（未按现代 IE 处理）"),
 ("[1894] A.C. 31", "1894ac31", "Tennant v. The Union Bank of Canada", "1894",
  "1893-12-09", J, "", "Ontario", "CA", "Ontario", "BAILII UKPC；Justis 判例库",
  B + "1893/1893_53.html；https://app.justis.com/case/"
  "tennant-v-union-bank-of-canada/overview/b4ytn2etoZaaa",
  "BAILII 标题 (Ontario)；报告年 1894 ≠ 判决年 1893"),
 ("[1922] 1 A.C. 191", "19221ac191",
  "In re The Board of Commerce Act 1919 and the Combines and Fair Prices Act "
  "1919", "1922", "1921", J, "", "Canada", "CA", "",
  "Wikipedia；BAILII UKPC 年度库", W + "Board_of_Commerce_case；" + B,
  "Board of Commerce 案（联邦/阿尔伯塔权限）；BAILII 索引 Canada→省别不写"),
 ("[1902] A.C. 73", "1902ac73",
  "The Attorney General for the Province of Manitoba v. The Manitoba Licence "
  "Holders Association", "1902", "1901-11-22", J, "", "Canada", "CA",
  "Manitoba", "BAILII UKPC",
  "https://knyvet.bailii.org/uk/cases/UKPC/1901/1901_52.html",
  "BAILII 索引 (Canada) 而案名为曼尼托巴协会案→省别按案名登记；报告年 1902 ≠ "
  "判决年 1901"),
 ("[1924] A.C. 328", "1924ac328",
  "The Attorney General of Ontario v. The Reciprocal Insurers", "1924",
  "1924-01-25", J, "", "Ontario", "CA", "Ontario", "BAILII UKPC",
  B + "1924/1924_5.html", "BAILII 标题 (Ontario)"),
 ("[1895] A.C. 202", "1895ac202",
  "Brophy and others v. The Attorney General of Manitoba", "1895",
  "1895-01-29", J, "", "Canada", "CA", "Manitoba", "BAILII UKPC",
  "https://knyvet.bailii.org/uk/cases/UKPC/1895/1895_1.html",
  "BAILII 索引 (Canada) 而案名为曼尼托巴总检察长案→省别按案名登记"),
 ("(1906), 3 C.L.R. 969", "19063clr969", "Enever v. The King", "1906",
  "1906-03-12", "High Court of Australia", "Supreme Court of New South Wales",
  "New South Wales", "AU", "New South Wales",
  "AustLII 判决全文；BarNet Jade 判例库",
  "https://vvv.austlii.edu.au/au/cases/cth/HCA/1906/3.html；"
  "https://jade.io/summary/mnc/1906/HCA/3",
  "AustLII 判词载「Enever Plaintiff Appellant; and The King」；HCA 判决日 "
  "1906-03-12"),
 ("(1963), 110 C.L.R. 234", "1963110clr234", "Plomp v. The Queen", "1963",
  "1963-10-18", "High Court of Australia", "Supreme Court of Queensland",
  "Queensland", "AU", "Queensland", "AustLII 判决全文；Australian Cases 判例页",
  "https://www4.austlii.edu.au/au/cases/cth/HCA/1963/44.html；"
  "http://www.netk.net.au/Australia/Plomp.asp",
  "AustLII 载 [1963] HCA 44；上诉自昆士兰"),
 ("(1884), 9 A.C. 371", "18849ac371",
  "Letterstedt (now Vicomtesse de Montmort) v. Broers", "1884", "1884-03-22",
  J, "", "Cape of Good Hope", "ZA", "Cape of Good Hope",
  "CaseNote AU；swarb.co.uk 判例页",
  "https://casenote.au/uk/cases/letterstedt-now-vicomtesse-de-montmort-v-"
  "broers-and-another-cape-of-good-hope；"
  "https://swarb.co.uk/letterstedt-v-broers-pc-22-mar-1884/",
  "上诉自好望角（今南非）；判决日 1884-03-22"),
 ("[1899] A.C. 99", "1899ac99", "Dilworth v. Commissioner of Stamps", "1899",
  "1899", J, "", "New Zealand", "NZ", "", "vLex UK 判例页",
  "https://vlex.co.uk/vid/dilworth-v-commissioner-of-803360453",
  "★上诉来源（新西兰）由案情当事人身份（Commissioner of Stamps 为新西兰法定"
  "职位）与 vLex 判例页确立；判决日未在本轮核准（只到年）；置信度中"),
 ("[1963] 3 All E.R. 659", "19633aller659", "R. v. Waterfield", "1963", "1963",
  "Court of Criminal Appeal", "", "England & Wales", "GB", "",
  "hrcr.org 判例库（载 COURT OF CRIMINAL APPEAL 与并行引证）；Wikipedia",
  "https://hrcr.org/safrica/arrested_rights/R_Waterfield.htm；"
  + W + "R_v_Waterfield",
  "英格兰刑事上诉法院判决；All E.R. 报告年 1963"),
 ("[1964] 1 Q.B. 164", "19641qb164", "R. v. Waterfield", "1964", "1963",
  "Court of Criminal Appeal", "", "England & Wales", "GB", "",
  "同 [1963] 3 All E.R. 659（Q.B. 并行印刷形）",
  "https://hrcr.org/safrica/arrested_rights/R_Waterfield.htm",
  "与 [1963] 3 All E.R. 659 同一判决；Q.B. 报告年 1964 ≠ 判决年 1963"),
 ("[1963] 2 All E.R. 575", "19632aller575",
  "Hedley Byrne & Co. Ltd. v. Heller & Partners Ltd.", "1963", "1963-05-28",
  HL, "", "England & Wales", "GB", "", "BAILII UKHL；lawcases.net（并行引证表）",
  "http://www.bailii.org/uk/cases/UKHL/1963/4.html；https://www.lawcases.net/"
  "cases/hedley-byrne-co-ltd-v-heller-partners-ltd-1963-ukhl-4-28-may-1963/",
  "All E.R. 并行引证（lawcases.net 载 [1963] 2 All ER 575 + [1964] AC 465）"),
 ("[1964] A.C. 465", "1964ac465",
  "Hedley Byrne & Co. Ltd. v. Heller & Partners Ltd.", "1964", "1963-05-28",
  HL, "", "England & Wales", "GB", "", "BAILII UKHL（[1963] UKHL 4）；lawcases.net",
  B.replace("UKPC/", "UKHL/") + "1965/4.html；https://www.lawcases.net/cases/"
  "hedley-byrne-co-ltd-v-heller-partners-ltd-1963-ukhl-4-28-may-1963/",
  "报告年 1964 ≠ 判决年 1963（1963-05-28）；上诉自英格兰"),
]


def main():
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for r in ROWS:
            printed, nk, name, ry, dec, dc, fc, fj, cc, sub, src, loc, notes = r
            w.writerow([printed, nk, name, ry, dec, "", dc, fc, fj, cc, sub, S,
                        src, loc, V, D, notes])
    from collections import Counter
    print("rows:", len(ROWS))
    print("by country:", dict(Counter(r[8] for r in ROWS)))
    print("written:", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()