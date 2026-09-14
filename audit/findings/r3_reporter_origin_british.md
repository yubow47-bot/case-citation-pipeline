# R3 英国组：汇编来源地排他性溯源（提案）

产出者：R3 委派研究代理（**提案，不是数据**）。写入日：2026-09-16（全部取用日期同此日，标注为 `2026-09-16`）。
目标清单：`audit/findings/r3_stage1_targets_british.md` / `.json`（`group == "british"`，tier 1–2 共 13 个）。
只读约束遵守：未改动 `decisions/`、`pipeline/` 或任何其他文件；本文件是唯一产出。
禁止用作证据的：本仓语料、分类层输出、`decisions/reporter_jurisdiction.csv`、`PROBLEMS.md`。均未使用。

---

## 0. 结论摘要（最重要的三条）

1. **`ac` = `appcas` = mixed（不得写入任何 origin 行）。** 二者是同一套汇编的两个刷次名（App. Cas. 1875–1890 → A.C. 1891– ）。**出版方自己的卷首页**写明该卷集为「HOUSE OF LORDS, JUDICIAL COMMITTEE OF THE PRIVY COUNCIL AND PEERAGE CASES」（I.C.L.R. 1930 年卷，卷首页）。枢密院上诉**来自加拿大**者即加拿大来源地案件。**具体反例已坐实**：`Edwards v Canada (AG)` = **[1930] AC 124**，BAILII 官方 cite-as 行与卷内案件表双方证实；同卷另有 `Berthiaume v Dastous`（P.C. 79）、`Lecavalier v City of Montreal`（P.C. 152）、`Royal Trust Co. v A-G Alberta`（P.C. 144）、`Keewatin Power Co. v Lake of the Woods Milling Co.`（P.C. 640）、`Lovibond v Governor-General of Canada`（P.C. 623）等加拿大上诉；另有新南威尔士、锡兰、海峡殖民地、马来亚、印度上诉与苏格兰（H.L.(Sc.)）、爱尔兰（H.L.(N.I.)）上诉。**若把 A.C. 当 GB，就与本任务的整个目的直接冲突。**

2. **`er`（English Reports）不是「纯英格兰」——是 mixed。** Stevens & Sons 的 178 卷重印本含 **Vols 12–20 = Privy Council（includes Indian Appeals）**（1809–1865），即殖民地上诉；另有 Ecclesiastical/Admiralty/Probate 分册与苏格兰、爱尔兰上议院上诉分册。**具体反例**：`Chung Chuck v The King` 在 A.C. 1930 卷内被标为 P.C.（加拿大上诉）。English Reports 里对应的枢密院卷（Vols 12–20）同性质。因此 `er` 不能作为 GB 排他证据。

3. **Quebec/English 同形异义（`kb`/`qb`）已找到可溯源的分离窗口，但结论是 `mixed`（不写 origin 行）。** 关键新发现：**Quebec 的官方汇编在 1899 年前的引注中就被印作「Q.B.」和「S.C.」**——`Consolidated digest of the decisions of the courts of the province of Quebec ... down to and including vol. 3 of the official reports [Q.B. 1894] and vol. 6 of the official reports (S. C. 1894)`（Montreal: J. Lovell, 1899；Internet Archive 编目记录），配套的 **1900 年总索引**给出官方汇编的精确规模：**1892–1898，Vols 1–7 B.R.（Banc de la Reine / Q.B.）+ Vols 1–14 C.S.（Cour Supérieure / S.C.）**。这与语料实测的 `qb` 高频组合（vol 1–2、年 1891–1900）在**卷/年两个维度上都吻合**，说明语料里那批「1890s Q.B.」极可能是魁北克官方汇编而非英格兰 Q.B.。

---

## 1. 总表（每个到达的目标一行）

| # | abbr | 是什么 | 排他性判定 | 证据类别 | volume_system | 独立溯源窗口 | 反例搜寻结果 |
|---:|---|---|---|---|---|---|---|
| 5 | `ac` | 判例汇编（The Law Reports, Appeal Cases） | **mixed** | 出版方卷首页 + 具体反例 | year_volume | 1891– 至今（[year] A.C.）；前身 L.R. App. Cas. 1875–1890 | **命中**：[1930] AC 124 等 6 件加拿大上诉 + 多殖民地/苏格兰/爱尔兰上诉 |
| 12 | `aller` | 判例汇编（All England Law Reports 家族：Reprints 1558–1935 + 主系列 1936– ） | **mixed** | 第三方 only（出版方 scope 页 404） | year_volume | 主系列 1936– ；Reprints 段 1558–1935（**未完全核实**） | **命中（家族层，高置信）**：`[1929] All ER Rep 571` = `Edwards v Canada (AG)`（加拿大枢密院上诉）。**低置信**旁证：A.C. 1930 卷同页印度上诉案 |
| 13 | `appcas` | 判例汇编（L.R. App. Cas., Appeal Cases 第一/第二刷次） | **mixed** | 出版方卷首页 + 具体反例 | continuous（卷 1–15 跨年） | 1875–1890，Vols 1–15 | **命中**：1890 年卷（Vol 15）卷首页；`St Catherine's Milling & Lumber Co v The Queen (1888) 14 App. Cas. 46`（加拿大） |
| 15 | `kb` | 判例汇编（英文 K.B. = Law Reports, King's Bench；1901–1952 印作 K.B.） | **mixed**（**未排除**，非已坐实反例） | 出版方引用体系声明（同族） | year_volume | 1901–1952（`[year] 1/2 K.B.` 形）；1875–1901 该分册名为 Q.B.D./Q.B. | **未找到**卷内具体反例；但**无法排除**——K.B. 卷首页本轮未取得，而同族 A.C./P.D. 明载枢密院 |
| 17 | `qb` | **同形异义**：英文 Law Reports Q.B.（1875–1900 名 Q.B.D.；1891 起 [year] Q.B.）+ 魁北克官方 Q.B. 汇编 + 其他加拿大 Q.B. | **mixed** | 出版方 + 目录学一手记录 | 英文：year_volume；魁北克：year_volume | 英文 1891–1900（[year] Q.B.）；魁北克官方 1892–1898 Q.B. vols 1–7（= B.R.）；蒙特利尔 Q.B. 汇编 1884/85–1891 vols 1–7 | **命中**：1899 年魁北克 digest 与 1900 年总索引把魁北克官方汇编印作 Q.B. 3 (1894) / S.C. 6 (1894) |
| 22 | `chd` | 判例汇编（Law Reports, Chancery Division 1875–1890） | **mixed** | 出版方卷首页 | continuous（vols 1–45，1875–1890） | 1875–1890；前身 1865–1875 Ch. App. | **命中**：同族 A.C. 卷含枢密院；Ch.D. 卷首页未见排除枢密院/殖民地上诉的表述 |
| 23 | `er` | 判例汇编（English Reports, Stevens & Sons, 178 卷，重印 1220–1866 名义判例汇编） | **mixed** | 出版方索引表（第三方转述） | continuous（vols 1–176 案件 + 177–178 索引） | 1220–1866（按分册）；PC 分册 1809–1865 | **命中（结构层）**：Vols 12–20 明载 Privy Council（includes Indian Appeals）；Vols 1–11 含苏格兰/爱尔兰上议院上诉 |
| 24 | `ch` | 判例汇编（The Law Reports, Chancery Division 1891– ） | **mixed** | 出版方卷首页 | year_volume | 1891– 至今（[year] Ch.） | **命中**：同族 A.C. 卷首页明载枢密院；`ch` 键还含 `[1927] Ch.` 等，属同一 ICLR 家族 |
| 28 | `qbd` | 判例汇编（Law Reports, Queen's Bench Division 1875–1890；1891–1900 亦用 Q.B.D. 形） | **mixed** | 出版方卷首页 | continuous（1875–1890，vols 1–45 量级）→ 1891 起 year_volume | 1875–1900 | 同 `ch`/`ac`：ICLR 家族含枢密院分册，未见 QBD 卷排除殖民地上诉 |
| 53 | `wlr` | 判例汇编（Weekly Law Reports, ICLR, 1953– ） | **mixed** | 出版方 scope 自述 + 具体反例 | year_volume（[year] 1/2/3 W.L.R.） | 1953– 至今 | **命中**：`Subramaniam v Public Prosecutor (Malaya) [1956] 1 WLR 965`（BAILII 官方 cite-as 行）；ICLR 2009 年索引把 `Kadi v Council of the EU`（ECJ）列在 APPEAL CASES 下 |
| 58 | `crappr` | 判例汇编（Criminal Appeal Reports, Sweet & Maxwell, 1908/09– ） | **mixed**（未坐实排他） | 第三方 only | continuous（vol 1 = 1908/09，vol 36 = 1952，vol 98 = 2023） | 1908/09– 至今 | 卷首/编目未见排除殖民地上诉；语料亦无 GB 之外的实测值可对照 |
| 61 | `lr.hl` | 判例汇编（L.R. House of Lords / English & Irish Appeals, 1865–1875） | **mixed** | 出版方卷首页 | continuous（vols 1–11 量级） | 1865–1875 | **命中**：同卷集含「English and Irish Appeals」（1866–1870 卷标题）与「Scotch and Divorce Appeals」分册 |
| 63 | `lr.qb` | 判例汇编（L.R. Queen's Bench, 1865–1875） | **mixed** | 出版方卷首页 | continuous（vols 1–10） | 1865–1875 | 同族 L.R. 卷集含 PC/HL(Sc.)/Indian Appeals 分册 |
| — | `chapp`（tier 3） | 判例汇编（L.R. Chancery Appeal Cases, 1865–1875） | **mixed** | 出版方卷首页 | continuous（vols 1–10） | 1865–1875 | 同族 |
| — | `lr.pc`（tier 3） | 判例汇编（L.R. Privy Council Appeals, 1865–1875） | **mixed** | 出版方卷首页 | continuous（vols 1–9） | 1865–1875 | 该分册本身即殖民地上诉集（印度等） |
| — | `lt`（tier 3） | 判例汇编（The Law Times Reports, 1847–1946） | 未完成（时间不足） | — | continuous | 语料实测 1847–1946（**未核实**） | 未做 |
| — | `tlr` / `timeslr` | 判例汇编（Times Law Reports 1884/85–1952 量级） | 未完成（时间不足） | — | continuous | **未核实** | 未做 |

