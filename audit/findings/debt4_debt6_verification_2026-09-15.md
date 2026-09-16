# 债 4 + 债 6 核实提案（C 阶段一）—— 2026-09-15

**执行者**：zcode（research agent；全部结论未经人核，核实状态一律 `verified_research_agent`，沿用 `case_origin_manual.csv` 先例）。
**冻结输入**：交付 run `data/run_20260914_r4c`（196 行影响行数按其 classify_out 实测）；证据源 = Cardiff Index to Legal Abbreviations（`legalabbrevs.cardiff.ac.uk`，逐条记录页实抓）+ LexisNexis Quicklaw 官方帮助页 + 法院官网印刷形。
**批准前只写了**：`audit/findings/` 下三个文件（本摘要 + 两张提案表）。`decisions/`、`pipeline/`、corpus 一律未动，未提交 git。

## 债 4 —— reporter_jurisdiction.csv 196 行（提案：reporter_jurisdiction_proposal.csv）

与生产表同列，末尾加三列 `old_value` / `new_value` / `evidence_quote`（引语为记录页字段逐字拼接，剔除页面「Copy」按钮文字，已在表头注明）。

| 行级状态 | 行数 | 含义 |
|---|---:|---|
| CONFIRMED | 166 | Cardiff 记录与现判定一致；`verification_level` 提为 `verified_research_agent` |
| BORDERLINE | 3 | 法域证据已取得，但表内区间与来源 Period 边界不完全重合（Q.B.-QC 1952..1970 / C.P.-QC 1965..1988 / A.L.R.-AU 无卷行 1895..1973），**区间留人工** |
| UNRESOLVED_FOR_HUMAN | 1 | `Q.B. GB vol1..18/yr1841..1852`：被 A.& E.（1834–40，备选缩写含 Q.B.）与 E.& B.（1852–58）夹住，Cardiff 无以 Q.B. 为缩写的对应记录，该行展开留人工（相邻系列记录已附进 evidence_quote） |
| NOT_VERIFIED | 25 | 可采源未取得，保持 `estimated`；其中 `O.J.` 附了 LexisNexis 出版方文档引语（证明 [年] O.J. No. n 是 Quicklaw 引用格式，展开义仍未核实） |

- **家族级**（161 族）：132 族全核；未核 23 族。按影响行数（对 r4c classified 全量、nk(abbreviation) 同形计数）加权：**全核 94.0%**（605,591 / 644,194），部分核 2.4%（qb / sc / clr / alr / cp 五个同形族里只有部分行核到），全未核 3.6%——头部是 Quicklaw 标识符族（O.J. 6,640 / S.C.C.A. 4,692 等 11 族 ≈15,600 行）与 C.P.C. 2,144 / C.T.C. 1,341 / B.L.R. 1,290。
- **`confidence` 全部维持 `estimated`**：升 `confirmed` 属阶段二（人抽 20 行批准后落表时再定，按台账口径执行）。
- **CHANGE = 0**：没有一行 propose 改法域。（不在 196 行内的 `Fox Pat. C.` 曾测得 Cardiff 记 Canada 而语料印形系伦敦出版 Fox's 系列——该族属「待填」桶，不在本表，记录在 `cardiff_confirmed_4.json` 备查。）
- **Quicklaw 标识符族（11 族，全部 NOT_VERIFIED）**：O.J./S.C.C.A./B.C.J./A.J./Q.J./F.C.J./S.C.J./J.Q./M.J./N.S.J./N.J.——LexisNexis 官方帮助页只给格式（如 `[1997] O.J. No. 4806` 的录入变体），没有「标识符→判决源」的公开对照表。出版方（LexisNexis）文档是唯一可采源，本轮未能取得展开义。**但同页给了两个可采证据**：① O.J. No. 的 Quicklaw 引用格式；② **"BR" 卷 1–71 = 加拿大 Banc de la reine、72+ = 美国 Bankruptcy Reporter**——据此 `B.R.`（QC，卷 15）族以出版方文档 CONFIRMED。
- 未核 23 族清单（全部如实保留 estimated）：oj, scca, cpc, bcj, ctc, blr, qj, aj, fcj, jq, rl, hlcas, cbns, scj, rra, ccpb, immlr, mj, nsj, hare, hlc, degmg, nj。

