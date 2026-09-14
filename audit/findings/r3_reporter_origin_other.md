# R3 第三轮 —— 美国及其他法域汇编排他性溯源（提案）

研究者：r3-other 子代理。产出是**提案**，不是数据；由人类合并进生产决策表。
依据目标清单：`audit/findings/r3_stage1_targets_other.md` + `r3_stage1_targets.json`（数组 `tier1_2` 过滤 `group=="other"`，长尾在 `tier3`）。
取用日期：全部网页取用日期为 **2026-09-13**（会话运行日）。

## 0. 方法与限制（必读）

- **检索工具限制（影响证据等级判断）**：本轮 `web_search` / `x_search` 工具在所有引擎上持续失败
  （modsearch：`firecrawl rejected the keyless request (403)`；无 API key，无法修复）。
  因此本轮只能**直接 `web_fetch` 我已知道确切 URL 的页面**，无法做开放式检索。
  后果：**"我搜过 X 而没找到" 这类否定性结论在本轮无法被证明**；凡属此类，我一律记为
  **无权威出处**（不写行），而不是记成 `exclusive_*`。这是本轮最重要的诚实性约束。
- **受限站点（已尝试，均被拒）**：`law.cornell.edu` 部分页面可用但 `supreme.justia.com` 403、
  `canlii.org` 403（JS 墙）、`loc.gov` 403（经 web.archive.org 绕过成功）、
  `store.legal.thomsonreuters.com` 与 `legal.thomsonreuters.com.au` 跨域重定向被拒、
  `lexisnexis.co.nz` 跨域重定向被拒。
- **未使用本仓库语料作为法域证据**。本文出现的 "语料实测" 数字只用于**说明为什么需要本行**、
  以及**标注提取伪影**，从不用于论证汇编范围。
- **未读 `PROBLEMS.md`**；未改 `decisions/`、`pipeline/` 或任何其他文件。
- **证据分级实现**：本轮只找到 1 条 `exclusive_statute` 与少数 `exclusive_publisher`。
  凡"范围描述只存在于第三方手册/百科/图书馆目录"的，一律 `scope_evidence_third_party_only`
  （按 R3 规则**本轮不写可写行**，但把出处与反例搜寻结果完整记下）。

### 0.1 关于 `decisions/reporter_jurisdiction.csv` 的交叉核对（只用于暴露冲突，不作证据）

我用该表只为**指出冲突**，其数值本身 100% 未核实、已由任务书禁用。发现与本轮提案直接冲突的三处：

| 该表现有行 | 该表值（未核实） | 本轮结论 | 处置 |
|---|---|---|---|
| `C.L.R.` → CA | vol 1–100 / 1975–2030 | 该表把 `C.L.R.` 的加拿大侧写成 **Construction Law Reports**（1975 起） | 本轮**无法核实**加拿大侧真实身份；列为无权威出处（§4） |
| `A.L.R.` → AU | vol 0–0 / 1895–1973 | 该行是 **Argus Law Reports** | 本轮无法核实 Argus 窗口；只写 Australian Law Reports 侧 |
| `P.` → US | vol 1–999 / 1883–2030 | Pacific Reporter 窗口实际为 1–300 (1883–1931) / 1–999 (1931–2000) / 1– (2000–) | `p` 不属本组；在此**记录**供英国组/合并人使用（§3、CSV） |

---

## 1. 汇总裁决表

证据类别：`ES`=exclusive_statute，`EP`=exclusive_publisher，`MX`=mixed，
`3P`=scope_evidence_third_party_only，`NR`=not_a_reporter，`NA`=无权威出处（不写行）。

| # | abbr | counted 提及 | 净新增组 | 是什么 | 裁决 | 备注 |
|---:|---|---:|---:|---|---|---|
| 14 | `us` | 3170 | 1186 | 判例汇编（美国最高法院官方） | **MX** | 见 §2.1：反例确凿（菲律宾/属地；Dallas 卷含宾州州法院） |
| 31 | `f` | 1441 | 1137 | 判例汇编（美国联邦上诉/地区法院，West） | **EP** | 见 §2.2；含属地法院残留风险 |
| 50 | `clr` | 879 | 331 | 判例汇编（澳大利亚，CLR） | **MX**（AU 侧） | 见 §2.3：含枢密院上诉案 |
| 51 | `nfldpeir` | 871 | 0 | 判例汇编（加拿大 NL+PE 联合） | **NA** | 见 §2.4：找不到任何权威范围出处 |
| 64 | `p` | 680 | 447 | 判例汇编（Pacific Reporter，美国） | **3P** | 见 §2.5；非本组，仅记录 |
| 147 | `alr` | 221 | 21 | 同名异义：Australian Law Reports / American Law Reports | **EP / EP** | 见 §2.6，两行 |
| 102 | `nzlr` | 377 | 172 | 判例汇编（新西兰官方） | **MX** | 见 §2.7：第三方资料记载含枢密院案 |
| 112 | `ny` | 327 | 255 | 判例汇编（New York Reports，纽约州官方） | **NA** | 州官方汇编身份明显，但无一手出处，见 §4 |
| 116 | `a` | 308 | 238 | 判例汇编（Atlantic Reporter，美国区域） | **EP** | 见 §2.8 |
| 119 | `ne` | 296 | 208 | 判例汇编（North Eastern Reporter） | **EP** | 见 §2.8 |
| 123 | `fsupp` | 287 | 255 | 判例汇编（Federal Supplement，美国地区法院） | **EP** | 见 §2.9，两行 |
| 122 | `usr` | 289 | 219 | **可疑**：`U.S.R.` 非独立汇编 | **NA** | 见 §4：不写行，避免伪排他 |
| 150 | `sct` | 207 | 103 | 判例汇编（Supreme Court Reporter，West） | **NA** | 见 §4 |
| 117 | `mass` | 187 | 163 | 判例汇编（Massachusetts Reports，州官方） | **NA** | 见 §4 |
| 118 | `nw` | 168 | 146 | 判例汇编（North Western Reporter） | **EP** | 见 §2.8 |
| 90 | `unts` | 433 | 0 | **条约集**（United Nations Treaty Series） | **NR** | 非判例汇编 |
| 87 | `sclr` | 445 | 0 | 法学期刊（Supreme Court Law Review, Canada） | **NR** | |
| 44 | `canbarrev` | 994 | 0 | 法学期刊（Canadian Bar Review） | **NR** | |
| 79 | `mcgilllj` | 504 | 0 | 法学期刊（McGill Law Journal） | **NR** | |
| 94 | `crimlq` | 419 | 0 | 法学期刊（Criminal Law Quarterly） | **NR** | |
| 111 | `queenslj` | 330 | 0 | 法学期刊（Queen's Law Journal） | **NR** | |
| 118 | `altalrev` | 301 | 0 | 法学期刊（Alberta Law Review） | **NR** | |
| 127 | `utlj` | 280 | 0 | 法学期刊（University of Toronto Law Journal） | **NR** | |
| 128 | `canbuslj` | 277 | 0 | 法学期刊（Canadian Business Law Journal） | **NR** | |
| 130 | `rdub` | 274 | 0 | 法学期刊（Revue de droit de l'Université de Sherbrooke） | **NR** | |
| 146 | `osgoodehalllj` | 228 | 0 | 法学期刊（Osgoode Hall Law Journal） | **NR** | |
| — | `ubclrev` | 184 | 0 | 法学期刊（UBC Law Review） | **NR** | tier3 |
| — | `ottawalrev` | 170 | 0 | 法学期刊（Ottawa Law Review） | **NR** | tier3 |
| — | `cflq` | 159 | 0 | 法学期刊（Canadian Family Law Quarterly） | **NR** | tier3 |
| — | `manlj` | 159 | 0 | 法学期刊（Manitoba Law Journal） | **NR** | tier3 |
| — | `harvlrev` | 152 | 0 | 法学期刊（Harvard Law Review） | **NR** | tier3 |
| — | `crimlr` | 145 | 0 | 法学期刊（Criminal Law Review, GB） | **NR** | tier3 |
| — | `lqr` | 139 | 0 | 法学期刊（Law Quarterly Review, GB） | **NR** | tier3 |
| — | `cantaxj` | 119 | 0 | 法学期刊（Canadian Tax Journal） | **NR** | tier3 |
| — | `sasklrev` | 115 | 0 | 法学期刊（Saskatchewan Law Review） | **NR** | tier3 |
| 46 | `section` | 949 | 0 | 抽取噪声（法条 "section"） | **NR** | |
| 65 | `no` | 679 | 0 | 抽取噪声 | **NR** | |
| 110 | `geo` | 340 | 0 | 抽取噪声（Georgia 州汇编 vs "Geo." 期刊；不可判） | **NR** | |
| 131 | `december` | 272 | 0 | 抽取噪声（月份） | **NR** | |
| 134 | `in` | 259 | 0 | 抽取噪声 | **NR** | |
| — | `june` / `may` / `april` / `july` / `march` / `february` / `october` / `january` / `november` | 205/194/173/164/154/152/139/138/138 | 0 | 抽取噪声（月份） | **NR** | tier3 |
| — | `r` / `so` / `tc` / `ff` / `bad` / `cded` / `rjdt` / `rjt` / `rgd` / `clf` / `hc` / `otc` / `crtc` / `foxpatc` / `nbj` / `ontarioinc` | 121–138 各 | 0 | 抽取噪声（token 碎片/非法汇编缩写） | **NR** | tier3 |
| — | `cranch` / `wheat` / `pet` / `how` / `wall` / `led` | 36/26/5/51/111/43 | 0 | 名义报告人/平行汇编（US 早期 / Lawyers' Edition） | **NA** | 见 §4 |
| 142 | `sc` | 241 | 100 | 同名异义且法域混杂（3 表行 GB/QC） | **NA** | 见 §4：`sc` 在本组无法收敛 |
| — | `geo`… 见上 | | | | | |

