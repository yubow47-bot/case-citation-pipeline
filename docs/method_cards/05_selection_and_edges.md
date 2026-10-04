# 第 5 层 选取，以及边文件

## 选取层做什么

**一道门槛，判据是 `distinct_decisions_count`（DD），不删行，只打标记 `kept`。**

- 输入：`decide_out/cross_court/decided.csv`。配置：`select_config.yaml`，用 `--profile`（`default` 阈值 5、`loose` 2、`strict` 10）。
- 输出（`select_out/`）【已核实：目录清单】：`selected.csv`（全部行加 `kept`，产品只读 `kept=true`，完整表始终留存）、`dd_profile.csv`（DD 分布）、`manifest.json`（阈值和原文）。
- **用 DD 不用 `occurrence_count`**：一个法官在一份判决里引十次只是一次法律行为；DD 还天然防 OCR 噪声（噪声串几乎只出现在一份判决里，DD=1）。
- **门槛必须放在最后一次合并之后**（裁定层的平行汇编和跨法院合并之后）。放早了，同一案件在 `A.C.` 下 2 次、`All E.R.` 下 2 次，两组各自不到门槛被砍掉，而真实是 4。
- **不设高频豁免通道**（旧管线有一条 `occ>=20 且 dd>=10…` 的并行路径，四个参数没有依据）。
- 门槛值是**产品决定，不是数据决定**，所以写在 YAML 里，不写进代码。
- 不删行：任何时候都能回答“某个案子为什么不在结果里”。

## DD≥5 现在有依据了（2026-10-03 CanLII 校准）

- 规格 §11.2 写的是“`threshold_dd: 5` 当前无依据，只是占位”。这句话**已过期**。
- 用 CanLII 对照加手工核对原文（215 条边，按法院×时期分层抽样），**边是真实案例引证的比例**（`audit/findings/canlii_crosscheck/run_20261002_tables2/t6_calibration.md`）：

  | 被引案件 DD 档 | 1 | 2–4 | 5–9 | 10+ |
  |---|---|---|---|---|
  | 真实引用比例 | 75% | 82% | 99% | 100% |

  全部边加权 87.0%。错误主要是期刊、条文号、目录、正文数字被抽成引证，集中在 DD≤4。
- 因此 DD≥5 保留的组里约 99% 是真实案例引证（这说明数据识别出的是真案例，**不说明案件重要性**）。
- 权重 `canlii-t6-v1`（加权 DD = DD × 该档可信度）在结果库里，标 `experimental`，**不改 `kept`，不改 `select_config.yaml`**。要让它影响筛选是另一个需要单独决定的改动。
- 样本局限：DD 5–9 档只核了 29 条、10+ 档 57 条，还没有留出独立验证样本。

## 边文件（`edges/`，`pipeline/edges.py`）

一条边 = `(source_decision, resolved_cited_case)`，后者是 `merged_group_id`。**边的成员资格只来自 `decide` 的 `effective_sources.csv`**，decide 是唯一权威。

【已核实：`edges/` 目录和 `citation_edges.csv` 表头】文件：

| 文件 | 内容 |
|---|---|
| `citation_edges.csv` | 去重后的边，一对来源和组只有一条。列含 `foreign_status`、`origin_country`、`group_origin_*`、`edge_support`、`identity_status`、`origin_basis`、`mention_count`、`distinct_decisions_count`、`case_name_modal`、`mention_detail_key` |
| `self_excluded_edges.csv` | `excluded_self` 的来源：保留供审计，**不得作为普通边重现** |
| `tentative_edges.csv` | 只能走启发式路径（name_year、cocitation、unanchored、笔误）的暂定关系 |
| `foreign_edges.csv` | 境外相关边 |

- 不变量：每个组的 counted 来源数 == 该组 DD（同口径，`edge_dd_mismatch` 检查）。
- `edge_support`：路径经 `ELIGIBLE_BASES`（`anchor`/`singleton`/`same_citation`/`anchor_variant_bilingual`）→ `supported`，组级来源地可用；只经启发式路径 → `heuristic_only`，**不继承** FOREIGN/DOMESTIC，`foreign_status=UNDETERMINED`。
- **关系类型**（`tools/foundation/relations.py`，不在 pipeline 里）：被引组同时包含来源判决自己印的引证 → `same_case_history`（同一诉讼的另一级判决，如最高法院判决引用它上诉自的下级判决），否则 `other_judgment`。按身份判定，**不看“APPEAL from”这类措辞**。

## 加新法院时

- **选取层通常不用改**。新法院只是多了一些行；`kept` 按同一个 DD 门槛。
- 要重新问的是**门槛是否仍合适**：新法院的数据质量（日期误报多、自引失效）会拉低低 DD 档的真实率。先看 `dd_profile.csv`，再对新法院按 `canlii_crosscheck` 的方法抽样校准，不要直接套 SCC/ONCA/BCCA 的 99%。
- 边的**可靠度分层**要新法院自己的样本（法院×时期），早年判决的差异大。

## 验证

- 全量导入结果库时自带 8 项校验（`tools/foundation/build.py`）：每组一条主行；组内 DD、`kept`、来源状态一致；边不重复；每组边数等于 DD；边都有来源判决；有效关联和边互相对得上；外键不违反。
- `test_layers.py` 里有选取层断言（“DD 过门槛才 kept，不删行”）。

## 已知的坑

| # | 内容 | 状态 |
|---|---|---|
| 60 | 按 `case_name_support` 设闸实测为净负，未启用 | 已决定不启用 |
| 106 | 案件身份按案件分组，老案的一审、上诉审、终审被并成一组，`same_case_history` 标记只能覆盖一部分 | 未修 |
| — | DD 5–9 和 10+ 档的核实样本偏少，权重还没有独立验证 | 待做 |

## 来源

规格 §11、§11.2（订正见上）；代码 `pipeline/select_layer.py`、`pipeline/edges.py`、`select_config.yaml`；`audit/findings/canlii_crosscheck/run_20261002_tables2/t6_calibration.md`；PROBLEMS #60、#105、#106。

核实状态：文件、阈值配置、表头对照实际 run（2026-10-03）【已核实】；校准数字来自我们自己的核实样本，见校准报告。
