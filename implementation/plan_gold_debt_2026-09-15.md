# 执行计划 v2：债 4 + 债 6 + 债 1（2026-09-15）

**执行者：zcode。** 范围按用户 2026-09-15 决定：只做债 4、债 6、债 1。
理由：现阶段是**制作方法**，不是最严格的论文发表口径。

**v1 与 v2 的差别**：v1 有三个任务（金标准备 / 债 8+9 文档 / 债 4+6），现已按新范围重写。
金标与文档任务暂缓，见 §5；债 3（BAILII 等外国来源授权）确认不做，理由见 §6——
**这一条不是搁置，是有测量支持的结论**。

---

## 0. 三处订正（v1 写错、已改）

| v1 的说法 | 实际（✅ 2026-09-15 实测） |
|---|---|
| 从 demo run `run_20260913_r2e` 抽样 | r2e 已在瘦身时删除。**唯一交付 run 是 `data/run_20260914_r4c`** |
| FOREIGN 384 条边、全来自 scope 规则 | r4c：FOREIGN 边 **629** = `court_scope_rule` 384 + `case_record` 245。过门槛的 FOREIGN 组只有 **11 个** |
| 债 4 解锁「域外引用」研究线 | 只对一半。196 行表只喂 `jurisdiction`（印在哪国的汇编里），**不喂来源地**（`decide.py:183` 明令禁止）。债 4 做完 FOREIGN 数不会变——这一点正好当不变量验 |

---

## 执行者须知（先读）

- **环境**：Windows，Python 3.11.9，pyarrow 25.0.0、PyYAML 6.0.3 已装，不新增依赖。控制台默认 gbk，打印中文或 `‑` 这类字符会报 `UnicodeEncodeError`，运行前设 `PYTHONIOENCODING=utf-8`。
- **大文件**：`candidates.csv` 约 380 MB、`classified.csv` 约 300 MB，一律 `csv` 模块流式读，设 `csv.field_size_limit(10**9)`。
- **语料**：`corpus/*.parquet` 只读，只能用 `pyarrow.parquet.ParquetFile.iter_batches` 按列投影，禁止 `pd.read_parquet`，禁止写入/移动/删除。
- **脚本**：bash heredoc 里嵌 Python 引号会坏，脚本先写成文件再运行。
- **run 目录**：`--out` 必须是新的空目录；失败目录原样保留、不删。
- **git**：不提交。做完由人审阅后再决定。
- **汇报**：每个任务 300 字以内，含产出文件、验收命令与退出码、实测数字（✅）与引自台账未复测的数字（📖）、本计划被发现写错的地方。

---

## 1. 任务总表

| 任务 | 内容 | 动生产代码？ | 人要做的 |
|---|---|---|---|
| C1 | 债 4：核实 `reporter_jurisdiction.csv` 196 行（**提案阶段**） | 否 | 抽 20 行复核后批准 |
| C2 | 债 6：核实 36 条境外中立码（**提案阶段**） | 否 | 同上 |
| C3 | C1/C2 批准后落表 + 全链重跑 | 否（只改决策表） | 看不变量报告 |
| D | 债 1：无卷号圆括号年份，**先测量、后决定是否改代码** | 可能（唯一一处） | 看判据是否过关，拍板 |

**写入范围**：C1/C2 只写 `audit/findings/`；C3 写 `decisions/` 两张表 + 新 run 目录；D 的测量阶段只写 `audit/findings/`，实现阶段才动 `pipeline/shapes.py`。
**全体禁区**：不改 `corpus/`；不删任何 run 目录；不批量抓取 BAILII / AustLII / SAFLII；CanLII API 限 1 次/秒且走缓存（key 在 `C:\api key\canlii.txt`）；未经核实的数字标【待核实】，不得作为实现依据（约束九）。

---

## 2. 任务 C1 + C2：债 4 与债 6（先提案，批准后落表）

### 2.1 这张表管什么、不管什么

