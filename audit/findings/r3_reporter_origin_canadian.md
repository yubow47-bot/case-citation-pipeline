# R3 加拿大商业/省级汇编：来源地排他性溯源（提案）

产出者：R3 委派研究代理（**提案，不是数据**）。写入日期：2026-09-13（全部取用日期统一标 `2026-09-13`）。
目标清单：`audit/findings/r3_stage1_targets_canadian.md` / `.json`（`group == "canadian"`）。
只读约束遵守：未改动 `decisions/`、`pipeline/` 或任何其他文件；本文件是唯一产出。
禁止用作证据的：本仓库语料、分类层输出、`decisions/reporter_jurisdiction.csv`、`PROBLEMS.md`。**均未使用。**

> **本轮最重要的结论（读这三条就够）**
> 1. **`D.L.R.` 不是排他汇编——它是明文的全国混合汇编。** 出版方自己的卷内题名页写死：「comprising every case reported in the courts of **every province**, and also all the cases decided in the Supreme Court of Canada, Exchequer Court, the Railway Commission, and the **Canadian cases appealed to the Privy Council**」（Canadiana 扫描件 oocihm.83107 书目转录的题名页原文）。反例已坐实：`Ford v. Quebec (AG), 54 D.L.R. (4th) 577`（Quebec 来源地）。**任何把 `dlr` 写成 CA 单一来源地的规则都会做错 9,148 个净新增组里最大的一块。**
> 2. **`C.C.C.` 也是明文的全国混合汇编。** 其题名页原文：「in criminal and quasi-criminal cases **in Canada** under the laws of the Dominion and of the provinces thereof, with special reference to decisions under the Criminal Code of Canada, 1892, **in all the provinces**」。
> 3. **可写（exclusive_statute）的最强一笔是魁北克官方汇编**，因为它的排他性是**法条**而非出版方自述：Loi sur la Société québécoise d'information juridique（RLRQ c. S-20）**s.21** 把出版物范围钉死为「les jugements rendus par les tribunaux judiciaires **siégeant au Québec**」。配合 S-20 r.1 与 SOQUIJ 自己的系列表，`rjq`（R.J.Q. 1986–2013）是干净的可写行。

---

## 1. 总表（每个到达的目标一行）

| # | abbr | 是什么 | 排他性判定 | 证据类别 | 独立溯源窗口（vol / 年） | 反例搜寻结果 |
|---:|---|---|---|---|---|---|
| 1 | `dlr` | Dominion Law Reports（Canada Law Book / Thomson Reuters 1912–） | **mixed** | 出版方卷内题名页（一手） | 卷 1–70（1912–1922）；1923–1955 按年卷；2d 1–70（1956–1968）；3d 1–150（1969–1984）；4th 1–（1984–） | **命中**：Quebec 来源地案被收（Ford 1988 = 54 D.L.R. (4th) 577） |
| 2 | `ccc` | Canadian Criminal Cases（Canada Law Book 1898–） | **mixed** | 出版方卷内题名页（一手） | 卷 1–（1898–） | **命中**：「in all the provinces」为明文自述；另 Slaw 记其对 Quebec 采选偏弱 |
| 3 | `or` | Ontario Reports（Law Society of Ontario 经 LexisNexis） | **exclusive_publisher** | LexisNexis 产品页自述（一手） | 3d 1991–；2d 1974–1991；1931–1973 同名；1882–1901 为分庭题名 | 未命中（查 CanLII/法院引用指南/期刊引用）；记载见 §2.3 |
| 4 | `wwr` | Western Weekly Reports（Burroughs→Carswell 1911–） | **exclusive_publisher** | 出版方卷内题名短语（经书目转录） | 年 1911– | 未命中；但上院/枢密院上诉的**来源地锚定**存在歧义（见 §2.4） |
| 5 | `ar` | Alberta Reports（Maritime Law Book 1976–） | **exclusive_publisher** | 出版方产品名 + MLB 自述 | 年 1976– | 未命中 |
| 6 | `altalr` | Alberta Law Reports（Carswell / Thomson Reuters） | **exclusive_publisher** | 出版方卷内题名页（一手） | 5th/6th 卷号体系；年 1908–1932/33 + 1977– | 未命中 |
| 7 | `excr` | Exchequer Court Reports（法院 Registrar 授权出版） | **exclusive_statute**（边缘） | 政府出版物卷首 + 法院设立法 | 年 1875–1970（1877–1970 为语料实测） | 未命中（该院对全国的排他管辖权本身排除他院） |
| 8 | `rjq` | Recueil de jurisprudence du Québec（SOQUIJ 1986–2013） | **exclusive_statute** | **法条** S-20 s.21 + SOQUIJ 系列表 | 年 1986–2013 | 未命中 |
| 9 | `manr` | Manitoba Reports (2d)（Maritime Law Book 1979–） | **exclusive_publisher** | 出版方自述（Slaw 转录 MLB 文稿） | 年 1979– | 未命中 |
| 10 | `saskr` | Saskatchewan Reports（Maritime Law Book 1979/80–） | **exclusive_publisher** | 出版方自述 | 年 1979– | 未命中 |
| 11 | `nsr` | Nova Scotia Reports / (2d)（Maritime Law Book） | **exclusive_publisher** | 出版方自述 | 1965–1969 + 1970– | 未命中 |
| 12 | `nbr` | New Brunswick Reports (2d)（Maritime Law Book 1969–） | **exclusive_publisher** | 出版方自述 | 年 1969– | 未命中 |
| 13 | `bclr` | British Columbia Law Reports（Carswell） | **exclusive_publisher** | 出版方被引用的范围短语（二手转录） | 年 1977–（1st 另有 1893–94） | 未命中 |
| 14 | `nr` | National Reporter（Maritime Law Book 1974–） | **exclusive_publisher** | MLB 数据库自述 | 年 1974– | 未命中 |
| 15 | `crr` | Canadian Rights Reporter（Butterworths/LexisNexis 1982–） | **mixed** | 第三方馆藏描述 | 年 1982–（2d 另起） | **命中**：Charter 案跨联邦与各省 → 非单一来源地 |
| 16 | `rfl` | Reports of Family Law（Carswell 1970–） | **mixed** | 出版方数据库自述 + CanLII 收录分布 | 年 1970– | **命中**：跨法域（Ontario 1,900 / Manitoba / BC 均有） |
| 17 | `cbr` | Canadian Bankruptcy Reports（Carswell 1920–） | **scope_evidence_third_party_only** | 仅第三方（UNB 馆藏表） | 年 1920–（未核实） | 未做（缺可写证据） |
| 18 | `bcac` | British Columbia Appeal Cases（Maritime Law Book 1994–） | **scope_evidence_third_party_only** | 仅第三方（ICLL 期刊表；非产品出版方） | 卷 38–（1994–）；1–37（1991–94）另考 | 未做（缺可写证据） |
| 19 | `oac` | Ontario Appeal Cases（Maritime Law Book 1984–） | **scope_evidence_third_party_only** | 仅第三方（ICLL；约克/TRU 馆藏） | 年 1984– | 未做（缺可写证据） |
| 20 | `olr` | Ontario Law Reports（Canada Law Book 1901–1931） | **scope_evidence_third_party_only** | 仅第三方（Osgoode 数字化题名） | 卷 1–66（1901–1931） | 未做（缺可写证据） |
| 21 | `ontlr` | （`ontlr`？）Ontario 省级汇编族；**缩写未定** | **scope_evidence_third_party_only** | 仅第三方 | 未定 | 未做 |
| 22 | `bcj` | **不是汇编**：Quicklaw「British Columbia Judgments」（+Yukon）数据库标识符 | **not_a_reporter** | 联邦司法部缩写表（一手官方） | 数据库覆盖年 1867– | 不适用 |
| 23 | `fcj` | **不是汇编**：Federal Court Judgments（Quicklaw 数据库标识符） | **not_a_reporter** | 同族标识符（与 `bcj` 同源） | — | 不适用 |
| 24 | — | 其余 8 个目标（`qr.kb` `queqb` `ucqb` `mpr` `cpc` `bcac` 双形等） | **未到达**（见 §4） | — | — | — |

---

## 2. 逐目标详情（引文 + URL + 取用日期 + 反例搜寻记录）

### 2.1 `dlr` = Dominion Law Reports —— **mixed**（本轮最重要的一行）

**它是什么**：Canada Law Book（1912 年创刊；2010 年随 Canada Law Book 并入 Thomson Reuters）出版的**全国性**通用判例汇编。

**书面证据（出版方卷内题名页，一手；书目记录逐字转录）**——Canadiana（加拿大国家图书档案馆 LAC 的数字化平台）CIHM 号 83107、83127、83135 等系列的 `Title` 字段一致：

> `Dominion law reports : cited "D.L.R." : comprising every case reported in the courts of every province, and also all the cases decided in the Supreme Court of Canada, Exchequer Court, the Railway Commission, and the Canadian cases appealed to the Privy Council`

（Vol. 32 = 83107；Vol. 45 = 83120；Vol. 50 = 83125；Vol. 52 = 83127；Vol. 60 = 83135；Vol. 7/10 等同一题名。1912 创刊卷的等价表述见 1913 年 Vol. 7 记录：「a new annotated series of reports comprising every case reported in the courts of every province ... together with Canadian cases appealed to the Privy Council」。）

来源：Canadiana（Library and Archives Canada / Canadiana.org 数字化题名页转录），
`https://www.canadiana.ca/view/oocihm.83107`（及 `oocihm.83127`、`oocihm.83135`、`oocihm.83120`）（取用 2026-09-13）。

**为什么这不是 exclusive**：题名页自己写「every province」（魁北克也是 province）以及「Canadian cases appealed to the Privy Council」——**枢密院对加拿大上诉的来源地是各省，不是加拿大这个国家**（这正是本项目 `case_origin.csv` 203 行注入的语义）。所以它同时覆盖 ON/QC/BC/AB/... 多个 subdivision，属于典型 mixed。

**反例搜寻（命中）**：
- 检索路径 A：`Ford v. Quebec (Attorney General)` 的 D.L.R. 平行引注。多篇美国/加拿大法学论文写明 `54 D.L.R.4th 577 (1988) (Can.)` 与 `Ford, 54 D.L.R.4th at 596`——Ford 是 **Quebec 来源地**（Quebec 招牌法/Charter 案）。来源：*The American Judicial Review Quagmire: A Canadian Proposal*（Indiana Law Journal PDF，脚注 48–50），`https://www.repository.law.indiana.edu/cgi/viewcontent.cgi?article=1569&context=ilj`（取用 2026-09-13）。
- 检索路径 B：`Alliance des professeurs de Montréal v. Attorney-General of Que., 21 D.L.R.4th 354 (Que. C.A. 1985)`——同一 PDF 脚注 24 及 46，明确标 `(Que. C.A.)`。
- 检索路径 C：`R. v. Rahard (1935), [1936] 3 D.L.R. 230 (Can. Que. Ct. Sess.)`——Drexel Law Review 论文脚注 49，同时标 D.L.R. 与 Quebec 法院。
- **结论**：三条独立路径均命中 Quebec 来源地案件印在 D.L.R.，出版方题名页亦自述覆盖 every province。`dlr` = `mixed`，**不得写 origin 行**。

**卷/年体系与系列断点（供 Stage 3）**：`continuous`（卷号跨年连续），但 **1923–1955 一段是例外**（按年卷，引注作 `[1923] 2 D.L.R. 485`）；且 3d→4th 断点在 **1984**（year 1984 同时可能出现 3d 卷 150 与 4th 卷 1，是本项目最易误判的一处）。
- 断点表来源（第三方，仅作窗口/断点，不作范围证据）：Bluebook T2.6 Canada（`https://www.legalbluebook.com/bluebook/v21/tables/t2-foreign-jurisdictions/t2-6-canada`）；lawi.ca（Encyclopedia of Canadian Laws）系列表；Bodleian Law Library 博客列出各系列卷数（Old 1–70 / New 1–133 / 2d 1–70 / 3d 1–150 / 4th 1–）：`https://blogs.bodleian.ox.ac.uk/lawbod/2014/06/13/dominion-law-reports-online/`（均取用 2026-09-13）。
- 出版方（Thomson Reuters）产品页只证明它是 Canada Law Book 的 Law Report 之一，**不含范围语**：`https://store.thomsonreuters.ca/en-ca/ereports`（取用 2026-09-13）。

### 2.2 `ccc` = Canadian Criminal Cases —— **mixed**

**书面证据（出版方卷内题名页，一手；Canadiana 书目转录）**：

> `Canadian criminal cases annotated : A series of reports of important decisions in criminal and quasi-criminal cases in Canada under the laws of the Dominion and of the provinces thereof, with special reference to decisions under the Criminal Code of Canada, 1892, in all the provinces; with annotations, a table of cases cited and a digest of the principal matters.`

来源：Canadiana，`https://www.canadiana.ca/view/oocihm.8_02258`（卷 I 1898 – 卷 III 1900；出版者 Canada Law Journal Company → Canada Law Book Company；取用 2026-09-13）。同一题名的第三方重印本转录（Forgotten Books / ZVAB 书商）逐字一致：`https://www.zvab.com/9780266835530/Canadian-Criminal-Cases-Annotated-Vol-0266835538/plp`（取用 2026-09-13）。

