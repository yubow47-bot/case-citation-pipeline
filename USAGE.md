# 使用说明：这份数据是什么、能回答什么、不能回答什么

**一句话。** 这是从加拿大两个法院（SCC、ONCA）的判决全文里抽出来的**全部被引案件统计表**
——外国与国内引证均在范围内，每条带案名、法域、来源地、引用频次。用途是学术研究：对
法庭历史中被引案件的完整图景做可审计的统计。数据只来自两个语料，**不是全加拿大法院**；
下面每一条限制都请先读完再用数字。

---

## 1. 「被引 N 次」量的是什么

只量**两份语料里那些判决**对某个判例的提及：

| 语料 | 判决数 | 判决年份范围 | 文件 |
|---|---:|---|---|
| 加拿大最高法院（SCC） | 10,891 | **1877–2026** | `corpus/SCC.parquet` |
| 安大略上诉法院（ONCA） | 24,089 | **1998–2026** | `corpus/ONCA.parquet` |

也就是说：**地方法院（省高等法院、上诉法院除 ONCA 之外、联邦法院、行政裁判所）的引证
完全不在内**。一个案子在安省高等法院被引 200 次、在 SCC 里被引 3 次，这张表只会显示 3。
年份范围同样是硬边界：1877 年前的 SCC 判决与 1998 年前的 ONCA 判决不在语料里，那里面的
引证再重要也不会出现。

「被引 N 次」的 N 是**判决份数**（`distinct_decisions_count`，见下），不是提及次数。

## 2. `dd`（distinct decisions count）与 `occurrence_count`

| 列 | 含义 | 什么时候用 |
|---|---|---|
| `occurrence_count` | 语料里这一引证写法**被提及的行数** | 想量「出现得多不多」时看 |
| `distinct_decisions_count`（简称 **dd**） | **有多少份不同的判决**引用过它（同一份判决引十次只算一份） | 产品门槛用的是这个 |

为什么用 dd：同一份判决里反复引用同一个案子十次是常见写法，但那只是**一位法官的一次
法律行为**；`occurrence_count` 会把「一个法官引了十次」和「十个法官各引一次」算成同样
重要。dd 还天然防 OCR 噪音：噪音串几乎只出现在一份判决里，dd = 1。

**选 dd 就必须在最后一次合并之后**：同一件案子可能分别以 `A.C.`、`All E.R.`、中立引用等
写法出现；若在归并层就砍，「各 2 次」的两组会双双不达标，而它真实的 dd 是 4。本表的 dd 是
跨汇编、跨法院合并**之后**的并集基数。

## 3. `kept` 门槛是**未校准的占位值**

`data/select_out/selected.csv` 的 `kept` 列 = `dd >= 5`。**这个 5 没有依据**。代码里写死：

```
pipeline/select.py: THRESHOLD_CALIBRATION = "uncalibrated_placeholder_see_spec_11_2"
```

规格 §11.2 原文的意思：该值是按「外国地标案例查表」场景调的，范围扩展为全部引证后失去
依据，**在首次全量跑按 dd 分布重定之前，它只是占位值，不得引用为经过校准的参数**。
`data/select_out/dd_profile.csv` 是定标仪器（各候选阈值下剩多少组），重定阈值的决定权在
产品侧，不在数据侧。

不满足门槛的行**不删除**，只是 `kept=false`；完整表始终留存，任何时候都能回答
「某个案子为什么不在结果里」。

## 4. `jurisdiction` 与 `case_origin` 是**两件事**

- **`jurisdiction`** = 这条引证**印在哪一国出版的判例汇编里**。`[1896] A.C. 348` 印在英国
  出的《Appeal Cases》里，所以 `jurisdiction = GB`——**这不代表案子是英国的**。
- **`case_origin`** = 这**件案子本身**来自哪个法域。上面那件是加拿大宪法上诉案，故
  `case_origin = CA`、`deciding_court = JCPC`。

研究「外国法对加拿大法院的影响」时，必须按 `case_origin`（而不是 `jurisdiction`）来分。
**已知覆盖缺口**：`decisions/case_origin.csv` 目前 **203 行**，来源是 CanLII 的 `ukpc` 库
（枢密院审理的加拿大上诉），该库**只收 1888–1959 年**；1888 年前的加拿大枢密院上诉
（如 *Citizens Insurance v. Parsons* 1881、*Hodge v. The Queen* 1883）**没有来源可查**，
一律老老实实留 `UNDETERMINED`。除加拿大枢密院案件外，本表不覆盖其他来源地情形。
详见 PROBLEMS #59。