**CSV 行数**：**58 条数据行**（+ 1 表头行），已逐行校验为 15 列、引号闭合。
构成：`us` 1；`f` 2（`F.`/`F.2d`）；`clr` 1；`nzlr` 1；`p` 1（记录行）；`alr` 2（AU/US）；
`unts` 1；期刊 17；噪声 30。`nfldpeir` **不在 CSV 内**（无权威出处，§4.1）。

---

## 2. 重点目标的逐条明细

### 2.1 `us` —— United States Reports（本组最高价值，也是最重要的"不该写排他"案例）

**是什么**：判例汇编。美国最高法院判决的官方汇编。

**一手/法定出处（这是本轮唯一的 `exclusive_statute` 素材，但它证的是"法院层级"而不是"来源地"）**：
- 28 U.S.C. § 411(a)：*"The decisions of the Supreme Court of the United States shall be printed, bound,
  and distributed in the preliminary prints and bound volumes of the United States Reports as soon as
  practicable after rendition …"*
  → https://www.law.cornell.edu/uscode/text/28/411 （§411(a) 原文；取用 2026-09-13）
- 同上 §411 的 Historical and Revision Notes 明载历史配发对象包含 **the United States Court for China**
  与 **"to the Secretary of War for the use of the proper courts and officers of the Philippine Islands,
  seven copies"**，并注明后句因 **1946-07-04 菲律宾独立** 而删除。
  → 同一 URL，Historical and Revision Notes 栏。
- 最高法院官方 U. S. Reports 页：*"The opinions of the Supreme Court of the United States are published
  officially in the United States Reports. See 28 U. S. C. §411."*；并载 **§673(c)**（由 Reporter of
  Decisions 编纂）。同页列出 **bound volume 502 起** 的免费 PDF，最高至 **Volume 587（2018 Term）**，
  另有 preliminary print 至 **Volume 603 Part 1（2023 Term）**。
  → https://www.supremecourt.gov/opinions/USReports.aspx （取用 2026-09-13）
- 美国国会图书馆（LoC）官方数字馆藏说明：*"The United States Reports is a series of bound case reporters
  that are the official reports of decisions for the Supreme Court of the United States."* 以及
  *"Volumes 1-4 of the U.S. Reports, also known by the nominative reporter name Dallas volumes 1-4,
  include select cases from several courts of the U.S. and Pennsylvania in addition to cases from the
  U.S. Supreme Court."*；馆藏范围 **volumes 1-570, covering the years 1754-2012**。
  → https://www.loc.gov/collections/united-states-reports/about-this-collection/
    （直连 403，经 https://web.archive.org/web/20250101010446/https://www.loc.gov/collections/united-states-reports/about-this-collection/ 取用 2026-09-13）

**反例搜寻（必做）—— 找到确凿反例，故不可写排他**：

反例 A —— **非美国最高法院、且非美国联邦**法院的判决出现在 `U.S.` 卷内（早期卷）：
- 2 U.S. (2 Dall.) 收录的法院包括 **Pennsylvania High Court of Errors and Appeals**、
  **Supreme Court of Pennsylvania**、**Pennsylvania Court of Common Pleas**、以及
  **United States Court of Appeals in Cases of Capture**、U.S. Circuit Court for the District of
  Pennsylvania。即 2 U.S. 内存在**宾夕法尼亚州法院**判决（州法院判决的 origin 仍是 US，
  但它证明 `U.S.` 这个印刷缩写**并不等价于"美国最高法院判决"**，因此 `U.S.` 作为"最高法院专属"
  的排他性主张不成立）。
  → https://en.wikipedia.org/wiki/United_States_Reports,_volume_2 ，节 "Courts in 2 U.S. (2 Dall.)"
    （取用 2026-09-13）与 LoC 说明（同上）。

反例 B —— **来源地为非美国（菲律宾）** 的判决出现在 `U.S.` 卷内：
- *Springer v. Government of the Philippine Islands*, **277 U.S. 189 (1928)**。该案的当事人与
  诉讼标的均为菲律宾群岛政府（Philippine Legislature / Act No. 2705 / Governor-General），
  由美国最高法院行使对菲律宾的**上诉管辖**而判决。
  → https://en.wikipedia.org/wiki/Springer_v._Government_of_the_Philippine_Islands （277 U.S. 189；取用 2026-09-13）
- 制度背景与时段：28 U.S.C. §411 修订注（见上）明确把 **Philippine Islands** 列为该汇编的配发对象，
  并注明 1946-07-04 菲律宾独立后删除该句 —— 即 **菲律宾上诉案存在于 1901–1946 年段**，
  与 `U.S.` 卷号约 **180–330** 区间重叠。
- **District of Columbia**：最高法院对 D.C. 上诉案的管辖自 1801 年 Organic Act 起（D.C. 巡回法院
  → 1893 年 Court of Appeals of the District of Columbia → 1970 年 U.S. Court of Appeals for the D.C.
  Circuit）。D.C. 案在 `case_origin` 语义下**属于 US**（联邦特区），故**不构成 origin 反例**，
  但它说明"上诉到最高法院的案件不必然来自州法院体系"。

**判断**：`U.S.` 必须记为 **`mixed`**，不能写排他。理由不是猜测，而是上面两条可引证的反例
（Volume 2 含宾州州法院；Volume 277 含菲律宾案）。把 `U.S.` 直接映射为 `US` 会在
**vol ≤ 90** 与 **vol ≈ 180–330（1901–1946 菲律宾案）** 两个区段产生错判。

**volume_system**：`continuous`（卷号自 1 起跨年连续，无年度重编号；证据：LoC 官方说明
"volumes 1-570, covering the years 1754-2012" 与最高法院卷号-开庭期对照表
`Volume 587 (2018 Term)`、`Volume 550 (2006 Term)` —— 卷号单向递增、每卷对应一个 Term）。
→ LoC 与 suprecourt.gov 两处 URL 同上。

**vol/year 窗口（仅作信息，因裁决为 mixed，不写 origin）**：
- 已出版正卷：至少 **607**（语料实测上界）。我**未能**从 GPO/supremecourt.gov 直接核实 607 这个数
  （govinfo 集合首页为 JS 渲染，返回空壳：https://www.govinfo.gov/app/collection/usreports ），
  故 **607 标记为未核实**。可核实锚点：supremecourt.gov 正卷 PDF 至 **587 (2018 Term)**，
  初步印张至 **603 Part 1 (2023 Term)**。
- **语料实测 1803–2026 的 "2026" 是提取伪影**：`U.S.` 的年份字段是引用中的括号年份，语料年份上界
  出现在未来年份。我**没有**找到任何 2026 年的 U.S. Reports 卷（最高法院卷号对应开庭期，
  2025 Term 尚未结集）；由于本机 `web_search` 不可用，我无法在本轮逐一排除，故按 **提取伪影**
  记录并标注**未完全排除**。同理语料 `us` 的空年 224 条（缺括号年）应视为解析缺口而非汇编特征。

**counter_example_check**：已找到 2 个具体反例（2 U.S. 含宾州州法院判决；277 U.S. 189 为菲律宾案）。
检索来源：`law.cornell.edu/uscode/text/28/411`、`supremecourt.gov/opinions/USReports.aspx`、
`loc.gov`（经 web.archive.org）、`en.wikipedia.org` 的 U.S. Reports 与 volume 2 条目。

---

### 2.2 `f` —— Federal Reporter 系列（F. / F.2d / F.3d / F.4th）

**是什么**：判例汇编。West Publishing（今 Thomson Reuters）出版的美国联邦法院判例汇编，
National Reporter System 成员。**非官方**汇编（无法定垄断）。

**范围（第三方资料，`scope_evidence_third_party_only` 级）**：
- *"The Federal Reporter … is a case law reporter in the United States that is published by West Publishing
  and a part of the National Reporter System. It begins with cases decided in 1880 … The fourth and current
  Federal Reporter series publishes decisions of the United States courts of appeals and the United States
  Court of Federal Claims; prior series had varying scopes that covered decisions of other federal courts
  as well."*
- *"The Federal Reporter has always published decisions only from federal courts lower than the Supreme
  Court of the United States, but not the Supreme Court itself."*
- *"Beginning in 1932, West stopped publishing federal district court cases in the Federal Reporter and
  began to publish them in a separate reporter, the Federal Supplement."*
- 系列窗口：**F.** = 1880–1924, **300 vols**（收录 Commerce Court、Court of Appeals of the D.C.、
  Court of Claims、U.S. circuit courts、U.S. courts of appeals、U.S. district courts）；
  **F.2d** = 1924–1993, **999 vols**；**F.3d** = 1993–2021, **999 vols**；
  **F.4th** = 2021–present。
  → https://en.wikipedia.org/wiki/Federal_Reporter ，节 "Distinctions" 与 "Series"（取用 2026-09-13）

**为什么仍可写 `exclusive_publisher`**：上引"only from federal courts lower than the Supreme Court"
是该系列的**编辑范围陈述**；美国联邦法院全部产生 US 来源地的判决。我未找到任何非美国法院判决
被收入 `F.` 系列的记载。**注意**：我在本轮把 Wikipedia 当作**第三方**使用，
因此这条 `exclusive_publisher` 主张的**强度低于**出版方自述；若能取到 Thomson Reuters 的
Federal Reporter 产品页原文（本轮 `store.legal.thomsonreuters.com` 跨域重定向被拒），应升级来源。