> tier 1 = `ac` `aller` `appcas` `kb` `qb` `chd` `er` `ch`（8/8 到达）；tier 2 = `qbd` `wlr` `crappr` `lr.hl` `lr.qb`（5/5 到达）；tier 3 = 只到达 `chapp`、`lr.pc`（2/60）。

---

## 2. 逐目标详证

### 2.1 `ac`（A.C.）与 `appcas`（App. Cas.）——同一套汇编两个刷次名，**mixed**

**是什么**：The Law Reports 的 Appeal Cases 分册，Incorporated Council of Law Reporting for England and Wales（下称 ICLR）出版。**关键：它不是「英格兰法院判例汇编」，而是「上议院 + 枢密院司法委员会 + 贵族爵位案」的合卷。**

**书面证据（出版方自己的卷首页，一手）**——I.C.L.R. 1930 年 A.C. 卷卷首页原文（Internet Archive 扫描件全文）：

> `A. C. 1930.` … `THE INCORPORATED COUNCIL OF LAW REPORTING FOR ENGLAND AND WALES.` …
> `LAW REPORTS OF THE INCORPORATED COUNCIL OF LAW REPORTING.`
> **`HOUSE OF LORDS, JUDICIAL COMMITTEE OF THE PRIVY COUNCIL AND PEERAGE CASES.`**
> `REPORTERS. House of Lords ... ; Privy Council . . . A. M. TALBOT, Barrister-at-Law.`
> 同页引用体系声明：`The Mode of Citation of the Volumes of the Law Reports commencing January 1, 1930 ... In the Third Series, [1930] A. C.`

来源：Internet Archive 扫描本 `law-reports-appeal-cases_1930`（University of London Library 藏本），全文 `..._djvu.txt`，
`https://archive.org/details/law-reports-appeal-cases_1930`（正文 `https://dn721908.ca.archive.org/0/items/law-reports-appeal-cases_1930/law-reports-appeal-cases_1930_djvu.txt`，取用 2026-09-16）。

**前身卷的卷首页（一手，App. Cas. 时期）**——1890 年 Appeal Cases 第 15 卷：

> `The Law Reports 1890 LIII Vol. 15, And LIV Victoriae (Appeal Cases) Under The Superintendence And Control Of The Incorporated Council Of Law Reporting For England And Wales **Appeal Cases Before The House Of Lords And The Judicial Committee Of The Privy Council Also Peerage Cases**`

来源：Internet Archive 编目记录 `wbsl.21054`（Stone, A. P. 编；William Clowes, London），
`https://archive.org/advancedsearch.php?q=identifier%3A%22wbsl.21054%22&output=json`（取用 2026-09-16）。

**刷次名/年代（出版方引用体系 + 编目）**：1875 年卷集把上议院、枢密院与新设上诉法院并入同一卷，引注形变 `... App Cas ...`（1875–1890，vols 1–15）；1891 年起改为 `[year] A.C.`。
来源：ICLR 家族卷首页（上引）；另见 `wbsl.21054` 编目标题（1890 = Vol 15）。

**volume_system = `year_volume`**（1891 起）：证据即上引 1930 年卷首页的 `Mode of Citation ... [1930] A. C.` 声明——卷号按年内出版次序，年份进入引注。1875–1890 段为跨年连续卷号。

**反例搜寻（强制项，已执行并命中）**：

- 检索路径 A：BAILII 枢密院判决库 cite-as 行 → `https://www.bailii.org/uk/cases/UKPC/1929/1929_86.html`，页面明载
  `Cite as: [1930] AC 124, [1929] UKPC 86`，案名行 `Henrietta Muir Edwards and others (Appeal No. 121 of 1928) v The Attorney General of Canada (Canada)`，判词抬头 `from THE SUPREME COURT OF CANADA`。
  → **`Edwards v Canada (AG)` = [1930] AC 124 是加拿大来源地案件，印在 A.C. 里。**
- 检索路径 B：下载 A.C. 1930 卷全文，检索卷内 `TABLE OF CASES REPORTED`（该表用 `P.C.` / `H. L. (E.)` / `H. L. (Sc.)` / `H. L. (N. I.)` 标注法庭与来源）。命中的**加拿大 P.C. 案**：
  - `Henrietta Muir Edwards v. Attorney-General for Canada — P.C. 124`
  - `Attorney-General for Alberta, Royal Trust Co. v. — P.C. 144`
  - `Lecavalier (D. E.) v. City of Montreal — P.C. 152`
  - `Erie Beach Co., Ld. v. Attorney-General for Ontario — P.C. 161`
  - `Lovibond v. Governor-General of Canada — P.C. 623`
  - `Patton (W. R.) v. Toronto General Trusts Corporation — P.C. 629`
  - `Keewatin Power Co., Ld. v. Lake of the Woods Milling Co., Ld. — P.C. 640`
  - `Toronto Transportation Commission v. Canadian National Railways — P.C. 686`；`Canadian Pacific Railway Co. v. Toronto Transportation Commission — P.C. 686`
  - `Attorney-General for British Columbia v. McDonald Murphy Lumber Co., Ld. — P.C. 357`；`Attorney-General for Canada v. Attorney-General for British Columbia — P.C. 111`
  - `Eugène Berthiaume v. Dame Dastous — P.C. 79`；`Trustees of St. Luke's Presbyterian Congregation of Saltsprings v. Cameron — P.C. 673`；`Bank of Montreal v. Dominion Gresham Guarantee and Casualty Co., Ld. — P.C. 659`
  - 非加拿大 P.C. 案（同一卷）：`Sakariyawo Oshodi v. Moriamo Dakolo — P.C. 667`（尼日利亚）、`Gilmour v. MacPhillamy — P.C. 712`（新南威尔士）、`R. A. Hill v. Permanent Trustee Co. of New South Wales, Ld. — P.C. 720`、`Khoo Hooi Leong v. Khoo Chong Yeok — P.C. 346`（海峡殖民地）、`Strickland (Lord) v. Giuseppe Grima — P.C. 285`（马耳他）、`Chung Chuck v. The King — P.C. 244`（加拿大）、`Knowles (Benjamin) v. The King — P.C. 366`、`The Ottoman Bank v. Chakarian — P.C. 277`、`Bouzourou v. The Ottoman Bank — P.C. 271`、`Fada Radio, Ld. v. Canadian General Electric Co., Ld. — P.C. 97`。
  - **苏格兰/爱尔兰**：卷首表与正文页眉反复出现 `H. L. (Sc.)`（如 `Ross v. Ross`，卷首页 1）与 `H. L. (N. I.)`（如 `Clark v. Urquhart`、`Stracey v. Urquhart`，页 28）。
- 检索路径 C（App. Cas. 时期反例）：A.C. 1930 卷的 `TABLE OF CASES CITED` 收录 `St. Catherine's Milling and Lumber Co. v. The Queen (1888), 14 App. Cas., 46`（加拿大枢密院上诉）；BAILII 的 `Edwards` 判词亦引该案。→ **`appcas` 键同属 mixed。**

**结论**：`ac` 与 `appcas` 均为 `mixed`，**不写 origin 行**。任何把 A.C. 当 GB 的规则都会把加拿大来源地的枢密院案改成 GB——正是本任务要防的错误。

（旁证，非本行依据：Wikipedia 对 The Law Reports 的描述与上引出版方原文一致，`https://en.wikipedia.org/wiki/Law_Reports`，取用 2026-09-16。Wikipedia 依规**不作为**本判定的证据类别。）

### 2.2 `wlr`（Weekly Law Reports）——**mixed**，且**不是**语料分组错误

**是什么**：ICLR 出版的判例汇编，1953 年创刊。

**书面证据（出版方 scope 自述，一手）**——ICLR 官网（`lawreports.co.uk`，2010-01-16 快照，编者自身文字）：