**另外：法域表本身未经核实。** `decisions/reporter_jurisdiction.csv` 现有 **196 行，100%
`confidence=estimated`、100% `verification_level=name_inference`**——全部是按缩写名字推断
的，**没有任何一行核对过权威来源**（PROBLEMS #40、Task 7 仍待决定用什么来源）。因此
`jurisdiction` 的取值应视为**未验证**；产品若要用它筛，请保留按 `confidence` 过滤的能力。

## 5. 表里几个需要知道的列

| 列 | 怎么看 |
|---|---|
| `kept` | `dd >= 5` 的占位门槛，见 §3 |
| `is_primary` | 组内代表行；一个 `merged_group_id` 下只有一行 `true`。**统计时按组去重、取代表行** |
| `case_name_modal` | 组内众数案名（先按归一折叠拼写变体，再取最常见的印刷形） |
| `case_name_agreement` | 投票者之间的同意度。**分母是「投了票的行」**——切不出案名的行是空票、不入分母，所以 199 行里只有 1 行切出名字时它也是 `1.0`。别把它当「全体一致」 |
| `case_name_support` | 赢家案名的票数 / `max(该键的计数行数, 票数)`。**这个才是「引用它的判决里有多少份站这个名字」**（PROBLEMS #60）；分母取 max 是因为自引行照样投票但不算计数行 |
| `case_origin` / `deciding_court` | 见 §4；未入表时是 `UNDETERMINED`，**不是**「等于 jurisdiction」 |
| `split_reason` | 这一组是怎么被拆出来的：`span`（年份跨度）/ `decision`（按中立引用拆判决）/ `unanchored`（无中立锚，靠共引拼组） |
| `same_name_near_year_peers` | 同名（归一后相等）、年份相差 ≤1 的**其他组**的组号。**只标记、不是合并建议**（PROBLEMS #62，见 §6） |

## 6. 少算清单：以下每一处都让真实引用数**不低于**表里的数

读到一个偏低的数字时，先对照这张表，不要直接下「这个案子很少被引」的结论。

1. **同名、年份相差 ≤1 的两组没有被合并**（PROBLEMS #62）。实测（组级计数）：所有组里
   同名、主行年份相差 ≤1 的组对 8,329 对，其中两边都过门槛的 **225 对**。它们混着两类：
   真不同的判决（`R. v. John` 每年一件）与**同一判决的两种写法**（例如 *R. v. O'Brien* 的
   `(1977), 35 C.C.C. (2d) 209` 与 `[1978] 1 S.C.R. 591`——两种写法在任何一份判决里都没
   同时出现过，数据里没有东西能连起来）。`same_name_near_year_peers` 列就是为这个加的，
   它同时也标出真不同的同名判决，机器分不开，**要人来判**。
2. **无中立锚的共引单元**（PROBLEMS #49/#55）。没有中立引用、又跟任何身份锚共引为 0 的
   写法，只能彼此拼组、标 `unanchored`。现行产出里 `split_reason` 含 `unanchored` 的过门槛
   组 **69 个，dd 合计 648**。（#55 登记时更窄的一次计数是 56 个单元、dd 合计 262、其中
   18 个 dd ≥5——两次口径不同，引用时写明是哪一次。）
3. **自引的残留**（PROBLEMS #54）。判决书头部会印自己的引证；归并层已不计入 dd，但
   `occurrence_count` 仍含「平行写法的自引提及」——即同一件判决用另一种汇编写法提到自己
   时，那一次提及仍在 occurrence 里，只有 dd 被剔干净。
4. **抽取层的 1.2% 少算**（PROBLEMS #63）。对语料自带的上游真值（74,750 条裸中立引用），
   只算最终保留的 span 召回 **98.80%**。漏掉的 **872 条不是没抽到，而是去重时输给了粘连
   案名的更长 span**（`Kvello Estate 2009 SCC 51` 顶掉 `2009 SCC 51`）。这些**不会变成
   错答案**：赢家串在分类层一律判 `UNSUPPORTED`（一部分带 `unrecognized_series_prefix`），
   是可见的诚实拒绝。效应量约「裸中立引用量的 1.2%」。
   **口径警示（2026-09 demo 修复轮加注）**：98.80% 是**上游自动中立引证对（判决, 引用串）
   的覆盖率**——它度量的是抽取+去重对语料自带元数据条目的覆盖，**不是**外国引证的
   整体召回率，更不是任何语义正确率证明；本轮（candidates-2.0 重叠枚举 + 仲裁）之后
   该数字对应的是旧去重路线的诊断口径，新路线的对照见 `implementation/diff_report.md`。
