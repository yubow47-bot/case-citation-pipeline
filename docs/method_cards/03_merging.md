# 第 3 层 归并

## 这一层做什么

**跨行统计：计数、投票、折叠。** 不做跨判决的判断，**不加载 `decisions/` 下任何文件**（这是与分类层的分界线，归并层只读行里的字段）。

- 输入：`classify_out/<法院>/classified.csv`。
- 输出（每个法院一份，`merge_out/<法院>/`）【已核实：目录清单和 `merged.csv` 表头】：
  - `merged.csv`：每个“键”一行；
  - `mentions_candidates.csv`：逐候选的**仲裁台账**（候选 id → 仲裁状态、让位对象、注记），追溯主干；
  - `folded_log.csv`：折叠日志（counted 行的印刷变体）；
  - `decision_ids.csv`：键 → 引用它的判决 id 并集；
  - `key_mapping.csv`、`manifest.json`。
- `merged.csv` 列：`merge_key`、`canonical_string`、`abbreviation`、`citation_kind`、`jurisdiction`、`jurisdiction_confidence`、`case_name_modal`、`occurrence_count`、`distinct_decisions_count`、`case_name_agreement`、`case_name_support`、`variants_count`、`candidates_admitted`、`candidates_rejected`、`self_citation_of`、`self_case_name`、`name_classes`、`observed_deciding_court`、`court_designation_*`、`year_printed`。

## 两件事

### 1. 判决内的重叠仲裁（全候选路线才有，规格 §9 没写，以代码为准）【已核实：`merge.py` 文件头和 `arbitrate_document`，`merge.py:351`】

抽取层给的是全部重叠候选。同一份判决（同 `source_decision_citation` + `corpus_row_index`）内，对重叠的候选做一次仲裁，决定谁计数：

- 行级先分：有 `rejected_reason` → `rejected_row`；`self_citation=true` → `self_citation_row`，二者不参与竞争。
- 同跨度同键折叠成一个等价类，只计一次。
- 攻击关系（胜者压败者）：`support_span`（同跨度异含义，表证据严格更强）、`same_key`（同键不同跨度，长者胜）、`contained`（相容包含，长者胜）、`dominated`（部分重叠，更高支持档）、`conflict_*`（同档不可裁决，互指）、`cross_boundary`（跨界解析）。
- 终态：**IN**（counted）、**OUT**（被压）、**UNDEC**（相持或无证据，**不计数，弃权**）。纯互指环保持 UNDEC，不用输入顺序或形状顺序破环。
- **“弃权”落成 0 计数**，不是 0.5，也不是重复计。这是约束四的计数版本。
- 仲裁**绝不**回调抽取或分类层。
- 状态取值（BCCA 实测）：`counted`、`alternative_unsupported_reading`、`self_citation_row`、`rejected_row`、`alternative_contained`、`alternative_same_key`、`span_alternative_undecided`、`overlap_undecided`、`cross_boundary_invalid`、`alternative_weaker_support`、`year_reread_as_vol_invalid`、`alternative_dominated_by_support`。

### 2. 键、计数、投票

- **归并键**用结构化字段拼接，不对整串压平：`year|vol|nk(abbreviation)|series|page`。卷号缺失留空位，不省略（`1978||ac||728` 与 `1978|1|ac||728` 是两个键，是否宽松匹配未决，#2）。`merge_key` 是内部标识，不承担与决策表关联（约束七）。
  - 认得的系列前缀并入缩写位（`Q.R.` 与 `L.R.` 不同键，#53）。
  - 年份位对“连续编卷”的汇编会零化（`volume_system`，由分类层盖章）。