**排他性判定**：「in all the provinces」为明文自述 → 跨 subdivision 混合。另有一层：**它对 Quebec 的采选显著偏弱**——Slaw 的出版史评论（Simon Chester 栏，2010-09-19）：「Over time, they came to be seen as the law report series for the criminal defence bar, with a focus of English language cases decided in the common law provinces of Canada. ... The CCCs greatest weakness was its comparative neglect of Quebec cases.」来源：`https://www.slaw.ca/2010/09/19/cr-ccc-crcc/`（取用 2026-09-13）。**注意：这是第三方评论，不作为范围证据，只作为「排除不了」的补充说明。**

**覆盖窗口（出版方，一手）**：Thomson Reuters CriminalSource 宣传册与官方产品页均称「The complete collection of the Canadian Criminal Cases back to **1898** and ongoing」。
来源：`https://www.thomsonreuters.ca/content/dam/ewp-m/documents/canada/en/pdf/brochures/westlaw/criminal-source-brochure-online.pdf` 与 `https://www.thomsonreuters.ca/en/westlaw-canada/products.html`（取用 2026-09-13）。
⚠️ 这是**覆盖**（coverage）而非**范围**（scope）声明——它不说「只收哪一来源地」，所以不能升级为排他证据。

**卷/年体系**：`continuous`（卷号跨年连续，语料实测卷 1–2008 与 1894–2019 年窗口吻合）。

**反例搜寻**：题名页「in all the provinces」本身即反例级自述；另检索 CCC 是否印过非加拿大材料（比较法重印、英国案）——未找到 CCC 印英国/外国判决的证据（检索词见 §3）。**未命中「非加拿大材料」型反例，但「跨省」型反例已由出版方自述坐实。**

### 2.3 `or` = Ontario Reports —— **exclusive_publisher**（可写）

**书面证据（出版方自己的产品页，一手）**——LexisNexis Canada 官方产品页，逐字：

> `Published by the Law Society of Ontario through LexisNexis Canada, Ontario Reports, Third Series provides, in full text, leading cases decided at all levels of Ontario courts. At least one case per month is presented in both French and English.`

同页另有：「Steeped in tradition, *Ontario Reports*, provides leading cases at all levels of the Ontario courts and weekly notices.」
来源：`https://www.lexisnexis.com/en-ca/products/ontario-reports`（HTTP 200，正文已取回；取用 2026-09-13）。同文另见 `https://www.lexisnexis.ca/en-ca/products/ontario-reports.page`。

**"all levels of Ontario courts" 的含义**：Ontario 的法院层级（Court of Appeal for Ontario / Superior Court of Justice / Ontario Court of Justice）全部**只审理来源地为 Ontario 的案件**；因此「Ontario 各级法院判决」≡「来源地 ON」。这条推理是本行可写性的关键：范围语锚定的是**法院**，而该法院群的来源地是排他 ON。

**系列与期间（供 Stage 3 的窗口）**：
- 3d：**1991–**（本行的可写窗口来源，见上引产品页「Third Series」）
- 2d：**1974–1991**；1931–1973 同名 O.R.；**1882–1901** 为分庭题名（O.R. 第 1 系列）。
- 断点来源（第三方，仅作窗口）：Bluebook T2.6 Canada 分省表逐行 `Ontario Reports | 1882–1901`、`*Ontario Reports | 1931–1973`、`*Ontario Reports (2d) | 1974–1991`、`*Ontario Reports (3d) | 1991–date`；`https://www.legalbluebook.com/bluebook/v21/tables/t2-foreign-jurisdictions/t2-6-canada`（取用 2026-09-13）。另有 NZ Law Foundation 附录（第三方）：`OR (2d) 1973–1990 / OR (3d) 1991–`，`https://lawfoundation.org.nz/style-guide2018/appendix-3.html`（取用 2026-09-13）。两源在 2d 起点上差一年（1973 vs 1974），**本文件取 Bluebook 的 1974，并标「未完全核实」**。
- 第 1 系列（1882–1900/01）的题名页是一手实物证据，但**出版方不是 Law Society**（Rowsell & Hutchison / Canada Law Book）：`The Ontario reports : containing reports of cases decided in the Queen's Bench and Chancery divisions of the High Court of Justice for Ontario`（Canadiana `https://www.canadiana.ca/view/oocihm.8_01894`；Osgoode `https://digitalcommons.osgoode.yorku.ca/lawreports/10`）。**故 1882–1900 段不能用 LexisNexis 那句话背书**，需另行溯源（见 §4）。

**关于法条依据**：LSO **By-Law 13「REPORTING OF COURT DECISIONS」** 确有「ONTARIO REPORTS」一节，但其条文只规定**分发**（向执照持有人提供副本）、**广告**（广告须与正文完全分离）及其他报告，「未」规定汇编的**刊登范围**。因此 Ontario 侧**没有**可用的法条依据 —— **本行的可写性来自出版方产品页，不是法条**（与魁北克相反）。
来源：`https://lso.ca/about-lso/legislation-rules/by-laws/by-law-13`（★**注意：直接抓取被 CloudFront 403 拦截**；条文文本来自搜索引擎对同一 URL 的正文抽取，故本行标记为「二级取回」，复核时请以浏览器直开该 URL 核对）。

**反例搜寻（未命中，记录检索过的来源）**：
- 检索 A：Ontario Court of Appeal 官方《Reference Guide for Citation Practices》`https://www.ontariocourts.ca/coa/files/rules-forms/citation-practices-EN.pdf` —— 该指南把 O.R. 与 D.L.R.、S.C.R. 并列为「Official and semi-official reporters」，示例 `1234 Inc. v. 7891 Ltd. (2013), 62 O.R. (3d) 123 (S.C.)` 均为 Ontario 法院；**未发现任何「非 Ontario 来源地案件印在 O.R.」的示例**。
- 检索 B：CanLII 的 O.R. 平行引注（如 `MacKinnon v. National Money Mart Co., 2004 BCCA 473, 50 B.L.R. (3d) 291` 型页面）——未找到 O.R. 承载他省案件的实例。
- 检索 C：查询 `Ontario Reports contains Supreme Court of Canada decision reported O.R. federal court case` 与 `"O.R." citation non-Ontario court` —— 未返回任何具体反例。
- **诚实声明**：以上是**未找到反例**，不是「已证明不存在」。若要升级为更硬的行，建议补一件实物：任一卷 O.R. (3d) 的卷首 `TABLE OF CASES REPORTED` 逐条核对法院标注。

### 2.4 `wwr` = Western Weekly Reports —— **exclusive_publisher**（可写，但有一处必须在 notes 里写明的歧义）

**书面证据（出版方卷内题名/范围短语，经 HathiTrust 书目转录）**——逐字：

> `Vols. for 1921- : "All cases of value in Western Canada from the Judicial Committee of the Privy Council, the Supreme Court of Canada, and the courts of Alberta, British Columbia, Manitoba and Saskatchewan"; vols. for 1971- include appeals to the Federal Court of Canada.`

来源：HathiTrust 书目记录（University of Michigan 藏本，`coo.31924065712675` / handle `http://hdl.handle.net/2027/coo.31924065712675`）（取用 2026-09-13）。★**抓取说明**：`babel.hathitrust.org` 对本会话返回 403（Cloudflare），故该引文来自同一 URL 的搜索引擎正文抽取（`https://babel.hathitrust.org/cgi/pt?id=coo.31924065712675`）。**这是一手出版方的卷内短语，但本轮是二级取回**，复核时请直开核对。

**独立佐证（第三方学术史，逐字）**：

> `Burroughs began publication of W.W.R. in November 1911 in Calgary. The series contained judgments delivered by and originating in the courts of British Columbia, Alberta, Saskatchewan, and Manitoba, including appeals to the Supreme Court of Canada and the Privy Council.`

来源：*Prairie quires: the history of law reporting in Manitoba and Saskatchewan*（Canadian Law Libraries, vol. 18, 1993；HeinOnline 全文），`http://heinonline.org/HOL/Page?collection=journals&handle=hein.journals%2Fcallb18`（取用 2026-09-13）。**第三方，单独不足以支撑可写行；与上面的出版方短语合用构成交叉印证。**

**为什么可写**：措辞把范围锚在**地理**（Western Canada = BC/AB/SK/MB）而非法院层级，且上院/枢密院/联邦法院上诉被表述为「来自 Western Canada 的」。因此 origin_subdivision ∈ {BC; AB; SK; MB}。

**必须在 notes 里写明的歧义（不许掩盖）**：上面的措辞有两种读法——(a)「来自西部四省的上院/枢密院/联邦法院上诉」；(b)「上院/枢密院/联邦法院的全部相关判决（不限来源省）」。另有一条第三方表述更宽：Manitoba Law Library Inc. 的博客称 WWR 是「a collection of significant cases from courts in the **western provinces**」而第三方检索摘要出现过「Western provinces **and the Territories**」（USask 馆页）。**若 (b) 成立，WWR 就含有 Ontario/Quebec 来源地的 SCC 案 → 应降级为 mixed。** 本轮未能取得卷首 `TABLE OF CASES REPORTED` 实物来判定，故按 (a) 记 `exclusive_publisher`，并在 notes 里把风险交回给复核人。

**卷/年体系**：**`year_volume` 的历史事实 + 语料呈现连续卷号**。HathiTrust 同记录另载：「Vols. for 1911-Sept. 1916 called v.1-10. **Numbering begins each year with v.1, 1917-1965**. Some years issued in 2-3 volumes. First series ceased with issue Dec. 30, 1950. New series published from 1951-1970.」（同 URL）——即 **1917–1965 为 year_volume**，而语料实测卷 1–75 与引注形如 `[1984] 4 W.W.R. 706`（年+年内卷号+页）也印证 year_volume。**本行按 `year_volume` 记**，并在 notes 保留 1911–1916 连续卷号与 1951–1970「New series」两个例外段。

**反例搜寻（未命中「非西部来源地」）**：
- 检索 A：`"W.W.R." citation "(Man. C.A.)" OR "(Alta. C.A.)" OR "(B.C.C.A.)"` → 命中的全是西部来源地，且与西部平行引注（A.R. / B.C.L.R. / Man. R.）成对出现，如 `Westfair Foods Ltd. v. Watt, [1991] 4 W.W.R. 695; 115 A.R. 34 (Alta. C.A.)`、`Re Western Grocers Ltd., [1936] 2 W.W.R. 81 (Man. Q.B.)`、`R. v. Colvin, [1942] 3 W.W.R. 465 ... (B.C. C.A.)`（vLex 判例页）。
- 检索 B：`"W.W.R." citation "(Ont. C.A.)" OR "(Que. C.A.)"` → **未返回任何 Ontario/Quebec 来源地案印在 W.W.R. 的实例**。
- 检索 C：`"W.W.R." citation Supreme Court of Canada case originating Ontario OR Quebec` → 未命中。
- 检索 D：**反向陷阱检查（非加拿大材料）**：W.W.R. 是 Burroughs/Carswell 的加拿大西部汇编，其上院/枢密院卷段理论上可能含英国上院案；本轮**未找到** W.W.R. 印非加拿大判决的证据，但**也未能取得卷首实物排除**——这一点与上面的 (a)/(b) 歧义是同一个缺口。

### 2.5 `ar` = Alberta Reports（Maritime Law Book）—— **exclusive_publisher**

**书面证据（出版方自述，经第三方转录，逐字）**：Maritime Law Book 的 National Reporter System 自述（2004-06-23 快照，由 CanadaLegal.info 图书馆页逐字转录）：

> `"... providing access to Canadian case law since 1969 MLB publishes 14 law reporters that cover every jurisdiction in Canada, except Quebec."`
> `The National Reporter System (NRS) includes the following databases ... - Alberta Reports - 1976 to present ...`

来源（转录）：`https://www.canadalegal.info/ref-library/index.html`（页面注明「above data base info quoted fr. www.mlb.nb.ca 040623」，即 2004-06-23 的原出版方网站内容）（取用 2026-09-13）。
**判别依据**：`ar` 被列为 **Alberta** 专用汇编之一（MLB 在 Quebec 以外每省一本），故汇编本身即 Alberta 省的排他容器。名称与「Alberta Reports / A.R.」的对应见 Bluebook T2.6（`Alberta Reports | 1977–date | A.R.`）与 vLex 判例页的 `MLB headnote and full text` + `(1994), 157 A.R. 241 (CA)` 组合（后者同时证明 A.R. 由 MLB 出版）。

**覆盖窗口**：**年 1976–**（出版方自述起点 1976；外部转述偶作 1977/1978，见 §4）。★**语料实测年下限 1880 与卷上限 1991 是解析噪声/他形混入**，不得作为窗口依据；年窗 1976 起可把这些挡在窗外。

**卷/年体系**：`continuous`（引注 `(1994), 157 A.R. 241` 用括号年、卷号跨年 → 连续卷）。

**反例搜寻（未命中）**：检索 `"Alberta Reports" Maritime Law Book "Court of Appeal of Alberta" description scope`、`(2013), 566 A.R. 105` 型 vLex 记录的 `Jurisdiction: Alberta` 字段——所查各页均标 Alberta；**未找到任何非 Alberta 来源地案件印在 A.R. 的实例**。