5. **判决身份判定的已知残余**：跨汇编平行引证的合并依赖共引（重合系数 ≥0.8）；法域表把
   全国性汇编（`D.L.R.`、`C.C.C.`）标为 CA，其中刊登的省级判决可能被分到最高法院
   （PROBLEMS #40）。错在少算或错分，不在虚高。
6. **数据库/厂商标识符引证**（R2F 轮修复；此前整类同档弃权 0 计数）。`YYYY CanLII N`、
   `YYYY CarswellJur N`、`YYYY DTC N`、`YYYY QCTAQ N` 等 identifier 引证曾在「年读法 vs
   卷读法」同档弃权下 0 计数。R2F 以 identifier_systems.csv 决策表（16 行，官方/权威手
   册来源）+ classify identifier 分支 + 既有支持分级解决。r2g 实测（shape_neutral_bare
   口径）：CanLII 1,763 → counted 1,760 + rejected 3；CarswellOnt 944 → counted 943 +
   rejected 1；DTC 年读法 counted（表语义 year_is_volume=yes）；QCTAQ 经新增法院代码
   counted；CanLIIDocs 为二手评论行级拒绝。拼写变体（CarswellNlfd 类）按精确匹配政策
   留空——是政策，不是债。

## 6b. 2026-09 修复轮：candidates-2.0 新路线（demo）

本轮加了第二条管线（extract 全候选 → classify 逐候选 → merge 判决内仲裁 → decide
→ select → edges），与上文 1–6 节的旧路线**并存**：

- **一次跑完**：`python pipeline/run_all.py --out <新的空目录>`（目录必须不存在或为空；
  失败目录保留，重试用新目录）。产物 `run_manifest.json`（status=complete 才算完整；
  complete 要求收尾时「输入身份指纹」——生产代码+全部决策表+select 配置+语料+参数——
  与启动时逐字节一致，R2-10），各层日志 `step_*.log`。
- **最终表怎么读**：`decide_out/cross_court/decided.csv`（组级结论写在**每一行**的
  group_foreign_status / group_origin_country / group_origin_status /
  group_origin_evidence_ids；成员级观察在 member_origin_* 与 identity_basis 列——
  组结论只由合格身份基础（anchor/同印刷串/双语变体/单例）聚合，启发式连接
  （name_year/cocitation/typo 变体）的证据留在 noncore_origin_evidence 审计列）；
  `select_out/selected.csv` 的 `kept` 仍只按 dd≥5（语义未动）；
  `decide_out/cross_court/effective_sources.csv` 是**唯一权威**的「来源判决→案件身份」
  关联（含被剔自引的 exclusion_reason）。
- **边**：`edges/citation_edges.csv` 一行 = 一条 (引用判决, 被引案件) 边；
  `edges/foreign_edges.csv` 只含 **supported 路径**的 FOREIGN 边（只经启发式路径
  到达的边标 edge_support=heuristic_only、foreign_status=UNDETERMINED，进
  `edges/tentative_edges.csv`——不冒充确证外国边）；`edges/self_excluded_edges.csv`
  留被剔自引供审计。
- **逐候选台账**：`merge_out/{SCC,ONCA}/mentions_candidates.csv`——每个候选的仲裁状态
  （counted / 让位 / 弃权 / 跨界作废…）与让位对象，是「为什么这个串不在结果里」的答案；
  `key_mapping.csv` 给出旧键→新键（系列/罗马页拆分）的映射。
- **案名投票口径**（R2 闭环 §8 敏感性参数，默认=生产行为不变）：
  `merge.py --name-vote-pool {current,dedup_position,counted_only}`。实测（run r2d_b）：
  dedup_position 与生产口径 100% 同结果；counted_only 只改案名列与分组切分
  （modal 变 5,271），dd/门槛/来源地/FOREIGN 边零变化。**case_name_modal 实际参与
  decide 的案件聚类，不是纯展示列。**
- **回溯原文**：`python pipeline/traceback.py --run-dir <run目录> --search <案名>`，
  再 `--candidate-id <id>` 取分类证据 + 仲裁状态 + 原文窗口（`<<…>>` 标出跨度）。
- 真实样例走读见 `implementation/demo_examples.md`；新旧差分见
  `implementation/diff_report.md`；修复工作记录见 `implementation/demo_repair_progress.md`。

## 6b. 2026-09 修复轮：candidates-2.0 新路线（demo）

本轮加了第二条管线（extract 全候选 → classify 逐候选 → merge 判决内仲裁 → decide
→ select → edges），与上文 1–6 节的旧路线**并存**：

