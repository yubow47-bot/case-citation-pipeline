# 决策表：往里加行之前要知道的

## 总规矩

- 目录 `decisions/`，**全部进 git**，是项目里唯一不可再生的东西。`data/` 可以整个删了重建，这些表不行。
- **每一行必须有 `source` 和 `source_locator`**（约束八）。没有出处的行不得入表；判定不得写在代码里。
- **键必须是判决书上印着的事实**（印刷缩写、法院码、引证串本身），不得是管线算出来的键、分组号、行号（约束七）。这样管线怎么改，人工查证的成果都不会失效。
- 管线**只读** `decisions/*.csv`，不调用 `decisions/tools/` 里的建表脚本，也不联网。建表脚本是人决定重建或扩充时手动运行的（key 走环境变量或 `--key-file`，不进仓库，限速 1 秒/次）。
- 空表不是故障（规格 §13.4）。填表的优先级按覆盖率报告 `audit/table_coverage.py`、`pipeline/coverage_report.py`，按 DD 降序，长尾一律 `UNSUPPORTED`。
- **加载成功不等于生效**：列名写错、状态值不在白名单，行都会被静默忽略。接入后必须抽样反查下游字段真的被填了（PROBLEMS #97）。

## 十张表：谁读、键是什么、加新法院要不要动

【已核实：行数和状态分布来自 `decisions/*.csv`（2026-10-03）；读取方来自 `classify.py:1043`、`decide.py:142-462`】

| 表 | 行数 | 读取方 | 键（印刷事实） | 加新法院时 |
|---|---|---|---|---|
| `neutral_court_codes.csv` | 327 | 分类、登记簿 | `court_code`（判决上印的那一段，如 `ONCA`） | **必加**新法院自己的码，以及它常引的外国码 |
| `reporter_jurisdiction.csv` | 197 | 分类 | `abbreviation` + `jurisdiction`（复合键）+ 卷号/年份区间 | 新法院常引、表里没有的汇编；同形缩写加区间行 |
| `series_prefix.csv` | 4 | 分类 | `canonical_prefix`（`L.R.`、`Q.R.`） | 很少 |
| `identifier_systems.csv` | 16 | 分类、裁定 | `printed_token`（**逐字、区分大小写**） | 该法院判决里的数据库/厂商标识符 |
| `court_designations.csv` | 16 | 分类 | `printed_designation`（括注里的法院标注） | 新法院常见的括注（`(Ont. C.A.)`），当前覆盖不足（#94） |
| `bilingual_neutral_codes.csv` | 46 | 裁定 | `code_en` ↔ `code_fr` | 有法语判决时 |
| `case_origin.csv` | 203 | 分类（载入）、裁定 | `citation_display`（印刷引证串） | 枢密院类上诉案；来源 CanLII `ukpc` 库，覆盖 1888–1959 |
| `case_origin_manual.csv` | 32 | 裁定 | `printed_citation` | 逐案人工核验的来源地 |
| `court_or_reporter_scope.csv` | 12 | 裁定 | `printed_key` + 年代窗 | 法院/标识符的排他来源地规则 |
| `reporter_origin_scope.csv` | 40 | 分类（`volume_system`）、裁定 | `printed_abbreviation` + 年代窗 | 排他汇编范围规则 |

## 各表的“可信等级”：哪些行真的会驱动判定

| 表 | 列 | 值（现有分布） | 哪些参与判定 |
|---|---|---|---|
| `reporter_jurisdiction.csv` | `confidence` | `estimated` 197 行（**全部**） | 只能升级为 `jurisdiction`，**不得升级为来源地事实**（约束九） |
| 同上 | `verification_level` | `verified_print_evidence` 101、`name_inference` 56、`verified_authority` 30、`authority_identity_only` 9、`authority_country_only` 1 | 管线**不读**这一列，它只记证据有多硬 |
| `identifier_systems.csv` | `verification_status` | `verified_authoritative_manual` 13、`verified_official_source` 3 | 只有这两种驱动推断（`ALLOWED_IDENTIFIER_STATUSES`） |
| `court_or_reporter_scope.csv` | `verification_status` | `verified_scope_rule` 12 | 只有 `verified` 开头的行参与 |
| `reporter_origin_scope.csv` | `verification_status` | `verified_mixed` 22、`verified_exclusive_publisher` 13、`verified_exclusive_statute` 5 | 只有 `verified_exclusive_statute`、`verified_exclusive_publisher` 参与；`verified_mixed` **只作档案**，永远不产生来源地 |
| `case_origin_manual.csv` | `status` | `verified_research_agent` 32 | 只有这一个值 |
| `bilingual_neutral_codes.csv` | `verification_status` | `rejected_renamed_code` 27、`verified_explicit_equivalence` 15、其余 4 | 只有 `verified_explicit_equivalence` 参与身份等价（`ALLOWED_BILINGUAL_STATUSES`，`decide.py:450`）；候选端点配对不自动授权 |
| `court_designations.csv` | `status` | `recognized` 13、`ambiguous_designation` 3 | 精确匹配（nk 归一后查表） |

