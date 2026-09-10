# Phase 2 溯源：境外中立引用法院代码

产出者：本轮人工溯源（审计环）。分诊清单来自 audit/neutral_triage.py。

## 一、已核实并写入 decisions/neutral_court_codes.csv（13 条）

出处标准与现表既有 313 行一致（规格 §5.2）：**取自法院／官方机构自己发布的
判决所印的中立引用串**，是印刷事实，满足约束七。逐行 source_locator 可重放。

| 代码 | 法院 | 法域 | 出处 |
|---|---|---|---|
| `UKSC` | United Kingdom Supreme Court | GB | UKSC official website |
| `UKHL` | House of Lords (Appellate Committee) | GB | UK Parliament official publications |
| `UKPC` | Judicial Committee of the Privy Council | GB | Find Case Law (The National Archives) |
| `EWCA Civ` | Court of Appeal of England and Wales (Civil Division) | GB | Find Case Law (The National Archives) |
| `EWCA Crim` | Court of Appeal of England and Wales (Criminal Division) | GB | Find Case Law (The National Archives) |
| `EWHC` | High Court of Justice of England and Wales | GB | Find Case Law (The National Archives) |
| `EWFC` | Family Court of England and Wales | GB | Find Case Law (The National Archives) |
| `UKUT` | Upper Tribunal (United Kingdom) | GB | Find Case Law (The National Archives) |
| `HCA` | High Court of Australia | AU | High Court of Australia official website |
| `NSWCA` | Court of Appeal, Supreme Court of New South Wales | AU | NSW Caselaw (NSW Government official) |
| `NSWSC` | Supreme Court of New South Wales | AU | NSW Caselaw (NSW Government official) |
| `NSWCCA` | Court of Criminal Appeal, Supreme Court of New South Wales | AU | NSW Caselaw (NSW Government official) |
| `ZACC` | Constitutional Court of South Africa | ZA | Constitutional Court of South Africa official repository |

**实测收益**（仪器 audit/table_coverage.py + pipeline/classify.py，均可重放）：
shape_bracket 精确命中 76 → **987**（+911）；shape_neutral_bare 142,208 → **142,215**；
分类层已解出法域 142,282 → **143,202（+918）**。

### 法域取值口径

现表 313 行全为加拿大，用省／地区二字码（AB/BC/ON/QC…，CA=联邦）。
境外行用 ISO 3166-1 alpha-2 国家码（GB/AU/ZA）。**粒度不对称是有意的**：
对加拿大判例产品而言，本国需要省级粒度，境外只需国别粒度。此口径须人复核。

### UKPC 的特别说明

枢密院受理多法域上诉——官方库实见 Trinidad & Tobago、Bahamas、Mauritius、
Gibraltar 等。但**法院自身**设于英国，本表的 jurisdiction 是**法院的**法域，
单值 GB；具体案件从哪个法域上诉而来属 case_origin.csv 的辖区（规格 §3.3
分类层与裁定层之分）。这正是那张表存在的理由。

## 二、待核实（36 条，**未入表**）

按约束四，查不到权威出处的一律不写进表——空着是正确行为，不是失败。
按约束九，下表全部标【待核实】，**不得作为实现依据**。

本轮中止原因：这些法院官网普遍改版（fedcourt.gov.au 404、courtsofnz.govt.nz
两次 300s 超时、concourt.org.za 旧路径 404），逐个摸索成本高，而按规格 §5.1
既定的填表策略（填头部、长尾落 UNSUPPORTED），本批合计仅 195 行，
收益递减明显。留清单待后续批量处理。

