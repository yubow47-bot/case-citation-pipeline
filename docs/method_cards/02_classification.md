# 第 2 层 分类

## 这一层做什么

**逐行独立判定**，只看这一行自带的字段：这条引证是什么种类、属于哪个法域、是不是误报、案名是什么。查决策表在这一层做，抽取层不查表。

- 输入：`extract_out/candidates.csv`。
- 输出：`classify_out/<法院>/classified.csv` 加 `manifest.json`。
- 在抽取层字段之后新增【已核实：`classified.csv` 表头】：`citation_kind`、`abbreviation`、`jurisdiction`、`jurisdiction_confidence`、`lookup_mode`、`vol_missing`、`series_prefix`、`candidate_case_name`、`rejected_reason`、`name_rejected_reason`、`disambiguated_by`、`self_citation`、`parse_status`、`year_vol_ambiguity`、`identifier_subdivision_code`、`jurisdiction_subdivision`、`volume_system`、`court_designation_status`、`observed_deciding_court`、`court_designation_evidence_id`。
- 分类层的类别（`citation_kind`）有四类：`reporter`（印刷汇编）、`neutral`（中立引证）、`identifier`（数据库或厂商标识符，如 CanLII、Carswell）、`ambiguous`（同时命中两表且同档）。

## 分类层 vs 裁定层（最容易混）

- 分类层判的是 **reporter 层面**：`A.C.` 属于哪个法域。答案对所有用这个缩写的引证一样，字段 `jurisdiction`。
- 裁定层判的是**案件层面**：`[1938] A.C. 415` 具体来自哪里（可能是加拿大上诉到枢密院的案子），字段 `case_origin`。
- 二者不总相等，这正是裁定层存在的理由。**未入表时来源地必须是 `UNDETERMINED`，不得默认取 `jurisdiction` 的值。**
- 判据：一条规则只要需要看别的行，就不属于分类层。

## 处理顺序（代码：`Classifier.run_row`，`classify.py:958`）

1. **Step 1 形状级预处理**（`step1`）：确定 `citation_kind` 与 `abbreviation`。
2. **Step 2 剔除非案例**（`step2`）：只打 `rejected_reason`，行不删。
3. **Step 3 法域查表**（`step3`）。
4. **Step 4 同形异义消歧**（Step 3 返回多候选时）。
5. **Step 5 案名候选切分与清洗**。

### Step 1：两表并查，精确优先

- `shape_bracket`、`shape_neutral_bare` 的 `token` 同时去查 `neutral_court_codes.csv` 和 `reporter_jurisdiction.csv`。
- **不设优先级**：法院码表能立即填满而 reporter 表长期为空，设优先级就是让填表进度决定结论。
- **精确 > 归一**：印刷串精确等于哪张表的键就归哪张；只有去标点后才同形的是归一命中。
  - **归一命中一律不下判定**（落 `ambiguous` + `UNSUPPORTED`，`lookup_mode=normalized` 留痕，计数器 `neutral_withheld_fuzzy_only`）。理由：它是推断不是印刷事实（#36）。
  - 结构闸：仅当本行**无卷号**才启用归一退路（`[1979] 1 F.C. 103` 有卷号，是汇编，不是中立码 `FC`；#33）。
  - 两表都命中但成色不同档 → 精确的一方胜出；同档才算 `table_conflict`（#41）。
- `shape_leading_abbr`：`leading_abbr` 要查 `series_prefix.csv`，不在表里 → `unrecognized_series_prefix`（大概率根本不是引证）。认得的前缀若带法域则参与消歧（`Q.R.` → 魁北克；#52）。
- **`unrecognized_series_prefix` 和 `UNSUPPORTED` 必须区分**：前者是“大概率不是引证”，后者是“确实是引证但法域未知”。
- 标识符：`CanLII`、`CarswellOnt` 等走 `identifier_systems.csv`，键是印刷 token **逐字**（大小写敏感，无模糊匹配），只有 `verification_status` 为 `verified_official_source` 或 `verified_authoritative_manual` 的行驱动推断（`ALLOWED_IDENTIFIER_STATUSES`，`classify.py:192`）。

### Step 2：非案例引证的拒收（`rejected_reason`，可累积，用 `|` 连接）

