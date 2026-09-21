# 执行计划：全局判决登记簿（PROBLEMS #88 / #89）

给执行方：本文件自带全部上下文，按「设计 → 实现 → 验收」顺序做。
**判据在动手之前已经写死，不得事后放宽**。任何一条不过，停手报告，不要改判据。

## 0. 项目铁律（先读，违反即整条作废）

1. **在产生问题的那一层修**。下游不得为上游缺陷加旁路名单／例外表。
2. 抽取层禁用任何固定缩写清单，只按结构匹配。**本次不改抽取层一个字**。
3. 不得从上下文关键词推断法域。
4. 无证据 → `UNSUPPORTED`，绝不填默认值。
5. **绝不删行**，只打标记（`rejected_reason` / `kept`）。
6. 层单向、各跑一次；下游可推翻上游结论，但**绝不回写上游产物文件**。
7. 决策表的键必须是**判决上印着的事实**，不得用管线生成的正典键。
8. 决策表每行必须带 `source` / `source_locator`；判断不得硬编码在代码里。
9. 未核实的数字与引文一律标【待核实】，不得作为实现依据。

口径：宁可漏（假阴性），不可错（假阳性）。

## 1. 要修什么（已核实的事实，勿重新论证）

裁定层 `pipeline/decide.py:481 same_decision_kind()` 的笔误规则：

> 同年、同法院代码、号码差一位（`_one_edit`）、且 `2*dda <= ddb`（少的那条不到多的一半）→ 判为号码笔误，并组。

它唯一的刹车在 `decide.py:570`：

```python
if own[k] and same_name[k]:
    continue          # 同名的另一件语料判决，不是笔误
```

`own[k]` 来自行上的 `self_citation_of`，而该标记**只在判决自己所属法院那一轮产生**（`merge.py:875`，条件 `self_citation == "true"`）。于是：

* **#88 跨院失明**：ONCA 那一轮不知道 `2002 SCC 3` 是真判决（Chieu v. Canada），把它与 `[2002] SCC 35`（R. v. Carlos）当成 `2002 SCC 33` Housen 的笔误并入——Housen 是主线 dd=602 的第二名。**同一个键 `2002||scc||3` 在 SCC 轮里带 self_of、正确自成一组（dd=31）**，两种结局并存于同一次运行。
* **#89 语料缺席**：实验线（BCCA+CITT）没有 SCC 语料，SCC 判决全部无锚。三件同名真判决 `[1989] 2 S.C.R. 368`（1989-09-14）／`[1989] 2 S.C.R. 1120`（1989-12-07）／`[1990] 1 S.C.R. 991`（1990-05-04）在主线分为三组（dd=7／3／6，basis=anchor|singleton），在实验线融为一组（dd=62，basis=cocitation）。`2003 SCC 47` R. v. Edgar 并进 `2003 SCC 46` R. v. Johnson、`2000 SCC 7` R.N.S. 并进 `2000 SCC 5` Proulx 同理（同日发布的系列案，编号连续）。

**实测规模**（口径：`identity_basis=anchor_variant_typo_number`）：

| | 合计 | 带 self_of（机制 A，见下） | 无 self_of（机制 B，本次要修的） |
|---|---|---|---|
| 主线 run_20260916_85date | 33 | 13 | **20** |
| 实验线 run_bcca_citt_post85 | 46 | 15 | **31** |

**机制 A 不在本次范围**：`same_name` 条件是刻意设计且有实测支撑（见 `decide.py` 文件头第五条：全量 101 对被当笔误并掉的语料判决，88 对头部名与组名一致、12 对不一致；例 `2008 ONCA 36` 真判决 Mickle v. Mickle 落在 R. v. Conway 组，那些 36 确是 326 的笔误）。**不要动它。**

## 2. 设计

### 2.1 全局登记簿

`run_all.py` 的执行顺序是三个独立循环：所有法院 classify → 所有法院 merge → 所有法院 decide。
因此**所有合并层跑完之后、第一个裁定层开跑之前**，是生成全局登记簿的天然位置，不打乱层序（约束六）。