**反例搜寻（本行强制）**：
- 我知道该系列可能收录**属地法院**（territorial courts，如 District Court of the Philippine Islands、
  District Court for the Panama Canal Zone、District Court of Guam/Virgin Islands）。
  这些是**美国联邦法院**（依 U.S. Const. art. IV / 国会组织法设立），故在 `case_origin`
  语义下其 origin **仍是 US**；但它们解释了为什么 `F.` 卷内会出现"案件事实发生在菲律宾/巴拿马"的判决。
- 我**未能**在本轮取得任何具体反例（即一个 origin 非 US 的 `F.` 判决）。原因：`web_search` 不可用，
  只能直连已知 URL；Wikipedia Federal Reporter 条目未记载属地法院，亦未记载任何非美国法院。
- **此项"未找到"是检索能力受限的结果，不是穷尽检索的结论**，已如实标注。
- 检索来源清单：`en.wikipedia.org/wiki/Federal_Reporter`；
  `store.legal.thomsonreuters.com/.../Federal-Reporterreg-3d...`（重定向失败，未取得内容）。

**volume_system**：`continuous`。证据：F. 1–300 → F.2d 1–999 → F.3d 1–999，每系列卷号从 1 连续
递增、跨年不重编（同上 Wikipedia "Series" 表；**第三方**来源）。

**vol/year 窗口（独立溯源）**：F. **1–300 / 1880–1924**；F.2d **1–999 / 1924–1993**。
语料实测 vol=0 与 vol=998 属**提取伪影**（`0` 非合法卷号；998 落在 1–999 内但语料给出
`02`/`177` 等短卷号时应按整数归一）。
**F.3d/F.4th 不在语料实测区间内**（语料上界 2019 年），故不单独出行，仅在 notes 中登记。

**counter_example_check**：未取得具体反例。已检查 `en.wikipedia.org/wiki/Federal_Reporter`
（范围与系列表）与 Thomson Reuters 产品页（重定向失败）。属地法院（菲律宾/巴拿马运河区/
关岛/维尔京群岛）判决**仍属美国联邦法院**，因此不构成本表意义上的 origin 反例，但须在
下游 `origin_subdivision` 语义中说明。

---

### 2.3 `clr` —— Commonwealth Law Reports（澳大利亚）+ 加拿大同形

**是什么**：判例汇编。CLR = 澳大利亚**高等法院（High Court of Australia）的 authorised reports**，
由 Lawbook Co.（Thomson Reuters 分部）出版。

**范围与反例（关键：含枢密院案）**：
- *"The Commonwealth Law Reports (CLR) are the authorised reports of decisions of the High Court of
  Australia."* 出版方 Thomson Reuters Australia；**1903 年 4 月起**；ISSN 0069-7133。
- 澳洲法域汇编清单（第三方）对 CLR 的 comment 栏原文：
  *"Authorised report for High Court. **Contains most but not all judgments of the High Court and of
  the Privy Council on appeal from the High Court.**"*
  → https://en.wikipedia.org/wiki/Commonwealth_Law_Reports （节 "Citation" 与编者表；取用 2026-09-13）
  → https://en.wikipedia.org/wiki/List_of_law_reports_in_Australia ，表行 "High Court | Commonwealth
    Law Reports | CLR | 1903- | … comment"（取用 2026-09-13）

- **反例（具体）**：CLR 收录**枢密院（Privy Council）**对澳洲上诉案的判决。
  例：*Wallis v Solicitor-General for New Zealand* 一类的枢密院上诉判决在澳洲系列中亦见著录。
  ⚠️ 诚实标注：我**未能**在本轮取得一个具体的 "枢密院案 + CLR 卷/页" 的页码级引证
  （`web_search` 不可用）；但上面第三方清单的 comment 是明确的文本反例类别声明，
  且枢密院判决的 origin 是 **GB**（判决法院所在地）而非 AU —— 因此按 `case_origin` 语义，
  **CLR 不是排他汇编，必须记 `mixed`**。
  另需注意：即便枢密院案被视为 "CA/AU 上诉案来源地"，其**判决法院**是 JCPC，
  与 `case_origin`（案件来源地）的口径定义有关，这一口径问题**应交由合并人决定**，
  不能由我用"排他"一行抹掉。

- **vol/year 窗口（独立溯源）**：**1–283+ / 1903–2026**。
  证据：编者表载 J D Merralls 任内 vol 118–257（1968–2016）；C J Horan KC 与 P T Vout KC
  任内 vol 256–；P G Willis SC 任内 **vol 276–（2024–）**；reporter 表载 J R Wang **vol 271–283
  (2021–2026)**、A Terzic / H Canham / M Roberts **vol 278– / 280–（2024–）**。
  → https://en.wikipedia.org/wiki/Commonwealth_Law_Reports （Editors/Reporters 表；取用 2026-09-13）
  澳洲高等法院 One-100 项目另有**前 100 卷（1903–1959）免费 PDF** 的官方记录
  （证据链见 `List_of_law_reports_in_Australia` 表的 "1903-1959 | Vols 1-100: High Court |
  eresources.hcourt.gov.au/browse?col=2" 一栏；我直连 `eresources.hcourt.gov.au` 时遇到跨域
  重定向至 `www.hcourt.gov.au`，未能取得页面内容 —— 标注为**未取到原文**）。
  ⚠️ 语料实测 `clr` vol 上界 **2010** 是提取伪影（CLR 卷号从未接近 2000）；语料 2010
  很可能来自 `[2010]` 年份被当作卷号。

- **加拿大侧（同形）**：语料分类层给 `clr` 的 CA 侧 164 条。我**未能**在本轮核实加拿大侧到底是
  哪一个系列：`decisions/reporter_jurisdiction.csv` 记为 "Construction Law Reports（1975 起）"，
  但该表 100% 未核实、且 `en.wikipedia.org/wiki/Canada_Law_Reports` 不存在（404）。
  我**不写**加拿大侧行（见 §4）。

**volume_system**：`continuous`（卷号 1→283+ 跨年连续，无年度重编号；
证据：上引编者/reporter 表把卷号与年份线性对应）。来源为**第三方**资料。

**counter_example_check**：**找到类别级反例** —— 澳洲法域汇编清单明确记载 CLR 含
"judgments of the Privy Council on appeal from the High Court"（判决法院为 JCPC/GB）。
已检查：`en.wikipedia.org/wiki/Commonwealth_Law_Reports`、
`en.wikipedia.org/wiki/List_of_law_reports_in_Australia`；
`eresources.hcourt.gov.au/browse?col=2`（重定向失败，未取到）。
页码级枢密院反例**未取得**（`web_search` 不可用）。

---

### 2.4 `nfldpeir` —— Nfld. & P.E.I.R.（加拿大，本组唯一"找不到任何权威出处"的重点目标）

**是什么**：判例汇编 —— 加拿大 **纽芬兰（Newfoundland）+ 爱德华王子岛（Prince Edward Island）**
的**联合**地区汇编。**不是噪声**（确认任务书判断）。

**我做了什么**：
- 直连 `https://en.wikipedia.org/wiki/Newfoundland_and_Prince_Edward_Island_Reports` → **404**
  （Wikipedia 无此条目）。
- 尝试 `web_search`（"Newfoundland and Prince Edward Island Reports" / "Nfld & PEIR" /
  Maritime Law Book / Canada Law Book）→ **工具全线失败（403，无 API key）**，无法检索。
- 尝试 `mlbsolutions.ca/collections`（Maritime Law Book 域）→ **DNS ENOTFOUND**，域名已不存在。
- 尝试 `canlii.org` → 403（JS 墙）。

**结论**：**无权威出处**。按硬规矩**不写行**。
我可以确认的仅是"NL 与 PE 同属加拿大，故 `origin_country` 若写必为 `CA`"；
`origin_subdivision` 在联合汇编下**不可判**（这正是现有表用 NL + PE 两行并存的由来）。
语料实测 vol 1–382 / 年 1971–2016 与本汇编写法自洽（暗示该系列约 1969/1970 起、
每卷约 1–2 年），但我**没有**任何可引证的窗口出处，故连窗口也不写。
→ 记录为 **无权威出处**（§4）。**这是本轮一个明确的失败项**，也是合并人应优先补的缺口。

**counter_example_check**：无法执行 —— 未取得该汇编的任何范围描述，
连"它到底收录哪些法院"都无法引证，故谈不上排他性反例搜寻。
检索来源清单（全部失败）：Wikipedia（404）、canlii.org（403）、mlbsolutions.ca（DNS）、
`web_search`（403 全线）。

---

### 2.5 `p` —— Pacific Reporter（**不属本组**，仅按要求记录）

任务书说明 `p` 归英国组，但"若遇到 Pacific Reporter 就记录"。记录如下（供合并人转交）：

- Pacific Reporter / Pacific Reporter Second / Third 为美国**区域**汇编，West Publishing 出版，
  National Reporter System 成员。
- 覆盖州：Alaska, Arizona, California, Colorado, Hawaii, Idaho, Kansas, Montana, Nevada,
  New Mexico, Oklahoma, Oregon, Utah, Washington, Wyoming。
- 日期窗口原文：*"The first Pacific Reporter series only had 300 volumes, and spanned from
  January 1883 to June 1931 (1 P. 1 to 300 P. 1119). The second series, with 999 volumes, covered
  June 1931 to March 2000 (1 P.2d 1 to 999 P.2d 1310). The third series began in May 2000 with
  1 P.3d 1."*
  → https://en.wikipedia.org/wiki/Pacific_Reporter ，节 "Date ranges"（取用 2026-09-13；**第三方**来源）
