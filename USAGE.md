# 使用说明：这份数据是什么、能回答什么、不能回答什么

**一句话。** 这是从加拿大两个法院的判决全文里抽出来的**外国判例引证频次表**：某个判例被
引了多少次。数据只来自两个语料，**不是全加拿大法院的引证统计**；下面每一条限制都请先读完
再用数字。

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
5. **判决身份判定的已知残余**：跨汇编平行引证的合并依赖共引（重合系数 ≥0.8）；法域表把
   全国性汇编（`D.L.R.`、`C.C.C.`）标为 CA，其中刊登的省级判决可能被分到最高法院
   （PROBLEMS #40）。错在少算或错分，不在虚高。

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