| 取值 | 含义 | 备注 |
|---|---|---|
| `federal_statute` | 联邦制定法被当成引证 | 作用域：`preceding_text + raw_string`（#37） |
| `party_initials` | `R. v. A.B.` 的当事人缩写被误抽 | 判据严格：前文正好以 `R. v.` 结尾且本行以 `X.Y.` 起头（#37） |
| `docket_not_decision` | v1.6：`shape_registered_id` 的案卷号，标识一场诉讼而非一份判决——**保留不计数**，不猜是哪一份（约束四）。注意它与其他取值性质不同：不是「不是引证」，而是「是引证但对不上判决」（规格 §8.8 的两类拒绝尚未为它另设字段，#111） | 见 `id_prefixes.csv` |
| `non_citation_word` | v1.6：缩写位是结构词/日历词/案名片段（`Footnote`、`Section`、`See …`、`On …`、月份、`X`），查 `non_citation_words.csv`（whole/first_word/last_word，**区分大小写**）；已登记汇编永不拒收（#113） | 观测计数在表里 |
| `versus_as_page` | v1.6：页位是小写罗马 `v` 且缩写未登记——案名里无句点的 versus 被读成罗马页（`Villani v Canada`）；纯字段判据（#113） | 边缘 24,532 行/主线 55 行 |
| `unverified_id_prefix` | v1.6：`decision` 型前缀（`AZ-`、`J.E.`…）所在表行尚未核实——保留不计数，核实后（状态 `verified_*`）自动转计数 | 用户裁定 2026-10-03 |
| `date_form` | `1 June 2007` 与“卷 缩写 页”同形 | 三条件同时成立：缩写槽是英文月份全称、卷 1–31、页 1600–2099（#85）。**常量 `MONTH_NAMES` 在代码里**（用户裁定，规格 §8.4 v1.7 写明理由：封闭的日历词不是报告集缩写） |
| `unrecognized_series_prefix` | 前缀不在系列表 | 结构骨架误报 |
| `table_conflict` | 同时命中两表且同档 | 待人裁 |

- **`rejected_reason`（行级）和 `name_rejected_reason`（案名级）必须分开**。归并层计数要排除前者但不能排除后者（切不出案名的行是真引证）；案名投票两个都排除。合并成一个字段会让引用次数被系统性低估（§8.8）。
- `name_rejected_reason` 取值：`no_v_structure`、`no_separator_before_v`、`too_long`（>120）、`has_bracketed_year`、`multi_v`、`empty_after_clean`。
- 刻意不拦的日期（登记未修）：缩写月份 `28 Feb. 1995`（#86）、法文月份、“年-月-日”形态（#85 残差栏）；`Apr` 归一后与 `A.P.R.` 撞键（#87）。

### Step 3/4：法域查表与同形异义消歧【按规格 §8.5/§8.6 加 #52 的实现订正】

- 先精确匹配缩写，再归一键，`lookup_mode` 记 `exact` 或 `normalized`。
- 同一缩写在表里出现多行 = 有同形异义（表本身就是索引，不需要另列清单）。
- 消歧只用**本行自带的结构证据**（卷号、年份），不读周边文本（约束三）：
  - 表里卷号区间含 0 表示该系列可不印卷号，从 1 起表示恒印卷号；无卷号行按 vol=0 参与并标 `vol_missing`；
  - 无年份时年份维度不参与、只凭卷号；
  - 命中的法域唯一才判定，零或多命中 → `UNSUPPORTED`；
  - 成色取命中表行中最弱者，上限 `inferred`；
  - `disambiguated_by` 记途径：`series_prefix`/`vol_year`/`novol_year`/`vol_only`。
- `shape_vol_abbr_page` 与 `shape_leading_abbr`（部分）没有年份组件，参与不了消歧，这是已知限制。

### Step 5：案名切分与清洗（`candidate_case_name`）【按规格 §8.7 加 #43/#45/#57/#58/#61】

- 从 `preceding_text` 里找**最后一个** ` v.`；起点取它前面最近的 `;`、`:`、换行；**找不到分隔符就放弃，不退化为从 0 开始**；候选取到 `preceding_text` 末尾（含被告方）。
- 清洗：剥引导符、`citing/see/per/applied` 等引导动词、引导性 `in `（保留 `in re`）；剥段落编号（#43）；切掉尾巴里的平行引证（#45）。
- 没有 ` v.` 的案名只认段首段尾的闭集标记：`Reference re`、`Re`、`In re`、`Ex parte`、`(Re)`、魁北克匿名名 `Droit de la famille — N`（#58）。
- 候选吞进左侧整句散文时切掉（≥3 个小写散文词触发；切完不像案名则原样退回，不判无名；#61）。
- 自引标记：本行 `nk(raw_string)` 等于本判决自身引证即 `self_citation=true`，**数值相等比较**（`2003 BCCA 0443` == `2003 BCCA 443`，PROBLEMS #105，`_unpad`）。它是真引证，不进 `rejected_reason`，只是不计数。