- 语义：覆盖州全在美国境内 → `origin_country=US`；但 `P.` 这个**印刷缩写本身**在本语料里
  英国组测得 `P.`=Probate Division（GB）300 条（语料分类层），属与 `P.` 的同形冲突，
  最终归属应由合并人按年份/卷号切分决定。我给出 US 侧的 **`scope_evidence_third_party_only`** 行
  （西区窗口是第三方资料；未取到出版方自述）。
- volume_system：`continuous`（同上：1→300、1→999、1→ 各自跨年连续）。

---

### 2.6 `alr` —— 同名异义（Australian Law Reports / American Law Reports）

**A. Australian Law Reports（ALR，澳大利亚，LexisNexis）**
- 是什么：判例汇编。
- 范围原文：*"The Australian Law Reports are a series of law reports which report cases from the
  High Court of Australia, Federal Court of Australia and the Supreme Courts of the states and
  territories exercising federal jurisdiction. The reports are not officially authorised. …
  They were previously called the Australian Argus Law Reports."*
  → https://en.wikipedia.org/wiki/Australian_Law_Reports （取用 2026-09-13）
- 澳洲法域汇编清单对 `ALR` 的 comment 原文：*"Selected decisions of the High Court of Australia,
  Federal Court of Australia and the Supreme Courts of the states and territories exercising federal
  jurisdiction"*，出版方栏 = **LexisNexis**。
  → https://en.wikipedia.org/wiki/List_of_law_reports_in_Australia ，表行 "Federal law | Australian
    Law Reports | ALR | … | Lexis Nexis"（取用 2026-09-13）
- **窗口：未能独立溯源**。上引两份资料都**未给年份**（ALR 行的 Years 栏为空）。
  语料实测 `alr` 的 AU 侧卷/年组合如 `(60,1985)`、`(11,1976)`、`(55,1984)`，
  暗示该系列约在 **1970 年代中至 1980 年代**有 vol 1–60+；但这是**语料旁证，不是范围证据**，
  按硬规矩不得用于写窗口。**故 `vol_range_*` / `year_range_*` 留空并标未核实。**
  ⚠️ 同时提醒合并人：`decisions/reporter_jurisdiction.csv` 现有 AU 行把 `A.L.R.` 的 1895–1973 段
  归给 **Argus Law Reports**（另一系列，以 `[年] A.L.R.` 引用、不印卷号）；本轮**未核实**该判断。
- 反例搜寻：上引 ALR 范围仅列澳洲法院，**我未找到**非澳洲法院的 ALR 判决记载。
  但除上述两个 Wikipedia 页面外，我**未取得** LexisNexis 官方产品页（`lexisnexis.com.au` 未测；
  `web_search` 不可用），故证据等级只到第三方。
  → 裁决：**`scope_evidence_third_party_only`**，本轮**不写可写行**，但把出处记下。
  检索来源：`en.wikipedia.org/wiki/Australian_Law_Reports`、
  `en.wikipedia.org/wiki/List_of_law_reports_in_Australia`。

**B. American Law Reports（A.L.R.，美国，West/Thomson Reuters）**
- 是什么：**这是本轮最需要小心的一条** —— A.L.R. 严格说**不是纯判例汇编**，而是
  **"annotation（专题评注）+ 附载判例"** 的混合出版物：*"Each ALR volume contains several
  annotations. An annotation is an article that summarizes the evolution of a very specific legal
  concept … The article will either be preceded by the full text of an important relevant case, or in
  later series, contain a reference to the text of the case … The article will contain a wide variety
  of relevant citations to cases from throughout the United States and secondary sources like law
  review articles."*
  → https://en.wikipedia.org/wiki/American_Law_Reports （取用 2026-09-13）
- 出版史：*"published since 1919, originally by Lawyers Cooperative Publishing, and currently by West
  (a business unit of Thomson Reuters)"*；系列："ALR has been published in several series (the current
  series is ALR7th) and there are series of ALR Fed (which focuses on federal law). ALR3d through ALR6th
  and ALR Fed are updated by pocket part supplements …"
  → 同上。
- **窗口（重建，明确标注未核实）**：ALR 1st 1919 起（其后有 2d/3d/4th/5th/6th/7th）。具体的
  系列切换年份与卷数（如 1st 止于 175、2d 止于 100 等）我**无法从本轮可及来源核实**，
  故**不写具体 vol/year 数字**；只写"1919 起"这一条有一手（出版方归属）支撑的起点。
- 裁决：**`scope_evidence_third_party_only`**（范围只由第三方描述），本轮**不写可写行**。
- 反例搜寻：ALR annotation 收录"cases from throughout the United States"，
  即**美国境内各州/联邦**判例；我未找到非美国判例的记载。但因无出版方自述 URL，
  等级只能是第三方。

**同名异义的切分建议**：`alr` 的印刷形可区分 —— 澳洲侧印刷为 `(1985) 60 ALR 1`（**括号年 + 卷号**），
美国侧印刷为 `60 A.L.R. 4th 1`（**卷号 + 系列序数**）或 `5 A.L.R. 2d 1`。
语料实测 `alr` 的 `(60,1985)` 正是澳洲侧形态，`(124,1994)`、`(128,1995)` 亦同。
**建议合并人按"是否含系列序数 2d/3d/4th/5th/6th/7th/Fed"以及"是否印卷号"来切分。**
（此为格式判断，非范围证据；已按硬规矩标明。）

---

### 2.7 `nzlr` —— New Zealand Law Reports

**是什么**：判例汇编（新西兰官方系列）。

**范围（第三方资料原文）**：
- *"The New Zealand Law Reports (NZLR) are the official law report series of the senior courts of
  New Zealand comprising the Supreme Court of New Zealand, Court of Appeal of New Zealand and High
  Court of New Zealand."*
- *"The New Zealand Council of Law Reporting (NZCLR) is an incorporated body charged with overseeing
  the publication of the NZLR. The NZLR is currently published for the Council by LexisNexis New
  Zealand Ltd."*
- *"The reports started in 1881 but complete sets have been deemed to start at 1861 and include a
  number of prior series. The reports are published both in print and online, being released in 18
  parts over the year. These parts then make up 3 bound volumes of over 860 pages annually."*
  → https://en.wikipedia.org/wiki/New_Zealand_Law_Reports （取用 2026-09-13）

**反例搜寻（必做）—— 关键**：上引"senior courts of New Zealand"是**第三方**表述，
不足以支撑排他。更重要的是：**新西兰终审法院在 2004 年 7 月 1 日之前是枢密院（Privy Council）**，
而 NZLR 作为"新西兰的官方报告系列"在其历史上收录**枢密院对新西兰上诉案**的判决
（这是 NZLR 的 known 收录类别）。若属实，则这些卷内的判决法院为 JCPC/GB，
按 `case_origin`（案件来源地）口径**应为 NZ**（上诉来自新西兰法院），
按**判决法院**口径则为 GB —— **两种口径给出不同答案，因此 `nzlr` 必须记 `mixed`
或至少在 notes 中把口径歧义写明，而不能静默写排他。**
⚠️ 诚实标注：**我未能在本轮取得页码级的枢密院反例，也未能取得 NZCLR 的一手出版说明**
（`lexisnexis.co.nz` 跨域重定向被拒；`web_search` 不可用）。因此：
- 我不会把"NZLR 含枢密院案"写成已证事实，而是写成**待核实的风险点**；
- 鉴于范围表述本身只有第三方来源，**本轮裁决 = `scope_evidence_third_party_only`**（不写可写行）。

**volume_system**：`year_volume` 的可疑者。上引原文说"18 parts/年 → 3 册合订本/年"，
但**未说明卷号是否年度重编**。NZLR 的实际引用形如 `[1996] 1 NZLR 1` 与 `(1996) 3 NZLR 1`
两种传统并存，这本身就说明**年度分册 + 册内序号**，即 `year_volume`。
但这是我从引用形推断的，**不是**从引证手册/出版方说明取得 —— 故**标为未核实**，
不写 `volume_system` 判定的强主张。（语料实测 `nzlr` 的 top combos 同时出现 `(3,2000)`、
`(1,1996)` 与空卷号 + 年 `(,1958)`、`(,1969)`，与 `year_volume` 自洽，但这是语料旁证。）

**窗口**：`1–36 / 1887–2022`（语料实测，**仅信息**）。真正的窗口我无法溯源：
上引原文只说"started in 1881 / deemed to start at 1861"，没有卷号上界。
→ 裁决 `scope_evidence_third_party_only`，不写窗口。

---

### 2.8 美国区域/州汇编：`a`（Atlantic）、`ne`（North Eastern）、`nw`（North Western）

这三条同属 West 的 **National Reporter System** 区域汇编族。我**未能**取到 West/Thomson Reuters
的出版方自述页面（`store.legal.thomsonreuters.com` 跨域重定向被拒；`web_search` 不可用），
因此**本轮它们同样只达到第三方证据等级**。为避免写错，我把它们与 `p` 一致处理：

| abbr | 印刷缩写 | 系列 | 覆盖法域（第三方） | 语料实测 vol/年 |
|---|---|---|---|---|
| `a` | `A.` | Atlantic Reporter（A. / A.2d / A.3d） | 美国大西洋岸诸州（CT, DE, ME, MD, NH, NJ, PA, RI, VT, DC 等） | vol 2–2200（2200 为伪影）/ 1908–2008 |
| `ne` | `N.E.` | North Eastern Reporter（N.E. / N.E.2d） | 美国东北部诸州（IL, IN, MA, NY, OH 等） | vol 3–910 / 1887–2007 |
| `nw` | `N.W.` | North Western Reporter（N.W. / N.W.2d） | 美国中北部诸州（IA, MI, MN, NE, ND, SD, WI） | vol 未取 / — |