## 怎么加一行（流程）

1. 先找**能对着判决本身或权威资料核实的来源**：CanLII API、McGill Guide、司法部缩写表、AGLC 等。**不得使用旧管线那约 70 条硬编码判定当输入**，只能事后差异对照。
2. 填 `source`（谁说的）和 `source_locator`（页码、URL、端点，逐行可独立复核）。CanLII 建表工具的 `source_locator` 自带可重放的端点 URL。
3. 填对应的 `verification_*` 或 `confidence` 值，**不要高估**：没核实过就写 `name_inference`/`estimated`，它们不会驱动来源地。
4. 同形缩写：同一缩写写多行，每行一个候选法域，带 `vol_range_*`、`year_range_*`（含 0 表示可不印卷号，从 1 起表示恒印卷号）。区间要有证据（语料印刷结构实测或出版史），不能拍脑袋。
5. 加完后：
   - 重跑分类并**全量差分**（`audit/classify_diff.py`），看变化的行是不是预期的；
   - 抽样反查下游字段被填了；
   - 跑 `test_layers.py`。
6. 改了表，**所有依赖它的 run 需要重跑**（输入身份指纹含决策表）。

## 建表工具（`decisions/tools/`，不属于生产线）

| 脚本 | 做什么 |
|---|---|
| `build_neutral_court_codes.py` | 从 CanLII `caseBrowse` 建中立码表；`--offline` 用缓存只重建 |
| `build_case_origin.py` | 抓 `ukpc` 库建枢密院来源地；`--offline`、`--key-file` |
| `build_bilingual_neutral_codes.py` | 双语码对照 |
| `build_identifier_systems_csv.py` | 标识符系统表 |

关键点（来自 `build_neutral_court_codes.py` 的三道拒收闸，约束四）：
- `court_code` **不是**从 `databaseId` 推出来的（409 个库里 118 个不符，如 `csc-scc`→`SCC`），一律取自该库真实案例引证串里印刷的那一段。
- 同一码在两个库对应不同法域 → 不写，交人裁；证据来自 `ukpc` 的不写（#32）；库名同时点到两个以上法域的不写（#34）。
- CanLII 的 `jurisdiction` 字段是“馆藏归属”，不是法院自身法域（#32）。
- CanLII 给没有中立码的机构分配 `CanLII` 伪代码，横跨 14 个法域，**不入中立码表**（#31）。

## 已知的坑

| # | 内容 |
|---|---|
| 31–35 | 建表首轮的缺陷：CanLII 伪代码、`ukpc` 馆藏语义、归一键假命中、overclaim“剩余全是噪声”、外国码供不出（约 1,042 行，须另找来源并先评估授权） |
| 40 | `reporter_jurisdiction.csv` 早期 166 行全是 `estimated`/`name_inference`，出产品前须逐条核实 |
| 97 | 列名不一致（`origin_country` 对 `case_origin`）导致 32 行加载成功但零生效 |
| 99 | `FCA` 加拿大和澳大利亚同码（表里只有加拿大一行，`[YYYY] FCA N` 带方括号的是澳大利亚） |
| 100 | `S.J.`：按卷号拆两行（有卷号英国，无卷号萨斯喀彻温 Quicklaw） |
| 102 | `A.R.`（安大略上诉 1880–1897）、`L.C.R.`（魁北克）缺区间行 |
| 103 | 双语码对照有判错，已按用户指示改表 |
| 104 | `FC` 与 Federal Court Reports 的方括号印刷形同形 |

## 来源

规格 §2（约束七、八）、§5；`decisions/README.md`；代码 `pipeline/classify.py`（`load_table`、`load_identifier_systems`、`load_court_designations`、`load_volume_systems`）、`pipeline/decide.py`；PROBLEMS #31–#35、#40、#97、#99–#104。

核实状态：行数、状态分布、读取方对照实际文件和代码（2026-10-03）【已核实】。