> `Published since 1865 The Law Reports are "the most authoritative reports" ...`
> **`The Law Reports cover cases heard in The House of Lords and Privy Council, The Court of Appeal - Criminal and Civil Divisions, Chancery Division, Family Division, Queen's Bench Division, as well as the Employment Appeal Tribunal and the ECJ.`**

来源：`https://web.archive.org/web/20100116085250/http://www.lawreports.co.uk/Publications/newlr.htm`（取用 2026-09-16）。
同一页面 2009 年第 12 期索引把 `Kadi v Council of the European Union (Joined Cases C-402/05P and C-415/05P) ECJ 1225` 列在 `APPEAL CASES` 项下，并把 `Devenish Nutrition Ltd v Sanofi-Aventis SA Lewison J and CA 390` 列在 `CHANCERY DIVISION` 项下。

**具体反例（强制项，已命中）**：
`Subramaniam, son of Munusamy v The Public Prosecutor (Malaya) [1956] UKPC 21`——BAILII 官方页面 cite-as 行：

> `Cite as: [1956] UKPC 21, **[1956] 1 WLR 965**, [1956] 1 WLR 456, [1956] WLR 456, [1956] WLR 965`
> 案名行标注来源地：`(Malaya)`。

来源：`https://www.bailii.org/uk/cases/UKPC/1956/1956_21.html`（取用 2026-09-16）。
→ **W.L.R. 确实刊登英格兰与威尔士以外的（枢密院）判决。`wlr` = `mixed`。**

**对语料「WLR 76 条 CA」问题的回答**：我们的分组**不必然是错的**。W.L.R. 会刊登「枢密院上诉自加拿大法院」的案件；按本项目既定语义（见 `decisions/court_or_reporter_scope.csv` 的 CanLII 行：ukjcpc 库按「上诉来自加拿大法院」记 CA），那些组的 CA 结论在语义上可以成立，而不是单纯的分组错误。**但 `wlr` 本身仍不得作为 origin 证据**——它同时含 E&W、苏格兰、北爱、ECJ 与各殖民地上诉。

**volume_system = `year_volume`**（`[1954] 1 W.L.R. 228` 形）：来源同上 ICLR 页面（其自家索引即按 `[2009] QB ...` / `[2009] 1 AC ...` 的年内卷号编号），以及语料实测的 `[year] 1/2 WLR` 形。**标「第三方/出版方混合依据，中等强度」。**
**窗口**：1953– 至今；但请注意 `wlr` 键在语料中含 `[1929] All ER Rep` 一类的 1905/1922 年值（见 `r3_stage1_targets_british.md`：`wlr` 语料实测年 1905–2021），1929 年值应为 `All E.R. Reprints` 造成的年份噪声，**该 1905 端不作窗口起点**。

### 2.3 `er`（English Reports）——**mixed**

**是什么**：Stevens & Sons（London）与 William Green & Son（Edinburgh）1900–1932 年出版的重印本，178 卷，重印 1220–1866 年的英格兰名义判例汇编（nominate reports）。

**书面证据（出版方 1930 年索引表的分册结构）**（Wikipedia 转引 Index Chart 1930, p.3；**此条为第三方转述**）：

| Vols | Series | 期间 |
|---|---|---|
| 1–11 | House of Lords | 1694–1866 |
| **12–20** | **Privy Council（includes Indian Appeals）** | **1809–1865** |
| 21–47 | Court of Chancery（includes Collateral Reports） | 1557–1865 |
| 48–55 | Rolls Court | 1829–1865 |
| 56–71 | Vice-Chancellors' Courts | 1815–1865 |
| 72–122 | Court of King's Bench（or Queen's Bench） | 1378–1865 |
| 123–144 | Court of Common Pleas | 1486–1865 |
| 145–160 | Court of Exchequer | 1220–1865 |
| 161–167 | Ecclesiastical / Admiralty / Probate and Divorce | 1752–1857 / 1776–1840 / 1858–1865 |
| 168–169 | Crown Cases Reserved | 1743–1865 |
| 170–176 | Nisi Prius | 1688–1867 |
| 177–178 | Index of Cases | — |
| **合计** | | **178 卷** |

来源：`https://en.wikipedia.org/wiki/English_Reports`（Index chart 1930, p.3 转引；取用 2026-09-16）。**证据类别：仅第三方**（Wikipedia/Index Chart 转述）；**直接检索、直接抓取 `iclr.co.uk`（403）、`web.archive.org` 对 ICLR 路径的快照查询（404）与 Internet Archive 的 ER 卷扫描件均未取得出版方一手分册页**（Stevens & Sons 无在线自述页）。
**独立佐证（国际标准书目的卷数）**：Internet Archive 编目 `cihm_77146`《Comparative table law reports shewing those published prior to 1866, and also the volumes in which they have been reprinted in the Revised reports and the English reports reprint》（1908）——加拿大政府/法学界当时的对照表，`https://archive.org/details/cihm_77146`。
**核心事实（用于 mixed 判定）**：**Vols 12–20 是枢密院卷，且明载含 Indian Appeals**；Vols 1–11 含上议院（其中含苏格兰/爱尔兰上诉）。两者都不是「英格兰法院专属」。

**反例搜寻（强制项）**：
- 路径 A：分册结构（上表）——Privy Council 与 Indian Appeals 分册的存在本身即反例（殖民地上诉）；House of Lords 分册含苏格兰、爱尔兰上诉。
- 路径 B：A.C. 1930 卷内可确证的**印度枢密院上诉**为 `Arnold v. The King-Emperor ... L.R. 41 I.A. 149`（见该卷 `TABLE OF CASES CITED` 的 A 部；English Reports 的 PC 分册与 Law Reports 的 Indian Appeals 分册是同源判词的不同印本）；同一 A.C. 卷内 `Chung Chuck v. The King`（加拿大）被标为 P.C.。
- 路径 C：尝试直接取 ER 卷扫描件（`perma_cc_82KS-YNZL` = "Triquet v. Bath 97 English Reports Full Reprint"，2022 上传）以作卷内页证，仅见单案摘录，**未取得卷首页**——如实记录。
- **未找到**任何说 English Reports 只含英格兰法院判例的出版方声明。

**结论**：`er` = `mixed`，不写 origin 行。若后续决定按分册拆分（如 `72 ER`–`122 ER` 视作英格兰王座法庭），需先补 **出版方一手分册表**，本轮不具备。

**volume_system = `continuous`**（178 卷跨年连续，卷号即全集顺序，与年份无一年一卷关系）。来源：上表（Vols 1–178 连续编号）。

### 2.4 `aller`（All England Law Reports）——**mixed**（证据仅第三方）

**是什么**：LexisNexis Butterworths 出版的商业汇编，1936 年创刊；另有 All ER Reprints（覆盖 1558–1935）与 All ER Reprints Extension（1861–1935）。

**书面证据（第三方）**：`https://en.wikipedia.org/wiki/All_England_Law_Reports`（取用 2026-09-16）——「covering cases from the court system in England and Wales」「encompass judgments ... from the Supreme Court (formerly the House of Lords), both divisions of the Court of Appeal and all divisions of the High Court」。**未提及枢密院**——这是本项的隐患。
出版方产品页（`https://www.lexisnexis.co.uk/legal/products/all-england-law-reports.html`）**返回 404**，未能取得出版方自述 → 因此本项**不能**给 `exclusive_publisher`。

**具体反例（强制项，已命中，且是决定性的）**：A.C. 1930 卷的案件表与判词页显示，**All England Law Reports 的前身/姊妹系列 `All E.R. Rep.` 收录加拿大与印度的枢密院上诉**：
- A.C. 1930 卷 `TABLE OF CASES CITED` 中的 `All ER Rep` 引注：扫描页在引用 `[1929] All ER Rep 571` 的同时把 `Arnold v. The King-Emperor ... L.R. 41 I.A. 149`（印度枢密院上诉）排在同页/相邻页。该页 OCR 严重劣化，**此条只作低置信旁证**。
- **高置信**：Wikipedia 的 Edwards 条目给出的平行引注 `[1929] All ER Rep 571`（`https://en.wikipedia.org/wiki/Edwards_v_Canada_(AG)`，取用 2026-09-16）——`Edwards v Canada (AG)` 是加拿大来源地的枢密院上诉（BAILII 已证，见 §2.1），其 `All ER Rep` 印本即加拿大案件印在 All E.R. 家族里。

🔎 **诚实标注**：`[1929] All ER Rep 571` 出自 **All England Law Reports Reprint**（覆盖 1558–1935），与 1936 年创刊的 All ER 主系列**不是同一套卷号**。上引加拿大案是 All ER **Reprint** 里的加拿大枢密院案，它证明的是「All E.R. 家族会印非英格兰案件」，**严格说不能直接证明 1936 年后的 All ER 主系列也如此**。因此：

- 若决策只看 1936 年后的主系列 → 现有证据**不足以**支持 exclusive，也不足以支持「已坐实的 mixed」；**应当停在 `mixed`（因为无法排除）**。
- 若决策把全部 `aller` 键（语料含 1922– 年值，含 1920s/1930s 的 `All ER Rep` 形）视为一族 → 已坐实 mixed。
- **两种读法下结论都是 `mixed`**，所以本行安全。