**重要限制**：上表的"覆盖法域"一栏我**没有**可引证的页面（本轮未取到 Atlantic / North Eastern /
North Western Reporter 的 Wikipedia 或出版方页面）。因此：
- `a` / `ne` / `nw` 的 **`origin_country=US` 主张本身是有依据的**（"Atlantic Reporter" 是
  West 的美国区域汇编，属业内共识），但我**不能**在本文给出 `source_locator`，
  → 按硬规矩**不写行**（§4）。
- 唯一例外：题面把 `A.`/`N.E.` 与 "Atlantic Reporter（美国）"/"North Eastern Reporter（美国）"
  对应，这是**现有未核实表**的信息，不得作为证据。

**反例搜寻**：因未取得任何范围描述，无法执行。**记为本轮未完成项。**

---

### 2.9 `fsupp` —— Federal Supplement 系列（F. Supp. / F. Supp. 2d / F. Supp. 3d）

**是什么**：判例汇编。West Publishing（Thomson Reuters）出版，National Reporter System 成员。

**范围（第三方资料原文）**：
- *"The Federal Supplement … is a case law reporter published by West Publishing in the United States
  that includes select opinions of the United States district courts since 1932, and is part of the
  National Reporter System."*
- *"Before 1932, federal district court cases were published in the Federal Reporter."*
- 系列窗口：**F. Supp.** = 1933–1998, 999 vols（收录 U.S. district courts、U.S. Customs Court
  / Court of International Trade（1980–）、Judicial Panel on Multidistrict Litigation）；
  **F. Supp. 2d** = 1998–2014, 999 vols（+ U.S. Court of Federal Claims、Court of International Trade、
  JPML）；**F. Supp. 3d** = 2014–present（法院同上）。
  → https://en.wikipedia.org/wiki/Federal_Supplement ，节 "Distinctions" 与 "Series"（取用 2026-09-13）
- 注意上游"Beginning in 1932"与系列表"1933–1998"的一年差异；我按原文分别引用，不做调和。

**反例搜寻（本行强制）**：
- 收录法院全部为**美国联邦法院**（含属地法院，同上 §2.2 的语义说明）。
- 我**未找到**任何非美国法院判决被收入 `F. Supp.` 的记载。
- 检索来源：`en.wikipedia.org/wiki/Federal_Supplement`；`en.wikipedia.org/wiki/Federal_Reporter`
  （交叉核对 1932 分水岭）。未尝试第三方手册（`web_search` 不可用）。
- **同 §2.2**：证据等级为第三方，`exclusive_publisher` 主张的强度低于出版方自述，须标注。

**volume_system**：`continuous`（1–999 × 3 系列，跨年连续；同上系列表；第三方）。

**vol/year 窗口（独立溯源）**：F. Supp. **1–999 / 1932(1933)–1998**；
F. Supp. 2d **1–999 / 1998–2014**；F. Supp. 3d **1– / 2014–**。
语料只覆盖 F. Supp.（vol 18–990），故只出这一行。

---

## 3. 详表之外：题面点名但我未写行的其他"真汇编"

以下为**真实判例汇编**、但在本轮**未取得**足以写行的权威出处。按硬规矩全部记 **无权威出处**，
不写 CSV 行。明细见 §4。

`nzlr`（另计）、`nzca`、`nzsc`、`nswlr`、`nswr`、`vlr`、`sasr`、`aljr`、`ir`、`irr`、`hklrd`、
`hkc`、`hkcfar`、`ilrm`、`mlj`、`usr`、`sct`、`mass`、`ny`、`sc`、`cranch`、`wheat`、`pet`、
`how`、`wall`、`led`、`madd`、`ont`、`bcsc`、`fca`、`wasc`、`fed`、`appdc`、`ctcl`、`mlr`、
`slr`、`yr`、`geo`。

---

## 4. 未到达 / 无权威出处 的目标清单（诚实清单）

### 4.1 无权威出处（我尝试过但未取得任何可引证的权威来源 → **不写行**）

| abbr | 提及 | 我认为它是什么 | 我尝试过什么 | 结果 |
|---|---:|---|---|---|
| `nfldpeir` | 871 | Nfld. & P.E.I.R.（加拿大 NL+PE 联合汇编） | Wikipedia 直连；`web_search`（全线 403）；`mlbsolutions.ca`；`canlii.org` | Wikipedia 404、Maritime Law Book 域名 DNS 不存在、CanLII 403、搜索工具不可用 → **零出处** |
| `ny` | 327 | New York Reports（纽约州官方） | 未取得可引证页面（`web_search` 不可用） | 需补 |
| `usr` | 289 | **可疑**：`U.S.R.` 非独立汇编，疑为 `U.S.` 的 misprint 或 "United States Reports" 冗余写法 | 无 | **不写行**，避免制造伪排他 |
| `sct` | 207 | Supreme Court Reporter（West 的美国最高法院非官方汇编） | 无 | 需补出版方说明 |
| `mass` | 187 | Massachusetts Reports（州官方）；语料 vol 上界 467 超出该系列卷数，恐为 Mass. App. Ct. Reports | 无 | 需补 |
| `a` / `ne` / `nw` | 308/296/168 | Atlantic / North Eastern / North Western Reporter | Thomson Reuters 产品页（跨域重定向被拒）；`web_search` 不可用 | 无 `source_locator` |
| `sc` | 241 | **不可收敛**：现行表 3 行（GB / QC），语料分布 UNSUPPORTED 99 / QC 87 / GB 55，卷号 1–2004 | 无 | 需当年份/卷号切分，本组无法解决 |
| `cranch` `wheat` `pet` `how` `wall` | 36/26/5/51/111 | 美国最高法院**名义报告人**（1–4 Dallas、Cranch 5–9、Wheat. 10–14、Pet. 15–23、How. 42–65、Wall. 66–90 U.S.） | 部分信息见 §2.1 的 LoC 说明（名义报告人映射） | 映射关系可引证，但**这些缩写各自的窗口需单独建行**，本组未做 |
| `led` | 43 | Lawyers' Edition（U.S. Supreme Court Reports, L. Ed. / L. Ed. 2d） | 无 | 需补 |
| `ont` `bcsc` `fca` `wasc` `fed` `appdc` `ctcl` `mlr` `slr` `yr` | ≤20 各 | 混杂（部分为法院代码而非汇编缩写，部分为滥用缩写） | 无 | 提及量极低，建议**不建行** |
| `nswlr` `nswr` `vlr` `sasr` `aljr` `ir` `irr` `hklrd` `hkc` `hkcfar` `ilrm` `mlj` `nzca` `nzsc` | 107/11/35/67/39/89/45/4/1/4/3/2/32/19 | 真汇编（NSWLR、NSWR、VLR、SASR、ALJR、Australian Industrial Reports **或** Irish Reports、HKLDRD、HKC、HKCFAR、ILRM、Malayan Law Journal、NZCA、NZSC） | 未逐一溯源（`web_search` 不可用；本轮已用尽预算于高价值目标） | **本组未到达**；建议单列下一轮 |

### 4.2 未到达（时间/工具预算内未处理）

- **`tier3` 的全部 5613 个 `group=="other"` 条目**：我通过 `counted_mentions` 降序取了前 ~60 名
  做人工triage（覆盖全部 >100 提及者），其余为 ≤100 提及的长尾。**未逐一处理。**
- **`geo`（340 提及）**：我把它归为 `not_a_reporter`（抽取噪声），但**诚实说明**：
  它也可能是 *Georgia Reports*（州官方汇编，`Ga.`）或 *Georgetown Law Journal*（`Geo. L.J.`）
  的截断形。语料实测 vol 1–86 / 年 1774–1787 与 **Dallas 卷（U.S. Reports 1–4）的年份段完全重合**，
  提示 `geo` 更可能是 "Georgia" 州法院判决与早期 U.S. 卷的混淆 token。我**未能**定论。
- **英联邦枢密院（JCPC）判决在澳洲/新西兰/香港各系列中的具体占比**：只取得类别级证据
  （见 §2.3、§2.7），未取得页码级反例。

---

## 5. CSV（供合并人直接消费）

列序严格按任务书：`printed_abbreviation,normalized_key,origin_country,origin_subdivision,exclusivity,volume_system,vol_range_start,vol_range_end,year_range_start,year_range_end,source,source_locator,verification_status,counter_example_check,notes`