- **计数**：`occurrence_count` 只数 counted 行（排除行级误报和自引行）；`distinct_decisions_count`（DD）是**判决 id 并集的基数**，不是取最大，也不是相加（#46）。判决 id 带法院前缀，跨法院天然唯一。
- **案名投票**：两级——先按 `nk()` 折叠拼写变体，再取众数；平票取更近年份（#44）。`case_name_agreement` 的分母是“投了票的行”，切不出案名的行是空票，所以 199 行里一行有名也报 1.0；因此另加 `case_name_support`（赢家票数 / max(计数行数, 票数)）（#60）。
- **质量列不做过滤**：`case_name_agreement`、`variants_count`、`candidates_admitted/rejected` 只作人工复核时的排序依据，**不用它们筛行**（候选少时一致度必趋近 1.0，不构成证据）。取舍交给选取层，且判据是 DD。
- **组内单值字段**（`citation_kind`、`jurisdiction` 等）在同键内可能不一致（`FC` 与 `F.C.` 同键）：取计数行的众数，平票取 `canonical_string` 所在行；不一致的组数进 manifest 的 `groups_with_internal_disagreement`，不静默（#42）。归并层不做裁决。
- `name_classes`：该键 counted 提及印出的案名类分布（如 `housen:4|chieu:2`），是纯信息列，供裁定层的混合键判据（#88）。

## 写表前的四条不变量（不过就拒绝写）【已核实：`merge.py` 文件头】

1. 每个键 `folded_log` 计数之和 == `occurrence_count`。
2. DD 是并集基数。
3. `mentions_candidates.csv` 行数 == 输入候选行数（不删候选，约束五）。
4. 每个键 `decision_ids.csv` 行数 == `distinct_decisions_count`。

## 加新法院时

- **归并层对法院基本无感**：用 `--court <码>` 参数化，同一套规则。**通常不用改。**
- 要警惕的是上游传下来的东西：
  - 零填充号码自成一键（`1999 BCCA 0010` 对 `10`）：**#90，仍未修**，BCCA 319 条、SCC 520 次、ONCA 27 次。#105 只处理了“判决引用自己”，没有处理“引用别的案子时的零填充写法”。
  - 日期被当引证会严重虚增（#85）：先确认分类层的 `date_form` 拦住了。
  - 自引识别失效（如 `citation_en` 不是引证）会让每份判决的 DD 多算一。
- 新法院的计数口径要和 SCC/ONCA 一致：DD 取并集，不要自己另算。

## 验证

- `python pipeline/tests/test_layers.py`：归并层单元断言和迷你全链。
- 守恒检查：各组 `occurrence_count` 之和 == 计数行总数（#47，迷你全链有断言）。
- 全量重跑后比对时，既查“既有键变大”，也查“全新键出现”。

## 已知的坑

| # | 内容 | 状态 |
|---|---|---|
| 2 | 卷号可省略的写法是否算同一引证 | 按严格匹配，未合并 |
| 42 | 组内单值字段取谁 | 取众数，计入 manifest |
| 44 | 案名投票对原始串计票，标点空格参与 | 已修（两级投票） |
| 46 | 只有数字不够裁定层算对 DD，相加虚高 62–90% | 已修（`decision_ids.csv`） |
| 47 | 跨法院轮 occurrence 虚高 1.59 倍 | 已修（用 `key_occurrence_count` 重算） |
| 53 | 归并键不含系列前缀 | 已修 |
| 60 | “一票定名”：切不出名的行不投票 | 加 `case_name_support`；**按它设闸实测为净负，未启用** |
| 72（B9） | 案名投票混入非 counted 候选（43.7%） | 【待核实】状态，以 PROBLEMS 原文为准 |
| 76（B13） | 年读作卷 | 已测，counted 0 条 |
| 90 | 零填充编号自成一键 | **未修** |

## 来源

规格 §9；代码 `pipeline/merge.py`（文件头、`arbitrate_document`、`build_merge_key_v2`）；PROBLEMS #2、#42、#44、#46、#47、#53、#60、#72、#76、#90。

核实状态：文件、列、仲裁状态、不变量对照代码与 BCCA 实测（2026-10-03）【已核实】；键与投票细节【按规格】。