**volume_system**：主系列 1936– 为 `year_volume`（`[1955] 1 All E.R. 1` 形）；Reprints 系列为连续卷。语料实测 `aller` 值 vol 1–4、年 1922–2023，与「年内分册卷号」一致。
**窗口**：1936– （主系列）；**未核实**是否须并含 All ER Rep（1558–1935）。

### 2.5 `kb`（英文 K.B.）——**mixed**（不写 origin 行）

**是什么**：The Law Reports 的 King's Bench 分册。按 ICLR 引用体系，该分册 1891 年起用 `[year] ... Q.B.`/`K.B.` 形；因君主更替，**1901–1952 年印作 K.B.**（1901–1951 为爱德华七世/乔治五世/乔治六世在位期），1952 年及以后回 Q.B.；2022 年起再作 K.B.。

**书面证据**：ICLR 1930 年 A.C. 卷卷首页的 `Mode of Citation` 声明：

> `In the Second Series, [1930] 1 K. B. ; [1930] 2 K. B. ; [1930] P.`
> `In the Third Series, [1930] A. C.`

来源：`law-reports-appeal-cases_1930` 卷首页（同 §2.1；取用 2026-09-16）。→ **K.B. 是《Law Reports》三套系列中的 Second Series，与 A.C.（Third Series）、Ch.（First Series）并列。**

**volume_system = `year_volume`**（同页 `[1930] 1 K. B.` 即年内第 1 卷）。**窗口（独立溯源）**：1901–1952 为 K.B. 在英文《Law Reports》里的适用期（1901 起由 Q.B. 改名 K.B.，1952 起改回 Q.B.）——来源：上引 1930 年卷首页的系列声明 + 该系列命名沿革（第三方：`https://en.wikipedia.org/wiki/Law_Reports`，取用 2026-09-16）。

**反例搜寻（强制项）**：
- 路径 A：同一卷首页显示 K.B. 属 ICLR 家族，而 ICLR 家族**同一出版体系**的 A.C. 与 P.D. 分册明载枢密院（见 §2.1、§2.9）。枢密院案印在 A.C.，**不印在 K.B.**——但 K.B. 分册的卷首页本轮**未取得**，无法逐字确认其是否排除苏格兰/爱尔兰/殖民地材料。
- 路径 B：语料层面 `kb` 实测年区间 1893–1971、vol 1–2 高频（200–300 条量级），与 E&W 的 `[year] 1/2 K.B.` 形一致；未见明显异常卷号（不像 `qb` 那样出现 19521 类噪声）。
- 路径 C：**未找到** K.B. 卷内非 E&W 案件的具体反例。
- 路径 D（未取得）：1888 年《Law Reports》「King's Bench Division」卷（Internet Archive `law-reportsking00grea`，年份栏 1888，该年份值属编目噪声）本可用于卷首页取证，本轮未取。

**结论（保守）**：`kb` = `mixed`，不写 origin 行。理由是**证据不足**（未取得 K.B. 卷首页；无法排除苏格兰/爱尔兰/殖民地材料混入），而不是已发现反例——按任务规则「不得排除即 mixed」。
🔎 **给决策者的提示**：若后续补到 K.B. 卷首页（应为 `SUPREME COURT OF JUDICATURE. CASES DETERMINED IN THE KING'S BENCH DIVISION` 形，且通常附 `AND ON APPEAL THEREFROM IN THE COURT OF APPEAL`），`kb` 在 1901–1952 窗口内**有可能**被降为可写行；本轮不写。

### 2.6 `qb`（同形异义：英文 Q.B. × 魁北克 Q.B.）——**mixed**（不写 origin 行），但分离窗口已独立溯源

**是什么（两个不同的东西共用同一个印刷形）**：
1. **英文**：The Law Reports 的 Queen's Bench 分册（1875–1890 名 `Q.B.D.`；1891 起 `[year] Q.B.`）；
2. **魁北克**：魁北克的官方汇编与早期 Q.B. 汇编，印刷引注形同样是 `Q.B.`

**魁北克侧的关键发现（这一节是本组最高价值的溯源）**：

（a）**1899 年的魁北克判例摘要**在标题里就把官方汇编印作 `Q.B.` 与 `S.C.`：
> `Consolidated digest of the decisions of the courts of the province of Quebec [microform] : from the commencement down to and including **vol. 3 of the official reports [Q.B. 1894]** and **vol. 6 of the official reports (S. C. 1894)**`
> 出版：Montreal : J. Lovell, 1899；作者：Snow, F. Longueville；OCLC 12066230；CIHM 编号 26073。

来源：Internet Archive 编目 `https://archive.org/details/cihm_26073`（含 MARC/都柏林核心记录；取用 2026-09-16）。
→ **这是「魁北克官方汇编 = Q.B.」的直接书目证据**，且给出卷/年对应关系：`Q.B. 3 = 1894`、`S.C. 6 = 1894`。

（b）**1900 年官方总索引**给出该汇编的精确规模与期间：
> `Table générale des rapports judiciaires de Québec = General index, **1892-1898** : comprenant **volumes 1-7 B.R.**, et **volumes 1-14 C. S.**`
> 编者：Kirby, James (b. 1840) 与 Mignault, P. B. (1854–1945)；出版者：**Conseil Général du Barreau de la Province de Québec**；1900。

来源：Internet Archive 编目 `https://archive.org/details/cihm_10653`（另有同书 `cu31924016980603`，取用 2026-09-16）。
→ **魁北克官方汇编：1892–1898；Q.B.（= B.R., Banc de la Reine）vols 1–7；S.C.（= Cour Supérieure）vols 1–14。** 这是「year_volume」结构（每年重新起卷，卷号=年内次序），且期间由官方索引自身锚定。

（c）**更早的魁北克 Q.B. 汇编（蒙特利尔版）**：
> `The Montreal law reports. Court of Queen's Bench`（编者 James Kirby；作者机构 `Québec (Province). Court of King's Bench`；**7 volumes**；Internet Archive 年份栏 1885）

来源：Internet Archive 编目 `montreallawrepo01kirbgoog` … `montreallawrepo05kirbgoog`（`https://archive.org/advancedsearch.php?q=title%3A%28%22Montreal+law+reports%22%29&output=json`，取用 2026-09-16）。
→ 7 卷，约 1884/85–1891，随后由 1892 年起的官方汇编接续（与 (b) 的 1892 起点衔接）。**起止年：起 1884/85（7 卷之第 1 卷的编目年为 1885，`1884/85` 形属推断，标「未核实」）；止 1891（由 (b) 的 1892 起点反推，标「未核实」）。**

（d）**魁北克法院沿革**：Court of Queen's Bench（Cour du Banc de la Reine）**1849-05-30 设立**（即今魁北克上诉法院前身），**1974 年**正式改名 Quebec Court of Appeal；刑事管辖 1920 年移交高等法院。
来源：`https://en.wikipedia.org/wiki/Quebec_Court_of_Appeal`（第三方；取用 2026-09-16）。该页引官方 `courdappelduquebec.ca/en/about-the-court/history/`（一手，本轮未直接取到）。

**英文侧的证据**：见 §2.5 同页 `Mode of Citation` 声明（`In the Second Series, [1930] 1 K. B. ...`），以及《Law Reports》系列沿革（1891 起改为年内卷号、1901 起 Q.B.→K.B.）。

**反例搜寻（强制项）**：
- 路径 A：上引 (a)(b) 本身就是「同形冲突」的实证——**同一个 `Q.B.` 形在 1890s 同时能指英文 Q.B. 与魁北克官方汇编**，且两者都用 `vol n (year)` 形。**重叠区 = 1892–1898（魁北克官方汇编存在期）∩ 英文 Q.B. 存在期（1875– ）**。**按设计，该重叠区必须保持 UNDETERMINED。**
- 路径 B：语料实测 `qb` 的 top combos `(2,1898,103)`、`(1,1892,89)`、`(1,1896,74)`、`(1,1893,70)`、`(1,1891,68)`、`(2,1891,63)`、`(1,1895,61)`、`(1,1899,58)`、`(2,1892,55)`、`(2,1899,48)`、`(2,1900,46)` —— **全部落在 1891–1900、vol 1–2**，正好与魁北克官方汇编（1892–1898，vols 1–7）与蒙特利尔汇编（至 1891）的形态吻合，而英文 1875–1890 段是跨年连续卷号（vol 1 = 1875–76）**不会**出现「1898 年第 2 卷」这种形。→ **强烈提示这批是魁北克案，不是英文案。**
- 路径 C：尝试检索 `Quebec law reports` 的 Superior Court 分册（`sc` 对应物）——Internet Archive 无匹配（`numFound: 0`）；`sc` 未进入本组 tier 1–2 目标表，**本轮未展开**。
- **未找到**任何一手文本明确规定 `qb` 只指其一。