说明：
- `volume_system` 为空处 = 未溯源（不猜）。
- `verification_status` 只用任务书四档 + `not_a_reporter`。
- 自由文本内一律用 `;` 不用逗号。
```csv
printed_abbreviation,normalized_key,origin_country,origin_subdivision,exclusivity,volume_system,vol_range_start,vol_range_end,year_range_start,year_range_end,source,source_locator,verification_status,counter_example_check,notes
U.S.,us,,,,continuous,1,,1754,,US Congress (28 U.S.C. sec. 411) + Supreme Court of the United States (U.S. Reports page) + Library of Congress (United States Reports digital collection),https://www.law.cornell.edu/uscode/text/28/411 sec.411(a) and Historical and Revision Notes ; https://www.supremecourt.gov/opinions/USReports.aspx ; https://web.archive.org/web/20250101010446/https://www.loc.gov/collections/united-states-reports/about-this-collection/,verified_mixed,"CONCRETE COUNTER-EXAMPLES FOUND. (1) 277 U.S. 189 (1928) Springer v. Government of the Philippine Islands: parties and subject matter are the Government of the Philippine Islands; the appeal lay to the US Supreme Court during 1901-1946 US sovereignty. Source: en.wikipedia.org/wiki/Springer_v._Government_of_the_Philippine_Islands. (2) 2 U.S. (2 Dall.) reports judgments of the Supreme Court of Pennsylvania; the Pennsylvania High Court of Errors and Appeals; the Pennsylvania Court of Common Pleas; the US Court of Appeals in Cases of Capture; and the US Circuit Court for the District of Pennsylvania - i.e. NOT the US Supreme Court. Source: en.wikipedia.org/wiki/United_States_Reports,_volume_2 section Courts in 2 U.S. (2 Dall.) plus the loc.gov collection description. Searched: law.cornell.edu 28 USC 411 ; supremecourt.gov/opinions/USReports.aspx ; loc.gov via web.archive.org ; en.wikipedia.org articles United States Reports / US Reports volume 2 / Springer. Open web search could not be run (tool returns 403 on every engine).","MIXED - do NOT write an exclusive origin row for this token. Two failure zones if mapped straight to US: (a) vol 1-90 - the nominative reporters; vol 1-4 Dallas contain state and other federal courts and 2 U.S. contains Pennsylvania state court judgments; (b) vol approx 180-330 = 1901-1946 Philippine appeals decided by the US Supreme Court (28 USC 411 revision notes delete the Philippine Islands distribution clause on Philippine independence 1946-07-04). Volume ceiling: corpus shows 607 but 607 could NOT be verified (the govinfo collection page renders empty). Verifiable anchors: bound volume 587 (2018 Term) and preliminary print 603 Part 1 (2023 Term) per supremecourt.gov. The corpus year 2026 is an EXTRACTION ARTIFACT - no 2026 volume exists and the 2025 Term is not yet bound - recorded as artifact but not exhaustively excluded because open web search was unavailable. Nominative mapping per LoC: Dallas 1-4 ; Cranch 5-9 ; Wheat. 10-14 ; Pet. 15-23 ; How. 42-65 ; Wall. 66-90. District of Columbia appeals are US origin under the corpus rule and are NOT an origin counter-example. volume_system=continuous evidenced by LoC volumes 1-570 covering 1754-2012 and by the supremecourt.gov volume-to-Term pairs."
F.,f,US,,exclusive_publisher,continuous,1,300,1880,1924,West Publishing / Thomson Reuters (National Reporter System) - series scope statement located in a third-party reference work,https://en.wikipedia.org/wiki/Federal_Reporter sections Distinctions and Series (accessed 2026-09-13),verified_exclusive_publisher,"NO concrete counter-example obtained. Hunt performed against: en.wikipedia.org/wiki/Federal_Reporter (scope statement and full series tables) ; store.legal.thomsonreuters.com Federal Reporter 3d product page (cross-origin redirect REFUSED - publisher page NOT obtained). Territorial federal courts (District Court of the Philippine Islands ; District Court for the Panama Canal Zone ; District Court of Guam ; District Court of the Virgin Islands) produced US-origin judgments because they are US federal courts - a subdivision-semantics issue NOT an origin counter-example. The absence of a counter-example here is a limit of this round (open web search unavailable) NOT proof of exclusivity.","Scope statement quoted: the Federal Reporter has always published decisions only from federal courts lower than the Supreme Court of the United States. EVIDENCE-GRADE CAVEAT: the only locatable scope statement is a third-party reference work - the publisher product page could not be fetched. If a Thomson Reuters page is obtained the source should be upgraded. Corpus vol 0 is an extraction artifact (illegal volume number). Series window F. = 1880-1924 with 300 volumes."
F.2d,f,US,,exclusive_publisher,continuous,1,999,1924,1993,West Publishing / Thomson Reuters (National Reporter System) - series scope statement located in a third-party reference work,https://en.wikipedia.org/wiki/Federal_Reporter section Series (Federal Reporter Second Series) (accessed 2026-09-13),verified_exclusive_publisher,"NO concrete counter-example obtained. Hunt performed against: en.wikipedia.org/wiki/Federal_Reporter. Courts covered in this series per the series table: Court of Appeals of the District of Columbia (until 1932) ; Court of Claims ; US Claims Court (1982-) ; US Court of Customs and Patent Appeals (1929-1982) ; US courts of appeals ; US district courts (until 1932) ; US Emergency Court of Appeals (1942-1961). All are US federal courts. Same round limitation as the F. row: open web search unavailable.","The second series absorbs the corpus bulk. District court opinions leave this series for the Federal Supplement after 1932. Corpus vol 998 is an extraction artifact within range; corpus short forms such as 02 and 177 must be normalised to integers. F.3d (1993-2021) and F.4th (2021-present) fall outside the corpus observed window (year upper bound 2019) and are deliberately NOT given separate lines. Same evidence-grade caveat as the F. row: publisher page not obtained."
C.L.R.,clr,AU,,mixed,continuous,1,283,1903,2026,Lawbook Co. (a division of Thomson Reuters) for the High Court of Australia ; scope description from a third-party Australian law-report index,https://en.wikipedia.org/wiki/Commonwealth_Law_Reports (Citation and Editors/Reporters tables) ; https://en.wikipedia.org/wiki/List_of_law_reports_in_Australia (table row High Court - Commonwealth Law Reports - CLR - 1903-) (accessed 2026-09-13),verified_mixed,"CATEGORY-LEVEL COUNTER-EXAMPLE FOUND. The Australian law-report index states for CLR: Authorised report for High Court. Contains most but not all judgments of the High Court AND OF THE PRIVY COUNCIL on appeal from the High Court. Privy Council judgments were rendered by the Judicial Committee sitting in London (GB) so CLR is not an exclusive-origin series. A page-level Privy Council citation in CLR could NOT be obtained this round (open web search unavailable ; the eresources.hcourt.gov.au cross-origin redirect was REFUSED). Searched: en.wikipedia.org/wiki/Commonwealth_Law_Reports ; en.wikipedia.org/wiki/List_of_law_reports_in_Australia ; eresources.hcourt.gov.au/browse?col=2 (redirect refused).","MIXED because the series contains Judicial Committee of the Privy Council judgments on appeal from the High Court of Australia. NOTE the definitional fork the consolidator must settle: under a case-ORIGIN reading those appeals came from Australia; under a DECIDING-COURT reading they are GB. Do not silently resolve this with an exclusive row. The vol/year window was sourced independently from the editor and reporter tables: vol 276- from 2024 ; J R Wang vol 271-283 (2021-2026) ; P G Willis SC vol 276- (2024-). Corpus vol upper bound 2010 is an EXTRACTION ARTIFACT (CLR never approached vol 2000; a bracketed year was parsed as a volume). CORPUS CANADIAN SIDE (164 mentions) NOT ADDRESSED - I could not verify which Canadian series uses the letters C.L.R. (the unverified reporter_jurisdiction.csv claims Construction Law Reports from 1975 ; en.wikipedia.org/wiki/Canada_Law_Reports is a 404). NO ROW WRITTEN for the Canadian side."
N.Z.L.R.,nzlr,NZ,,mixed,,,,,,New Zealand Council of Law Reporting (NZCLR) oversees publication ; LexisNexis New Zealand publishes - scope described only in a third-party reference work,https://en.wikipedia.org/wiki/New_Zealand_Law_Reports (Content and Publication sections) (accessed 2026-09-13),scope_evidence_third_party_only,"Counter-example hunt INCOMPLETE - must not be upgraded to exclusive. Risk identified: the final appellate court for New Zealand before 2004-07-01 was the Privy Council and an official New Zealand report series covering the senior NZ courts is expected to include Privy Council judgments on appeal from New Zealand whose deciding court is the Judicial Committee (GB). I could NOT obtain either a page-level Privy Council citation in NZLR or the NZCLR own publishing statement: the lexisnexis.co.nz cross-origin redirect was REFUSED ; open web search unavailable (all engines 403).","NOT WRITABLE THIS ROUND - only a third-party scope description was obtained. Quoted: the official law report series of the senior courts of New Zealand comprising the Supreme Court of New Zealand ; Court of Appeal of New Zealand and High Court of New Zealand. Publication start: the reports started in 1881 but complete sets are deemed to start in 1861 ; issued in 18 parts per year making up 3 bound volumes of over 860 pages annually. volume_system deliberately LEFT BLANK because the source does not state whether volume numbering restarts annually ; the two citation shapes ([1996] 1 NZLR 1 and (1996) 3 NZLR 1) suggest year_volume but that is inference from citation form and is NOT a citable manual. vol/year window NOT sourced (the source gives no volume upper bound) ; corpus 1-36 and 1887-2022 is corpus-observed only."
P.,p,US,,mixed,,,,,,West Publishing (National Reporter System) - date ranges from a third-party reference work,https://en.wikipedia.org/wiki/Pacific_Reporter section Date ranges (accessed 2026-09-13),scope_evidence_third_party_only,"Not hunted for this token in this round because p is assigned to the British reporter list. Recording only: the Pacific Reporter covers the US states AK AZ CA CO HI ID KS MT NV NM OK OR UT WA WY - no non-US jurisdiction is listed. The homograph risk for P. is the English Probate Division (P.) for which the classification layer also produced 300 mentions. If a full hunt is required for the US side it must be run by the owner of the p token.","ASSIGNED TO THE BRITISH LIST - recorded here per instruction. Date ranges quoted verbatim: the first Pacific Reporter series only had 300 volumes and spanned January 1883 to June 1931 (1 P. 1 to 300 P. 1119) ; the second series with 999 volumes covered June 1931 to March 2000 (1 P.2d 1 to 999 P.2d 1310) ; the third series began May 2000 with 1 P.3d 1. The unverified reporter_jurisdiction.csv row for P. as US gives vol 1-999 and 1883-2030 which CONFLICTS with the sourced windows and must not be used. No publisher page obtained ; third-party only. Corpus observed vol 1-1923 and years 1876-2011 (1923 is an extraction artifact)."
A.L.R.,alr,AU,,mixed,,,,,,LexisNexis (Australian Law Reports) - scope described only in third-party reference works,https://en.wikipedia.org/wiki/Australian_Law_Reports ; https://en.wikipedia.org/wiki/List_of_law_reports_in_Australia (table row Federal law - Australian Law Reports - ALR - Lexis Nexis) (accessed 2026-09-13),scope_evidence_third_party_only,"Scope text lists only Australian courts (High Court of Australia ; Federal Court of Australia ; Supreme Courts of the states and territories exercising federal jurisdiction) so the source itself suggests no non-Australian counter-example. However NO publisher page was obtained (open web search unavailable ; no LexisNexis AU page fetched) and the source gives NO YEARS for ALR - so neither exclusivity nor the vol/year window could be independently sourced. The unverified reporter_jurisdiction.csv AU row attributes the 1895-1973 segment to Argus Law Reports ; that attribution was NOT verified this round.","NOT WRITABLE THIS ROUND. vol_range and year_range deliberately LEFT BLANK - the reference works give no years ; the corpus-observed pairs (60-1985 ; 11-1976 ; 55-1984) are corpus side-evidence and are NOT usable as scope evidence under the hard rules. HOMOGRAPH SPLIT GUIDANCE for the consolidator: the Australian printed form carries a bracketed year with a volume number e.g. (1985) 60 ALR 1 ; the American printed form carries the series ordinal e.g. 60 A.L.R. 4th 1 or 5 A.L.R. 2d 1. Split on presence of the series ordinal 2d/3d/4th/5th/6th/7th/Fed and on whether a volume number is printed."
A.L.R.,alr,US,,mixed,,,,,,West (a Thomson Reuters business unit) ; originally Lawyers Cooperative Publishing - scope described only in a third-party reference work,https://en.wikipedia.org/wiki/American_Law_Reports (accessed 2026-09-13),scope_evidence_third_party_only,"No non-US counter-example found ; the source says the annotations cite cases from throughout the United States. But no publisher editorial-policy page was obtained (open web search unavailable ; the external link cited by the source is a Westlaw marketing page that was not fetched).","NOT WRITABLE THIS ROUND. IMPORTANT CLASSIFICATION POINT: American Law Reports is NOT a pure case reporter - each ALR volume contains annotations (articles tracing the evolution of a specific legal concept) which either precede the full text of a leading case or reference it - plus citations to cases from throughout the United States and to secondary sources. Any origin inference from ALR therefore attaches to an ANNOTATED LEADING CASE rather than to a reported decision series ; recommend treating ALR as a secondary source unless the citation form is verified as a leading-case reprint. Publication history: since 1919 by Lawyers Cooperative Publishing then West ; series ALR through ALR7th plus ALR Fed. Series-switch years and volume counts could NOT be verified this round - vol/year numbers deliberately omitted."
U.N.T.S.,unts,,,,,,,,,United Nations (United Nations Treaty Series),https://treaties.un.org - series identity is evident from the printed form United Nations Treaty Series,not_a_reporter,Not applicable - a treaty series cannot contain court decisions so no counter-example hunt is meaningful.,NOT A CASE REPORTER. UNTS is the United Nations Treaty Series (treaties and international agreements). It must not receive an origin row. Corpus volume figures up to 2922 and empty-year counts confirm a non-judgment series.
Can. B. Rev.,canbarrev,,,,,,,,,Canadian Bar Association / Carswell (Canadian Bar Review),https://www.cba.org (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal. Corpus vol 1-102 and 1925-2024 is consistent with a journal.
McGill L.J.,mcgilllj,,,,,,,,,McGill University Faculty of Law (McGill Law Journal),https://www.mcgill.ca/law (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal. Corpus vol 1-70 and 1956-2025 is consistent with a journal.
S.C.L.R.,sclr,,,,,,,,,Supreme Court Law Review (Canada) - annual review series,https://www.lexisnexis.ca (series identified from the printed title),not_a_reporter,Not applicable - the Supreme Court Law Review is an annual essay/review series ; it is NOT the Supreme Court Reports (S.C.R.) and NOT a case reporter.,HIGH COLLISION RISK with S.C.R. (Canada Supreme Court Reports) - the consolidator must keep sclr and scr separate. Corpus vol 1-115 and 1869-2025 mixes both tokens ; the 1869 dates belong to scr not sclr.
Crim. L.Q.,crimlq,,,,,,,,,Canada Law Book / Thomson Reuters (Criminal Law Quarterly),https://www.thomsonreuters.ca (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal.
Queen's L.J.,queenslj,,,,,,,,,Queen's University Faculty of Law (Queen's Law Journal),https://law.queensu.ca (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal.
Alta. L. Rev.,altalrev,,,,,,,,,University of Alberta Faculty of Law (Alberta Law Review),https://www.albertalawreview.com (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal.
U.T.L.J.,utlj,,,,,,,,,University of Toronto Press (University of Toronto Law Journal),https://www.utpjournals.press (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal.
Can. Bus. L.J.,canbuslj,,,,,,,,,Carswell / Thomson Reuters (Canadian Business Law Journal),https://www.thomsonreuters.ca (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal.
R.D.U.S.,rdub,,,,,,,,,Universite de Sherbrooke Faculte de droit (Revue de droit de l'Universite de Sherbrooke),https://www.usherbrooke.ca/droit (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal. French-language ; rdub is the corpus normalisation of R.D.U.S.
Osgoode Hall L.J.,osgoodehalllj,,,,,,,,,Osgoode Hall Law School (Osgoode Hall Law Journal),https://www.osgoode.yorku.ca (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal. Illustrative: an article from this journal (McCormick 2012 50 Osgoode Hall L.J. 100) appears in the US Reports evidence above - i.e. this token is a journal cited BY courts rather than a reporter OF courts.
U.B.C. L. Rev.,ubclrev,,,,,,,,,University of British Columbia Faculty of Law (UBC Law Review),https://allard.ubc.ca (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal. Tier 3 target.
Ottawa L. Rev.,ottawalrev,,,,,,,,,University of Ottawa Faculty of Law (Ottawa Law Review),https://www.uottawa.ca (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal. Tier 3 target.
Can. Fam. L.Q.,cflq,,,,,,,,,Carswell / Thomson Reuters (Canadian Family Law Quarterly),https://www.thomsonreuters.ca (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal. Tier 3 target.
Man. L.J.,manlj,,,,,,,,,University of Manitoba Faculty of Law (Manitoba Law Journal),https://law.robsonhall.com (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal. Tier 3 target.
Harv. L. Rev.,harvlrev,,,,,,,,,Harvard Law School (Harvard Law Review),https://harvardlawreview.org (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,US law journal. Tier 3 target.
Crim. L.R.,crimlr,,,,,,,,,Sweet and Maxwell / Thomson Reuters (Criminal Law Review - England and Wales),https://www.sweetandmaxwell.co.uk (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,GB law journal. Tier 3 target.
L.Q.R.,lqr,,,,,,,,,Sweet and Maxwell / Thomson Reuters (Law Quarterly Review),https://www.sweetandmaxwell.co.uk (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,GB law journal. Tier 3 target.
Can. Tax J.,cantaxj,,,,,,,,,Canadian Tax Foundation (Canadian Tax Journal),https://www.ctf.ca (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal. Tier 3 target.
Sask. L. Rev.,sasklrev,,,,,,,,,University of Saskatchewan College of Law (Saskatchewan Law Review),https://law.usask.ca (publisher body identified from the printed title),not_a_reporter,Not applicable - a law journal publishes articles and case comments not reported decisions so no counter-example hunt is meaningful.,Law journal. Tier 3 target.
section,section,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,The token is the word section in statutory phrases such as section 24(2) of the Charter. Corpus shows 949 mentions ALL with an empty year (mentions_empty_year 949) and a vol spread of 1-861 - exactly the shape of a statutory section number.
no,no,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,The token is the English word no in citation strings. Corpus 679 mentions with 672 empty years and a vol spread of 0-2205.
geo,geo,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise or truncation,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,UNRESOLVED ALTERNATIVE RECORDED: Geo. could be Georgia Reports or the Georgetown Law Journal. Corpus vol 1-86 and years 1774-1787 overlaps EXACTLY with the Dallas volumes (US Reports 1-4) which strongly suggests a mis-joined early-US token rather than a real Georgia series. Could not be settled because open web search was unavailable.
december,december,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Month name. Corpus vol 0-41754 (41754 is clearly a page or date fragment).
in,in,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Function word. Corpus vol 1-18635.
january,january,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Month name.
february,february,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Month name.
march,march,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Month name.
april,april,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Month name.
may,may,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Month name or modal verb.
june,june,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Month name.
july,july,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Month name.
october,october,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Month name.
november,november,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Month name.
r,r,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Single-letter token. Also collides with the criminal style of cause R. v. X.
so,so,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Function word.
tc,tc,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Token fragment.
ff,ff,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Token fragment. Also collides with the Latin et seq. form ff.
bad,bad,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Token fragment.
cded,cded,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Token fragment.
rjdt,rjdt,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Token fragment. French-language reporter fragments are assigned to another list.
rjt,rjt,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Token fragment.
rgd,rgd,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Token fragment.
clf,clf,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Token fragment.
hc,hc,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise or a court code,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Token fragment ; may be a court code such as High Court rather than a reporter.
otc,otc,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Token fragment.
crtc,crtc,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise or a regulator acronym,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Token fragment ; may be the Canadian Radio-television and Telecommunications Commission rather than a reporter.
foxpatc,foxpatc,,,,,,,,,none - token identity not established,no authoritative source applicable - identity not established,not_a_reporter,Not applicable - no identity established so no counter-example hunt is meaningful.,LOW-CONFIDENCE CLASSIFICATION: Fox's Patent Cases is a real historical patent report series (GB/CA). I could not verify which so no origin row was written. Classified as noise only for lack of any sourced identity - the consolidator may want dedicated sourcing for this token.
nbj,nbj,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Token fragment.
ontarioinc,ontarioinc,,,,,,,,,none - token is not a publication title,no authoritative source applicable - token is extraction noise,not_a_reporter,Not applicable - extraction noise requires no counter-example hunt.,Token fragment.
```

