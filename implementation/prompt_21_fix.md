# 任务：#21 无卷号圆括号年份引证漏抽 —— 定位并修复

> 这份文件是交接给编码 agent 的完整任务书。它是**自包含**的：不需要任何对话上下文。
> 工作区：`D:\cases data analisis`（路径含空格，所有命令都要正确处理）

---

## 0. 先读什么（不要跳过）

| 文件 | 作用 |
|---|---|
| `README.md` | 五层架构与总体约束 |
| `USAGE.md` | 数据怎么读、有哪些已知少算（**读数据前必读**） |
| `DEBT_LEDGER.md` | 技术债台账；本任务对应 **债 1** |
| `PROBLEMS.md` | 历史问题台账；本任务对应 **#21**（只读，除本条状态行） |
| `data/README.md` | `data/` 目录说明与 run 保留规则 |
| `外国引证数据整理抽取管线项目技术规格.md` | 技术规格（§7.2 形状、§7.4 去重） |

**环境**：Windows + **Windows PowerShell 5.1**（不是 pwsh）+ Python 3.11.9 + pyarrow 25.0.0。

---

## 1. 问题（一句话）

老式英国上诉判决的引证有时写成 **`(1938) S.C.R. 423`** —— 年份在圆括号里、**没有卷号**。
现行 7 个抽取形状一个都匹配不上，**这类引证在最终产出里根本不存在**（不是抽错，是没抽）。

代码位置：`pipeline/shapes.py`（`SHAPES` 是 `(名字, 正则字符串)` 的列表，共 7 条；`SHAPE_ORDER` 是名字顺序表）。

**已实测确认（✅ 可直接复跑验证）**：

```
(1938) S.C.R. 423        → 7 个形状全部零命中      ★ 本任务的缺口
[1893-94] 1 S.C.R. 1     → shape_vol_abbr_page 抓到 "1 S.C.R. 1"（year=None）
100 O.R. (3d) 241        → shape_vol_abbr_page 抓到（year=None，因该汇编不印年份）
117 U, S. R. 113         → 零命中（属 PROBLEMS #12，不在本任务范围）
```

---

## 2. 已完成的测量（**不要从零重做**，但请复算校验）

用下面的形态在全语料枚举，并按"末尾数字是卷号还是页码"分类：

```
\((?P<year>(?:1[6-9]|20)\d{2})\)\s*,?\s*(?P<mid>[A-Z][A-Za-z'’.]*(?:\s+[A-Z][A-Za-z'’.]*){0,3})\s+(?P<num>\d{1,4})
```

判定规则：
- `num` 之后（允许标点/空白）若还跟着 `缩写 + 数字` → **num 是卷号**（如 `(1868) L.R. 3 Ex. 71`，内层 `3 Ex. 71` 是正确引证）
- 否则 → **num 是页码**（如 `(1924) A.C. 222`）

实测结果（SCC + ONCA 两份语料，全量）：

| 类 | 条数 | 含义 |
|---|---:|---|
| 数字是**卷号**，内层已被既有形状抽到 | 1,462 | **不是本任务的缺口**（只是缺年份 → PROBLEMS #10） |
| 数字是**卷号**，内层未被覆盖 | 7 | 待查 |
| 数字是**页码**，已被其他形状覆盖 | 577 | 无缺口（别处也印了标准写法） |
| **数字是页码，真漏抽** | **571** | ★ **本任务要修的** |
| 非汇编（`Chapter` / `Section` / `Arts` / `R.S.C.` 等） | 67 | **抽不到是正确的**，必须继续不抽 |
| 合计 | 2,684 | |

571 条真漏抽的构成（✅ 实测）：

- **判例引证约 280 条**：`A.C.` 144、`S.C.R.` 53、`O.J. No.` 22、`ONCA` 13、`P.` 9、`L.R.` 8、`O.R.` 8、`SCC` 8、`CanLII` 7、`S.C.` 5、`Crim. L.R.` 6
- **非判例约 50–70 条**：`Chapter`、`Section`、`Study Paper`、`Sup. Ct. Rev.`、`Working Paper`、`Arts`、`R.S.C.` —— 这些**必须继续抽不到**
- 其余零散，需逐条人工判定

> `PROBLEMS.md` #21 记的是"漏抓约 626 次（A.C. 250、S.C.R. 79）"。与实测 571～578 量级吻合；
> 但台账把 626 全算作缺口，实测显示其中约 50–70 条是**非判例、本就不该抽**。以实测为准。

**复算脚本**（直接 `python -` 或存文件运行；全语料扫描需数分钟）：