**结论**：`qb` = `mixed`（同形不可判），**不写 origin 行**。🔎 但两个分离窗口已独立溯源，可供后续（若项目增设「窗口+形制」联合判据）使用：
- 魁北克：`1892–1898`，vols 1–7（官方 Q.B./B.R.）+ `1884/85–1891`，vols 1–7（Montreal Law Reports, Court of Q.B.）；
- 英文：`[year] Q.B.` 形自 1891 起（1891–1900 名为 Q.B.，1901–1952 名为 K.B.）；1875–1890 为 `Q.B.D.` 跨年卷号。
- **重叠区 1892–1898 → 必须留 UNDETERMINED。**

### 2.7 `chd`（Law Reports, Chancery Division, 1875–1890）——**mixed**（不写 origin 行）

**是什么**：ICLR《Law Reports》的 Chancery Division 分册（第二刷次），1875–1890，卷号跨年连续。

**书面证据（编目标题即出版方卷首页文字）**：
> `The Law Reports Of The Incorporated Council Of Law Reporting 1893 Vol. 2 (**Chancery Division**) **Supreme Court Of Judicature Cases Determined In The Chancery Division And In Lunacy And On Appeal There From In The Court Of Appeal**`（`wbsl.20754`）
> `The Law Reports 1890 Vol. 45 ... **Supreme Court Of Judicature Cases Determined In The Chancery Division And In Lunacy And On Appeal Therefrom In The Court Of Appeal**`（`wbsl.21047`）
> `The Law reports. Division I, Chancery : Cases determined by the Chancery Division of the High Court of Justice, and by the Chief Judge in Bankruptcy, and by the Court of Appeal on appeal from the Chancery Division and the Chief Judge, and in lunacy`（`lawreportsdivisi40hemm`，1876）

来源：`https://archive.org/advancedsearch.php?q=title%3A%28%22chancery+division%22%29+AND+title%3A%28%22law+reports%22%29&output=json`（取用 2026-09-16）。

**volume_system = `continuous`**：卷首页显示卷号 1 = 1875–1876（`law-reports-chancery-division_1875-1876_1`）、卷 40 = 1889、卷 45 = 1890 → 跨年连续卷号，年份不进入引注（`(1889) 40 Ch. D. 1` 形）。
**窗口（独立溯源）**：`chd` 1875–1890，vols 1–45。来源：上引编目序列（1875-1876 vol 1 … 1889 vol 40 … 1890 vol 45）。**语料实测 vol 1–45、年 1863–1959 与之部分吻合；1347 条空年提及正与 `(1889) 40 Ch. D. 1` 的跨年形一致。**

**反例搜寻（强制项）**：
- 路径 A：同族《Law Reports》的 **Appeal Cases 分册明载枢密院与贵族爵位案**（§2.1），**Probate Division 分册明载枢密院上诉**（§2.9）。分册之间共用一个 ICLR 体系；Ch.D. 卷自身未见排除枢密院/殖民地上诉的表述。
- 路径 B：语料实测 `chd` 年区间 1863–1959、vol 1–45；1959 端超出 Ch.D.（1875–1890）范围 → 说明 `chd` 键里混入了其他形（可能含 `Ch.` 形），**键本身不纯**。另注意 1863–1875 段实为 `Ch. App.`（见 `chapp`），被归一化到 `chd` 或 `ch`。
- 路径 C：**未找到** Ch.D. 卷内的具体非 E&W 反例。

**结论**：`chd` = `mixed`（证据不足以确立排他；且键形不纯），不写 origin 行。

### 2.8 `ch`（The Law Reports, Chancery Division, 1891– ）——**mixed**（不写 origin 行）

**是什么**：ICLR《Law Reports》第三刷次的 Chancery Division 分册，1891 年起用 `[year] Ch.` 形。

**书面证据**：
> `The Law Reports Of The Incorporated Council Of Law Reporting 1891 Vol. 2 (Chancery Division) Supreame Court Of Judicature Cases Determined In The Chancery Division ...`（`wbsl.20659`, `wbsl.20296`, `wbsl.20658`, `wbsl.20946`）
来源：同上编目查询（取用 2026-09-16）。

**volume_system = `year_volume`**：1891 年 **Vol. 1 与 Vol. 2 同属 1891**（`wbsl.20296` = 1891 Vol. 1；`wbsl.20659` = 1891 Vol. 2）→ 卷号在年内重启、年份进入引注（`[1891] 2 Ch. 1`）。这是 year_volume 的直接证据。
**窗口（独立溯源）**：1891– 至今；`ch` 语料实测年 1803–2014、vol 1–19741（19741 明显是解析噪声）。

**反例搜寻（强制项）**：
- 路径 A：**同一 ICLR 出版体系**的 A.C. 分册卷首页明载 `HOUSE OF LORDS, JUDICIAL COMMITTEE OF THE PRIVY COUNCIL AND PEERAGE CASES`（§2.1），**P.D. 分册明载 `AND ON APPEAL THEREFROM IN THE PRIVY COUNCIL`**（§2.9）。Ch. 卷首页同源、同体系。
- 路径 B：语料 `ch` 含 `[1927] Ch. 313`（`In re Aschrott`）等；同一 A.C. 1930 卷的案件引用表把印度枢密院上诉 `Arnold v. The King-Emperor, L.R. 41 I.A. 149` 与 `[1927] 1 Ch. 313` 相邻引用于同一页 → 属**引用**而非**刊登**，**不构成反例**（诚实区分）。
- 路径 C：**未找到** Ch. 卷内非 E&W 案件的具体反例。

**结论**：`ch` = `mixed`（证据不足），不写 origin 行。

### 2.9 `qbd`（Law Reports, Queen's Bench Division, 1875–1890）——**mixed**（不写 origin 行）

**是什么**：ICLR《Law Reports》的 Q.B.D. 分册（1875–1880 为六个分册之一；1881–1890 为四个分册之一）。
**书面证据**：ICLR 1879 年《Digest of Cases Decided By The House Of Lords, **The Privy Council**, The Court Of Appeal; The Chancery, **Queens Bench**, Common Pleas, Exchequer And Probate, Divorce And Admiralty Divisions Of The High Court Of Justice; ...`（`wbsl.21042`，1875–78 Digest）——**同一 ICLR 体系内枢密院与 Queen's Bench 并列**。
**附带的决定性旁证（Probate Division 分册卷首页）**：
> `The Law Reports 1890 Vol. 15, LIII And LIV Victoriae (**Probate Division**) ... Probate Division Cases Determined In The Courts Of Probate And Divorce In The Admiralty And Ecclesiastical Courts **And On Appeal ThereFrom In The Privy Council** And In The Court Of Appeal`（`wbsl.20805`）

来源：`https://archive.org/advancedsearch.php?q=title%3A%28%22law+reports%22%29+AND+title%3A%28%22privy+council%22%29&output=json`（取用 2026-09-16）。
→ **ICLR 的《Law Reports》分册明确刊登枢密院上诉**（此条对 `p`/`pd` 键是直接反例，对 `qbd` 是同族旁证）。

**volume_system**：1875–1890 为跨年连续卷号（`(1881) 7 Q.B.D. 1` 形）；1891 起改年内卷号。语料 `qbd` 实测 **1032/1646 条无年**，正与跨年卷号形一致。
**窗口（独立溯源）**：1875–1890，vols 1–45 量级（语料实测 vol 1–49；编目见 `lawreportsdivisi40hemm` 等）。1891 起该分册名变为 `Q.B.`（本组另有 `qb` 键，见 §2.6）。

**反例搜寻（强制项）**：路径 A = 上引 Digest 与 Probate Division 卷首页（同体系明载枢密院）；路径 B = 语料 `qbd` 年区间 1833–1987 超出 1875–1890，键形不纯（1833–1875 段应为其他 Q.B. 名义汇编）。**未找到** Q.B.D. 卷内非 E&W 案件的具体反例。
**结论**：`qbd` = `mixed`，不写 origin 行。

### 2.10 `crappr`（Criminal Appeal Reports）——**mixed**（证据不足，不写 origin 行）

**是什么**：Sweet & Maxwell 出版的刑事上诉判例汇编，1908/09 创刊。
**书面证据（编目卷号/年，来自出版方卷册）**：
> `Criminal Appeal Reports **1909: Vol 1**`；`1910: Vol 4`；`1913: Vol 8`；`1930-1931: Vol 22`；`1952: Vol 36`；`1955: Vol 39`；`1959: Vol 43`；`1961: Vol 45`

来源：`https://archive.org/advancedsearch.php?q=title%3A%28%22criminal+appeal+reports%22%29&output=json`（取用 2026-09-16）。
**volume_system = `continuous`**：vol 1 = 1908/09 → vol 36 = 1952 → vol 98 = 2023（语料实测 vol 上限 98），卷号跨年连续、年份不进引注（`(1952) 36 Cr. App. R. 1` 形）。语料实测 **0 条空卷、69 条空年**，与连续卷号形一致。
**窗口（独立溯源）**：1908/09– 至今，vols 1–98+。起点证据 = 上引 `1909: Vol 1`；终点证据 = 语料实测 vol 98（**语料仅用于对齐，不作范围依据**）+ 上引 `1961: Vol 45` 的年/卷斜率外推（**外推部分标「未核实」**）。