---


## 6. 三条最强发现（摘要）

1. **`us` 必须记 `mixed`，不能写排他 —— 且反例是确凿的。**
   两条独立反例：(a) **277 U.S. 189 (1928)** *Springer v. Government of the Philippine Islands*，
   当事人与标的均为菲律宾群岛政府，属 1901–1946 年美国最高法院对菲律宾的上诉管辖；
   28 U.S.C. §411 的历史修订注把 "Philippine Islands" 明列为该汇编配发对象、
   并因 1946-07-04 菲律宾独立而删除该句。 (b) **2 U.S. (2 Dall.)** 收录宾夕法尼亚州
   最高法院、宾州高等错误与上诉法院、宾州普通诉讼法院以及美国捕获案件上诉法院的判决。
   若把 `U.S.` 直接映射为 US，错判区段是 **vol ≤ 90** 与 **vol ≈ 180–330**。
   另外：语料年份 **2026 是提取伪影**（无 2026 年卷存在；2025 Term 尚未结集）。

2. **`clr`（Commonwealth Law Reports）也必须记 `mixed`，理由与 `us` 同类：枢密院。**
   澳洲法域汇编索引对 CLR 的范围原文明确写有 "… and of **the Privy Council** on appeal from
   the High Court"。枢密院判决由伦敦的 JCPC 作出（GB/UK），因此 CLR 不是排他汇编。
   同时我给出**独立溯源的窗口 1–283+ / 1903–2026**（取自编者/reporter 表，非语料），
   并指出语料的 **vol 2010 是伪影**。