### 2.6 `altalr` = Alberta Law Reports（Carswell / Thomson Reuters）—— **exclusive_publisher**

**书面证据（出版方卷内题名页，一手，逐字）**——Carswell（Thomson Reuters Canada）出版的 Alberta Law Reports 第 5/6 系列卷首：

> `ALBERTA LAW REPORTS Fifth Series Reports of Selected Cases from the Courts of Alberta and Appeals`
> `VOLUME 53 (Cited 53 Alta. L.R. (5th))` … `CARSWELL, A DIVISION OF THOMSON REUTERS CANADA LIMITED`

同族 6th 系列同题名：`ALBERTA LAW REPORTS Sixth Series Reports of Selected Cases from the Courts of Alberta and Appeals VOLUME 34 (Cited 34 Alta. L.R. (6th))`。
来源：卷首页扫描转录 `https://docslib.org/doc/5353162/alberta-law-reports-fifth-series-reports-of-selected-cases-from-the-courts-of-alberta-and-appeals` 与 `https://docslib.org/doc/4292438/western-weekly-reports`（后者含 6th 系列卷首）（取用 2026-09-13）。★**取回方式说明**：出版方卷首实物的一手文本，经第三方扫描站转录；复核时建议以任一 Alta. L.R. (5th/6th) 纸本或 Westlaw 卷首核对。

**为什么可写**：「Cases from the **Courts of Alberta** and Appeals」——范围锚在 Alberta 法院群（含其判决被上诉的情形）。「Selected」只影响**哪些** Alberta 案入选，不影响**来源地**。

**覆盖窗口**：Bluebook T2.6 分省表（第三方）：`*Alberta Law Reports | 1908–1932/1933 | Alta. L.R.`；`Alberta Law Reports (2d) | 1977–1992`；`(3d) | 1992–2002`；`(4th) | 2002–date`（同 URL，取用 2026-09-13）。★与语料实测（年 1908–2019）大体吻合，但 **1933–1977 的断档未解释**（2d 起点 1977 vs 语料/其他源偶作 1977/1982）——**窗口标「未完全核实」**。

**反例搜寻（未命中）**：卷首题名页本身排除他省来源地；另查 Alta. L.R. 是否印过联邦法院/他省案——未找到实例。

### 2.7 `excr` = Exchequer Court Reports —— **exclusive_statute**（边缘：以法院设立法 + 政府出版物为依据）

**书面证据（法院授权出版的卷首，一手，逐字）**：

> `REPORTS OF THE EXCHEQUER COURT OF CANADA / PUBLISHED UNDER AUTHORITY BY THE REGISTRAR OF THE COURT / VOL. 16. / CANADA LAW BOOK CO., LIMITED TORONTO, CANADA 1918`

另一卷另有 `ARNOLD W. DUCLOS, K.C. OFFICIAL LAW REPORTER / PUBLISHED UNDER AUTHORITY BY REGISTRAR OF THE COURT`。
来源：加拿大政府出版物数字化（Office of the Commissioner for Federal Judicial Affairs / publications.gc.ca）：`https://publications.gc.ca/collections/collection_2020/cmf-fja/JU1-2-1-16-eng.pdf`（Vol. 16）与 `https://publications.gc.ca/collections/collection_2020/cmf-fja/JU1-2-1-20-eng.pdf`（另一卷）（取用 2026-09-13）。

**法定基础（"Binding" 的一侧）**：Exchequer Court of Canada 是**单一联邦法院**，其管辖为加拿大全国范围的特定联邦事项；该汇编是**该法院自己的官方报告**（「by the Registrar of the Court」）。因此「汇编范围 = 该法院判决」≡ 来源地 = 加拿大（联邦法院）。★**诚实标注**：本轮**未取得**设立该院的成文法条文（Exchequer Court Act）中的「报告出版」条款，也未取得现行 Federal Courts Act s.58 对该院历史卷的覆盖；**严格说本行的法定文本链不完整**。可写性主要靠「政府出版物卷首 + 单一法院机构」两点；若复核要求与 S.C.R./F.C. 同级的 statute 明文，本行应降级为 `exclusive_publisher`（出版方＝法院自身）。

**覆盖窗口**：语料实测 1877–1994；Bluebook/Federal Judicial Affairs 记 1877–1970（该院 1971 年被联邦法院取代）；UNB/Melbourne 两馆记 1875/1877–1970。**取 1877–1970 为窗口**（列 Bluebook 与 Government of Canada 数字化的重合段），并在 notes 标 1875–1877 的馆藏分歧。

**反例搜寻（未命中）**：检索 `"Exchequer Court Reports" published under authority registrar`、`Exchequer Court Reports non-Canadian case` —— 未找到该刊印非该院判决的证据（该院对全国的排他管辖本身使其不可能印他院判决）。

### 2.8 `rjq` = Recueil de jurisprudence du Québec —— **exclusive_statute**（本类里最硬的一行）

**法条文本（一手，逐字）**——Loi sur la Société québécoise d'information juridique（RLRQ c. S-20）**s.21**：

> `21. La Société collabore avec l'Éditeur officiel du Québec à la publication des jugements rendus par les tribunaux judiciaires siégeant au Québec et des décisions rendues par les personnes ou les organismes y exerçant des fonctions juridictionnelles.`
> `La Société établit par règlement les modalités de la cueillette de ces jugements et décisions ainsi que les critères relatifs à la sélection de ceux et celles à rapporter et à la façon dont ils doivent l'être.`
> `La Société rend ce règlement public.` — `1975, c. 12, a. 2; 1997, c. 43, a. 764.`

来源：Légis Québec（魁北克政府官方立法数据库），`https://www.legisquebec.gouv.qc.ca/fr/document/lc/s-20`（及 `https://www.legisquebec.gouv.qc.ca/fr/document/lc/S-20?cible=`）（取用 2026-09-13）。★**抓取说明**：`legisquebec.gouv.qc.ca` 对本会话直接抓取返回 **403（CloudFront）**；s.21 文本来自搜索引擎对同一 URL 的正文抽取，**逐字与两个独立 URL 一致**。复核时请以浏览器直开核对（这是本文件最该被复核的一条）。

**配套规章（一手）**——S-20, r. 1《Règlement sur la cueillette et la sélection des décisions judiciaires》：

> `1. Les greffiers des tribunaux judiciaires du Québec expédient à la Société québécoise d'information juridique une copie de toutes les décisions judiciaires motivées. ...`
> `2. La Société prend connaissance de ces décisions et les sélectionne en vue de leur intégration dans ses divers produits.`
> `3. Une décision peut être sélectionnée si elle contient un des éléments suivants ... 1° un point de droit nouveau; 2° une orientation jurisprudentielle nouvelle; 3° des faits inusités; 4° une information documentaire substantielle; 5° une problématique sociale particulière.`

来源：`https://www.legisquebec.gouv.qc.ca/fr/document/rc/S-20,%20r.%201`（及 `.../fr/ShowDoc/cr/S-20,%20r.%201%20/`）（取用 2026-09-13；同样为 403 + 正文抽取）。
**意义**：**全部**魁北克司法法院的有理由判决都送交 SOQUIJ（s.1），SOQUIJ 再**按五个法律标准筛选**（s.3）。因此：汇编的**来源地**被法条钉死为「siégeant au Québec」；筛选只决定**哪些**魁北克案入选，不影响来源地。

**R.J.Q. 的产品范围与期间（出版方自己的产品表，一手）**——SOQUIJ 帮助中心《Tableau des recueils jurisprudentiels publiés par SOQUIJ》：

> `| R.J.Q. 1986 à 2013 | Recueil de jurisprudence du Québec |`

同表并列各主题/专门汇编（R.D.I. 1986–2010、R.D.F.Q. 1977–2010、R.J.D.T. 1998–2013 等）。
来源：`https://aide.soquij.qc.ca/s/article/tableau-recueils-jurisprudentiels-publies-par-SOQUIJ`（取用 2026-09-13）。

**谱系（出版方自己的博客，一手）**——SOQUIJ 官方博客逐字：

> `«Constitué en mai 1974, le Service des publications de SOQUIJ s'était vu confier le mandat d'assurer la relève de la préparation des recueils de jurisprudence de la Cour supérieure et de la Cour d'Appel, assumée par le Barreau du Québec depuis 1892. Il devait également permettre la publication d'un nouveau recueil de jurisprudence rendant compte de jugements émanant de la Cour provinciale, de la Cour des Sessions de la paix et de la Cour de Bien-être social du Québec.»`
> `Avec l'abonnement collectif du Barreau du Québec instauré en 1986, ... SOQUIJ a alors «réuni dans un même recueil de dix fascicules les jugements de la Cour d'appel, de la Cour supérieure, de la Cour provinciale, de la Cour des Sessions de la paix et du Tribunal de la jeunesse. ...» C'est ainsi que le Recueil de jurisprudence du Québec (R.J.Q.) est né.`

来源：`https://blogue.soquij.qc.ca/2016/05/10/retour-sur-les-recueils/`（取用 2026-09-13）。
**意义**：R.J.Q. 是**五类魁北克法院判决合为一体的单一汇编**（Cour d'appel + Cour supérieure + Cour provinciale + Cour des Sessions de la paix + Tribunal de la jeunesse）——五种法院全部「siégeant au Québec」，故仍是排他 QC。

**本行的窗口（请复核人重点看这一格）**：`year_range_start=1986`、`year_range_end=2013`。**依据是 SOQUIJ 自己的产品表**（1986 年起的集体订阅改革创建一个新汇编 = R.J.Q.；表中止于 2013）。
⚠️ **风险披露**：表中止于 2013 可能只反映**纸质版**终止（SOQUIJ 之后转线上），不代表引注 `R.J.Q. 2014` 不存在。**本行按可溯源的表值写 2013，并在 notes 明确标注「若复核发现 R.J.Q. 延续至 2013 之后，把 year_range_end 留空（开放上界）」**。这是本轮最可能被修正的一格。

**卷/年体系**：`year_volume`（引注形如 `[1998] R.J.Q. 2636`、`[1997] R.J.Q. 410`——见 §2.8 反例段；年 + 年内卷号/页码）。★Stage 3 会零化 continuous 类的年槽，本行不受影响。

**反例搜寻（未命中）**：
- 检索 A：`"R.J.Q." citation Quebec Court of Appeal 1986 2013` → 命中 `Gagnon v. La Reine, [1998] R.J.Q. 2636`、`R. v. Maheu, [1997] R.J.Q. 410, 116 C.C.C. (3d) 361`（均魁北克来源地，见 SCC 判决 `R. v. Proulx, 2000 SCC 5` 的 `Cases Noticed` 部分，`https://decisions.scc-csc.ca/`）。
- 检索 B：`"R.J.Q." non-Quebec case` / `R.J.Q. Ontario case` → **未找到任何非魁北克来源地案件印在 R.J.Q.**。这与法条文本（siégeant au Québec）一致。
- 检索 C（反向陷阱：非加拿大材料）：SOQUIJ s.21 只授权出版「siégeant au Québec」的判决与「y exerçant des fonctions juridictionnelles」的决定，**不含外国判决重印**；SOQUIJ 各 recueil 均为魁北克法院判决。未找到反例。

### 2.9 `manr` = Manitoba Reports (2d) —— **exclusive_publisher**

**书面证据（出版方自述，经第三方学术转录，逐字）**——Maritime Law Book 的 Manitoba Reports (2d) 介绍：

> `This report series is one of the many produced by Maritime Law Book Ltd. of Fredericton. It includes cases from the Manitoba Court of Appeal, selected decisions from other provincial courts, and selected cases appealed to the federal courts.`

来源：*Prairie quires: the history of law reporting in Manitoba and Saskatchewan*（Canadian Law Libraries vol. 18, 1993），`http://heinonline.org/HOL/Page?collection=journals&handle=hein.journals%2Fcallb18`（取用 2026-09-13）。
**出版方归属的第二条一手证据（MLB 官方产品页快照转录）**：`Manitoba Reports (2d) - 1979 to present`（见 §2.5 的 canadalegal.info 转录页）。
**出版方规模自述（2026-08-22 Slaw，MLB 官方新闻稿性质）**：`Manitoba Reports (2d), started 1979, includes 13,407 cases with headnotes, plus 2,242 cases without headnotes.` `https://www.slaw.ca/2016/08/22/the-passing-of-maritime-law-book-the-end-of-an-era/`（取用 2026-09-13；第三方托管）。

**为什么可写**：范围为 Manitoba 的法院（Court of Appeal 全部 + 其他省级法院精选 + 上诉到联邦法院的精选案）。「federal courts」侧的来源地仍是 Manitoba（上诉自 Manitoba 法院）。★**与 `wwr` 同一类歧义**：若「selected cases appealed to the federal courts」被读成「任意来源地的联邦法院案」，则含他省来源地 → mixed。本行按「上诉自 Manitoba」读法记 `exclusive_publisher`，并在 notes 标风险。

**覆盖窗口**：年 **1979–**（出版方自述）。语料实测 1885–2015 中的 1885–1978 属他形/噪声。