- **管**：`classify.py` 用 `reporter_jurisdiction.csv` 给每行填 `jurisdiction` = **这条引证印在哪国出版的汇编里**（`A.C.` = 英国 Appeal Cases → GB）。✅ 实测 196 行，100% `confidence=estimated`、100% `verification_level=name_inference`；按法域分：GB 60、CA 47、QC 39、ON 13、US 12、BC 5、AU 4、AB 3、NS 3、MB 2、NB 2、SK 2。📖 台账：境外 51,024 行的 `jurisdiction` 全靠这张表。
- **不管**：来源地。来源地走三级瀑布 `case_record` → `court_or_reporter_scope`（12 行）→ `reporter_origin_scope`（40 行，法条级核实）。196 行表不在其中。

### 2.2 阶段一：提案（不碰 `decisions/`）

**债 4**
1. 用 `python pipeline/coverage_report.py --kind reporter` 按影响行数排序（先看 `--help`；需要 run 目录就用 `data/run_20260914_r4c`），**从影响最大的往下核**。
2. 每行至少一个权威来源，明确写出该缩写展开成哪套汇编、属于哪个法域，并抄下逐字 `evidence_quote`。可用来源：Cardiff Index to Legal Abbreviations、McGill Guide 的汇编附录、Bluebook 法域表、出版方或法院官网、国家图书馆目录。**只有维基百科不够。**
3. 带卷号/年份区间的同形异义行（#52）要把**每一种展开都核到**，并核对现有区间与来源是否一致。
4. 来源冲突或找不到 → 保持 `estimated` 并写明原因。**正确的「未核实」胜过自信的猜测。**
5. 核实状态记 `verified_research_agent`，沿用 `case_origin_manual.csv` 的先例：机器核的不冒充人核的。

**债 4 附带项（顺手做，成本极低）**：`decisions/series_prefix.csv` 现有 4 行（L.R.、Q.R.、Q.O.R.、M.L.R.），来源栏写着「语料结构证据（非权威源，待核实）」。这 4 行用同一批来源就能核（L.R. = 英国 Law Reports、Q.R. = Quebec Official Reports、M.L.R. = Montreal Law Reports），**而且任务 D 要靠这张表**，核实了它 D 的判据才站得住。同样只写提案，不落表。

**债 6**：按 `audit/findings/neutral_foreign_proposal.md` 的 36 条清单逐条到法院官网核。**只提议加进 `neutral_court_codes.csv`，不得顺带往 `court_or_reporter_scope.csv` 加来源地规则**——那需要单独的排他性证据，另走流程。

**产出**
- `audit/findings/reporter_jurisdiction_proposal.csv`：与生产表同列，加 `old_value`、`new_value`、`evidence_quote`；`confidence` 只在来源明确时升 `confirmed`。
- `audit/findings/series_prefix_proposal.csv`（4 行）
- `audit/findings/neutral_foreign_verified.csv`
- `audit/findings/reporter_jurisdiction_proposal_summary.md`：核了多少行 / 改了多少行 / 核不下来多少行 / 按影响行数加权覆盖率 / **逐条列出原来猜错的行** / 建议人工抽查的 20 行随机清单。

**没核完 196 行没关系**——停在干净处，报告到哪一行，高影响的优先。

### 2.3 人工关卡

在核实行里随机抽 20 行（约 10%），由人按 `evidence_quote` 回到来源复核。全对才批准落表；错 1 条以上整批退回重核。

### 2.4 阶段二：落表 + 重跑（批准后）

1. 写进 `decisions/reporter_jurisdiction.csv`、`decisions/neutral_court_codes.csv`、`decisions/series_prefix.csv`，逐行带 `source` 与 `source_locator`（约束八）。
2. `python pipeline/run_all.py --out data/run_<日期>_r5a`
3. 回归门全跑：`test_layers.py`、`test_candidates.py`、`run_regression.py --selftest`、`extract.py --fixture-check`、`test_layers.py --golden`（差分逐项解释，**不得**直接 `--golden-write`）。
4. **不变量（任一不成立就停下报告）**：
   - 相对 r4c，FOREIGN 边数 **629**、FOREIGN 组数 **342**、过门槛 FOREIGN 组 **11** 必须不变——196 行表不喂来源地，变了就说明有意外依赖。
   - 组数 **173,845**、过门槛组 **8,646**、dd 应不变：`jurisdiction` 只影响分类列。变了要逐组解释。
   - `occurrence` 守恒值 **532,101** 不变。