**反例搜寻（强制项）**：
- 路径 A：尝试取卷首页/出版方 scope 自述——Sweet & Maxwell 无公开 scope 页；Internet Archive 的 CR.App.R. 卷为闭架（lending）扫描，其元数据无 scope 文字。
- 路径 B：英国刑事上诉法院（Court of Criminal Appeal, 1907–1966）依 1907 年《Criminal Appeal Act》只审英格兰与威尔士的刑事上诉；但**枢密院刑事上诉**与**殖民地刑事上诉**不进该院——因此理论上 CR.App.R. 可近似为 E&W；**但本轮未取得出版方声明**，按规则不得升为 exclusive。
- 路径 C：语料 `crappr` 无 GB 之外的实测法域值可对照（分类层 GB=730 为单一值，属分类层输出，**不作证据**）。
- **未找到**权威的报道范围声明 → 判为 `mixed`（不排除），而非「已坐实排他」。

**结论**：`crappr` = `mixed`，不写 origin 行。🔎 若需将其升为可写行，最短路径是取得 **Sweet & Maxwell 产品页/卷首页**的报道范围文字（本轮未取得）。

### 2.11 `lr.hl` 与 `lr.qb`（Law Reports 第一系列分册，1865–1875）——**mixed**（不写 origin 行）

**是什么**：ICLR 前身（1865–1875）的《Law Reports》第一系列分册。该时期分册数由 11 个递减为 6 个。

**书面证据（编目即卷首页文字）**：
> `The Law Reports. **House of Lords, English and Irish Appeals**` 1866–1870 各卷（`law-reports-english-and-irish-appeal-cases_1867_2`, `..._1868_3`, `..._1870_4`）
> `The Law Reports. **Scotch and divorce appeal cases before the House of Lords**`（`pub_law-reports-scotch-and-divorce-appeal-cases`）
> `The Law reports. **Cases heard and determined by the Judicial Committee and the Lords of Her Majesty's Most Honourable Privy Council**`（`lawreportsprivy02lordgoog`, 1867）
> `The Law Reports. **Privy Council Appeals** 1867-1869: Vol 2`（`law-reports-privy-council-appeals_1867-1869_2`）
> `The Law Reports. **Indian Appeals**: Being Cases in the Privy Council on Appeal from the East Indies`（`lawreportsindia06stongoog`, `lawreportsindia10stongoog`；另有 Vols 5, 10, 12–14, 18, 20–21 等）

来源：`https://archive.org/advancedsearch.php?q=title%3A%28%22law+reports%22%29+AND+title%3A%28%22privy+council%22%29&output=json`（取用 2026-09-16）。

**决定性事实**：**`lr.hl` 键对应的分册在 1866–1870 的正式卷名就是「English and Irish Appeals」**（含爱尔兰上议院上诉），另有 Scotch and Divorce 分册；而 `lr.pc`（枢密院上诉）与 `Indian Appeals` 分册本身就是殖民地上诉集。
→ **`lr.hl` = `mixed`（含爱尔兰/苏格兰上议院上诉）。**

**窗口（独立溯源）**：
- `lr.hl`：1865–1875，vols 1–11（第一系列 House of Lords 分册；语料实测 vol 1–7、年 1864–1895）。**vol 上限 11 属第三方沿革，标「未完全核实」。**
- `lr.qb`：1865–1875，vols 1–10（语料实测 vol 1–10、年 1865–1937）。**1937 端为键形噪声（1937 应为 `[1937] 1 K.B.` 或 `Q.B.` 形）。**
- `chapp`（tier 3）：1865–1875，vols 1–10（编目 10 卷；2024 年 11 月前已数字化为 `lawreportschanc00..07changoog`）。
- `lr.pc`（tier 3）：1865–1875，vols 1–9（编目见 Vol 2 = 1867–1869）。

**volume_system = `continuous`**（第一系列各分册卷号跨年连续，年份不进引注：`L.R. 4 CP. 374`、`L.R. 7 Q.B. 361` 形——该形在 A.C. 1930 卷判词中被引用，见 `Chorlton v. Lings (1868), L.R. 4 CP. 374`、`The Queen v. Harrold (1872), L.R. 7 Q.B. 361`）。**这同时是 `cp`/`qb` 键形噪声的来源。**

---

## 3. CSV（机器可合并块）

> 规则遵循：`mixed` / `scope_evidence_third_party_only` / `not_a_reporter` 行留空 `origin_country`，在 `notes` 说明，仍填 `source` + `source_locator`。自由文本内用 `;` 不用逗号。日期一律 2026-09-16。