## 加新法院时要改什么

分类层的代码一般不用改，**要改的是决策表**（详见 `06_decision_tables.md`）：

1. `neutral_court_codes.csv`：新法院自己的中立码，以及它判决里常引的外国码。只收**判决上印的那一串**（约束七）。用 `decisions/tools/build_neutral_court_codes.py`（CanLII API，限速 1 秒/次，key 走环境变量或 `--key-file`，不进仓库）。
2. `reporter_jurisdiction.csv`：新法院常引、表里还没有的汇编缩写，同形异义加区间行。
3. `identifier_systems.csv`：该法院判决里的数据库标识符。
4. `court_designations.csv`：括注里的法院标注（`(Ont. C.A.)`），当前只有 16 行，`unrecognized` 桶很大（#94）。
5. `bilingual_neutral_codes.csv`：有法语判决时。
6. 不要用默认值填空。查不到就让它 `UNSUPPORTED`，登记到 PROBLEMS。

如果分类层“反复拒收同一模式”，那是**缺一个形状的信号**，正确处置是把信号送回审计环、评估后在抽取层建形状并全量重跑，**不是让分类层就地重抽**（那会让它变成第二个抽取器）。

## 验证

- `python pipeline/tests/test_layers.py`（单元断言 171 条加迷你全链）；`--golden` 只证明旧产出没变（#98）。
- 改 `classify.py` 前后各留一份 `classified.csv`，用 `python audit/classify_diff.py --snapshot <目录>` 然后 `--before/--after` **全量逐行差分**，不要抽样（历史上抽样漏过 145 行回归）。
- 决策表接入后**抽样反查下游字段真被填了**，不能只看加载行数（#97）。
- 覆盖率：`python audit/table_coverage.py`（`--assert-only` 先自检口径）。

## 已知的坑

| # | 内容 | 状态 |
|---|---|---|
| 31 | `CanLII` 是 14 个法域共用的伪代码，不能入中立码表 | 走 `identifier_systems.csv`，法域由尾括注取 |
| 32 | CanLII 的 `jurisdiction` 是“馆藏归属”不是法院法域（`ukpc`=`ca`） | 建表脚本硬排除 |
| 33/36/41 | 归一键假命中（`F.C.`→`FC`） | 已修（结构闸、归一不判定、精确优先） |
| 34 | 建表首轮 overclaim“剩余全是噪声” | 已订正 |
| 35 | CanLII 供不出外国中立码（UKHL、EWHC、HCA…约 1,042 行）和机构自用码 | 须另找来源，授权要先评估 |
| 40 | `reporter_jurisdiction.csv` 早期是临时表，全部 `estimated` | 之后部分行升级，见 `verification_level` |
| 52 | 同形缩写（K.B./Q.B./S.C./P./C.L.R.…） | 已修（区间多行、前缀参与） |
| 85 | 日期被当引证 | 一期已修；#86 #87 未修 |
| 93/94 | 括注标注嵌套括号抓不到；`court_designations` 覆盖不足 | 未修 |
| 95 | 语料自带案名可能是错的（`[1914] A.C. 599`） | 案名投票会原样继承 |
| 96 | 报告年≠判决年（Anns 1977→1978 等 8 例） | 键里的年份是报告年 |
| 99 | `FCA` 加拿大与澳大利亚同码 | 未修（表层只有加拿大行；`[YYYY] FCA N` 带方括号的 17 行全是澳大利亚案） |
| 100 | `S.J.` 萨斯喀彻温判例 vs 英国 Solicitors' Journal | 已修（按卷号拆两行） |
| 102 | `A.R.`（安大略上诉 1880–1897 年）被判成 AB；`L.C.R.` 省丢了 | 未修 |
| 103 | 法语码对照有判错 | 已改表，13 行 |
| 104 | `[1998] 1 FC 549` 是汇编，不是中立码 `FC` | 未修 |

## 来源

规格 §5、§8；PROBLEMS #5、#31–#41、#43–#45、#52、#57、#58、#61、#85–#87、#93–#104；代码 `pipeline/classify.py`；表 `decisions/`。

核实状态：处理顺序、字段、函数位置、种类、标识符状态对照代码和 `classified.csv`（2026-10-03）【已核实】；各步规则细节【按规格】，规格标“待复核”的不另外核实。