新增步骤 `build_registry`，产出 `<run>/registry/decision_registry.csv`，字段：

```
merge_key, decision_id, source_court, source
```

* `source=self_citation` —— 来自各法院 `merge_out/<court>/merged.csv` 中 `self_citation_of` 非空的行（union）。
* `source=corpus_citation` —— 来自语料 `citation_en`（见 2.2），仅锚语料用。

登记簿是机器产物、可重建，**落在 `data/` 下，不得进 `decisions/`**（约束八只约束人工判断表）。

### 2.2 锚语料（#89）

`run_all.py` 新增 `--anchor-corpus <COURT>[,<COURT>...]`（可重复）：该语料**只生成登记簿，不抽取、不分类、不计数**。默认空——不传则行为与现在逐字节一致。

登记簿从语料的 `citation_en` 直接构键，必须复用既有归一函数，**不得新写正则**：

```python
# 键形状见 merge.py:244 build_merge_key_v2 → "year|vol|abbr|series|page"
# 中立引证 "2002 SCC 3" → year=2002, vol="", abbr=nk("SCC"), series="", page=3
#   => "2002||scc||3"
from normalize import nk
```

读语料只能用 `pyarrow.parquet.ParquetFile.iter_batches` 按列投影，**禁止 `pd.read_parquet`，禁止写入/移动/删除语料文件**。

**自校验闸（必须实现）**：对同时被抽取、又能从语料构键的法院（主线的 SCC、ONCA），两条路径（`self_citation` 与 `corpus_citation`）产出的键集合必须比对，输出
`<run>/registry/registry_crosscheck.csv`，列出双方差集的每一条。**差集不为空不等于失败**（早年判决没有中立引证、`citation_en` 是案卷号的 CITT 等都会造成差异），但**每一类差异必须在报告里归类说明**；无法归类的条目 > 0 → 停手报告。

### 2.3 裁定层怎么用它

`decide.py` 新增 `--registry <file>`（不传 = 空登记簿 = 行为不变）。
**只改一处**：`decide.py:570` 附近的笔误闸，`own[k]` 的判断改为

```python
in_registry = bool(own[k]) or k in registry     # registry 为全局登记簿键集合
if in_registry and same_name[k]:
    continue
if in_registry and not same_name[k]:
    # 机制 A：维持现状（仍可当笔误），但必须留痕
    stats["typo_over_registered_decision"] += 1
    audit_rows.append((k, big, registry.get(k, ""), dda, ddb))
```

**严禁**把 `registry` 掺进 `own[k]` 本身。`own` 另有三处用途——身份锚资格（`neu[k] or own[k]`）、dd 自引排除（`selfd |= own[k]`，#54）、#56 起始年判据（`neu[k] and not own[k] and _before_start`）。本次只授权笔误闸使用登记簿；动到其余三处需另行立项并各自测量。

`audit_rows` 落盘 `<run>/decide_out/<scope>/typo_over_registered.csv`——机制 A 现在是隐形的，这份清单让它可审。

### 2.4 天花板监测仪（必须实现，不是可选）

新增 `pipeline/registry_report.py`，每次运行产出 `<run>/registry/ceiling.json`：

```
{"typo_merges_total": N,
 "by_court_family": {"canadian": N1, "foreign": N2, "unclassified": N3},
 "foreign_examples": [...]}
```

分类依据 `decisions/neutral_court_codes.csv` 的 `jurisdiction` 列：GB/AU/ZA/US 等非加拿大法域 → `foreign`（现有 13 条：UKSC/UKHL/UKPC/UKUT/EWCA Civ/EWCA Crim/EWHC/EWFC/HCA/NSWCA/NSWCCA/NSWSC/ZACC）。