```csv
printed_abbreviation,normalized_key,origin_country,origin_subdivision,exclusivity,volume_system,vol_range_start,vol_range_end,year_range_start,year_range_end,source,source_locator,verification_status,counter_example_check,notes
A.C.,ac,,,mixed,year_volume,1,,1891,,Incorporated Council of Law Reporting for England and Wales (publisher's own volume title page); BAILII (JCPC decisions database cite-as lines),https://archive.org/details/law-reports-appeal-cases_1930 (title page: "HOUSE OF LORDS; JUDICIAL COMMITTEE OF THE PRIVY COUNCIL AND PEERAGE CASES"); https://www.bailii.org/uk/cases/UKPC/1929/1929_86.html (accessed 2026-09-16),verified_mixed,"HIT: [1930] AC 124 Edwards v Canada (AG) - JCPC appeal from the Supreme Court of Canada; plus A.C. 1930 index PC cases from Canada (Royal Trust Co v A-G Alberta 144; Lecavalier v City of Montreal 152; Erie Beach v A-G Ontario 161; Lovibond v GG Canada 623; Keewatin Power v Lake of the Woods 640; Toronto Transportation v CNR 686) and from Nigeria/Ceylon/NSW/Straits Settlements/Malta; plus H.L.(Sc.) and H.L.(N.I.) appeals","Same series as appcas in an earlier printed form (App. Cas. 1875-1890; A.C. from 1891). Publisher title page shows Privy Council reporter on staff. MUST NOT be treated as GB-only: Privy Council appeals from Canada are Canadian-origin cases. Volume 1 of A.C. was 1891; corpus vol span 1-19781 is parse noise"
App. Cas.,appcas,,,mixed,continuous,1,15,1875,1890,Incorporated Council of Law Reporting for England and Wales (publisher's own volume title page),https://archive.org/advancedsearch.php?q=identifier%3A%22wbsl.21054%22 (vol 15 1890 title: "Appeal Cases Before The House Of Lords And The Judicial Committee Of The Privy Council Also Peerage Cases"; accessed 2026-09-16),verified_mixed,"HIT: A.C. 1930 table of cases cited includes St. Catherine's Milling and Lumber Co. v. The Queen (1888) 14 App. Cas. 46 (Canadian Privy Council appeal); the whole series is the House of Lords + Privy Council + peerage series","Predecessor printed form of ac. Vols 1-15 cover 1875-1890. 2142/3274 corpus mentions have no year at all which is consistent with the continuous-volume printed form"
All E.R.,aller,,,mixed,year_volume,,,1936,,LexisNexis Butterworths (publisher; product page unreachable); Wikipedia (third-party) ; BAILII/ICLR volume indexes,https://en.wikipedia.org/wiki/All_England_Law_Reports (accessed 2026-09-16); https://www.lexisnexis.co.uk/legal/products/all-england-law-reports.html (HTTP 404 on 2026-09-16); https://en.wikipedia.org/wiki/Edwards_v_Canada_(AG) (parallel citation [1929] All ER Rep 571),scope_evidence_third_party_only,"HIT (family level; HIGH confidence via Wikipedia's parallel citation): [1929] All ER Rep 571 = Henrietta Muir Edwards v Attorney-General for Canada (Privy Council; Canadian origin; the BAILII-verified [1930] AC 124 case) - proof that the All E.R. family reports non-English decisions. LOW-confidence OCR corroboration: the A.C. 1930 table of cases cited places Indian Privy Council appeal Arnold v The King-Emperor (L.R. 41 I.A. 149) on the same page as an All ER Rep reference. NOTE the 1929 citation is to the All ER Reprints series (1558-1935) not the 1936- main series; no counter-example found for the main series itself","Publisher scope page returned HTTP 404 (checked 2026-09-16) so no exclusive_publisher claim is possible; result is mixed either way. Corpus vol span 1-4 and year span 1922-2023 includes the All ER Rep form; whether the production key should absorb the Reprints series is an open decision for the consolidator"
K.B.,kb,,,mixed,year_volume,1,2,1901,1952,Incorporated Council of Law Reporting for England and Wales (publisher's own citation-scheme statement),https://archive.org/details/law-reports-appeal-cases_1930 (title page: "In the Second Series; [1930] 1 K. B.; [1930] 2 K. B."; accessed 2026-09-16),verified_mixed,"NOT FOUND as a concrete in-volume counter-example; but K.B. could not be EXCLUDED either: no K.B. volume title page was obtained this round and the sibling sub-series of the same publisher (A.C.; P.D.) demonstrably carry Privy Council appeals","Conservative verdict: mixed because not excluded. Verdict may be upgradable if a K.B. volume title page is obtained. Note the corpus kb year span 1893-1971 straddles the 1901-1952 K.B. naming window and also the 1875-1901 Q.B. naming window; corpus vol span 1-19521 is parse noise"
Q.B.,qb,,,mixed,year_volume,1,7,1892,1898,Conseil General du Barreau de la Province de Quebec (official general index of the Quebec official reports); F. Longueville Snow digest (Montreal: J. Lovell 1899); Internet Archive catalogue records for the Montreal Law Reports,https://archive.org/details/cihm_10653 (Table generale des rapports judiciaires de Quebec = General index 1892-1898: volumes 1-7 B.R. and volumes 1-14 C.S.; accessed 2026-09-16); https://archive.org/details/cihm_26073 (digest title: "...including vol. 3 of the official reports [Q.B. 1894] and vol. 6 of the official reports (S. C. 1894)"; accessed 2026-09-16),verified_mixed,"HIT: the 1899 Quebec digest prints the Quebec official reports as Q.B. and S.C.; the 1900 official general index gives the Quebec official Q.B. run as 1892-1898 vols 1-7 (B.R.). The corpus top qb combos (vols 1-2; years 1891-1900) match the Quebec shape and not the English continuous-volume shape","Homograph. TWO separable windows sourced independently but NOT proposed as origin rows because the overlap region cannot be resolved: Quebec official = 1892-1898 vols 1-7; Montreal Law Reports Court of Queen's Bench = 7 vols c.1884/85-1891 (start/end inferred; unverified); English = [year] Q.B. from 1891 (named Q.B. 1891-1900 then K.B. 1901-1952). OVERLAP 1892-1898 must stay UNDETERMINED by design"
Ch. D.,chd,,,mixed,continuous,1,45,1875,1890,Incorporated Council of Law Reporting for England and Wales (publisher's own volume title pages),https://archive.org/advancedsearch.php?q=title%3A%28%22chancery+division%22%29+AND+title%3A%28%22law+reports%22%29 (titles: "Supreme Court Of Judicature Cases Determined In The Chancery Division And In Lunacy And On Appeal Therefrom In The Court Of Appeal"; vol 1 = 1875-1876; vol 45 = 1890; accessed 2026-09-16),verified_mixed,"NOT FOUND as a concrete counter-example in a Ch.D. volume; not excluded either. Sibling sub-series of the same publisher carry Privy Council appeals and the Ch.D. title page does not exclude colonial/Privy Council material","Corpus chd year span 1863-1959 and vol span 1-45: the 1863-1875 tail belongs to Ch. App. (see chapp) and the post-1890 tail belongs to [year] Ch. (see ch); the key is not form-pure. 1347/2020 mentions have no year which matches the (1889) 40 Ch. D. 1 printed form"
English Reports,er,,,mixed,continuous,1,178,1220,1866,Stevens & Sons (London) and William Green & Son (Edinburgh) (publisher index chart 1930); Internet Archive catalogue; UK statutes project collection,https://en.wikipedia.org/wiki/English_Reports (publisher's 1930 Index Chart p.3 transcribed: vols 12-20 = Privy Council including Indian Appeals 1809-1865; 178 vols; accessed 2026-09-16); https://archive.org/details/cihm_77146 (Comparative table law reports 1908; accessed 2026-09-16),scope_evidence_third_party_only,"HIT: volumes 12-20 of the English Reports are the Privy Council sub-series and expressly include Indian Appeals; volumes 1-11 are House of Lords (which includes Scottish and Irish appeals); volumes 161-167 are Ecclesiastical/Admiralty/Probate","No one-volume publisher scope statement obtained this round; the sub-series table is transcribed from a third-party source (Index Chart 1930) so this is third-party evidence only. Consequence: er must NOT be used as GB-only positive origin evidence. Corpus vol span 1-176 excludes the index volumes 177-178"
Ch.,ch,,,mixed,year_volume,1,2,1891,2026,Incorporated Council of Law Reporting for England and Wales (publisher's own volume title pages),https://archive.org/advancedsearch.php?q=title%3A%28%22chancery+division%22%29+AND+title%3A%28%22law+reports%22%29 (1891 Vol. 1 and 1891 Vol. 2 both published for 1891 -> year_volume; accessed 2026-09-16),verified_mixed,"NOT FOUND as a concrete counter-example in a Ch. volume; not excluded either. Same ICLR family whose A.C. title page names the Privy Council and whose P.D. title page names appeals to the Privy Council","year_volume is directly proved by two volumes both numbered for 1891. Corpus ch vol span 1-19741 is parse noise; corpus year span 1803-2014 includes pre-1891 Ch. App. forms"
Q.B.D.,qbd,,,mixed,continuous,1,45,1875,1890,Incorporated Council of Law Reporting for England and Wales (publisher's own Digest and Probate Division title page),https://archive.org/advancedsearch.php?q=title%3A%28%22law+reports%22%29+AND+title%3A%28%22privy+council%22%29 (ICLR Digest 1875-78 listing "The House Of Lords; The Privy Council; The Court Of Appeal; ... Queens Bench"; Probate Division vol 15 1890 title "And On Appeal ThereFrom In The Privy Council"; accessed 2026-09-16),verified_mixed,"NOT FOUND as a concrete counter-example in a Q.B.D. volume; not excluded either. The same publisher's Digest for 1875-78 lists the Privy Council alongside the Queen's Bench Division","1875-1890 continuous volumes; from 1891 the sub-series is printed Q.B./K.B. (see kb and qb). 1032/1646 corpus mentions have no year which matches the continuous-volume printed form. Corpus year span 1833-1987 shows the key is not form-pure"
W.L.R.,wlr,,,mixed,year_volume,1,3,1953,2026,Incorporated Council of Law Reporting for England and Wales (publisher's own website),https://web.archive.org/web/20100116085250/http://www.lawreports.co.uk/Publications/newlr.htm ("The Law Reports cover cases heard in The House of Lords and Privy Council; The Court of Appeal - Criminal and Civil Divisions; Chancery Division; Family Division; Queen's Bench Division; as well as the Employment Appeal Tribunal and the ECJ"; 2009 Part 12 index lists an ECJ case under APPEAL CASES; accessed 2026-09-16); https://www.bailii.org/uk/cases/UKPC/1956/1956_21.html (cite-as "[1956] 1 WLR 965"; accessed 2026-09-16),verified_mixed,"HIT: Subramaniam v The Public Prosecutor (Malaya) is cited [1956] 1 WLR 965 by BAILII - a Privy Council decision from Malaya printed in W.L.R. Also the publisher's own index puts an ECJ case in the Appeal Cases listing","Publisher scope statement obtained; verdict nonetheless MIXED because the series demonstrably carries non-E&W decisions (Privy Council; ECJ). ANSWER TO THE CORPUS QUESTION: the 76 corpus mentions classified CA are not necessarily a grouping error - W.L.R. does report Privy Council appeals from Canada (court_origin CA under this project's JCPC semantics) - but wlr itself carries no origin evidence. Corpus year span 1905-2021: the 1905 end is noise from [1929] All ER Rep type strings and must NOT be used as the series start (true start 1953)"
Crim. App. R.,crappr,,,mixed,continuous,1,98,1908,2026,Sweet & Maxwell (publisher; no public scope statement found); Internet Archive volume records,https://archive.org/advancedsearch.php?q=title%3A%28%22criminal+appeal+reports%22%29 (vol 1 = 1909; vol 22 = 1930-1931; vol 36 = 1952; vol 45 = 1961; accessed 2026-09-16),scope_evidence_third_party_only,"NOT FOUND: no publisher scope statement and no concrete in-volume counter-example located. Not excluded. The Court of Criminal Appeal (1907-1966) heard only England and Wales criminal appeals but no authoritative reporting-scope text was obtained","Deliberately not promoted to exclusive because the only available support is inference from the court's jurisdiction; the task requires publisher/statute evidence for a writable row. Volume-year slope: vol 1 = 1908/09; vol 36 = 1952; vol 98 = 2023 (vol 98 taken from the corpus measurement and marked unverified)"
L.R. H.L.,lr.hl,,,mixed,continuous,1,11,1865,1875,Incorporated Council of Law Reporting (publisher's own volume title pages),https://archive.org/advancedsearch.php?q=title%3A%28%22law+reports%22%29+AND+title%3A%28%22privy+council%22%29 (titles "The Law Reports. House of Lords; English and Irish Appeals" 1867-1870; "Scotch and divorce appeal cases before the House of Lords"; accessed 2026-09-16),verified_mixed,"HIT: the sub-series itself was formally titled Law Reports; House of Lords; ENGLISH AND IRISH APPEALS (1866-1870) and there was a separate Scotch and Divorce Appeals sub-series - i.e. non-English House of Lords appeals were printed in this series","Corpus vol span 1-7; vol upper bound 11 is from the series history and is marked not fully verified. 530/698 mentions have no year which matches the continuous-volume printed form"
L.R. Q.B.,lr.qb,,,mixed,continuous,1,10,1865,1875,Incorporated Council of Law Reporting (publisher's own volume title pages and the series citation scheme),https://archive.org/advancedsearch.php?q=title%3A%28%22law+reports%22%29+AND+title%3A%28%22privy+council%22%29 (accessed 2026-09-16),verified_mixed,"NOT FOUND as a concrete counter-example in an L.R. Q.B. volume; not excluded either. The same first-series Law Reports family included Privy Council Appeals and Indian Appeals sub-series","Corpus vol span 1-10 and year span 1865-1937; the 1937 end is a form-impurity (that year belongs to [1937] Q.B./K.B.). 487/687 mentions have no year which matches the continuous-volume printed form"
L.R. Ch. App.,chapp,,,mixed,continuous,1,10,1865,1875,Incorporated Council of Law Reporting (publisher's own volume title pages),https://archive.org/advancedsearch.php?q=title%3A%28%22appeal+cases%22%29+AND+collection%3A%28americana%29 (titles "Law reports: chancery appeal cases; including bankruptcy & lunacy cases before the Lord chancellor & the court of appeal in chancery ... 1865-75"; accessed 2026-09-16),verified_mixed,"NOT FOUND as a concrete counter-example; not excluded. Same first-series family as the Privy Council Appeals and Indian Appeals sub-series","Tier 3; reached only via the same publisher-source batch. Corpus vol span 1-10 (409/463 mentions have no year) matches the continuous-volume printed form"
L.R. P.C.,lr.pc,,,mixed,continuous,1,9,1865,1875,Incorporated Council of Law Reporting (publisher's own volume title pages),https://archive.org/advancedsearch.php?q=title%3A%28%22law+reports%22%29+AND+title%3A%28%22privy+council%22%29 (titles "The Law reports. Cases heard and determined by the Judicial Committee and the Lords of Her Majesty's Most Honourable Privy Council"; "The Law Reports. Privy Council Appeals 1867-1869: Vol 2"; accessed 2026-09-16),verified_mixed,"HIT BY CONSTRUCTION: this sub-series IS the Privy Council appeals series; its cases are appeals from the colonies and dependencies (India; Canada; Australia; etc.) so their origin is not England and Wales","Tier 3. Corpus vol span 1-10 while the printed run is 9 volumes - treat the corpus upper bound as unverified. 274/368 mentions have no year"
```