5. 报告：`jurisdiction` 各值的行数变化；`jurisdiction_confidence` 从 `estimated` 升 `confirmed` 的行数与加权覆盖率。
6. 更新 `implementation/run_registry.csv`；DEBT_LEDGER 关掉债 4、债 6。**交付 run 是否切到 r5a 由人决定。**

---

## 3. 任务 D：债 1（#21 无卷号圆括号年份）

### 3.1 是什么

`(1938) S.C.R. 423`、`(1874), L.R. 9 Ex. 192` 这类老式排版（省略卷号）目前七形状**零命中**。
📖 台账：形态出现 670 次/424 份，对照生产产出实际漏抓 **626 次**（A.C. 250、S.C.R. 79）。
这批集中在 19 世纪到 20 世纪中叶的判决，正是老地标案例那一批。

### 3.2 上次为什么回滚（两个失败都要防住）

1. **守卫在真实排版上从不触发**：尾部否定前瞻 `(?![0-9A-Za-z.,;])` 把句点也排除了，而脚注引证后几乎总跟句点，真实排版 ` Ch. App. 127.` 上守卫内层永远走不完。
   **当时的验证探针用的是自己手写的、没有句点的合成串。** 这个教训在本项目已经应验两次——
   **本轮任何正则探针必须从语料里取真实排版做输入，禁止手写合成串当验证依据。**
2. **误解析在去重中胜出**：`(1874), L.R. 9 Ex. 192` 与误解析 `(1874), L.R. 9` 跨度打平（14=14），次键起点更早者胜，正确串被挤进 superseded——**全语料毁掉上千条正确捕获**，而当时的仪器看不见"毁掉了多少正确的"。后来补了 `is_covered` 的 exact 档才看得见。

### 3.3 先测量，再决定（这是本任务的主体）

上一轮原型实测判据：**M1 真无卷号 1,091 / M2 正确拒掉的撞车误解析 1,632 / M3 误拒 14 → 1,091/1,646 = 0.66 < 3 → 维持登记不修。**

更深的结论是：`(1868) L.R. 1 H.L., Sc. 348`（「1」是卷号）与真无卷号 `(1924) A.C. 222` **结构上不可区分**，要分开必须靠 series_prefix 表。
当时表是空的，所以 #21 写下的解锁条件是：**「series_prefix.csv 就位后按前缀表区分 L.R./Q.R. 形态，再重测本判据」。**

✅ **这个前提现在满足了**：`series_prefix.csv` 已有 4 行（L.R.、Q.R.、Q.O.R.、M.L.R.，2026-09-11 填入）。所以本任务第一步是**重测**，不是直接改代码：

1. 在临时目录做原型（**零仓库改动**），用前缀表把 `(年) 前缀 卷 缩写 页` 这一族先识别出来、排除在候选之外。
2. 重测三个量：M1（真无卷号）、M2（正确拒掉的撞车）、M3（误拒），给出 `M1/(M2+M3)`。
3. 条件一的断言必须含**真实排版**的三组正反样例：尾随句点、单大写词尾部、分号平行。
4. **停止条件：判据 < 3 就不实现**，把重测结果写进 `audit/findings/` 和 DEBT_LEDGER，任务到此结束。这是允许的结果，不算失败。

### 3.4 若判据过关才进入实现

- 改的是 `pipeline/shapes.py`（形状自身结构），**不得**加任何缩写清单、法域清单或例外表（约束一、约束二）。
- 三道门全过才算数（#16）：
  - **门 1 零破坏（硬门槛）**：全量 kept 集合差分，改动前 kept、改动后不再被任何 kept 行覆盖的区间数必须为 **0**，否则逐条论证为非引证。**任一条真引证被毁即否决，不论收益多大。**
  - **门 2**：冻结散文样本 `pipeline/tests/prose_sample.py` 上，误报不得出现已知类之外的新类，去重后误报事件数不得高于锚值（现行锚：83 命中 / 6 误报）。
  - **门 3**：夹具 A–F **exact** 档零退化（A18/B15/C27/D6/E0/F0）。