**这个仪器的意义**：登记簿只能覆盖我们有语料的法院。外国法院的判决原文 a2aj 数据集里根本不存在，**再加多少加拿大语料也补不出那一页**。当前实测 `foreign = 0`（主线 33 起、实验线 46 起全部是加拿大法院），说明现阶段这条数据驱动路径够用。**哪天 `foreign > 0`，就是必须重新校准笔误规则本身（收紧判据、不再单靠数量悬殊）的信号**——到那时会有具体案例支撑，不是凭空改阈值。

## 3. 验收（判据已锁死，逐条报结果）

| # | 判据 | 通过条件 |
|---|---|---|
| 1 | 默认行为不变 | 不传 `--registry` / `--anchor-corpus` 时，全链产出与 `data/run_20260916_85date` **逐字节一致** |
| 2 | 主线目标键 | `2002\|\|scc\|\|3`、`2002\|\|scc\|\|35` 不再带 `anchor_variant_typo_number`；Chieu、Carlos 各自成组 |
| 3 | 机制 B 归零 | `identity_basis=anchor_variant_typo_number` 且 `self_citation_of` 为空的键数：主线 20 → **0**；实验线（带 SCC 锚语料）31 → **0** |
| 4 | 机制 A 不动 | 带 self_of 的那一档：主线 13、实验线 15，**数量与键集合均不变**，且全部出现在新的 `typo_over_registered.csv` 里 |
| 5 | 实验线身份 | 三件 R. v. Smith 分为三组；`2003 SCC 47`、`2000 SCC 7` 各自独立 |
| 6 | 干净 A/B | 同一份 `candidates.csv`、只换「有无登记簿」跑第 3–5 层。除第 2/3/5 条涉及的键及其直接成员外，**其余键的 `occurrence_count` / `distinct_decisions_count` 变化必须为 0**；**新增键与消失键都要逐条列出并解释**（教训：只查「既有键有没有变大」会漏掉「全新键从未计数变为计数」） |
| 7 | 地标解释 | Housen 的 dd 变化量必须能**逐条**归因到具体哪些键脱离，差额对得上 |
| 8 | 测试 | `test_layers.py` 现有 134 条断言全过 + 新增断言钉 #88/#89（登记簿命中不当笔误、机制 A 仍可当笔误且留痕、不传参时行为不变）；`test_candidates.py` 378 条、`test_shape_21.py` 76 条全过 |
| 9 | 金标 | 逐项复核差分后才 `--golden-write`。**注意**：仓库金标相对当前 HEAD 本就过期（末次更新 `4a19fbf`，其后 #21 修复改了 `extract.py` +94／`shapes.py` +40 却没更金标），所以差分里会混入与本次无关的底座变动——**必须分两次写**：先用「无登记簿」基线写一次（纯底座换代），再叠加本次改动写一次（纯规则效应），两次差分分别复核 |
| 10 | 天花板仪器 | `ceiling.json` 产出且 `foreign` 计数与人工复算一致；当前应为 0 |

## 4. 需要用户裁定的事（**不要自行决定，做到这里停下来报告**）

* 验收第 7 条会让 **Housen v. Nikolaisen 的 dd 下降**（主线 602、实验线 937 都会变）。它是全表最显眼的数字，账本规定「地标数字大幅变动须先解释清楚才能接受」。
* `--anchor-corpus` 是新接口，属动架构。
* 实验线要用 SCC 语料当锚，需把 `corpus/SCC.parquet` 提供给 `D:\cases data analisis-exp-bcca-citt`（**只读引用，不得移动或复制覆盖主线语料**）。

## 5. 工程注意

* Windows + PowerShell/Git Bash。bash heredoc 里嵌 Python 引号会破；脚本先用 Write 落到暂存目录再执行。
* 多文件改动用打补丁脚本，每处替换都断言「恰好命中一次」。
* `PROBLEMS.md` 是 CRLF 表格，**任何脚本都不得读取它**（约束：它绝不能变成载入式配置）。
* 主线跑法：`python pipeline/run_all.py --out data/run_<tag>`；实验线加 `PIPELINE_COURTS=BCCA,CITT`。
* 语料只读；`data/` 可随时删除重建；`decisions/` 是本项目唯一不可再生资产。
