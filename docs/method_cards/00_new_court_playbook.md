# 加一个新法院：总流程

## 先分清你要做的是哪一种

| 情况 | 例子 | 主要工作量在 |
|---|---|---|
| 引证写法和已有法院基本一样 | 另一个省的上诉法院 | 决策表（法院代码、汇编缩写、同形缩写区间）和核对 |
| 有自己的标识符体系 | 行政裁判所的案卷号、`J.E. 2004-1234`、`WT/DS58`、数据库标识符 | 抽取层可能要新形状；分类层 `identifier_systems.csv` |
| 判决头部不印自己的引证 | CITT 的 `citation_en` 是案卷号，自引记 0（实验线 E2） | 自引识别、裁定层身份锚 |
| 有法语判决 | 魁北克 | 双语中立码表 `bilingual_neutral_codes.csv`，法语编号体例 `no` |

## 流程（按顺序）

**0. 拿语料**【已核实：`pipeline/extract.py:65`】
- 语料是 `corpus/<法院码>.parquet`，只读快照。列：`citation_en`（判决自己的引证）、`document_date_en`、`unofficial_text_en`。
- 快照要登记下载日期、字节数和 SHA-256（规格 §1.3）。已有快照不得改写、移动、删除。
- 下载脚本 `scripts/download_corpus.sh`，注意它最初的目标是 SCC 加安大略法院，用之前先 `list` 看目标清单是否包含新法院。

**1. 先探语料，不要直接跑**
- `citation_en` 是不是真引证？CITT 的就是案卷号，`source_decision_citation` 会是 `CITT_<案卷号>`，自引识别随之失效。
- 判决头部是否印着自己的引证？SCC 和 ONCA 每份判决头 3,000 字符内都印（PROBLEMS #13，实测 100%）。新法院要自己测，不能假设。
- 引证里有没有零填充号码（`2007 BCCA 0443` 对 `443`）？BCCA 有，SCC 520 次、ONCA 27 次也有（PROBLEMS #90，仍未修；#105 只修了自引）。
- 有没有判决日期被当引证抽出来（`1 June 2007`）？BCCA 实测 13.8%、CITT 60.9%（#85，已在分类层修）。

**2. 跑抽取（小批量冒烟）**
- 选法院：环境变量 `PIPELINE_COURTS=BCCA,CITT` 或 `run_all.py --court X`（`run_all.py:196`、`extract.py:66`）。
- 冒烟：`python pipeline/run_all.py --out data/run_smoke --court NEW --limit-batches 1`。
- 判决 id 格式 `{法院}_{nk(citation_en)}`（`extract.py:364`），**必须带法院前缀**，否则跨法院并集会把两院碰巧同格式的编号当成同一份判决。

**3. 看分类层的输出，找缺口**
- 看哪些行是 `UNSUPPORTED`、`unrecognized_series_prefix`、`date_form`、`table_conflict`，哪些方括号标注 `unrecognized`。
- 覆盖率：`python audit/table_coverage.py`（漏网的疑似真法院码）。
- 抽取层有没有漏：`python audit/residual_mining.py --court NEW --out audit/findings/<目录>`（找“像引证但没被抽取层覆盖”的字符串，按模板归类）。
- 不要猜。查不到就让它 `UNSUPPORTED`，登记下来。

**4. 按症状找该改哪一层（只在产生问题的那层改）**

| 症状 | 层 | 做什么 |
|---|---|---|
| 一种引证写法完全抽不到 | 抽取 | 新形状或新槽位；走准入判据，见 `01_extraction.md` |
| 抽到了但法域是 `UNSUPPORTED` | 分类 | 往决策表加带出处的行，见 `06_decision_tables.md` |
| 同一个缩写在不同国家/年代指不同汇编 | 分类 | 同一缩写多行，带卷号或年份区间（#52、#100、#102） |
| 日期、期刊、条文号被当成引证 | 分类 | 结构判据拒收（`rejected_reason`），不改抽取层（#85） |
| 案名切错、带出整句散文 | 分类 | §8.7 案名清洗（#43、#45、#57、#58、#61） |
| 同一案件被拆成几组，或不同案被并成一组 | 裁定 | 身份判据（#48、#49、#55、#56、#88） |
| DD 虚高或数错 | 归并或裁定 | 并集基数、自引（#46、#47、#54、#105） |
| 来源地（外国案、枢密院上诉）判不出 | 裁定 | `case_origin*`、范围规则表（#59、#64–#68） |
| 保留多少、门槛 | 选取 | `select_config.yaml`，只打标记 |

**5. 验证（每次改动后）**，见 `07_verification_gates.md`：
`run_regression.py --selftest`、`--field-audit`，`test_layers.py`，`--golden`（只证明旧产出没变，#98），分类层全量差分 `audit/classify_diff.py`。

**6. 全量跑**
- `python pipeline/run_all.py --out data/run_<日期>_<名字>`（输出目录必须不存在或为空；`status=complete` 才算完整）。
- 跑完生成结果库和检索：`python tools/foundation/after_run.py --run data/run_...`。

**7. 外部核对（可选，但推荐）**
- 新法院在 CanLII 有库的话，用 `audit/canlii_crosscheck/` 抽样对照，对照脚本里 `DB = {"SCC":"csc-scc","ONCA":"onca","BCCA":"bcca"}` 要加上新法院的 CanLII databaseId。
- 样本要按法院和时期分层；早年判决差异更大。

## 表是空的不是故障（规格 §13.4）

新法院刚加上时，大量行 `jurisdiction=UNSUPPORTED`、`case_origin=UNDETERMINED`，这是正确状态：它如实表示“还没查证”。旧管线看起来填得满，是因为用推断填了空，其中相当一部分是错的。

## 在这条线上工作的几条纪律

- 约束一：不要在下游加绕过上游缺陷的清单。发现上游有缺陷，修上游。
- 改了 `shapes.py` 或规则，**全量重跑**才算数；抽样会漏回归（分类层历史上抽样漏过一次 145 行）。
- 验收既查“既有键变大”，也查“全新键出现”（实验线 #85 只查了前者，漏掉 5 行腾位效应）。
- “计数正确”不等于“语义生效”：新增决策表后要抽样反查下游字段真的被填了（#97，列名不一致导致 32 行加载成功但零生效）。
- 审计环（`audit/`）的产出是提案，生产线的任何脚本不得读它。

## 来源

规格 §1.3、§2、§3、§4.3、§12、§13.4；PROBLEMS #13、#85、#90、#97、#98、#105；实验线记录 `implementation/exp_bcca_citt_findings.md`；代码 `pipeline/extract.py`、`pipeline/run_all.py`。

核实状态：命令、文件名、参数对照代码（2026-10-03）【已核实】；症状到层的对应表依据规格和 PROBLEMS【按规格】。