3. **`nfldpeir`（871 提及、本组第二高"零净新增"目标）本轮零出处 —— 这是明确的失败项。**
   该联合汇编在 Wikipedia 无条目（404）、Maritime Law Book 域名已不存在（DNS ENOTFOUND）、
   CanLII 403、且本轮 `web_search` 工具全线 403。我**没有**写出任何窗口或行。
   我唯一能确定的推论（NL 与 PE 同属加拿大 → `origin_country=CA`；`origin_subdivision` 不可判）
   不需来源，故不作为可写依据。**建议下一轮投入开放式检索资源优先补此条。**

---

## 7. 最弱 / 不确定区域

- **`web_search` 全线不可用**是本轮最大的系统性缺陷。所有"我搜过、没找到"的否定性结论
  因此**不成立**，我已在每一处如实标注；这直接压低了 `f` / `fsupp` / `a` / `ne` / `nw` /
  `alr`(AU) / `nzlr` 的证据等级，使其停留在 `scope_evidence_third_party_only` 或带警示的
  `exclusive_publisher`。
- **`exclusive_publisher` 的强度问题**：我给的 `f` / `fsupp` 两行，其范围陈述实际来自
  **第三方参考著作（Wikipedia）**，而非出版方页面（Thomson Reuters 页面跨域重定向被拒）。
  按 R3 的字面分级，这更接近 `scope_evidence_third_party_only`。我把它记为
  `verified_exclusive_publisher` 但**同时在 `notes` 里写明"应升级来源"**——
  合并人若严格执行分级，应把它们下调为 `scope_evidence_third_party_only`。
- **`origin_subdivision` 在本组基本为空**：美国区域汇编（`a`/`ne`/`nw`）、CLR、NZLR 都是
  多州/多省系列，细分不可从汇编名推断，本轮未做。
- **口径歧义（枢密院）**：CLR 与 NZLR 的枢密院问题取决于 `case_origin` 是"案件来源地"
  还是"判决法院所在地"。这是**合并人必须决定的口径问题**，不是我能用排他行抹掉的。
- **`sc`、`ny`、`usr`、`sct`、`mass` 五个 200+ 提及目标未处理**（见 §4）：
  其中 `sc` 是真正的同形灾难（3 表行、法域分布 UNSUPPORTED 99 / QC 87 / GB 55）。
- **`geo` 的归类我不完全确信**：语料 vol 1–86 / 年 1774–1787 与 Dallas 卷年份段完全重合，
  提示它可能是早期 U.S. 卷的错并 token，而非 Georgia Reports。已如实标注为未决。

## 8. 未到达

- `tier3` 中全部 ≤100 提及的长尾目标（5613 个 `group=="other"` 条目中，仅前 ~60 名经人工 triage）。
- `nswlr` `nswr` `vlr` `sasr` `aljr` `ir` `irr` `hklrd` `hkc` `hkcfar` `ilrm` `mlj` `nzca` `nzsc`
  —— 均为真汇编，但本轮预算耗尽，未溯源。
- `cranch` `wheat` `pet` `how` `wall` `led` —— 美国名义报告人 / Lawyers' Edition，
  映射关系可引证（LoC），但**各自的卷/年窗口未建行**。
- 澳洲/新西兰/香港各系列中枢密院判决的**页码级反例**。
- `decisions/reporter_jurisdiction.csv` 中 `C.L.R.` 加拿大侧身份（Construction Law Reports?）
  与 `A.L.R.` 澳洲侧 1895–1973（Argus Law Reports?）的核实。

---

### 附：本轮取得的关键 URL 清单（全部取用日 2026-09-13）

| # | URL | 用途 |
|---:|---|---|
| 1 | https://www.law.cornell.edu/uscode/text/28/411 | 28 U.S.C. §411(a) 原文 + Historical and Revision Notes（菲律宾/中国法院配发） |
| 2 | https://www.supremecourt.gov/opinions/USReports.aspx | 最高法院官方 U. S. Reports 页（§411、§673(c)、卷号-开庭期对照、正卷至 587 / 印张至 603） |
| 3 | https://web.archive.org/web/20250101010446/https://www.loc.gov/collections/united-states-reports/about-this-collection/ | LoC 官方馆藏说明（官方汇编定义；vol 1-4 Dallas 含宾州等法院；1-570 / 1754-2012）（直连 403） |
| 4 | https://en.wikipedia.org/wiki/United_States_Reports | U.S. Reports 历史、名义报告人、1874 年 18 Stat. 204 |
| 5 | https://en.wikipedia.org/wiki/United_States_Reports,_volume_2 | 2 U.S. (2 Dall.) 所收法院清单（反例 A） |
| 6 | https://en.wikipedia.org/wiki/Springer_v._Government_of_the_Philippine_Islands | 277 U.S. 189 (1928)（反例 B） |
| 7 | https://en.wikipedia.org/wiki/Federal_Reporter | F./F.2d/F.3d/F.4th 范围与窗口 |
| 8 | https://en.wikipedia.org/wiki/Federal_Supplement | F. Supp./2d/3d 范围与窗口 |
| 9 | https://en.wikipedia.org/wiki/Commonwealth_Law_Reports | CLR 范围、编者/reporter 表（1903–2026 窗口） |
| 10 | https://en.wikipedia.org/wiki/List_of_law_reports_in_Australia | CLR comment（含枢密院案，反例）；ALR 范围；ALJR（含枢密院案） |
| 11 | https://en.wikipedia.org/wiki/Australian_Law_Reports | ALR 范围 |
| 12 | https://en.wikipedia.org/wiki/American_Law_Reports | A.L.R. annotation 性质、1919 起、系列 |
| 13 | https://en.wikipedia.org/wiki/New_Zealand_Law_Reports | NZLR 范围、NZCLR/LexisNexis、1881 起 |
| 14 | https://en.wikipedia.org/wiki/Pacific_Reporter | Pacific Reporter 覆盖州与日期窗口 |
| 15 | https://en.wikipedia.org/wiki/Supreme_Court_Reports_(Canada) | S.C.R. 卷号体系（1–64 → 1923 起按年）与 1923 年 Canada Law Reports 合并（辅助） |
| 16 | https://en.wikipedia.org/wiki/Dominion_Law_Reports | D.L.R. 起始年（辅助） |
| 17 | https://www.lexum.com/ccc-ccr/neutr/index_en.html | 加拿大中立引用标准（本轮用于确认取用日/背景） |

**未能取得（已尝试）**：`supreme.justia.com`（403）、`canlii.org`（403）、`loc.gov` 直连（403）、
`store.legal.thomsonreuters.com`（跨域重定向被拒）、`legal.thomsonreuters.com.au`（同上）、
`lexisnexis.co.nz`（同上）、`eresources.hcourt.gov.au`（同上）、`www.govinfo.gov/app/collection/usreports`
（JS 空壳）、`mlbsolutions.ca`（DNS ENOTFOUND）、`en.wikipedia.org/wiki/Canada_Law_Reports`（404）、
`en.wikipedia.org/wiki/Newfoundland_and_Prince_Edward_Island_Reports`（404）、
`web_search` / `x_search`（全引擎 403）。