## 债 6 —— 境外中立码 36 条（提案：neutral_foreign_verified.csv）

| 状态 | 条数 | 明细 |
|---|---:|---|
| CONFIRMED | 5 | NZCA / NZSC / NZHC（courtsofnz.govt.nz 判决列表自印，上一轮两次 300s 超时的站本轮正常）、TASSC、NICA（judiciaryni.uk 自印） |
| CONFIRMED_NOT_PRINTED | 1 | EWCA 裸码：TNA Find Case Law 目录只印带分庭词的形式（`[2026] EWCA Civ 1184`），裸 EWCA 是抽取层把分庭词丢进 series 槽的产物，不属可入表印刷码 |
| CONFIRM_NOT_IN_TABLE（复核维持） | 3 | AZ（八位序号非判决流水号）、OJN（抽取层粘连产物）、UHKL（UKHL 拼写错） |
| 移交 reporter 流程 | 1 | CLLC（Canadian Labour Law Cases，印刷汇编——属债 4 范畴，本轮未替它做 reporter 核实） |
| UNRESOLVED_FOR_HUMAN | 1 | DCSC（dccourts.gov/decisions 404；孤例归属不明维持） |
| NOT_FOUND | 25 | FCAFC、VSCA、VSC、SGCA、SGHC、WASC、QCA、EWHCCH、HKCFI、HKCA、IEHC、IESC、ACTSC、ECHR、UKIAT、NIQB、SASC、AATA、NSWADT、SAIRC、UKSIAC、ZASCA、ZAWCHC、SASCFC、HCJAC |

NOT_FOUND 的原因与上一轮（2026-09-09）相同：这些官网的判决检索器全部 JS 化或改版（fedcourt 门户页无自印引用、elitigation.sg / caselaw.nsw.gov.au / hudoc 为 JS 应用、scotcourts 改用 `#/` 路由、爱尔兰列表异步加载、南非两站改路径 404）。每条的 notes 里列了本轮实际试过的 URL。**维持空表是正确行为**（约束四）。

## 仪器与可重放性

- 证据全部为「本会话实抓页面上的逐字字段/印刷串」：Cardiff 记录页（真 Chrome 过 Cloudflare 直连）+ 官网印刷串正则抽取 + LexisNexis 帮助页（WebFetch）。**没有一条引语来自模型记忆**；未用 BAILII/AustLII/SAFLII/CanLII/维基（既定禁令）。
- 全部证据 URL 写在两张提案表的 `source_locator` / `source_url` 列，人工可逐条打开。
- **抽样自检**：随机取 4 个证据页重抓（western-law-reporter / session-cases / law-reports-probate / NZCA 列表页），提案表内引语碎片逐字命中 **13/13**。
- 会话中间产物（Cardiff 记录字段 JSON、影响行数排序、合并脚本）在系统临时目录 `verify_c/`，未入仓库；如需完整重放材料可索要。

## 与计划书的偏差（如实记）

1. **`pipeline/coverage_report.py --kind reporter` 排不了 196 行**——该报告排的是「不在表内的待填族」（含 Ontario Inc.、月份名等噪声桶）。改为按同一口径补算：对 r4c 的 classified.csv 全量按 `nk(abbreviation)` 计数给 196 行排序（仪器脚本见汇报）。
2. **子代理并发额度受限**（约 1 个并发 + 后续 quota 限制），网核全部由主线程真浏览器完成，未影响产出。
3. **WebFetch 对 Cardiff 一律 403**（Cloudflare），改用浏览器实抓；LexisNexis 帮助页 WebFetch 可达。

## 下一步（等你）

1. 在 CONFIRMED 行里**随机抽 20 行**（约 10%），按 `evidence_quote` 的 URL 回源核对；错 1 条以上整批退回。
2. 批准后走 C 阶段二：写进 `decisions/reporter_jurisdiction.csv`（196 行逐行带 source/source_locator）与 `decisions/neutral_court_codes.csv`（本轮 5 条新 CONFIRMED），全链重跑 r5a，并验证「FOREIGN 边 629 不变」不变量（196 行表不喂来源地）。
