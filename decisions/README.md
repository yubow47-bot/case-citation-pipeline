# decisions/ — 人工判断，唯一事实源

事实表及其出处全部进 git。下面四张表是项目初期的核心表清单，后续增加的表以实际 CSV schema 和规格中的日期说明为准。

2026-10-15 的身份事实另有严格原文凭证：`identity_court_facts.csv` 的三个完整 key 记录裁决法院；`identity_separations.csv` 的一条事实排除一个完整 key 与单一已证实文档的错误合并，不能据此猜测法院。它们保存 `source_corpus`、源行、字段、corpus/text/span SHA、`evidence_id`、`source_locator`；这些具体字段替代泛化的 source 文本。排除事实还绑定目标的完整当前 qualified proofs，过期、缺失、冲突或串绑会拒绝执行。

这些是研究代理回到原文核查后形成的可复查事实，不是随机人工标注或准确率。不得写运行内的 group ID 作为身份事实。新增事实与真实小子集回归、全量来源集合验收见 [后续记录](../audit/findings/project_review_20261015/release_summary_final.json)。

| 表 | 用途 |
|---|---|
| `reporter_jurisdiction.csv` | 缩写到法域（分类层主要事实源） |
| `neutral_court_codes.csv` | 中立引用法院代码（封闭穷举）——**已填，300 行**，源 CanLII API v1 caseBrowse，覆盖语料中立引用 96.5%，见规格 §5.2 |
| `series_prefix.csv` | 系列汇编前缀（L.R. 家族） |
| `case_origin.csv` | 案件真实来源地（主要针对 JCPC 案件）——**已填 203 行**：CanLII `ukpc` 库（枢密院对加拿大上诉）1888–1959 年内的对上者；库外一律 UNDETERMINED，见 PROBLEMS #59 |