| 代码 | 桶 | 语料行数 | 主印刷形 | 去哪查 / 处置线索 |
|---|---|---:|---|---|
| `NZCA` | A | 32 | `NZCA` | 新西兰上诉法院 — courtsofnz.govt.nz（本轮实测该站两次 300s 超时） |
| `NZSC` | A | 19 | `NZSC` | 新西兰最高法院 — courtsofnz.govt.nz（同上） |
| `FCAFC` | A | 15 | `FCAFC` | 澳大利亚联邦法院合议庭 — fedcourt.gov.au（本轮该站 URL 结构已改版，404） |
| `VSCA` | A | 15 | `VSCA` | 维多利亚州上诉法院 — supremecourt.vic.gov.au |
| `SGCA` | A | 9 | `SGCA` | 新加坡上诉法院 — judiciary.gov.sg |
| `NZHC` | A | 8 | `NZHC` | 新西兰高等法院 — courtsofnz.govt.nz（同上） |
| `WASC` | A | 8 | `WASC` | 西澳最高法院 — supremecourt.wa.gov.au |
| `QCA` | D | 7 | `QCA` | 昆士兰上诉法院 — sclqld.org.au / courts.qld.gov.au |
| `EWHCCH` | A | 6 | `EWHC Ch` | EWHC 衡平庭早期写法 EWHC Ch n（现行体例作 EWHC n (Ch)） |
| `HKCFI` | A | 6 | `HKCFI` | 香港原讼法庭 — legalref.judiciary.hk |
| `IEHC` | A | 6 | `IEHC` | 爱尔兰高等法院 — courts.ie |
| `SGHC` | A | 6 | `SGHC` | 新加坡高等法院 — judiciary.gov.sg |
| `IESC` | A | 5 | `IESC` | 爱尔兰最高法院 — courts.ie |
| `ACTSC` | A | 4 | `ACTSC` | 首都领地最高法院 — courts.act.gov.au |
| `ECHR` | A | 4 | `ECHR` | 欧洲人权法院 — hudoc.echr.coe.int |
| `UKIAT` | A | 4 | `UKIAT` | 英国移民上诉裁判所（2010 并入 UT）— 历史机构，Find Case Law 未收 |
| `VSC` | A | 4 | `VSC` | 维多利亚州最高法院 — supremecourt.vic.gov.au |
| `CLLC` | D | 3 | `C.L.L.C.` | **不入表** — C.L.L.C. = Canadian Labour Law Cases，印刷汇编，应移交 reporter 表 |
| `EWCA` | D | 3 | `EWCA` | EWCA 裸码（分庭词在 shape_neutral_bare 落 series 槽） |
| `NICA` | D | 3 | `NICA` | 北爱尔兰上诉法院 — judiciaryni.uk |
| `NIQB` | D | 3 | `NIQB` | 北爱尔兰高等法院王座庭 — judiciaryni.uk |
| `SASC` | D | 3 | `SASC` | 南澳最高法院 — courts.sa.gov.au |
| `AATA` | A | 2 | `AATA` | 澳大利亚行政上诉裁判所（2024 改制为 ART）— art.gov.au |
| `HKCA` | A | 2 | `HKCA` | 香港上诉法庭 — legalref.judiciary.hk |
| `NSWADT` | A | 2 | `NSWADT` | 新州行政裁判所（2014 并入 NCAT）— caselaw.nsw.gov.au |
| `SAIRC` | A | 2 | `SAIRC` | 南澳劳资关系法院 — courts.sa.gov.au |
| `TASSC` | A | 2 | `TASSC` | 塔斯马尼亚最高法院 — supremecourt.tas.gov.au |
| `UKSIAC` | A | 2 | `UKSIAC` | 英国特别移民上诉委员会 — Find Case Law 目录已列（262 份），本轮未取判决页 |
| `ZASCA` | A | 2 | `ZASCA` | 南非最高上诉法院 — supremecourtofappeal.org.za |
| `ZAWCHC` | A | 2 | `ZAWCHC` | 南非西开普高等法院 — judiciary.org.za |
| `AZ` | A | 1 | `AZ` | **不入表** — [2022] AZ 51826418 — 序号八位，非判决流水号，疑为抽取噪声 |
| `DCSC` | A | 1 | `DCSC` | **不入表** — 归属不明，孤例 [2002] DCSC 760，需人核 |
| `HCJAC` | A | 1 | `HCJAC` | 苏格兰高等刑事法院上诉庭 — scotcourts.gov.uk |
| `OJN` | A | 1 | `OJN` | **不入表** — O.J. No 粘连变体（抽取层 _SERIAL_SLOT 不收无句点的 No，见 PROBLEMS） |
| `SASCFC` | A | 1 | `SASCFC` | 南澳最高法院合议庭 — courts.sa.gov.au |
| `UHKL` | A | 1 | `UHKL` | **不入表** — UKHL 的拼写错（U-H-K-L），孤例 [2005] UHKL 41，不入表 |

合计 36 条 / 195 行。

## 三、溯源出处的可采性分级（本轮所用）

| 级 | 源 | 可采性 |
|---|---|---|
| 甲 | 设立该中立引用体例的业务指引原文（Practice Direction / Practice Note） | 最硬 |
| 乙 | 法院官网／官方法律报告机构发布的自身判决所印的中立引用 | **可采（本轮全部为此级）** |
| 丙 | 专门的法律缩写索引 | 仅作交叉印证，不单独作为唯一出处 |
| 不可采 | 语料上下文（约束三）、模型自身知识、百科类站点 | — |

甲级本轮未获取：英格兰 2001 年 Practice Direction (Judgments: Form and Citation)
在 judiciary.uk 站内已下架（该站 PD 归档最旧只到 2009），Wayback 亦未命中本体。
乙级已足以支撑约束七与约束八，故未继续追甲级。

未使用第三方判例数据库（BAILII / AustLII / SAFLII）——授权条款与 IP 干净度
须先评估（规格 §5.1 对外部源的既定立场）。本轮所有出处均为法院或官方机构自有站点。