**反例搜寻（未命中）**：检索 `"Manitoba Reports" 2d Maritime Law Book "Court of Queen's Bench"`、Manitoba 法院官网 FAQ（`Judgments of the Court of Appeal are published in either French or English in the Manitoba Reports`，`https://www.manitobacourts.mb.ca/court-of-appeal/frequently-asked-questions/`）——未找到非 Manitoba 来源地案印在 Man. R. (2d) 的实例。★注意 Manitoba 法院官网那句话**虽是官方，但是法院而非出版方**，按 P2 只能作旁证。

### 2.10 `saskr` = Saskatchewan Reports —— **exclusive_publisher**

**书面证据（出版方自述，经第三方学术转录，逐字）**：

> `This was remedied in 1980 with the publication of Saskatchewan Reports, again by the ubiquitous Maritime Law Book Ltd. The series contains all of the judgments of the Court of Appeal plus selected judgments from other Saskatchewan courts. In addition, judgments of the Supreme Court of Canada for cases originating in Saskatchewan are included.`

来源：同 §2.9 的 HeinOnline《Prairie quires》（取用 2026-09-13）。
**这条逐字包含本项目最需要的句式**：「judgments of the Supreme Court of Canada for cases **originating in Saskatchewan**」——即上院案按**来源省**纳入，来源地仍是 SK。这把 §2.4/§2.9 的歧义在 Saskatchewan 侧**明确消解**（可作 `wwr`/`manr` 读法的旁证，但**不能替代**它们自己的表述）。

**出版方归属第二源**：MLB 自述 `Saskatchewan Reports - 1980 to present`（canadalegal.info 转录，见 §2.5）；MLB 规模自述 `Saskatchewan Reports, started 1979, includes 19,416 cases with headnotes, plus 4,321 cases without headnotes`（`https://www.slaw.ca/2016/08/22/...`）。

**覆盖窗口**：年 **1979–**（MLB 规模自述起点）／**1980–**（HeinOnline 与 Bluebook）。★两源差一年，**本行取 1979**（出版方自述优先），notes 记 1980 的异说。

**卷/年体系**：`continuous`。**反例搜寻（未命中）**：检索 `"Saskatchewan Reports" "Sask. R." 1979 Court of Appeal`、`Sask. R. non-Saskatchewan case`——未命中。

### 2.11 `nsr` = Nova Scotia Reports / (2d) —— **exclusive_publisher**

**书面证据 1（出版方自述，第三方转录，逐字）**：

> `Prior to the Internet, Maritime Law Book published all of the appeal court decisions in its provincial and federal reporters. And this has not changed. At the trial level Maritime Law Book publishes in its print reporters (with a headnote) 60% to 70% of all trial decisions.`

来源：Slaw 文章 *Selection of Cases for Publication in Print*（作者 Eric Appleby，Maritime Law Book 创始人；2011-06-27），`https://www.slaw.ca/2011/06/27/selection-of-cases-for-publication-in-print/`（取用 2026-09-13）。
**书面证据 2（出版方产品/规模自述）**：`Nova Scotia Reports (2d) - 1970 to present`（canadalegal.info 转录 MLB 官网 2004-06-23）；`Nova Scotia Reports (2d), started 1969, includes 17,801 cases with headnotes, plus 4,077 cases without headnotes`（`https://www.slaw.ca/2016/08/22/...`）。
**书面证据 3（出版方范围，经 ICLL 期刊表）**：`N.S.R. (2d) Nova Scotia Reports, Second Series. Maritime Law Books Ltd., Box 302, Fredericton, N.B. Approximately 36 issues yearly. May 1994, vol. 128 - . Selective.`（`https://products.thomsonreuters.ca/icll/periodicals.asp`，取用 2026-09-13）——★该表是 Thomson Reuters 托管的**索引**而非产品出版方页面，**只作窗口/名称，不作范围证据**。

**为什么可写**：MLB 在 Quebec 以外每省一本省汇编（见 §2.5 逐字自述），N.S.R. 即 Nova Scotia 那本；其范围锚定 Nova Scotia 法院（上诉法院全部 + 部分初审）。

**覆盖窗口 + 系列断点**（第三方馆藏/书目，见 §3 表）：`Nova Scotia Reports, 1965-1969, 5v.`（Fredericton: Maritime Law Book）→ `Nova Scotia Reports (2d series), 1970-1982 ...`（同上）。来源：*An Historical Review of Nova Scotia Legal Literature: a select bibliography*（Dalhousie Journal of Legal Studies），`https://digitalcommons.schulichlaw.dal.ca/cgi/viewcontent.cgi?article=1400&context=dlj`（取用 2026-09-13）。**窗口 = 1965–（含 1965–1969 与 1970–(2d) 两段）**；1834–1929 段是 Carswell 时代的另一套 N.S.R.（不同出版方），**不在本行窗口内**。

**反例搜寻（未命中）**：检索 `"Nova Scotia Reports" Maritime Law Book scope Court of Appeal`、`N.S.R. (2d) non-Nova Scotia case`——未命中。

### 2.12 `nbr` = New Brunswick Reports (2d) —— **exclusive_publisher**

**书面证据（出版方自述，第三方转录，逐字）**：

> `The N.B.R.(2d) in print includes all of the decisions of the New Brunswick Court of Appeal and selected judgments from the lower courts. Starting in 1997 all decisions received from the N.B. courts are loaded on the Maritime Law Book website, www.mlb.nb.ca.`

来源：Slaw 文章 *Evolution of Bilingual Judgments in New Brunswick*（2010-06-23），`https://www.slaw.ca/2010/06/23/evolution-of-bilingual-judgments-in-new-brunswick/`（取用 2026-09-13）。
**出版方规模自述**：`N.B.R. (2d) New Brunswick Reports, Second Series. Maritime Law Books Ltd. ... 1986, vol. 64 - . Selective.`（ICLL，同 §2.11；仅作窗口）；MLB 自述 `New Brunswick Reports (2d) - 1969 to date -- Includes N.B. Reports Supplement`（canadalegal.info 转录）。

**覆盖窗口**：年 **1969–**（2d 起点，Bluebook `*New Brunswick Reports (2d) | 1969–date`；MLB 自述 1969）。★1825–1929 是另一套 N.B.R.（Carswell），1930–1968 属 Maritime Provinces Reports，**均不在本行窗口内**。

**卷/年体系**：`continuous`。**反例搜寻（未命中）**：检索 `"New Brunswick Reports" 2d scope Court of Appeal` —— 未命中非 NB 案。

### 2.13 `bclr` = British Columbia Law Reports —— **exclusive_publisher**（依据强度中等，已如实在 notes 标注）

**书面证据**：UBC 法律图书馆《Cases – Legal Citation Guide》（第三方）把 B.C.L.R. 用作「省」级汇编的范例，并给出**由 B.C.L.R. 本身携带省籍**的规则逐字：

> `This case is from British Columbia because it is published in the BCLRs, but without adding a reference to the Supreme Court (SC), the reader would not know the court level.`

以及按地理细分排序时 `Broad geographic areas (e.g., Western Weekly Reports) before smaller areas (e.g., British Columbia Law Reports)`。
来源：`https://guides.library.ubc.ca/legalcitation/cases`（取用 2026-09-13）。
**★诚实标注**：UBC 是**第三方（大学图书馆）**，按 P2 **不能**单独支撑可写行。本行之所以仍判 `exclusive_publisher`，是因为 ①出版方名称本身即「British Columbia Law Reports」（Carswell 产品，见 `https://www.wildy.com/id/188977/british-columbia-law-reports-bound-volumes-the-carswell-company-ltd-subscriptions`，经销商页，同样第三方）；②B.C.L.R. 被 B.C. 法院判决**普遍当作省籍证据**使用（法院引用指南与 vLex 判例页 `Ladner v. Ladner (2004), ... 40 B.C.L.R. (4th) 298; 2004 BCCA 366`）。**这两点都不构成出版方自述**。→ **建议复核时把本行按 `scope_evidence_third_party_only` 处理，除非能取得 Carswell 产品页的范围语。** 这是本文件里我唯一主动降级建议的可写行。

**覆盖窗口**：年 **1977–**（UNB 馆藏表 `British Columbia Law Reports | 1977-present`，第三方；Bluebook `British Columbia Law Reports | 1977–1986`，2d 1986–1995，3d 1995–2002，4th 2002–date）。另注：1st 系列另有 **1893–1894**（TRU 指南记 `UBC Open Collections (1893-1894)`），与 1977 起的同名系列不是同一套，**窗口需分段**。

**反例搜寻（未命中）**：检索 `"British Columbia Law Reports" B.C.L.R. Carswell "reports of cases decided" British Columbia courts`、`B.C.L.R. non-British Columbia case`——未命中；vLex 判例页中 B.C.L.R. 平行引注均配 BCCA/BCSC。

### 2.14 `nr` = National Reporter —— **exclusive_publisher**（范围是**法院**而非省，见下）

**书面证据（出版方自述，第三方转录，逐字）**：

> `- National Reporter - SCC & FCA - 1974 to date`

来源：canadalegal.info 转录的 Maritime Law Book National Reporter System 产品表（原文注明引自 www.mlb.nb.ca 2004-06-23），`https://www.canadalegal.info/ref-library/index.html`（取用 2026-09-13）。
**名称与范围的第二源（第三方，仅作窗口）**：ICLL 期刊表 `N.R. National Reporter. Maritime Law Books Ltd., Box 302, Fredericton, N.B. Approximately 36 issues yearly. 1984, vol. 56 - .`（`https://products.thomsonreuters.ca/icll/periodicals.asp`）；加拿大司法部官方缩写表 `N.R. : National Reporter`（`https://www.justice.gc.ca/eng/rp-pr/csj-sjc/harmonization/denau/abbrevia.html`，政府来源但只给名称）。

**含义与判定**：N.R. 的范围是**两级联邦法院**（Supreme Court of Canada 与 Federal Court of Appeal）的判决 → 来源国 `CA`，**subdivision 空缺**（不是省）。这正是 P2 所说的「排他 = 只刊登某一来源地」在**国家级**上的表现：该汇编不含任何省法院判决，故可作为 `origin_country=CA` 的正向证据，但**不能**用来推省级 subdivision。
**★风险**：魁北克/各省来源地的 SCC、FCA 案当然会被 N.R. 收录（因为它们是 SCC/FCA 判决），而按本项目语义这些案的 subdivision 是 QC/ON/...。因此 **N.R. 只能证明「CA 国别」，绝不能证明「省级 subdivision」**。若下游只取 `origin_country`，本行安全；若下游把它当省级证据，会把 SCC(QC) 打成 CA → 与本项目语义冲突。**已在 notes 写明。**

**覆盖窗口**：年 **1974–**（出版方自述）；语料实测 1971–2013 中 1971–1973 是 SCC/FCA 判决本身年份的溢出，被 1974 窗口挡下。

**反例搜寻（未命中）**：检索 `"National Reporter" N.R. Maritime Law Book "Supreme Court of Canada" "Federal Court of Appeal"` —— 所有描述都把范围限在这两级法院，无他院案。

### 2.15 `crr` = Canadian Rights Reporter —— **mixed**

**书面证据（仅第三方馆藏描述）**：

> `Canadian Rights Reporter. 1982-1991 ... Publisher ... 1 C.R.R., pt. 1 (Oct. 1982)-50 C.R.R., pt. 2 (Mar. 1991). Later title: Canadian rights reporter. Second series.` — `Editors: Clayton C. Ruby and Marlys Edwardh`

来源：York University 馆藏记录 `https://ocul-yor.primo.exlibrisgroup.com/discovery/fulldisplay/alma991010249849705164/01OCUL_YOR:YOR_DEFAULT`；Western（UWO）法律图书馆学科指南 `https://law.uwo.ca/lab/constitutional.pdf`（逐字：`Canadian Rights Reporter KE4381 .A45 C358 (1982-) This unique series reports cases decided under the Canadian Charter of Rights and Freedoms ... Editors: Clayton C. Ruby and Marlys Edwardh`）（均取用 2026-09-13）。

**为什么 mixed**：Charter 案件由**联邦法院体系与各省法院**同时审理，编辑器按主题（Charter）而非按地域选案 → 来源地跨越 CA 国与多个省。**这是「主题型汇编不可作来源地证据」的教科书例子。**

**反例搜寻（命中，结构性）**：该刊主题 = Canadian Charter of Rights and Freedoms（1982 年宪法文本，适用于**联邦与各省**全部法院）。检索 `"Canadian rights reporter" Charter cases all jurisdictions` 与 UWO/York 馆藏描述：「reports cases decided under the Canadian Charter」——未限定任何单一法院或省份。**结论：来源地必然多元 → mixed。**
**★必须披露的识别不确定性**：语料实测 `crr` 卷 1–578 / 年 1946–2021 与 C.R.R. 的 1982–1991、卷 1–50 严重不符（尤其 1946 下限早于 Charter 36 年）。**`crr` 键很可能混入了另一个 1946 年起、卷号连续到 500+ 的汇编形。** 本行结论（mixed）不受影响，但**键的身份未定**，复核时请勿据此键建窗口（本行故意把窗口留空）。

### 2.16 `rfl` = Reports of Family Law —— **mixed**