```python
import re, sys, collections
sys.path.insert(0, "pipeline")
import shapes
import pyarrow.parquet as pq

CAND = re.compile(r"\((?P<year>(?:1[6-9]|20)\d{2})\)\s*,?\s*(?P<mid>[A-Z][A-Za-z\u2019'’.]*(?:\s+[A-Z][A-Za-z\u2019'’.]*){0,3})\s+(?P<num>\d{1,4})")
SUB  = re.compile(r"^\s*,?\s*(?:at\s+)?[A-Z][A-Za-z\u2019'’.]{0,12}\.?\s+\d{1,4}")
NONREP = re.compile(r"^(Cap|No|Vol|Art|s|ss|c|para|R\.S|ch|Chap)\.?$", re.I)

def covered(win):
    return any(re.search(pat, win) for name, pat in shapes.SHAPES)

buckets = collections.defaultdict(list)
for court in ("SCC", "ONCA"):
    pf = pq.ParquetFile("corpus/%s.parquet" % court)
    for b in pf.iter_batches(batch_size=200, columns=["unofficial_text_en"]):
        for t in b.to_pydict()["unofficial_text_en"]:
            if not t: continue
            for m in CAND.finditer(t):
                s, e = m.span()
                cov = covered(t[s:min(len(t), e+45)])
                num_is_vol = bool(SUB.match(t[e:e+30]))
                mid = m.group("mid").strip()
                if num_is_vol:
                    k = "A 卷号" + ("（已覆盖）" if cov else "（未覆盖）")
                else:
                    k = "B 页码" + ("（已覆盖）" if cov else "（★ 真漏抽）")
                if not num_is_vol and NONREP.match(mid):
                    k = "C 非汇编"
                buckets[k].append(m.group(0))
for k in sorted(buckets):
    print("%-16s %5d" % (k, len(buckets[k])))
```

---

## 3. 历史：这条修过一次，**当天回滚**。回滚原因就是本任务的核心风险

（`PROBLEMS.md` #21 原文记录，2026-09-06）

上次的实现是给新形状加了一道"误解析守卫"：**页码后面紧跟「两个大写词 + 数字」就拒绝**。
结果发现三重问题：

1. **守卫失效**：守卫写成 `(?![0-9A-Za-z.,;])`，把**句点**排除在外；而真实脚注引证几乎总是以句点结尾
   （真实排版：`… Ch. App. 127.`），于是守卫内层永远走不完、**恒不触发**，等于没有守卫。
   → 根因：实施时的验证探针用的是**无句点的合成串**（教训原话：「验证/测量正则必须对真实排版测试」）。

2. **守卫失效的后果比不做更糟**：`(1874), L.R. 9 Ex. 192` 被误解析成 `(1874), L.R. 9`；
   这个错串与正确的长串**跨度打平（14 = 14）**，而去重规则在平局时取**起点更早**者 —— 正确的串被挤进 `superseded`。

3. 因此**修它反而弄丢了本来正确的引证**，当天回滚。

**去重规则现状**（`pipeline/normalize.py: dedup_overlapping`）：同一判决内区间重叠只保留跨度最长者；
排序键 `(-match_span, match_start_offset, shape_order.index(shape_name))`。

**新路线现状**（candidates-2.0，交付 run 走的就是这条）：`pipeline/extract.py: extract_candidates` 输出**全候选**，
由 `pipeline/merge.py: arbitrate_document` 在判决内仲裁（`KIND_PRIORITY` / `IN`·`OUT`·`UNDEC` 状态机）。
**动手前必须先读这两个函数，确认"容器候选 vs 被包含候选"的现行归属方向。**

---

## 4. 硬性约束（违反即失败）

1. **只在抽取层改**（约束一：问题在产生它的那一层修；约束六：形状改动必须在抽取层）。
2. **禁止固定缩写清单、禁止查表**（约束二）。排除 `Chapter` / `Section` / `Study Paper` 之类必须用**结构判据**，
   不得写死一张词表。
3. **只增不减（本任务最重要的不变量 K）**：改动后，**任何一条现有 kept 行都不得消失，
   也不得改变它的 `(match_start_offset, match_end_offset, shape_name)`**。
   → 等价于验收闸门①的「全量 kept 差分**破坏 0**」。
4. **禁止用合成串验证守卫**。所有守卫与边界测试必须用**真实原文**（带句点、带脚注号 `[12]`、带前后散文）。
   上次翻车就是这个原因。
5. **不删行**（约束五）：新增不上的只能留痕/进 `superseded`，不得删除任何既有行。
6. 不许顺手修别的债（本任务只做 #21）。

---

## 5. 必须满足的设计

### 5.1 兜底语义（fallback-only）

**新形状只允许在"该位置没有任何既有 7 形状命中"的地方生效。**

