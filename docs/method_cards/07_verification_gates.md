# 改完以后怎么验证没改坏

## 先记住这几条教训（每条都是真踩过的）

1. **`--golden` 只证明旧产出没变，不证明新规则对**（PROBLEMS #98）。新增或改动的代码要另跑全链测试并人工看差分。
2. **差分要全量，不要抽样**。分类层历史上抽样漏过一次 145 行的回归。
3. **验收既查“既有键变大”，也查“全新键出现”**。实验线 #85 只查了前者，漏掉 5 行腾位效应（被拒行退出仲裁池后，与它竞争的垃圾候选转判 counted）。
4. **“计数正确”不等于“语义生效”**。新增决策表后要抽样反查下游字段真的被填了（#97：32 行加载成功、零生效）。
5. **守卫和验证正则必须对真实排版测试**（含句点、脚注），合成串不算数（#21 的守卫对真实脚注引证失效）。
6. **A/B 要同输入同底座**，只换一个开关；否则差异分不清是谁引起的。
7. **测量脚本必须落盘、可重放**。只把数字写进文档等于没量（#34）。
8. **用一个结构上排除了某情况的仪器去证明该情况不存在，是循环论证**（#33：`shape_neutral_bare` 的 token 正则不收句点，所以拿它证明“中立码从不带句点”无效）。

## 命令清单

【已核实：命令和参数对照 `run_regression.py:401-404`、`test_layers.py` 文件头、`run_all.py`；2026-10-03】

### 抽取层

| 命令 | 作用 |
|---|---|
| `python pipeline/tests/run_regression.py --selftest` | 合成判例、去重等价断言、`12n` 截断、`_SEP` 逗号探针（应输出空） |
| `python pipeline/tests/run_regression.py --field-audit` | 五条字段不变量（形状层），改 `shapes.py` 必跑 |
| `python pipeline/tests/run_regression.py --verify` | 按行重读 parquet，核对夹具切片逐字一致 |
| `python pipeline/tests/run_regression.py --throughput` | 全语料单核吞吐 |
| `python pipeline/extract.py --fixture-check` | 夹具验收门（exact 档，A18/B15/C27/D6） |
| `python pipeline/tests/corpus_counts.py` | 语料级计数的唯一产生脚本（`--dedup`、`--prose-sample`）；规格和 PROBLEMS 里的语料级数字必须能由它重放 |

任何 `shapes.py` 改动：回归和 `--field-audit` 都要跑。负对照误报数增加或夹具漏项增加，修改退回重议。

### 第 2–5 层

| 命令 | 作用 |
|---|---|
| `python pipeline/tests/test_layers.py` | 单元断言（现 171 条）加迷你全链（合成数据，秒级） |
| `python pipeline/tests/test_layers.py --golden` | 当前产出对照金标（全量差分）；**只证明旧产出没变** |
| `python pipeline/tests/test_layers.py --golden-write` | 显式重写金标；只在改了规则、逐项复核过差分之后才用 |

每条断言都钉着一个真栽过的坑并注明 PROBLEMS 号，**删断言前先读那一条**。迷你全链不经抽取与分类，直接造 `classified.csv` 喂归并层，因为“每层单看都对、接起来才错”的缺陷只有全链测得出来（#47）。

### 审计环（`audit/`，只出提案，生产线不读它的产出）

| 工具 | 用途 |
|---|---|
| `audit/classify_diff.py` | 改 `classify.py` 前后的 `classified.csv` 全量逐行差分（`--snapshot`、`--before/--after`） |
| `audit/table_coverage.py` | 决策表对抽取产出的覆盖率，漏网的疑似真法院码；`--assert-only` 先钉口径 |
| `audit/neutral_triage.py` | 漏网“疑似真法院码”的三判据分诊 |
| `audit/extraction_recall_audit.py` | 对语料自带真值 `cases_cited_en` 量抽取召回 |
| `audit/residual_mining.py` | 找“像引证但抽取层没覆盖”的串，按模板归类（`--court`、`--out`） |
| `audit/gap_audit.py` | 抽取层缺口审计，残差聚类供人判断要不要新形状 |
| `audit/select_content_diff.py`、`audit/r21_diff.py` | 选取表和某次修复的内容差分 |

### 外部核对（CanLII）

- `audit/canlii_crosscheck/`：`t1_catalog.py`（库名录）、`t2_sample_fetch.py`、`t2_compare.py`（边级对比，用 `CROSSCHECK_RUN` 指向 run）、`t3_landmarks.py`、`t5_review_packet.py`、`t5_q_resolve.py`、`t6_calibrate.py`。
- 加新法院：`t2_compare.py` 里 `DB = {"SCC":"csc-scc","ONCA":"onca","BCCA":"bcca"}` 要加新法院的 CanLII databaseId；抽样按法院×时期分层。
- 结论的局限：CanLII 侧自己也不是真值；“配不上”多数是标识符对不上。**不能由此推出整库准确率**，只能给分层的估计。

### 结果库和检索

- `python tools/foundation/after_run.py --run data/run_X`：导入（8 项一致性校验）、权重、检索文本、向量。
- `python tools/foundation/acceptance.py`：固定问题验收（案件 15 题、方法 12 题）。案件题偏向知名先例，**不能当总体质量**。

## 一次完整验证的顺序

1. 改动前：留 `classified.csv` 快照（`classify_diff --snapshot`）；记下现有 run 的关键计数。
2. 改动后：`run_regression.py --selftest`、`--field-audit`，`test_layers.py`。
3. 小批量冒烟：`run_all.py --out data/run_smoke --limit-batches 1`。
4. **全量重跑到新目录**（`run_all.py --out data/run_<日期>_<名字>`，目录必须不存在或为空；`status=complete` 才算完整，完成要求输入身份指纹与启动时逐字节一致）。
5. 与旧 run 做差分：新增键、消失键、既有键变化、`kept` 变化，逐类解释。
6. `test_layers.py --golden`，差分是预期内的才 `--golden-write`。
7. 登记到 `PROBLEMS.md`（用 `audit/append_problems_entry.py`，它只按 CRLF 追加，不会把整份文件改写成 LF），写清数字和处置。
8. 旧 run 按保留规则处理：保留新交付 run 加上一基线，更老的先在 `implementation/run_registry.csv` 登记，再压缩归档或删除（`data/README.md`）。

## 来源

规格 §12、§13.1；PROBLEMS #16、#21、#33、#34、#47、#85、#97、#98；`pipeline/tests/`、`audit/`；`data/README.md`。

核实状态：命令与参数对照代码（2026-10-03）【已核实】；教训来自 PROBLEMS 原文【按规格】。