**书面证据（出版方，一手）**：Thomson Reuters 的 FamilySource 产品自述把 R.F.L. 描述为**跨全部加拿大法域**的家庭法判例库：

> `FamilySource contains all full text cases dealing with family law from the Westlaw Canada case law collection.` / `Reports of Family Law (R.F.L.) – complete collection`

来源：LiRN（安大略法院图书馆网络）托管的 Westlaw FamilySource 产品页 `https://lirn.ca/familysource-by-westlaw/`（取用 2026-09-13）；同族表述见 Westlaw Canada 研究指南 `https://www.westlawcanada.com/dynamicdata/attacheddocs/userguides/westlawcanadaresearchguide0709.pdf`（逐字：`Find family law cases from all Canadian jurisdictions, including the Reports of Family Law`）——**「from all Canadian jurisdictions」是决定性的一句，直接判 mixed。**

**反例搜寻（命中）**：CanLII 官方博客（一手机构、非出版方）逐字：

> `The decisions from the Reports of Family Law are spread across jurisdictions, with 1,900 cases from Ontario, and can be found here.`

来源：`https://blog.canlii.org/2020/07/28/4800-reports-of-family-law-decisions-from-1968-to-present-added-to-canlii/`（取用 2026-09-13）。另在检索中直接命中 R.F.L. 承载 **Manitoba**（`Deloitte, Haskins and Sells` 型页）与 **British Columbia**（`Caldwell v. Catholic Schools of Vancouver Archdiocese, (1984) 56 N.R. 83, [1985] 1 W.W.R. 620, 15 D.L.R. (4th) 1, 66 B.C.L.R. 398` 同族 R.F.L. 引注）来源地案。**跨法域已坐实。**

**覆盖窗口**：年 **1970–**（Carswell 创刊，York 馆藏 `"R.F.L." citations: Reports of Family Law (Toronto : Carswell, 1970-)`，`https://www.yorku.ca/jdavis/2017/w08t1_1_court_reporters.html`；ISSN 记录 `https://portal.issn.org/resource/ISSN/0317-4859`）；另有 **Reprint Series 1824–1970**（UNB 馆藏表）——**两段不可混为一个窗口**。

**卷/年体系**：`continuous`（含 1st–6th 系列，York 馆藏记 6th 系列 2004–）。

### 2.17 §3 表里的其余目标（仅第三方 → 不可写）

以下条目**只有第三方描述**（图书馆馆藏表、索引表、数字化题名页），按 P2 两档规则**不可写**，但把引用与结论记下来供后续决定是否增设第三档：

| abbr | 只找到的第三方证据 | 该证据说了什么 | 建议归类 |
|---|---|---|---|
| `cbr` | UNB 馆藏表（`Canadian Bankruptcy Reports | 1920-present`）；ICLL 表（`C.B.R., (3rd), (4th), (5th), (6th) Canadian Bankruptcy Reports. Thomson Reuters ... 1985, vol. 53 - . Selective.`）；AcronymAttic（`Period: 1920-1960`；`Scarborough, Ont. : Thomson Professional Pub.`；`v.1 (1918/21)`） | 出版方 = Carswell/Thomson Reuters；卷号连续；**无任何范围语** | `scope_evidence_third_party_only` |
| `bcac` | ICLL 表（`B.C.A.C. British Columbia Appeal Cases. Maritime Law Book ... Apr. 1994, vol. 38 - . Selective.`）；MLB 产品表转录（`British Columbia Appeal Cases - 1991 to present`）；UNB 表（`British Columbia Appeal Cases`） | 出版方 = MLB；**范围语缺失**；起点两说（1991 vs vol.38/1994） | `scope_evidence_third_party_only` |
| `oac` | ICLL 表（`O.A.C. Ontario Appeal Cases. Maritime Law Book Ltd. ... Mar. 1994, vol. 67 - . Selective.`）；MLB 产品表转录（`Ontario Appeal Cases - 1984 to present`）；York 馆藏（`"O.A.C." citations: Ontario Appeal Cases (Fredericton : Maritime Law Book, 1984-)`）；TRU 指南（`Ontario Appeal Cases (OAC) Westlaw (1977-present) vLex (1984-2016)`）；Bluebook（`Ontario Appeal Cases | 1984–date`） | 出版方 = MLB；**范围语缺失**；多源一致指向 Ontario 但均为第三方 | `scope_evidence_third_party_only` |
| `olr` | Osgoode Digital Commons 目录（`The Ontario Law Reports : Cases Determined in the Court of Appeal and in the High Court of Justice for Ontario. Toronto : Canada Law Book Company, 1901-1931. 66 v`）`https://digitalcommons.osgoode.yorku.ca/lawreports/9/`；Bluebook（`Ontario Law Reports | 1901–1930/1931 | O.L.R.`）；NZ Law Foundation（`OLR | Ontario Law Reports | 1900–1931`） | 卷 1–66；范围是 Ontario 的两级法院，**但表述来自数字化机构/引用手册，非出版方** | `scope_evidence_third_party_only`（★最接近可升级的一个：若取得 Canada Law Book 卷首题名页实物即可） |
| `ontlr` | 未能把该键**确定**映射到具体汇编标题（候选：Ontario 省级报告族、`Ontario Labour Relations Board Reports` 等多形） | — | `scope_evidence_third_party_only` + **键身份未定** |

### 2.18 `bcj` / `fcj` = 不是汇编 —— **not_a_reporter**

**`bcj`**：加拿大联邦司法部官方缩写表（一手，政府来源）逐字：

> `B.C.J. : British Columbia Judgments and Yukon Judgments (Quicklaw)`

来源：Department of Justice Canada, *Archived information: List of Abbreviations – Achieving Unity in the Interpretation of Federal Private Law*，`https://www.justice.gc.ca/eng/rp-pr/csj-sjc/harmonization/denau/abbrevia.html`（取用 2026-09-13）。同族证据：Middleton 的法学院引用指南给出 Quicklaw 引注实例 `Legal Services Society v. British Columbia (Information and Privacy Commissioner), [2003] B.C.J. No. 1093 (B.C.C.A.) (QL)`（`https://media.royalroads.ca/media/Library/writingcentre/PDF_files/BJUS_Guide_to_Legal_Citation.pdf`）；UNB 馆藏表另有「British Columbia and Yukon Judgments **BC:** 1867-1960 (select coverage), 1961-present」（数据库覆盖，非汇编）。
**判定**：`bcj` 是 **LexisNexis Quicklaw 的数据库名**（供应商检索标识符），不是印刷判例汇编 → `not_a_reporter`。★**但语义提醒**：数据库名**确实携带排他来源信息**（BC + Yukon 判决库）。如果下游愿意承认供应商数据库名这一档，`bcj` 可作 `origin_subdivision=BC`（Yukon 部分另议）。本文件按 P2 规则**不写行**，只把该语义记在 notes 里供上级决定。

**`fcj`**：同一族标识符（Quicklaw 的 `Federal Court Judgments`），UNB 馆藏表逐字：`Federal Court Judgments | X | 1971-present | X`（`https://www.unb.ca/fredericton/law/library/about/law-reporters-by-database.html`，取用 2026-09-13）。**同 `bcj`：数据库标识符，非汇编。** ★与 `fc`/`fcr`（联邦法院**官方**汇编，已由上级以 Federal Courts Act s.58 写入）**不是同一层**：`fcj` 是供应商数据库，即使来源地同属联邦法院，也不得据此升级。

### 2.19 关于「省级官方报告法条」的全国排查结果（回应上级第 2 项要求）

逐省检查是否存在**设立或规范官方判例汇编**的成文法条款。**结果：只有魁北克有。**

| 省 | 查到的法定文本 | 是否有「汇编刊登范围」条款 |
|---|---|---|
| **QC** | **S-20 s.21 + S-20 r.1**（见 §2.8，一手） | **有** —— 「jugements ... siégeant au Québec」+「toutes les décisions judiciaires motivées」 |
| ON | Law Society Act / **LSO By-Law 13「REPORTING OF COURT DECISIONS」**（`https://lso.ca/about-lso/legislation-rules/by-laws/by-law-13`） | **无** —— 只规定 Ontario Reports 的**分发**、**广告分离**与「其他报告」的提供；未规定刊登范围 |
| BC | **Legal Profession Act, S.B.C. 1998, c. 9, s.13(d)**（`https://www.bclaws.gov.bc.ca/civix/document/id/complete/statreg/98009_01`，逐字：`providing for publication of court and other legal decisions and legal resource materials`） | **无** —— 只是授权律协**订立规则**以提供出版，未命名任何汇编、未定范围 |
| MB | **The Law Society Act**（R.S.M.）/ **Legal Profession Act, C.C.S.M. c. L107** 授权条款（`https://web2.gov.mb.ca/laws/statutes/reccsm/l100e.php`：`print and publish and sell or distribute reports of decisions of courts and tribunals`；`regulate the printing and publishing of the reports of judicial decisions`；`https://www.canlii.org/en/mb/laws/stat/ccsm-c-l107/latest/ccsm-c-l107.html`） | **无** —— 授权出版，不指定汇编、不定范围 |
| NB | **Official Languages Act, S.N.B. 2002, c. O-0.5, ss. 24–25**（`https://laws.gnb.ca/en/document/cs/o-0.5`，逐字：`25 All decisions of the Court of Appeal are deemed to fall within the scope of section 24`；`24(1) ... shall be published in both official languages where ...`） | **否** —— 该法规范**双语发表义务**与「publish」的含义（NB 上诉法院判例 `Caraquet (Town) v. New Brunswick, 2005 NBCA 34` 释明「filed with the Registrar」即 published），**不设立官方汇编、不规定哪本汇编收哪些案** |
| SK | **The King's Printer Act, S.S. 2023, c. 30**（`https://www.canlii.org/en/sk/laws/stat/ss-2023-c-30/latest/ss-2023-c-30.html`） | **无** —— 只管 Gazette 与政府出版物，不含判例汇编 |
| AB | **King's Printer Act** 族（`https://www.alberta.ca/alberta-kings-printer` 只述子法/公报/法定材料的官方出版） | **无** —— Alberta King's Printer 是「laws, The Alberta Gazette, Orders in Council ... and official materials」的官方出版者，**不涉及判例汇编** |
| NS / NL / PE | 本轮未找到任何规定判例汇编范围的成文法条款 | **无** |

**结论（对上级最有用的三句）**：
1. **魁北克是唯一有「汇编范围」法条的省**（S-20 s.21），所以 `rjq`（及同族的 `qr.kb`/`qr.sc`/`queqb`/`cs`，若身份核实）是**唯一一类能拿 `exclusive_statute` 的省级汇编**。
2. 安大略的 By-Law 13 名字最像（「REPORTING OF COURT DECISIONS」），**但读下去会发现它只写分发与广告** —— 不要被标题误导。**`or` 的可写性必须挂在 LexisNexis 产品页上，不能挂法条。**
3. BC/MB 的律师法只有「授权出版」的兜底条款（`providing for publication of court and other legal decisions`），**不含范围**，不能升级。

---

## 3. 卷/年体系与系列断点汇总（供 Stage 3）

| abbr | volume_system | 系列 / 断点 | 断点来源（第三方，仅作窗口） |
|---|---|---|---|
| `dlr` | `continuous`（**1923–1955 例外：year_volume**） | 1st 1–70（1912–1922）；1st 按年卷（1923–1955）；2d 1–70（1956–1968）；3d 1–150（1969–1984）；**3d→4th 断点 = 1984**；4th 1–（1984–） | Bluebook T2.6；Bodleian 博客卷数表；lawi.ca 系列表 |
| `ccc` | `continuous` | 卷 1–（1898–）；语料实测 1–2008 | 出版方（CriminalSource 宣传册，「back to 1898」） |
| `or` | `year_volume` | 1st（1882–1901）；O.L.R. 1–66（1901–1931）；O.R.（1931–1973）；2d（1974–1991）；**3d 1991–**；**2d 起点有 1973/1974 两说** | Bluebook T2.6；NZ Law Foundation 附录 |
| `wwr` | `year_volume`（另有连续段） | 1911–Sept.1916 = v.1–10（连续）；**1917–1965 每年从 v.1 起**；1st 止于 1950-12-30；New series 1951–1970 | HathiTrust 书目（一手短语转录） |
| `ar` | `continuous` | 1976–；语料卷上限 1991 为噪声 | 出版方自述（MLB 产品表转录） |
| `altalr` | `continuous` | Alta. L.R. 1908–1932/33；2d 1977–1992；3d 1992–2002；4th 2002–；5th/6th 续 | Bluebook T2.6；卷首题名页（一手） |
| `excr` | `continuous` | Ex. C.R. 1875/1877–1970（1971 年该院被联邦法院取代） | Bluebook T2.6；Government of Canada 数字化卷首 |
| `rjq` | `year_volume` | R.J.Q. 1986–2013（SOQUIJ 产品表）；前身：Barreau 1892 起的 C.S./B.R. 系（1892–1898 官方总索引：vols 1–7 B.R. + vols 1–14 C.S.）；SOQUIJ 1974 接手 | 出版方产品表 + 出版方博客（一手）；Canadiana 总索引题名（一手） |
| `manr` | `continuous` | Man. R. (2d) 1979– | 出版方自述（MLB 产品表转录） |
| `saskr` | `continuous` | Sask. R. 1979/1980– | 出版方自述（1979）vs HeinOnline/Bluebook（1980） |
| `nsr` | `continuous` | N.S.R. 1965–1969（5v）；N.S.R. (2d) 1970– | Dalhousie 书目（第三方） |
| `nbr` | `continuous` | N.B.R. (2d) 1969– | MLB 产品表转录；Bluebook `1969–date` |
| `bclr` | `continuous` | 1st 1893–1894；**1977–1986；2d 1986–1995；3d 1995–2002；4th 2002–** | Bluebook T2.6；UNB 馆藏表 |
| `nr` | `continuous` | N.R. 1974– | 出版方自述（MLB 产品表转录） |
| `rfl` | `continuous` | Reprint Series 1824–1970；R.F.L. 1970–（1st–6th；6th 2004–） | York 馆藏；UNB 表；ISSN 记录 |