这样新候选与现有候选不可能同时出现在同一处，**从结构上消除**"新匹配挤掉正确匹配"的可能——
也就是把 §3 第 2 条的病因从根上拔掉，而不是靠仲裁规则去补救。

**约束 2 与兜底语义有张力，需你判断并在报告里说明**：candidates-2.0 路线的原则是"抽取层全量输出，不筛不判"。
若在生成处过滤会违反该原则，则改为**在仲裁处保证**：新形状的候选**永远不能**压过任何重叠的其他形状候选
（例如令其在 `KIND_PRIORITY` 中处于最低、且必须被 `contained` 关系攻击）。
**两条路都可以，但必须给出"不变量 K 成立"的证明或证据**。若无法在不违反约束的前提下达成，**停下来报告，不要强改。**

### 5.2 守卫按真实排版写

- 页码后**允许**紧跟句点、逗号、分号、右括号、脚注号 `[n]`、行尾。
- 真正要拒绝的是：页码之后**还有引证材料**（即"缩写 + 数字"，说明这个数字是**卷号**不是页码）。
- 用一个真实原文的样例集专门测这道守卫（见 §6.2）。

### 5.3 结构排除非汇编

要求 `mid` 呈"点分缩写形"（含句点、各段为短大写串），使 `Chapter` / `Section` / `Study Paper` /
`Working Paper` 自然匹配不上。**不得为此写死词表。**

### 5.4 必须钉死的回归用例（把上次的 bug 变成永久测试）

| 输入（真实排版风格，带句点） | 必须的结果 |
|---|---|
| `(1874), L.R. 9 Ex. 192` | **新形状不得在此生效**；仍解析为 year=1874 / series=L.R. / vol=9 / abbr=Ex. / page=192，且跨度为改动前原值 |
| `(1868) L.R. 3 Ex. 71, at 74.` | 同上，且不得被误解析为 page=3 |
| `(1924) A.C. 222.` | **必须新增**：page=222（A.C. 不印卷号），带句点也要命中 |
| `(1896) A.C. 359. [20] (1898) A.C. 700.` | 两条都要命中，且都不越界吞掉对方 |
| `(1926), Chapter 45, and by Section 2` | **必须仍然零命中** |
| `(1962), Sup. Ct. Rev. 107.` | **必须仍然零命中**（期刊，非判例） |

---

## 6. 验收：三道闸门 + 必做验证

### 6.1 三道闸门（`PROBLEMS.md` #16 既定规矩，缺一不可）

```powershell
python pipeline/tests/run_regression.py --selftest
python pipeline/tests/test_layers.py
python pipeline/tests/test_layers.py --golden
python pipeline/tests/test_candidates.py
```

- 闸门①：**全量 kept 差分「破坏 0」**——任何现有 kept 行消失即否决。
- 闸门②：冻结散文样本（`pipeline/tests/prose_sample.py`）**误报不新增类、且不超锚**（现行锚按 6 计）。
- 闸门③：夹具 A–F **exact** 零退化。

**当前基线（改动前就已验证为全绿）**：
`--selftest` exit 0；`test_layers.py` 120 断言全过；`test_layers.py --golden` 报「全量金标逐项一致」exit 0。
`test_candidates.py` 按文件头注释运行。

### 6.2 真实原文守卫测试

从语料里挑**真实**含目标形态的段落（至少 20 条，覆盖 §2 的 A/B/C 三类），断言守卫的行为符合预期。
**不要用自己拼的合成串做主证据。**

### 6.3 全量重跑与差分

```powershell
# 输出目录必须不存在或为空；失败的目录保留、换新目录重试
python pipeline/run_all.py --out data/run_<新目录名>
```

- 用 `run_manifest.json` 的 `status=complete` 判定跑通（complete 要求收尾时输入身份指纹与启动时逐字节一致）。
- **基线的 run 不要写死**：执行前先读 `data/README.md` 与 `implementation/run_registry.csv`，确认**当时的交付 run**
  是哪一个（本任务书写于 `data/run_20260914_r4c` 时代，其输入指纹为
  `92bd2840dc315383e7e5b6cde976d74d2ea9484bd838b15224dd3c8a4ea8426d`；
  但若 `plan_gold_debt_2026-09-15.md` 的任务 C 阶段二已经落表重跑，交付 run 可能已变成 `r5a` 之类）。
  **照抄该 run 的 `run_manifest.json` 里的 `input_identity.fingerprint` 作为基线指纹**，并在报告里写明用的是哪个 run。
- 全量重跑约 **14 分钟**（`implementation/rebuild_run.py` 记录了这个量级）。
- **要重跑就新建空目录；不要覆盖或修改 `data/` 里已登记的 run。**