- **一次跑完**：`python pipeline/run_all.py --out <新的空目录>`（目录必须不存在或为空；
  失败目录保留，重试用新目录）。产物 `run_manifest.json`（status=complete 才算完整；
  complete 要求收尾时「输入身份指纹」——生产代码+全部决策表+select 配置+语料+参数——
  与启动时逐字节一致，R2-10），各层日志 `step_*.log`。
- **最终表怎么读**：`decide_out/cross_court/decided.csv`（组级结论写在**每一行**的
  group_foreign_status / group_origin_country / group_origin_status /
  group_origin_evidence_ids；成员级观察在 member_origin_* 与 identity_basis 列——
  组结论只由合格身份基础（anchor/同印刷串/双语变体/单例）聚合，启发式连接
  （name_year/cocitation/typo 变体）的证据留在 noncore_origin_evidence 审计列）；
  `select_out/selected.csv` 的 `kept` 仍只按 dd≥5（语义未动）；
  `decide_out/cross_court/effective_sources.csv` 是**唯一权威**的「来源判决→案件身份」
  关联（含被剔自引的 exclusion_reason）。
- **边**：`edges/citation_edges.csv` 一行 = 一条 (引用判决, 被引案件) 边；
  `edges/foreign_edges.csv` 只含 **supported 路径**的 FOREIGN 边（只经启发式路径
  到达的边标 edge_support=heuristic_only、foreign_status=UNDETERMINED，进
  `edges/tentative_edges.csv`——不冒充确证外国边）；`edges/self_excluded_edges.csv`
  留被剔自引供审计。
- **逐候选台账**：`merge_out/{SCC,ONCA}/mentions_candidates.csv`——每个候选的仲裁状态
  （counted / 让位 / 弃权 / 跨界作废…）与让位对象，是「为什么这个串不在结果里」的答案；
  `key_mapping.csv` 给出旧键→新键（系列/罗马页拆分）的映射。
- **案名投票口径**（R2 闭环 §8 敏感性参数，默认=生产行为不变）：
  `merge.py --name-vote-pool {current,dedup_position,counted_only}`。实测（run r2d_b）：
  dedup_position 与生产口径 100% 同结果；counted_only 只改案名列与分组切分
  （modal 变 5,271），dd/门槛/来源地/FOREIGN 边零变化。**case_name_modal 实际参与
  decide 的案件聚类，不是纯展示列。**
- **回溯原文**：`python pipeline/traceback.py --run-dir <run目录> --search <案名>`，
  再 `--candidate-id <id>` 取分类证据 + 仲裁状态 + 原文窗口（`<<…>>` 标出跨度）。
- 真实样例走读见 `implementation/demo_examples.md`；新旧差分见
  `implementation/diff_report.md`；修复工作记录见 `implementation/demo_repair_progress.md`。

## 7. 语料许可（原文照录）

两份 parquet 的 `upstream_license` 列逐字如下（**两院不同**）：

**SCC**（10,891 行，全部同一段）：

> See upstream license, including non-commercial use and other restrictions: https://perma.cc/6Z3Z-UPAC. Note: This is an unofficial reproduction of a Supreme Court of Canada decision, without endorsement or affiliation by the Supreme Court of Canada.

**ONCA**（24,089 行，全部同一段）：

> See upstream license, including non-commercial use and other restrictions: https://perma.cc/55T7-3UEX. Note: This is an unofficial reproduction of an Ontario Court of Appeal decision, without endorsement or affiliation by the Ontario courts.

两段都明写 **non-commercial use and other restrictions**。**任何下游产品（包括商业用途）的
授权是否成立，是使用者的决定，这份文档解决不了、也不构成法律意见**；请自行打开上面两个
`perma.cc` 链接核对当时的许可条款。本项目对语料只做只读使用，不复制、不再分发判决全文；
**产出表里只保留引证串、案名、频次这些事实性数据**。

## 8. 怎么确认你手上的数字还是最新的

```bash
python pipeline/tests/test_layers.py --golden      # 全量产出与金标逐项比对
```

`pipeline/tests/golden_layers.json` 存着各层 manifest 的计数与榜单前 25——**上面引用的
每一个数字，只要重跑全链就会在这里现形**。`--golden` 报「与金标一致」说明你手上的数字与
写这份文档时一致；报差分说明数据已经变了，**以差分后的新数字为准，不要再用本文档里的旧数**。

回归防线：`pipeline/tests/run_regression.py`（抽取层）、`pipeline/tests/test_layers.py`
（第 2–5 层：单元断言、迷你全链、全量金标差分）。

本文档里的数字对应的产出：`data/select_out/selected.csv` **206,213 行 / 190,153 组 /
8,610 组过门槛**（2026-09-11）。