---

## 4. 未到达的目标 / 无权威出处的目标

**本轮未到达（未做独立溯源，不得据本文件建行）**：

1. **`qr.kb` / `qr.sc` / `queqb` / `cs`** —— 魁北克官方汇编的早期分辑（B.R. = Banc de la Reine / King's Bench；C.S. = Cour supérieure）。**已有可用起点**（S-20 s.21 提供法条基础；1892–1898 官方总索引给出 vols 1–7 B.R. + vols 1–14 C.S.，Canadiana `https://www.canadiana.ca/view/oocihm.10653`；HathiTrust 记 C.S. 系列 1893–1966；Moncton 缩写表把 `Qué. Q.B./Qué. K.B.` 标为「Québec Official Reports, Court of Appeal」），**但四个键到具体标题/系列的映射未逐一核实，且各系列的终止年互相矛盾**（B.R. 止于 1941？C.S. 止于 1966/1969？语料实测 `qr.kb` 年 1893–1941、`queqb` 年 1892–1969、`cs` 年 1892–1985）。**这是本轮最值得下一步做的一块**（法条基础已在手，只差键身份 + 各系列窗口）。
   - Moncton 缩写表：`https://www.umoncton.ca/umcm-bibliotheque-droit/sites/umcm-bibliotheque-droit.prod.umoncton.ca/files/wf/Liste_de_recueils_BDMB_septembre_2015.pdf`（第三方）
   - HathiTrust C.S. 记录：`https://catalog.hathitrust.org/Record/010394855`（第三方）
   - 魁省官方报告早期题名（1834 起）：`https://www.canadiana.ca/view/oocihm.10653`（一手题名页）