**报告里必须给出的数字**：
1. 新增 kept 行数
2. **消失的 kept 行数（必须 0）**
3. **引用串身份发生变化的行数（必须 0）**
4. 对 `distinct_decisions_count`（dd）、门槛（`kept` 组数）、榜单前 25 的影响
5. 新形状命中的**逐条清单**（供人工分类：判例 vs 非判例）

---

## 7. 必须交付

1. 代码改动（`pipeline/shapes.py`，必要时 `pipeline/extract.py` / `pipeline/merge.py` / `pipeline/normalize.py`）。
2. 测试（§5.4 的 6 条回归用例 + §6.2 的真实原文守卫测试）。
3. 一份报告 `implementation/r21_fix_report.md`：改了什么 / 为什么这样改 / §6.3 的 5 组数字 / 未解决问题。
4. 更新 `PROBLEMS.md` 的 **#21** 状态行（改完写"已修（日期）+ 证据"，未完成写"未修 + 卡在哪"）。
5. 更新 `DEBT_LEDGER.md` 的**债 1**：关账则移到 §3 并写明关账方式；未关账则更新影响数字。

---

## 8. 不要做的事

- **不要 `git add -A`**（本项目历史上因此误纳过临时文件，见提交 `ed30689`）。
- **不要删除或修改 `data/` 里已登记的 run**；不要动 `corpus/*.parquet`。
- 不要修改 `decisions/` 决策表（本任务与决策表无关）。
- 不要顺手改 `shapes.py` 里其他形状，不要"顺便清理"。
- 不要把 §2 的测量当成结论直接跳过——**至少复算一次**，数字对不上就报告差异。

---

## 9. 环境坑（本项目踩过两次）

1. **`.ps1` 文件必须带 UTF-8 BOM**，否则 Windows PowerShell 5.1 按 GBK 读，中文注释被撕碎、脚本语法直接崩。
2. 控制台输出中文会乱码；跑 python 前设 `$env:PYTHONIOENCODING='utf-8'` 和
   `[Console]::OutputEncoding=[System.Text.Encoding]::UTF8`。**文件本身是否 UTF-8 要用字节校验，不要靠控制台显示判断。**

---

## 10. 与其他在跑任务的关系（**动手前必读**）

本任务与 `implementation/plan_gold_debt_2026-09-15.md`（人工金标 + 债 8/9 + 债 4/6）**是串行的**，本任务**排在它之后**执行。
原因：本任务会**新增引证**，必然改变 dd、组数、边数；而那个计划把「FOREIGN 边数与组数不变、组数和 dd 不变」
当作不变量来验收（§4.4），并且把当时交付 run 的**代码指纹**冻结进了金标抽样表表头（§2.2）。

### 10.1 动手前先确认（避免踩到它的残留）

1. `plan_gold_debt_2026-09-15.md` 的三个任务是否都已收尾（尤其**任务 C 阶段二**是否已重跑完）。
2. 读 `implementation/run_registry.csv` 与 `data/README.md`，确认**当前交付 run** 是哪个，并记下它的输入指纹。
3. 对该交付 run 先跑一遍 §6.1 的四条测试命令，**确认改动前就是全绿**。不绿就先停——那是前一阶段留下的问题，不是本任务的。

### 10.2 不要碰它的产出

- `audit/gold/` 全体（抽样表 `sheet_P.csv` / `sheet_G.csv` / `sheet_R.csv`、`CODEBOOK.md`、`gold_score.py`、`test_gold.py`）——
  这是人工标注的载体，**是不可重建资产**，只读。
- 任务 B 已改写的 `USAGE.md`、`DEBT_LEDGER.md` 的债 8/债 9 部分、`implementation/spec_v1.7_ratification.md`。
  本任务只动 `DEBT_LEDGER.md` 的**债 1 那一节**和 `PROBLEMS.md` 的 **#21**，不要整文件重写。

### 10.3 与本任务有关的一条既有结论（会影响你怎么写 §2 的对照）

金标（任务 A）是在**修改前**的 run 上抽的：它的 `P`（提及级精确率）与 `G`（组级正确率）样本来自旧产出，
本任务落地后这两张表**相对新产出已过期**，不要拿它们当本任务的验收依据。
但它的 **`R`（召回下界）样本是从语料段落抽的**，与代码无关——那 40 段可以复用，用来量本任务带来的召回提升。
**是否重抽金标由人决定，你不要自行重抽、也不要修改 `audit/gold/` 下任何文件。**

### 10.4 如果发现依赖冲突

若在执行中发现本任务的改动**必然**破坏 10.1 第 3 步已确认的某个基线（例如交付 run 已被切换但登记表没更新），
**停下来写清冲突再报告**，不要自行决定牺牲哪一边。