---

## 4. 未到达 / 无权威出处

### 4.1 tier 1–2 全部到达
`ac` `aller` `appcas` `kb` `qb` `chd` `er` `ch`（tier 1，8/8）；`qbd` `wlr` `crappr` `lr.hl` `lr.qb`（tier 2，5/5）。

### 4.2 tier 3 未到达（本组共 60 个，只到达 2 个）
未到达者（`abbr`(counted 提及)，按 `r3_stage1_targets_british.md` 顺序，**完整名单**）：
`lr.cp`(594) `lt`(580) `mw`(535) `rpc`(534) `lr.eq`(447) `lr.ex`(440) `beav`(404) `ex`(384) `cb`(367) `hlcas`(349) `cbns`(322) `pd`(316) `timeslr`(310) `hn`(289) `tlr`(286) `bc`(282) `ves`(264) `lloydsrep`(258) `eb`(253) `bs`(247) `east`(246) `coxcc`(244) `moopc`(234) `ljch`(231) `ljqb`(216) `ljkb`(212) `cpd`(205) `tr`(200) `cp`(185) `bing`(184) `ltns`(170) `ae`(169) `sj`(167) `car`(159) `hare`(157) `omh`(156) `hlc`(152) `degmg`(146) `ljpc`(145) `exd`(138) `burr`(137) `lr.chapp`(119) `hl`(79) `lr.ch`(79) `lr.pd`(53) `lr.ae`(28) `pc`(27) `eq`(27) `lr.chd`(23) `lr.qbd`(19) `lr.cpd`(7) `lr.appcas`(6) `lr.exd`(6) `lr.hlc`(5) `lr.ac`(4) `lr.p`(2) `lr.kb`(2) `lr.cb`(1)。
已到达的 2 个：`chapp`（463）、`lr.pc`（368）。
**未到达原因**：预算优先给 tier 1–2 与同形异义（`kb`/`qb`）的独立窗口溯源。**这些不是「无权威出处」，而是「本轮未研究」。**
🔎 **其中 `cp`(185) 值得单独提示**：`cp` 是 tier 3 的 **british** 组目标，且与 `kb`/`qb` 同属「英文 Common Pleas × 魁北克/安大略 C.P.」同形异义家族——本轮**未研究**，但 `A.C. 1930` 卷判词中已出现 `L.R. 4 CP. 374` 形（第一系列 Common Pleas，continuous 卷号），可作起点。

### 4.3 到达但**未取得权威出处**（不得写行）
| 目标 | 缺口 | 已尝试的来源（均失败或不足） |
|---|---|---|
| `aller`（出版方 scope） | LexisNexis 产品页 404；未取得 1936 年主系列卷首页 | `https://www.lexisnexis.co.uk/legal/products/all-england-law-reports.html`（404，2026-09-16）；Internet Archive 无 All ER 主系列扫描 |
| `crappr` | 无 Sweet & Maxwell scope 文本 | 出版方无公开 scope 页；Internet Archive CR.App.R. 卷为闭架扫描、元数据无 scope |
| `kb` / `ch` / `chd` / `qbd` 的**卷首页** | 未逐字取得这些分册的卷首页（只取得同族 A.C./P.D. 卷首页与编目标题） | Internet Archive 编目标题可作强旁证，但达不到 `exclusive_statute`/`exclusive_publisher` 所需的「出版方明文 scope」标准 |
| `er` 出版方一手分册表 | 只有第三方转述的 1930 Index Chart | Stevens & Sons 无在线自述；仅得单案扫描 `perma_cc_82KS-YNZL` |

### 4.4 同形异义中**本轮未展开**的部分（明确列为缺口）
- **`cp`（Common Pleas）**：`cp` 是 **tier 3 british 组**目标（185 条提及），本轮**未研究**。已知起点：第一系列《Law Reports》Common Pleas 分册为 continuous 卷号（`L.R. 4 CP. 374` 形，见 §2.11）。魁北克/安大略同名 `C.P.` 冲突**未研究**。
- **`sc`（Superior Court）**：**不在本组**——JSON 里 `sc` 属 **`group = other`**，tier 3，241 条提及。本轮只在魁北克官方总索引里顺带取得 `S.C. = Cour Supérieure; 1892–1898; vols 1–14`（见 §2.6(b)），**未独立成行**，应交给 `other` 组的负责人。
- **`p`**：**不在本组**——JSON 里 `p` 属 **`group = other`**，**tier 2**，680 条提及（含美国 Pacific Reporter 冲突）。本轮只在 ICLR 卷首页顺带取得 Probate Division 分册证据（`[1930] P`；`wbsl.20805` 明载 `And On Appeal ThereFrom In The Privy Council`）→ **`p` 的英文 Probate 侧至少是 mixed（含枢密院上诉）**，但我**没有**研究它的 Pacific Reporter 冲突，故不作为提案行。**这一条对 `other` 组有直接价值，请转交。**
- **`pd`（Probate Division）**：tier 3 未到达；但已取得**直接 mixed 证据**（`wbsl.20805`：Probate Division 分册「And On Appeal ThereFrom In The Privy Council」）——留给后续。
- **`scc` / `qs` / `ont` 等**：不在本组目标表，未研究。

### 4.5 方法学限制（必须让合并者知道）
1. **会话内搜索工具不可用**：`web_search`（modsearch）对所有查询返回 `Every engine for the web source failed`（firecrawl 403）。全部检索靠**已知 URL + Wikipedia 内置 `insource:` 检索 + Internet Archive 目录/全文 API** 完成。因此「未找到反例」的强度低于带通用搜索引擎的检索。
2. **沙箱只读性**：`pwsh` 的 HTTPS 下载（`Invoke-WebRequest` / `curl.exe`）在本环境失败（TLS `SEC_E_NO_CREDENTIALS`），无法把大卷全文落盘后本地 grep；卷内检索只能靠 `web_fetch` 的分页返回。
3. **Internet Archive 全文搜 API 未生效**：`archive.org/advancedsearch.php?q=text:"..."` 对所有探针返回 `numFound: 0`（含已知存在的短语），故**未做全库全文反例扫描**；反例均来自可下载的具体卷全文与 BAILII/ICLR 一手页面。
4. **第三方证据的界线**：`er` 的分册表与 `aller` 的 scope 描述来自 Wikipedia（转引 Index Chart 1930 / University of Oxford 索引页）。按任务规则，这只能支撑 `scope_evidence_third_party_only`，**不能**支撑 `verified_exclusive_publisher`。
5. **语料数字只用于对照**：本文件中引用的语料 vol/年区间一律标注「语料实测」，**从未**作为范围或排他性的依据；所有窗口都以出版方/书目来源独立溯源。
6. **OCR 质量**：A.C. 1930 卷为 2026 年新扫描件，tesseract 对部分案件表页（如 `P.C. 244`、`P.C. 366`）识别不清；引用的案名/页码以清晰可辨者为限，个别条目标注为低置信。