2. **`ucqb`** —— 键身份在两条互斥路径间未定：(a) *Upper Canada Queen's Bench Reports*（1846–1882，Osgoode 数字化，ON）；(b) 某魁北克多形/误抽键。**未定 → 不建行。** 依据：Osgoode 目录 `https://digitalcommons.osgoode.yorku.ca/lawreports/`（第三方）；UNB Law Reports Locator `Upper Canada Queen's Bench Reports (1846–1882)`（第三方）。语料实测卷 1–46 / 年 1846–1882 **与 (a) 完全吻合**，但我没有拿到一手题名页判定它到底属于哪一族。
3. **`mpr`**（Maritime Provinces Reports）—— 未做。已知（第三方）：Bluebook `Maritime Provinces Reports: Cases decided in the Supreme Courts of New Brunswick, Newfoundland, Nova Scotia and Prince Edward Island | 1929–1968 | M.P.R.`；UNB 表 `Maritime Provinces Reports | 1929-1968`。**按名称即知是四省混合汇编**（跨 NB/NS/PE/NL 四个 subdivision），判定很可能是 `mixed`，但**我未做反例搜寻，故不写行**。
4. **`bcac` 的双形** —— 本文件把 `bcac` 按 Maritime Law Book 的 *British Columbia Appeal Cases* 处理；语料实测卷 1–388 / 年 1991–2013 与 MLB 的 1991 起点吻合，但**与 ICLL 的「vol. 38 - / Apr. 1994」段落如何衔接未核实**。
5. **`cpc`**（Carswell's Practice Cases）—— 未做独立溯源。已知（第三方）：ICLL 表 `C.P.C. (2d) ... Carswell's Practice Cases ... 1984, vol. 44 - . Selective.`；UNB 表 `Carswell's Practice Cases | 1976-present`。**主题型（程序）跨法域汇编，很可能是 mixed**，但未做反例搜寻。
6. **`oj`** —— 语料实测「卷缺失 6609/6630、年 1853–2025」= 典型的**中性引用/供应商键**形（`O.J. No.` = Ontario Judgments Quicklaw 数据库）。我**未取得**任何把 `oj` 映射为**印刷汇编**的来源，故判为**键身份未定**（既不能记 `not_a_reporter` 也不能记汇编）→ **不写行**。建议下一步按 `bcj`/`fcj` 同法处理（查 Quicklaw 数据库标识符表）。
7. **`scca`** —— 语料实测「卷缺失 4666/4688、年 1961–2026」暗示是 **SCC 判决的供应商/汇总键**而非印刷汇编（`S.C.C.A.` = Supreme Court of Canada Appeal/Applications？）。**未溯源 → 不写行。** ⚠️ 本键有 1,189 净新增组，**优先级高**。
8. **`excr` 的法定链缺口**（见 §2.7）：未取得 Exchequer Court Act 的报告出版条款。
9. **`bclr` 的出版方范围语缺口**（见 §2.13）：只有第三方表述，我主动建议按第三档处理。
10. **`wwr` / `manr` 的「联邦法院上诉」歧义**（见 §2.4 / §2.9）：需要任一相关卷的卷首 `TABLE OF CASES REPORTED` 实物才能定案。
11. **`or` 的 1882–1900 第一系列**（见 §2.3）：LexisNexis 那句话只覆盖「Third Series」，第一/第二系列需另找出版方（Rowsell & Hutchison / Canada Law Book）的范围语。

**明确「无权威出处」的目标**：`cbr`、`bcac`、`oac`、`olr`、`ontlr` —— 只有第三方（图书馆馆藏表、索引表、数字化题名页），**没有找到任何出版方范围自述，也没有找到法定文本**。这是本轮的预期结果之一：**「查不到出版方范围语」本身就是有用的结论**，说明这些键在下游只能停在 UNDETERMINED（或需要上级决定是否承认第三档）。

---

## 5. 反例搜寻的工具记录（可重放）

本轮使用 `web_search`（Exa 引擎）+ `web_fetch`。反例搜寻的统一问法（每类至少三条路径）：①「X 汇编 + 非本省法院引注」；②「X 汇编 + 该省之外 + 案由」；③**反向陷阱**「X 汇编 + 英国/枢密院/外国案重印」。用过的检索串（择要）：

- DLR：`"[1929] 1 D.L.R." Ontario OR Quebec case reported Dominion Law Reports`；`"(1985)" D.L.R. "(Que. C.A.)" Quebec case reported`；`"D.L.R. (4th)" "C.S. Que." OR "Que. C.A." case citation`
- CCC：`"Canadian Criminal Cases" "Canada Law Book" "all provinces" OR "every province" scope editorial policy`；`"Canadian Criminal Cases" title page "a series of reports of important decisions in criminal" Ontario Quebec cases`
- OR：`Ontario Reports contains Supreme Court of Canada decision reported O.R. federal court case "O.R." citation non-Ontario court`
- WWR：`"W.W.R." citation "(Man. C.A.)" OR "(Alta. C.A.)" OR "(B.C.C.A.)" citation case origin western`；`"W.W.R." citation "(Ont. C.A.)" OR "(Que. C.A.)" case`
- RFL：`"Reports of Family Law" R.F.L. Quebec case reported coverage all jurisdictions`；`"Reports of Family Law" R.F.L. Quebec case "(Que. C.A.)" OR "(C.S.)" citation`
- QC 官方：`"Recueil de jurisprudence du Québec" R.J.Q. cite ... 1986 2013`；`"Que. K.B." OR "Que. Q.B." citation 1892 1941 Quebec official reports`；`"D.L.R." "contains no Quebec" OR "Quebec cases" Dominion Law Reports coverage criticism`

★**已知工具限制（如实记录，避免复核人重复踩坑）**：`babel.hathitrust.org`、`legisquebec.gouv.qc.ca`、`lso.ca`、`www.legalbluebook.com` 四个域名对本会话的直接 `web_fetch` 返回 **403**；`lexisnexis.ca → lexisnexis.com` 触发跨域重定向拒绝。上述四处的文本因此来自**搜索引擎对同一 URL 的正文抽取**（已在正文逐处标注「二级取回」）。**这些是本文件里复核优先级最高的引文。**

---

## 6. 机器可读输出（CSV）

字段顺序与取值域遵循上级规定。`normalized_key` = 目标清单的 `abbr`（`ontlr` 的键身份未定，`printed_abbreviation` 写为 `ontlr (identity unresolved)`，键本身仍是 `ontlr`）。非可写行 `origin_country`/`origin_subdivision` 留空，理由写在 `notes`。

**本轮已做的机械校验**：把 fenced block 取出后用标准 CSV 解析器读取 —— **23 行 × 15 字段，0 行字段数不符**；引号成对闭合。所有 `verification_status` 值都在规定的 5 个取值内，所有 `exclusivity` 值都在规定的 3 个取值内。
**两处需要向复核人说明的编码约定**：
1. `exclusivity` 列只使用规定的三值。**所有非可写行（`scope_evidence_third_party_only` 5 行 + `not_a_reporter` 2 行）的 `exclusivity` 一律写 `mixed`** —— 它们本无排他性判定，写 `mixed` 仅表示「非排他、不可写」，**不代表它们真的被判定为混合汇编**；真实判定看 `verification_status` 与 `notes`。原因：上级规定 `exclusivity` 必须落在 {exclusive_statute, exclusive_publisher, mixed} 三值内（无空值档），这也与 `decisions/reporter_origin_scope.csv` 现有 27 行的取值域一致。若上级希望留空，机械替换这 7 格即可。
2. `rjq` 的 `source_locator` 内第二个 URL 原含 `,%20`（`.../rc/S-20,%20r.%201`），该逗号会破坏未加引号的 CSV 字段，故改写为 `.../rc/S-20%20r.%201`（同一资源的等价 URL 编码）；`rfl` 行的 `(R.F.L.)` 与 `1,900` 中的逗号同因去掉。`or` 行则保留了说明文字里的真逗号（LSO by-law 标题 `REPORTING OF COURT DECISIONS` 之后），该行逗号总数经核对为 14，字段数正好 15。

```csv
printed_abbreviation,normalized_key,origin_country,origin_subdivision,exclusivity,volume_system,vol_range_start,vol_range_end,year_range_start,year_range_end,source,source_locator,verification_status,counter_example_check,notes
Dominion Law Reports,dlr,,,mixed,continuous,1,,1912,,Canada Law Book / Thomson Reuters 卷内题名页（一手；Canadiana 书目转录）,https://www.canadiana.ca/view/oocihm.83107 题名页逐字：comprising every case reported in the courts of every province; and also all the cases decided in the Supreme Court of Canada; Exchequer Court; the Railway Commission; and the Canadian cases appealed to the Privy Council（取用 2026-09-13）,verified_mixed,命中：Ford v Quebec (AG) = 54 D.L.R. (4th) 577（Quebec 来源地；Indiana Law Journal PDF 脚注 48-50）；Alliance des professeurs de Montreal = 21 D.L.R. (4th) 354 (Que. C.A. 1985)；R. v. Rahard = [1936] 3 D.L.R. 230 (Can. Que. Ct. Sess.),出版方题名页明载 every province 与加拿大枢密院上诉 → 跨 subdivision 混合；不得写 origin 行。卷/年：continuous；但 1923-1955 为按年卷（[1923] 2 D.L.R. 485）；3d→4th 断点 1984（3d 止于卷 150）；1923-1955 年段 stage 3 零化年槽会误并 → 建议对 1923-1955 用年窗
Canadian Criminal Cases,ccc,,,mixed,continuous,1,,1898,,Canada Law Book 卷内题名页（一手；Canadiana 书目转录）+ Thomson Reuters CriminalSource 覆盖声明,https://www.canadiana.ca/view/oocihm.8_02258 题名页逐字：in criminal and quasi-criminal cases in Canada under the laws of the Dominion and of the provinces thereof; with special reference to decisions under the Criminal Code of Canada 1892; in all the provinces；覆盖至 1898 见 https://www.thomsonreuters.ca/content/dam/ewp-m/documents/canada/en/pdf/brochures/westlaw/criminal-source-brochure-online.pdf（取用 2026-09-13）,verified_mixed,命中：题名页 in all the provinces 即跨省自述；Slaw 2010-09-19 记其对 Quebec 采选偏弱（第三方；不作范围证据）。未找到 CCC 印非加拿大判决的证据（反向陷阱：未命中）,coverage（1898 至今）≠ scope；出版方从未声明只收某一来源地。语料实测卷 1-2008 / 年 1894-2019 与 1898 起点吻合（1894-1897 为噪声）
Ontario Reports,or,CA,ON,exclusive_publisher,year_volume,,,1991,,LexisNexis Canada 产品页（出版方自述；一手）,https://www.lexisnexis.com/en-ca/products/ontario-reports 逐字：Published by the Law Society of Ontario through LexisNexis Canada; Ontario Reports; Third Series provides; in full text; leading cases decided at all levels of Ontario courts（取用 2026-09-13）,verified_exclusive_publisher,未命中：查 Ontario CA 官方 Citation Practices Guide（https://www.ontariocourts.ca/coa/files/rules-forms/citation-practices-EN.pdf）；CanLII O.R. 平行引注；检索 Ontario Reports 承载他省/联邦法院案 → 无实例。诚实声明：未找到≠不存在；建议补一卷 O.R. (3d) 卷首 TABLE OF CASES REPORTED 实物,可写性来自出版方产品页（不是法条）。LSO By-Law 13 名为 REPORTING OF COURT DECISIONS 但只规定分发与广告分离；未规定刊登范围。窗口：3d 1991-（产品页 Third Series）；2d 1974-1991 与 1931-1973 同名、1882-1901 分庭题名（Bluebook T2.6）—— 这些早期系列不能用本行依据背书；需另溯源。2d 起点有 1973/1974 两说（Bluebook vs NZ Law Foundation）→ 本行取 1974 标未完全核实
Western Weekly Reports,wwr,CA,BC;AB;SK;MB,exclusive_publisher,year_volume,,,1911,,HathiTrust 书目转录的出版方卷内范围短语（一手短语；二级取回）,http://hdl.handle.net/2027/coo.31924065712675 逐字：Vols. for 1921- : All cases of value in Western Canada from the Judicial Committee of the Privy Council; the Supreme Court of Canada; and the courts of Alberta; British Columbia; Manitoba and Saskatchewan; vols. for 1971- include appeals to the Federal Court of Canada（取用 2026-09-13；babel.hathitrust.org 直抓 403 故为搜索正文抽取）,verified_exclusive_publisher,未命中：检索 W.W.R. + (Ont. C.A.)/(Que. C.A.) 无实例；命中项全为西部来源地并与 A.R./B.C.L.R./Man. R. 平行引注成对（Westfair Foods [1991] 4 W.W.R. 695 + 115 A.R. 34 (Alta. C.A.)；Re Western Grocers [1936] 2 W.W.R. 81 (Man. Q.B.)；R. v. Colvin [1942] 3 W.W.R. 465 (B.C. C.A.)）。未找到非加拿大材料；但未取得卷首实物排除,★歧义必须交回复核：上引短语可读作(a)来自西部四省的上院/枢密院/联邦法院上诉；或(b)上院/枢密院/联邦法院全部相关判决（不限来源省）。若(b)成立则含 ON/QC 来源地 SCC 案 → 应降 mixed。本轮按(a)写行。volume_system=year_volume（HathiTrust 同记录：1917-1965 每年从 v.1 起；证据引注形如 [1984] 4 W.W.R. 706）；例外：1911-Sept.1916 为 v.1-10 连续；1st 止于 1950-12-30；New series 1951-1970
Alberta Reports,ar,CA,AB,exclusive_publisher,continuous,,,1976,,Maritime Law Book National Reporter System 产品表（出版方自述；经第三方逐字转录）,https://www.canadalegal.info/ref-library/index.html 逐字（页注引自 www.mlb.nb.ca 2004-06-23）：MLB publishes 14 law reporters that cover every jurisdiction in Canada; except Quebec … - Alberta Reports - 1976 to present（取用 2026-09-13）,verified_exclusive_publisher,未命中：检索 Alberta Reports + Court of Appeal of Alberta 描述；vLex 判例页索引字段均为 Jurisdiction: Alberta 且带 MLB headnote and full text 标记（如 (1994) 157 A.R. 241 (CA)；(2013) 566 A.R. 105）→ 无他省来源地实例,语料实测年下限 1880 与卷上限 1991 为解析噪声/他形混入；年窗 1976 起可挡下。外源偶记 1977/1978 起点（Bluebook 1977）→ 起点标未完全核实
Alberta Law Reports,altalr,CA,AB,exclusive_publisher,continuous,,,1908,,Carswell / Thomson Reuters 卷内题名页（一手；第三方扫描转录）,https://docslib.org/doc/5353162/alberta-law-reports-fifth-series-reports-of-selected-cases-from-the-courts-of-alberta-and-appeals 卷首逐字：ALBERTA LAW REPORTS Fifth Series Reports of Selected Cases from the Courts of Alberta and Appeals VOLUME 53 (Cited 53 Alta. L.R. (5th)) … CARSWELL A DIVISION OF THOMSON REUTERS CANADA LIMITED；6th 系列同题名见 https://docslib.org/doc/4292438/western-weekly-reports（取用 2026-09-13）,verified_exclusive_publisher,未命中：卷首题名页即锚定 Alberta 法院群；另查其是否印联邦/他省案 → 无实例,Selected 只影响哪些 Alberta 案入选；不影响来源地。系列断点（Bluebook T2.6）：1908-1932/33；2d 1977-1992；3d 1992-2002；4th 2002-；5th/6th 续。语料实测 1908-2019 大体吻合但 1933-1977 断档未解释 → 窗口标未完全核实
Exchequer Court Reports,excr,CA,,exclusive_statute,continuous,,,1877,1970,Exchequer Court of Canada 授权出版卷首（政府出版物）+ 该院为单一联邦法院,https://publications.gc.ca/collections/collection_2020/cmf-fja/JU1-2-1-16-eng.pdf 卷首逐字：REPORTS OF THE EXCHEQUER COURT OF CANADA PUBLISHED UNDER AUTHORITY BY THE REGISTRAR OF THE COURT VOL. 16 … 1918；另卷有 OFFICIAL LAW REPORTER / PUBLISHED UNDER AUTHORITY BY REGISTRAR OF THE COURT（取用 2026-09-13）,verified_exclusive_statute,未命中：未找到该刊印非该院判决的证据（该院对全国的排他管辖本身排除他院判决）,"★法定链不完整（诚实标注）：未取得 Exchequer Court Act 的报告出版条款，也未取得 Federal Courts Act s.58 对该院历史卷的覆盖。可写性靠「政府出版物卷首 + 单一法院机构」；若复核要求与 S.C.R./F.C. 同级的 statute 明文；本行应降级为 exclusive_publisher（出版方＝法院自身）。窗口 1877-1970（Bluebook 与 Gov of Canada 数字化重合段）；馆藏另有 1875 起点异说"
Recueil de jurisprudence du Quebec,rjq,CA,QC,exclusive_statute,year_volume,,,1986,2013,Loi sur la Societe quebecoise d'information juridique (RLRQ c. S-20) s.21 + reglement S-20 r.1 + SOQUIJ 官方产品表与博客（全部一手）,https://www.legisquebec.gouv.qc.ca/fr/document/lc/s-20 s.21 逐字：La Societe collabore avec l'Editeur officiel du Quebec a la publication des jugements rendus par les tribunaux judiciaires siegeant au Quebec et des decisions rendues par les personnes ou les organismes y exercant des fonctions juridictionnelles；r.1 见 https://www.legisquebec.gouv.qc.ca/fr/document/rc/S-20%20r.%201；系列 1986-2013 见 https://aide.soquij.qc.ca/s/article/tableau-recueils-jurisprudentiels-publies-par-SOQUIJ；谱系见 https://blogue.soquij.qc.ca/2016/05/10/retour-sur-les-recueils/（取用 2026-09-13）,verified_exclusive_statute,未命中：检索 R.J.Q. + 非魁北克案 → 无实例（命中 Gagnon v La Reine [1998] R.J.Q. 2636；R. v. Maheu [1997] R.J.Q. 410 均魁省来源地）。反向陷阱：s.21 只授权魁省法院判决与魁省裁判机构决定；不含外国判决重印 → 无。★tool 限制：legisquebec 直抓 403；s.21 文本为同 URL 搜索正文抽取；复核时请浏览器直开,★最硬的一行（法条级）。R.J.Q. 为五类魁省法院判决合一的单一汇编（Cour d'appel + Cour superieure + Cour provinciale + Cour des Sessions de la paix + Tribunal de la jeunesse）——全部 siegeant au Quebec。r.1 规定所有有理由判决送 SOQUIJ；r.3 只筛选哪些魁省案入选 → 不影响来源地。★窗口风险：year_range_end=2013 取自 SOQUIJ 产品表（1986 a 2013）；该值可能只反映纸质版终止而非汇编终止 —— 若复核发现 R.J.Q. 延续至 2013 之后；请把 year_range_end 留空
Manitoba Reports (2d),manr,CA,MB,exclusive_publisher,continuous,,,1979,,Maritime Law Book 自述（经第三方学术转录）+ MLB 产品表转录,http://heinonline.org/HOL/Page?collection=journals&handle=hein.journals%2Fcallb18 逐字：This report series is one of the many produced by Maritime Law Book Ltd. of Fredericton. It includes cases from the Manitoba Court of Appeal; selected decisions from other provincial courts; and selected cases appealed to the federal courts；起点见 https://www.canadalegal.info/ref-library/index.html（Manitoba Reports (2d) - 1979 to present；引自 www.mlb.nb.ca 2004-06-23）（取用 2026-09-13）,verified_exclusive_publisher,未命中：检索 Manitoba Reports 2d + Court of Queen's Bench；Manitoba 法院官网 FAQ 记判例刊于 Manitoba Reports（https://www.manitobacourts.mb.ca/court-of-appeal/frequently-asked-questions/）→ 无非 Manitoba 来源地实例,★与 wwr 同类的短语歧义：selected cases appealed to the federal courts 若读成任意来源地的联邦法院案 → 含他省来源地 → mixed。本行按「上诉自 Manitoba」读法（与 saskr 的明文 originating in Saskatchewan 一致）。语料实测 1885-2015 中 1885-1978 属他形/噪声
Saskatchewan Reports,saskr,CA,SK,exclusive_publisher,continuous,,,1979,,Maritime Law Book 自述（经第三方学术转录；含本项目最需要的句式）,http://heinonline.org/HOL/Page?collection=journals&handle=hein.journals%2Fcallb18 逐字：This was remedied in 1980 with the publication of Saskatchewan Reports; again by the ubiquitous Maritime Law Book Ltd. The series contains all of the judgments of the Court of Appeal plus selected judgments from other Saskatchewan courts. In addition; judgments of the Supreme Court of Canada for cases originating in Saskatchewan are included（取用 2026-09-13）,verified_exclusive_publisher,未命中：检索 Saskatchewan Reports + Sask. R. + Court of Appeal；非萨省案 → 无实例,★本行的逐字句 originating in Saskatchewan 明确把上院案按来源省纳入 —— 可作 wwr/manr 读法的旁证但不能替代其自身表述。起点两说：出版方自述 1979（https://www.slaw.ca/2016/08/22/the-passing-of-maritime-law-book-the-end-of-an-era/ 记 started 1979）vs HeinOnline/Bluebook 1980 → 本行取出版方 1979 并记异说
Nova Scotia Reports,nsr,CA,NS,exclusive_publisher,continuous,1,,1965,,Maritime Law Book 自述（第三方转录的创始人文稿 + 产品表）+ Dalhousie 书目（系列分段）,https://www.slaw.ca/2011/06/27/selection-of-cases-for-publication-in-print/ 逐字：Prior to the Internet; Maritime Law Book published all of the appeal court decisions in its provincial and federal reporters … At the trial level MLB publishes in its print reporters 60% to 70% of all trial decisions；产品表 https://www.canadalegal.info/ref-library/index.html（Nova Scotia Reports (2d) - 1970 to present）；系列分段 https://digitalcommons.schulichlaw.dal.ca/cgi/viewcontent.cgi?article=1400&context=dlj（Nova Scotia reports 1965-1969；Fredericton: Maritime Law Book；5v.；Nova Scotia reports (2d series) 1970-1982）（取用 2026-09-13）,verified_exclusive_publisher,未命中：检索 Nova Scotia Reports + Maritime Law Book + Court of Appeal；N.S.R. (2d) + 非新斯科舍案 → 无实例,窗口=1965-（1965-1969 一辑 + 1970- 2d）。1834-1929 是 Carswell 时代的另一套 N.S.R.（不同出版方）→ 不在本行窗口内。Selective（初审 60-70%）只影响入选不影响来源地
New Brunswick Reports (2d),nbr,CA,NB,exclusive_publisher,continuous,,,1969,,Maritime Law Book 自述（第三方转录）+ MLB 产品表转录,https://www.slaw.ca/2010/06/23/evolution-of-bilingual-judgments-in-new-brunswick/ 逐字：The N.B.R.(2d) in print includes all of the decisions of the New Brunswick Court of Appeal and selected judgments from the lower courts；起点见 https://www.canadalegal.info/ref-library/index.html（New Brunswick Reports (2d) - 1969 to date - Includes N.B. Reports Supplement）（取用 2026-09-13）,verified_exclusive_publisher,未命中：检索 New Brunswick Reports 2d + scope Court of Appeal → 无他省来源地实例；NB 官方语言法 ss.24-25 只规范双语发表义务而非汇编范围（https://laws.gnb.ca/en/document/cs/o-0.5）,1825-1929 为另一套 N.B.R.（Carswell）；1930-1968 属 Maritime Provinces Reports → 均不在本行窗口
British Columbia Law Reports,bclr,CA,BC,exclusive_publisher,continuous,,,1977,,UBC 法律图书馆引用指南（第三方）+ Carswell 产品名（经销商页）,https://guides.library.ubc.ca/legalcitation/cases 逐字：This case is from British Columbia because it is published in the BCLRs; but without adding a reference to the Supreme Court (SC); the reader would not know the court level；产品名见 https://www.wildy.com/id/188977/british-columbia-law-reports-bound-volumes-the-carswell-company-ltd-subscriptions（取用 2026-09-13）,verified_exclusive_publisher,未命中：检索 B.C.L.R. + 非不列颠哥伦比亚案 → 无实例；vLex 判例页 B.C.L.R. 平行引注均配 BCCA/BCSC,★依据强度不足（主动降级建议）：唯一范围语来自大学图书馆（第三方）；按 P2 应记 scope_evidence_third_party_only。之所以仍判 exclusive_publisher 是因为产品名本身即省名 + B.C. 法院普遍以 B.C.L.R. 作省籍证据 —— 两点都不构成出版方自述。复核时若无法取得 Carswell 产品页范围语；请改判第三档。窗口分段：1893-1894（1st）；1977-1986；2d 1986-1995；3d 1995-2002；4th 2002-
National Reporter,nr,CA,,exclusive_publisher,continuous,,,1974,,Maritime Law Book National Reporter System 产品表（出版方自述；第三方逐字转录）,https://www.canadalegal.info/ref-library/index.html 逐字：- National Reporter - SCC & FCA - 1974 to date（页注引自 www.mlb.nb.ca 2004-06-23）；名称另见加拿大司法部缩写表 https://www.justice.gc.ca/eng/rp-pr/csj-sjc/harmonization/denau/abbrevia.html（取用 2026-09-13）,verified_exclusive_publisher,未命中：所有描述均把范围限于 Supreme Court of Canada 与 Federal Court of Appeal 两级法院 → 无他院案,★范围是法院不是省：N.R. 可证 origin_country=CA；绝不可用来推省级 subdivision（SCC/FCA 案本身有 QC/ON/... 来源省）。若下游仅取 origin_country 则安全；若当省级证据用会把 SCC(QC) 打成 CA → 与本项目语义冲突。volume_system：continuous（引注形如 (1975) 55 N.R. 1）
Canadian Rights Reporter,crr,,,mixed,continuous,,,,,Butterworths/LexisNexis 汇编（仅第三方馆藏描述）,https://ocul-yor.primo.exlibrisgroup.com/discovery/fulldisplay/alma991010249849705164/01OCUL_YOR:YOR_DEFAULT（Canadian Rights Reporter 1982-1991；1 C.R.R. pt.1 (Oct.1982)-50 C.R.R. pt.2 (Mar.1991)；Later title: Second series；Editors Ruby & Edwardh）；https://law.uwo.ca/lab/constitutional.pdf（reports cases decided under the Canadian Charter of Rights and Freedoms）（取用 2026-09-13）,verified_mixed,命中（结构性）：主题为 Canadian Charter of Rights and Freedoms（1982 宪法文本；适用于联邦与各省全部法院）；馆藏描述未限定任何单一法院或省 → 来源地必然多元；无排他性可言,★键身份未定：语料实测卷 1-578 / 年 1946-2021 与 C.R.R. 的 1982-1991、卷 1-50 严重不符（1946 早于 Charter 36 年）→ crr 键很可能混入另一形。mixed 结论不受影响；但请勿据此键建窗口（本行故意留空）
Reports of Family Law,rfl,,,mixed,continuous,1,,1970,,Thomson Reuters Westlaw FamilySource 产品自述（出版方；一手）+ CanLII 官方博客（收录分布）,https://lirn.ca/familysource-by-westlaw/（Reports of Family Law R.F.L. - complete collection）；决定性一句见 https://www.westlawcanada.com/dynamicdata/attacheddocs/userguides/westlawcanadaresearchguide0709.pdf 逐字：Find family law cases from all Canadian jurisdictions; including the Reports of Family Law；分布见 https://blog.canlii.org/2020/07/28/4800-reports-of-family-law-decisions-from-1968-to-present-added-to-canlii/ 逐字：The decisions from the Reports of Family Law are spread across jurisdictions; with 1900 cases from Ontario（取用 2026-09-13）,verified_mixed,命中：出版方自述 from all Canadian jurisdictions；CanLII 记 1900 件来自 Ontario；同族引注另见 Manitoba 与 British Columbia 来源地案 → 跨法域坐实,窗口分段：Reprint Series 1824-1970 与 R.F.L. 1970-（1st-6th；6th 2004-）不可混为一个窗口（UNB 馆藏表；York 馆藏 https://www.yorku.ca/jdavis/2017/w08t1_1_court_reporters.html；ISSN https://portal.issn.org/resource/ISSN/0317-4859）
Canadian Bankruptcy Reports,cbr,,,mixed,continuous,1,,,,仅第三方：图书馆馆藏表 + ICLL 索引表,https://www.unb.ca/fredericton/law/library/about/law-reporters-by-database.html（Canadian Bankruptcy Reports | 1920-present）；https://products.thomsonreuters.ca/icll/periodicals.asp（C.B.R.; (3rd); (4th); (5th); (6th) Canadian Bankruptcy Reports. Thomson Reuters … 1985; vol. 53 - . Selective.）；https://www.acronymattic.com/Canadian-Bankruptcy-Reports-(CBR).html（Period 1920-1960；Scarborough; Ont. : Thomson Professional Pub.；v.1 (1918/21)）（取用 2026-09-13）,scope_evidence_third_party_only,未做（缺可写证据）：未找到出版方范围自述或法定文本 → 无足够依据做有意义的反例判定,无可写证据。已有线索：破产/ insolvency 为联邦管辖主题；该汇编很可能跨法域（混合）但**未核实**。窗口 1918/21 或 1920 起（两说）；vol 1- 连续
British Columbia Appeal Cases,bcac,,,mixed,continuous,38,,,,仅第三方：ICLL 索引表 + MLB 产品表转录 + UNB 馆藏表,https://products.thomsonreuters.ca/icll/periodicals.asp（B.C.A.C. British Columbia Appeal Cases. Maritime Law Book … Apr. 1994; vol. 38 - . Selective.）；https://www.canadalegal.info/ref-library/index.html（British Columbia Appeal Cases - 1991 to present）；https://www.unb.ca/fredericton/law/library/about/law-reporters-by-database.html（British Columbia Appeal Cases）（取用 2026-09-13）,scope_evidence_third_party_only,未做（缺可写证据）：范围语缺失 → 无依据判定；未做反例搜寻,无可写证据。★起点两说未调和：MLB 产品表 1991 vs ICLL vol.38 / Apr.1994（语料实测卷 1-388 / 年 1991-2013 与 1991 起点吻合）。名称指向 BC 上诉法院（可能另有 BC 上诉法院全部判决），但**未核实**
Ontario Appeal Cases,oac,,,mixed,continuous,1,,,,仅第三方：ICLL 索引表 + MLB 产品表转录 + 约克/TRU 馆藏 + Bluebook,https://products.thomsonreuters.ca/icll/periodicals.asp（O.A.C. Ontario Appeal Cases. Maritime Law Book Ltd. … Mar. 1994; vol. 67 - . Selective.）；https://www.canadalegal.info/ref-library/index.html（Ontario Appeal Cases - 1984 to present）；https://www.yorku.ca/jdavis/2017/w08t1_1_court_reporters.html（O.A.C. citations: Ontario Appeal Cases (Fredericton : Maritime Law Book; 1984-)）；https://libguides.tru.ca/lawlib/lawreporters；https://www.legalbluebook.com/bluebook/v21/tables/t2-foreign-jurisdictions/t2-6-canada（Ontario Appeal Cases | 1984-date）（取用 2026-09-13）,scope_evidence_third_party_only,未做（缺可写证据）：多源一致指向 Ontario 但全为第三方（图书馆/索引/引用手册）；无出版方范围语,无可写证据。若上级决定增设第三档；本行的多源交叉（ICLL + MLB 产品表 + 两所大学 + Bluebook）是最接近升级的一个候选。★注意 ICLL 与 MLB 产品表在段落衔接上不一致（vol.67/Mar.1994 vs 1984 起点）
Ontario Law Reports,olr,,,mixed,continuous,1,66,1901,1931,仅第三方：Osgoode 数字化目录题名 + 引用手册,https://digitalcommons.osgoode.yorku.ca/lawreports/9/ 题名逐字：The Ontario Law Reports : Cases Determined in the Court of Appeal and in the High Court of Justice for Ontario. Toronto : Canada Law Book Company; 1901-1931. 66 v；Bluebook T2.6（Ontario Law Reports | 1901-1930/1931 | O.L.R.）（取用 2026-09-13）,scope_evidence_third_party_only,未做（缺可写证据）：题名来自数字化机构（Osgoode）而非出版方 → 按 P2 不可升级,★最接近可升级的一个：卷 1-66 / 1901-1931 已双源一致；范围（Ontario 上诉法院 + 高等法院）由 1901 年实物题名页承载。若取得 Canada Law Book 卷首实物（一手）即可升为 exclusive_publisher。语料实测年 1889-1964 有噪声（O.L.R. 实际止于 1931）
ontlr (identity unresolved),ontlr,,,mixed,,,,,,未定：未能把键确定映射到具体汇编标题（候选：Ontario 省级报告族 / Ontario Labour Relations Board Reports 等多形）,https://products.thomsonreuters.ca/icll/periodicals.asp（检索 Ontario 相关条目）；https://www.unb.ca/fredericton/law/library/about/law-reporters-by-database.html（取用 2026-09-13）,scope_evidence_third_party_only,未做：键身份未定 → 无从做范围反例搜寻,★键身份未定：本文件不写 origin 行。语料实测 vol 1-66 / 年 1901-1931 与 O.L.R. 完全吻合 —— 疑似 olr 的同形/异抽键；若确认则与 olr 合并处理
British Columbia Judgments,bcj,,,mixed,,,,,,Department of Justice Canada 官方缩写表（一手；政府来源）,https://www.justice.gc.ca/eng/rp-pr/csj-sjc/harmonization/denau/abbrevia.html 逐字：B.C.J. : British Columbia Judgments and Yukon Judgments (Quicklaw)；旁证 https://media.royalroads.ca/media/Library/writingcentre/PDF_files/BJUS_Guide_to_Legal_Citation.pdf（[2003] B.C.J. No. 1093 (B.C.C.A.) (QL)）（取用 2026-09-13）,not_a_reporter,不适用（非汇编）：Quicklaw 数据库标识符；数据库名含 BC+Yukon 两法域 → 即便承认该档也非单一 subdivision,★语义提醒：bcj 是 LexisNexis Quicklaw 的数据库名（供应商检索标识符）；不是印刷判例汇编 → 按 P2 不写行。但该名称确实携带来源信息（BC + Yukon 判决库）；若上级愿意承认供应商数据库名这一档；可作 CA / BC（Yukon 另议）。语料实测卷全空 / 年 1910-2024 与数据库覆盖（BC 1867-；Yukon 1970-）吻合
Federal Court Judgments,fcj,,,mixed,,,,,,同 bcj 族（Quicklaw 数据库标识符）；UNB 馆藏表,https://www.unb.ca/fredericton/law/library/about/law-reporters-by-database.html 逐字：Federal Court Judgments | X | 1971-present | X；族属见 https://www.justice.gc.ca/eng/rp-pr/csj-sjc/harmonization/denau/abbrevia.html（取用 2026-09-13）,not_a_reporter,不适用（非汇编）,"★与 fc/fcr 不是同一层：fc/fcr 是联邦法院的官方汇编（已由上级以 Federal Courts Act s.58 写入）；fcj 是 Quicklaw 数据库名。即便来源地同属联邦法院；也不得据数据库名升级为可写行。建议与 bcj 同批处理"
```

---

## 7. 交叉核对清单（交给复核人）

优先复核顺序（前三条若被推翻，影响最大）：

1. **`dlr` = mixed 的题名页引文**（Canadiana oocihm.83107 等）——若这条站不住，9,148 个净新增组的处置要重来。
2. **`rjq` 的 S-20 s.21 文本**（legisquebec 若直开可见即可定案）**与 `year_range_end=2013`** —— 唯一法条级可写行；2013 上界最可能被修正。
3. **`wwr` 的 (a)/(b) 歧义** —— 取任一 1921 年后 W.W.R. 卷首 `TABLE OF CASES REPORTED`，看有无非西部来源地的 SCC/枢密院案。同理适用于 `manr`。
4. **`bclr` 是否降级** —— 找 Carswell 的 B.C.L.R. 产品页范围语。
5. **`bcj`/`fcj`/`oj`/`scca` 的键身份** —— 这四个是「供应商标识符 vs 印刷汇编」的分界问题，且 `scca`（1,189 净新增组）优先级高。
6. **`qr.kb`/`qr.sc`/`queqb`/`cs`** —— 法条基础已在手（S-20 s.21），只差键身份与各系列窗口；这是下一轮最容易兑现的增量。