- 然后 `run_all.py --out data/run_<日期>_r5b`（与 C3 的 r5a 分开跑，一次改动一个原因，便于归因）；回归门全跑；`--golden` 差分逐项解释。
- 报告：新增捕获行数、`jurisdiction` 落 UNSUPPORTED 的比例、过门槛组与 dd 的变化，以及**受影响最大的 10 个案子**（老地标预计在内）。

---

## 4. 执行顺序

```
C1 + C2 提案（并行）          D 的重测（可与 C 并行，不碰仓库）
        ↓                              ↓
人工抽查 20 行 → 批准            判据 ≥ 3 ？ → 否：写进台账，结束
        ↓                              ↓ 是
C3 落表 + 重跑 r5a              人拍板 → 实现 + 三道门 + 重跑 r5b
```

C 与 D 的测量阶段可以并行（写入范围不重叠）。**两次全链重跑必须分开**，否则 golden 差分无法归因。

---

## 5. 暂缓的两项（记录在案，不是取消）

| 项 | 暂缓代价 |
|---|---|
| 人工金标（v1 任务 A） | 现在没有任何"输出对不对"的独立证据：回归门只证明「和上次一样」，98.80% 召回只覆盖裸中立引证，而过门槛组的 **79%**（6,873/8,646）是汇编式引证，其精确率与召回率从未测过。发论文前必须补。 |
| 债 8 + 债 9（v1 任务 B） | 债 8：`USAGE.md` 没写 `key_occurrence_count`，两个 occurrence 列差 2.05 倍，谁拿错列对账就会以为数据错了。债 9：规格 v1.7（提交 `a70b3ca`）注记已写好但全标「待复核」，**只差人追认**，成本约 1 小时。 |

---

## 6. 债 3 确认不做（有测量支持，不是搁置）

**测量（✅ 2026-09-15，`select_out/selected.csv`，is_primary & kept）**：

| 汇编印在 | 来源地结论 | 组数 | dd 合计 |
|---|---|---|---|
| 外国汇编 | DOMESTIC_CA | **119** | 1,770 |
| 外国汇编 | FOREIGN | 11 | 241 |
| 外国汇编 | UNDETERMINED | 757 | 6,692 |
| 加拿大汇编 | DOMESTIC_CA | 6,072 | 99,323 |
| 加拿大汇编 | UNDETERMINED | 1,540 | 16,248 |

**两条结论：**

1. **来源地完全不影响案件统计。** dd 与分组由引证身份决定，来源地是事后贴的标签，不进计数、不进合并、不进门槛。榜单一个数都不会变。
2. **但"汇编分类 = 来源地"这个代理会错得很厉害，而且错在最显眼的地方。** 印在外国汇编、来源地已知的 130 组里，**119 组（92%）其实是加拿大案子**——枢密院审的加拿大上诉，判决印在英国 Appeal Cases 里。反方向误判 0 组。被引最多的几个：Citizens Insurance v. Parsons（dd 59）、Union Colliery v. Bryden（49）、Proprietary Articles Trade Assn v. AG Canada（48）、John Deere Plow v. Wharton（48）、AG Canada v. AG Ontario 禁酒案（40）——全是加拿大宪法经典。

**为什么债 3 仍然不做**：认出上面这 119 组靠的是**加拿大这边**的表（`case_origin.csv`，CanLII 的 ukpc 库 203 行，收 1888–1959 年加拿大上诉）加 R4 手工核的 32 行，**不是 BAILII**。BAILII 只对现代英国中立码（UKSC/EWCA 那类）有用，而过门槛的外国中立码只有 Thorner v. Major 一个。所以债 3 的投入产出比极低。

**口径限制（必须随数字一起引用）**：那个 92% **不能**推广到剩下 757 组未知来源的组。`case_origin.csv` 本来就只收加拿大枢密院上诉，"已知的里面九成是加拿大"部分是收录范围造成的选择效应。能说的只是：**至少 119 组是加拿大案子**（下界，不是比例）。要知道 757 组的真实构成，只能逐案核（R4 Stage 3 那种做法），不是抓 BAILII 能解决的。