2026-10-16 additions (PROBLEMS #134-#139; every row carries `source` and `source_locator`; agent review authorized by the user, not human review):

| Table | Read by | Use |
|---|---|---|
| `court_designation_codes.csv` | decide (CourtEvidence) | Links a recognized printed designation to its neutral court code (`Ont.C.A.` -> ONCA, `P.C.`/`J.C.P.C.` -> UKPC). Before it, the link existed only when the normalized strings happened to coincide (`B.C.C.A.` = BCCA). |
| `court_designation_reporter_scope.csv` | classify | A bare `(C.A.)` printed after a reporter that holds one province's decisions (`O.R.`, `O.A.C.`, `B.C.L.R.` ...) names that province's Court of Appeal. Used only when `court_designations.csv` marks the designation ambiguous. |
| `non_case_sources.csv` | classify | Periodicals, treaty series and statutes printed in the reporter slot (`Can. Bar Rev.`, `U.N.T.S.`, `Stat.`, `Geo.`). Exact rows, five DOJ-sourced suffix rows (`L. Rev.`, `Bar Rev.` ...) and 186 rows from the quoted-title print-evidence channel (`audit/non_case_quote_channel.py`). Built by `decisions/tools/build_non_case_sources.py`. Registered reporters are never matched. |
| `bilingual_reporter_abbreviations.csv` | decide (identity) | `R.C.S.` is the French title of `S.C.R.`: the same year, volume and page name one report (7,959 same-row corpus pairs, 0 disagreements). |

## 规则

- 每一行必须带来源及 `source_locator`；通用表使用 `source`，原文身份事实使用上述严格文件／行／字段／SHA schema
- 判定不得写在代码里
- 键必须是印刷事实（缩写、法院代码、引证串本身），不得使用管线计算出的分组标识

## `tools/`

建表工具，**不属于生产线**（膜的规则见 `audit/README.md`）：它产出的是决策表行，不是管线数据。
管线只读 `decisions/*.csv`，从不调用这些脚本，也从不联网。只在人决定重建/扩充某张表时手动运行。

| 脚本 | 产出 |
|---|---|
| `build_neutral_court_codes.py` | `neutral_court_codes.csv`（源：CanLII API v1 caseBrowse） |
| `build_case_origin.py` | `case_origin.csv` 的枢密院部分（源：CanLII API v1 caseBrowse `ukpc`，枢密院对加拿大上诉）＋报告 `audit/findings/case_origin_review.md`（可重放） |
| `build_non_case_sources.py` | `non_case_sources.csv`（官方缩写表行、后缀规则、`audit/findings/non_case_sources_20261016/quote_channel.csv` 印刷证据行） |

```
set CANLII_API_KEY=...
python decisions/tools/build_neutral_court_codes.py --cache-dir <缓存目录>
python decisions/tools/build_neutral_court_codes.py --cache-dir <缓存目录> --offline   # 只重建表

python decisions/tools/build_case_origin.py --key-file <key 文件>     # 抓 ukpc 全表并重建
python decisions/tools/build_case_origin.py --offline                  # 只用缓存重建（缓存默认 data/canlii_cache）
```

API key 走环境变量或 `--key-file`，**不进仓库、不写进任何输出**。抓取限速 1 秒/次。
缓存是机器产物，不进 git——每一行的 `source_locator` 自带可重放的端点 URL，逐行可独立复核。
`build_case_origin.py` 的缓存固定落在 `data/canlii_cache/ukpc_list.json`（仓库内、gitignore）：
缓存留在会话临时目录会让 `--offline` 只在一台机器上可复现（PROBLEMS #59）。

## `reporter_jurisdiction.csv` 的 `verification_level`

管线**不读**这一列，它只记这一行的法域判断有多硬的证据。

| 值 | 含义 |
|---|---|
| `name_inference` | 据缩写全称推断，未核对任何来源 |
| `verified_print_evidence` | 语料印刷证据支持（六渠道，`audit/findings/jurisdiction_channels/`；机器整理，未人工复核） |
| `verified_authority` | 外部权威资料列明该汇编的身份与表列法域（2026-10-02 代理审批，非人工复核）；不证明逐案来源或独占范围 |
| `authority_identity_only` | 外部资料只支持汇编身份，表列法域/省份范围未经该资料确认（如 `Nfld. & P.E.I.R.`） |
| `authority_country_only` | 外部资料只支持到国家层，省级未核（如 `Sask. L.R.`） |

`S.J.` 按卷号拆两行（PROBLEMS #100）：有卷号归英国 Solicitors' Journal，无卷号 `[YYYY] S.J. No. N` 归萨斯喀彻温（Quicklaw）。


## Identity evidence follow-up (2026-10-16)

`identity_pair_separations.csv` contains reviewed negative identity facts, not positive aliases. Each endpoint is bound to its own native document, citation offsets, corpus/text/span SHA-256 and distinction context. Two endpoints may occur in one document (McCormack, Green, Hazout) or different documents (Marshall). `pipeline/identity_pairs.py` verifies both original spans through the production candidate/key functions before the scoped solver consumes a fact; unrelated offline fixture scopes need no production corpus. The table row is content addressed, and both source proofs enter the identity ledger. Builder and source receipt: `audit/build_identity_pair_facts_20261016.py`, `audit/findings/followup_fixes_20261016/identity_pair_sources.json`. Reviews are agent reviews, not human adjudication.

`reporter_identity_court_sets.csv` gives conservative sets of possible deciding courts for explicitly sourced reporter/year windows. It supplies only a cannot-link when two known sets are disjoint, or a printed positive court is outside the other set. It never assigns a court, country, or origin. SCC leave reports, Yukon decisions and federal appeals are included where counterexamples require them; unknown years and unsupported windows abstain. A province in `reporter_jurisdiction.csv` is never used as an identity exclusion. Sources and counterexamples: `audit/findings/followup_fixes_20261016/reporter_scope_sources.json`.

History instances retain the originating artifact hash, record locator, source decision, candidate, connector and endpoint keys. A new run requires history inputs; an old fixture/run must explicitly declare `--history-input-mode legacy-none`. The bilingual reporter alias row is also cited by the exact identity proposal that consumes it.

The pair table now has 22 rows: the original four ruling pairs and 18 native exclusions for complex history wording or the repaired Waldick citation. The complete frozen 38-pair residual probe has separate reviewed dispositions. Scherer's contradictory leave wording is retained as a conflict and supplies no negative fact. Source bytes and policy bytes are checked again whenever pair facts are loaded, using the same classification tables and continuous-volume year normalization as the production CLI.

`reporter_compound_locators.csv` records two sourced I.L.R. paragraph-locator formats. The complete numeric `1-2261` or letter `I-6271` is retained literally in the locator slot; `1` and `I` are never equated. The table verifies the bounded printed format only, and supplies no country, court, origin or global interpretation of the ambiguous abbreviation. Additional extraction shapes retain the old candidates; classification marks a rule only after exact policy validation. The merge completion of an old page-1 prefix additionally requires matching native year/page spans and raw text. Unknown reporters and ordinary page ranges do not receive that completion. Source evidence is retained in `implementation/followup_fixes_20261016/ilr_compound_locator_receipt.json`; excerpt hashes are explicitly distinguished from PDF file hashes.
