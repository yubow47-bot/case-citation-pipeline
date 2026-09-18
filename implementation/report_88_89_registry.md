# #88 / #89 全局判决登记簿 — 执行报告

执行对象：`implementation/prompt_88_89_registry.md`（下称「任务书」）。
本报告只报**实测**结果；判据在动手前已锁死，未放宽任何一条。

---

## 0. 一句话结论

任务书 §2.1 / §2.2 / §2.4 的**基础设施**（全局登记簿、锚语料、天花板监测仪）已按设计
落地并有测试与实测支撑；但 **§2.3 授权的笔误闸改法在实测下是「无操作」**——
`in_registry = bool(own[k]) or k in registry` 与紧随其后的 `and same_name[k]` 合并之后，
`or k in registry` 这一支恒被同名闸旁路，主线全 run **0 键变化**、Housen 的 dd 分毫不动。

我另做了两档取值实测（未授权，默认关闭、按 manifest 可追）：
只有把闸门条件改成 **「登记簿命中、且本轮看不见它是真判决 → 挡住笔误」** 才真正修得动
#88：主线机制 B 键 21 → 12（救回 9 个，其中 8 个是 SCC 判决），Housen 的 dd 602 → 570；
实验线（BCCA+CITT + SCC 锚语料）机制 B 键 35 → 24（救回 11 个）。
**是否采用这一档，请你裁定**（见 §7）。

---

## 1. 已实现的东西

| 文件 | 内容 |
|---|---|
| `pipeline/registry.py`（新） | 全局判决登记簿：`<run>/registry/decision_registry.csv`（`merge_key, decision_id, source_court, source`）+ `registry_crosscheck.csv` + `manifest.json` |
| `pipeline/registry_report.py`（新） | 天花板监测仪：`<run>/registry/ceiling.json` |
| `pipeline/decide.py` | `--registry <file>`、`--registry-gate {literal,own_or_registry,registered_only}`；笔误闸只多一个 `registered` 量，**`own` 的三处用途一处未动**；`<scope>/typo_over_registered.csv` 留痕 |
| `pipeline/run_all.py` | `build_registry` 步骤（所有 merge 跑完、第一个 decide 之前）；`--court`、`--anchor-corpus`（可重复）、`--corpus-dir`、`--registry-gate` |
| `pipeline/extract.py` | `--corpus-dir`（锚语料/外部语料只读引用）；`--corpus` 去掉 `choices` 限制（实验线要跑 BCCA/CITT） |
| `pipeline/tests/test_layers.py` | 新增 `test_registry_gate` / `test_registry_audit`（+21 条断言，134 → 155） |

**铁律遵守**：抽取层一个字没改（只加了 `--corpus-dir` 与放开 `choices`）；登记簿构键
**复用** `extract.process_text`（形状匹配 + #21 兜底语义 + 重叠去重）、
`classify.Classifier.run_row`、`merge.build_merge_key_v2`、`normalize.nk`——
**没有新写任何正则、没有任何缩写清单**；语料只用 `pyarrow.ParquetFile.iter_batches`
按列投影、只读；`PROBLEMS.md` 未被任何脚本读取。

### 登记簿的两个来源

* `source=self_citation` —— 各院 `merge_out/<court>/merged.csv` 里 `self_citation_of`
  非空的行（union）。主线实测 15078 键（SCC 8308 / ONCA 6770）。
* `source=corpus_citation` —— 锚语料 `citation_en` 逐条构键。主线语料实测
  SCC 1708 / ONCA 17772 键。
  **入表条件**：`citation_en` 整串恰好留下 1 条候选，且键的缩写槽属于
  `neutral_court_codes`（法院代码封闭集合）。其余如实跳过并计数：
  SCC 9119 条缩写槽是 `S.C.R.` 类汇编写法（条数多、进表只增噪声）、62 条空串、
  2 条形状不认；ONCA 6181 条是案卷号（`C33725`）、136 条空串。
  *注：这些「跳过」是按**缩写槽是不是法院代码**判的，与任务书 2.2 只举了中立引证的
  例子相比更宽——`[1989] 2 S.C.R. 368` 这类也会被跳过。*

**接线上的一个设计选择（请你确认）**：`run_all` 只在传了 `--anchor-corpus` 时才把
`--registry` 交给 `decide.py`（因为任务书的默认口径是「不传 `--anchor-corpus` 行为不变」）。
代价是：想用「自引并集」这一份登记簿（不需要任何锚语料），也得顺手写一个
`--anchor-corpus`。若你希望「有登记簿就用」，我可以改成只要 registry 文件存在就传，
默认仍为空、判据 1 不受影响。

### 天花板监测仪（判据 10）✅

主线：`typo_merges_total = 35`（`typo_number` 33 + `typo_year` 2）、
`by_court_family = {canadian: 35, foreign: 0, unclassified: 0}`、
`by_court_code = {scc: 14, onca: 18, bcca: 2, onsc: 1}`——与人工复算一致。
**foreign = 0**：现阶段登记簿这条数据驱动路径够用；哪天 foreign > 0 才是「必须重新
校准笔误判据本身」的信号（`ceiling.json` 的 `foreign_examples` 会给出具体案例）。

---

## 2. 判据逐条结果（判据未放宽）

| # | 判据 | 结果 | 实测 |
|---|---|---|---|
| 1 | 默认行为不变 | ✅ **通过** | 不传 `--registry` 重放 9 个裁定层产物（SCC/ONCA/cross 各 3 张表）与归档基线 **sha256 逐字节一致**（`criteria_results.json` 的 `criterion_1.files`）；另做**空登记簿对照**（把 `--registry` 默认值指向一张只有表头的空表、其余逐字节相同的副本）→ 9 张表同样全一致，证明「空登记簿 == 无登记簿」而不是「那段代码没跑」；`test_layers` 155 条断言全过 |
| 2 | 主线目标键不再带 `typo_number` | ❌ **不过** | `2002\|\|scc\|\|3`、`2002\|\|scc\|\|35` 在 `literal`（任务书写法）下**与基线完全相同**；两键的 `self_citation_of` 为空的那些行 `same_name` 恒为假，闸门永不动作 |
| 3 | 机制 B 归零（主线 20→0、实验线 31→0） | ❌ **不过** | 主线 21 → 21（0 键变化）；实验线 35 → 35。基线口径复算见 §3 |
| 4 | 机制 A 不动且全部留痕 | ✅ **通过** | 机制 A 键集合 14 个（主线）/ 17 个（实验线）逐字不变；`typo_over_registered.csv` 落 14 行（cross_court，与真机制 A 键一一对应） |
| 5 | 实验线身份 | ❌ **不过** | 三件 R. v. Smith 仍在一组；`2003 SCC 47`、`2000 SCC 7` 仍被并 |
| 6 | 干净 A/B | ⚠️ **字面通过** | 同一份 `candidates.csv`、只换登记簿：新增键 0、消失键 0、既有键计数变化 0——因为没有**任何**变化（不等于没漏，而是这次改动确实没生效） |
| 7 | 地标解释 | ⚠️ **无需解释** | Housen 的 dd 602 → 602，脱离/新进均为空。任务书预期的「dd 下降」在本实现下不发生（见 §5 的 570 一档） |
| 8 | 测试 | ✅ **通过** | `test_layers` 155（134 旧 + 21 新）、`test_candidates` 378、`test_shape_21` 76，全过 |
| 9 | 金标 | ⏸ **未写** | 见 §6 |
| 10 | 天花板仪器 | ✅ **通过** | `ceiling.json` 产出，`foreign = 0` 与人工复算一致 |

---

## 3. 三个口径的实测对照（同一份 `merge_out`，只换登记簿）

数据源：`data/run_20260916_85date` → `data/ab_88_89/`（重放产物与 `ab_report.txt` 都在
`data/` 下，可重建、可删）。**没有为 A/B 重跑抽取**。

| 重放 | 登记簿 | gate | typo 键 | 机制 B 行/键 | 机制 A 键 | Housen dd |
|---|---|---|---|---|---|---|
| 归档基线 | 无 | — | 35 | 21 / 21 | 14 | 602 |
| selfonly | 自引 union（15078 键） | literal | 35 | 21 / 21 | 14 | 602 |
| corpus | 语料 SCC+ONCA（19480 键） | literal | 35 | 21 / 21 | 14 | 602 |
| union | 并集（26435 键） | literal | 35 | 21 / 21 | 14 | 602 |
| union_intent | 并集 | own_or_registry | 35 | 21 / 21 | 14 | 602 |
| **union_regonly** | 并集 | **registered_only** | **26** | **12 / 12** | **14（不变）** | **570** |
| （只读内存复算 *） | 并集 | ideal | 29 | — | 14（不变） | — |

\* `implementation/_probe_rule_variants.py`：把各院 decided 行并成一轮来复算
`decisions_of`，目标是分辨三种规则本身，不替代生产重放；结论与 `union_regonly` 一致
（救回 9 个键、机制 A 不动）。进程内复算把三轮并作一轮、组边界与生产不同构，故 typo 键
总数报 38 而不是 35（差在 `2003||scc||7`、`2015||scc||48` 等键的另一处归属上）。

**为什么任务书的写法不动**（`decide.py` 内的实测注释）：

* 机制 B 的定义是「键的真判决在**别的法院轮**」——本轮的 `own[k]` 为空；
* 闸门是 `if in_registry and same_name[k]: continue`，而机制 B 的 `same_name[k]`
  （本组那一行 `self_case_name` 与组名比）**恒为假**；
* 于是无论 `in_registry` 怎么算（`own or registry`、`registry or own`、只 `registry`），
  条件都是假，笔误照样并。**任务书 2.3 的两行代码自相矛盾**。

`registered_only` 之所以有效：它不看名字，只看「登记簿知道它是真判决、而本轮不知道」
——这正是机制 B 的定义性特征；机制 A 的 `own[k]` 非空，走原来的同名闸，结论逐字不变。

### 判据 7 的逐条归因（`registered_only` 档）

Housen 组 `XC-G016818`：**dd 602 → 570（差 32）**，脱离 6 个键、新进 0 个键：

```
脱离：2002|211|dlr|4d|577  2002|2|scj||31  2002|2|scr||236
      2002||scc||3  2002||scc||35  2002||scj||31
```

**差额不是 6 而是 32**，因为 `dd` 数的是**判决**不是键：`2002|2|scr||236` 这一个键在
原组里挂了 27 个不同的被引判决（它的 `distinct_decisions_count` 是 1 是**单独成组时**
的值，成组后按组算）。同一批变化还把 `2000||scc||18` 组从 dd 121 降到 38、
`2002||scc||33` 从 1392 降到 570——即**共 39 个既有键的 occ/dd 变化**，全部是这 9 个键
各自脱离后带走的判决。这一档的爆炸半径比 9 个键听起来大得多，见 §7 的裁定要点。

---

## 4. 机制 B 的天花板：登记簿救不了它没有的键（可判定的新发现）

### 主线（SCC + ONCA 两语料）

21 个机制 B 键里，**只有 9 个**在「自引 ∪ 语料」登记簿里（`registered_only` 救回的正是
这 9 个）。剩下 12 个不在表里，例子：

```
2004||bcca||472   2004||scc||90   2008||onca||2006   2011||onca||903
2011||onsc||54    2015||onca||11  2015||scc||217    2016||scc||333
2017||bcca||457   2020||onca||2018 2023||scc||119   2012||scc||689
```

它们的真判决**不在任何一份被载入的语料里**（BCCA/ONSC/NSCA/FCA/YKCA/LSBC 无语料；
个别 SCC 键的语料写法与引文写法不同形，与 `citation_en` 的键形状差异同源）。
**结论：判据 3 的「主线 20 → 0」在登记簿这条路线上不可达**——上限是 12（本轮实测
能到 21 → 12）。

### 实验线（BCCA + CITT + SCC 锚语料）

35 个机制 B 键里，**只有 11 个**在登记簿里（全部是 SCC 判决）：

```
救回：2000||scc||3  2000||scc||7  2002||scc||6  2003||scc||47  2005||scc||31
      2011||scc||60 2013||scc||9  2015||scc||2  2016||scc||16  2016||scc||46
      2023||scc||3
```

**24 个救不回**，其中 22 个是「语料里没有那个法院」的键（BCCA/BCSC/FCA/NSCA/YKCA/
LSBC/ONCA），另有两个新问题值得单独立项：

1. **零填充口径不一致**：BCCA 语料自己的 `citation_en` 是 `2007 BCCA 306`（不填充），
   但引用文本里印的是 `1999 BCCA 0165`、`2003 BCCA 0443`——两种写法落在**两个不同的
   merge_key**（`1999||bcca||165` 在 BCCA 自引登记簿里，`1999||bcca||0165` 不在）。
   登记簿对不上，**再加语料也补不出这一页**。这属于抽取/归一层。
2. 三件 R. v. Smith 的 S.C.R. 键（`1989|2|scr||368` 等）仍靠共引成组：
   它们是 1989/1990 年的旧判决，`citation_en` 是汇编写法，走不到中立引证登记簿。

---

## 5. 任务书里与实测不符的三处（判据未动，只报事实）

1. **§1「同日发布的系列案」例证**：`2003 SCC 47 R. v. Edgar` 并进 `2003 SCC 46
   R. v. Johnson`、`2000 SCC 7 R.N.S.` 并进 `2000 SCC 5 Proulx`——**实测两例属实**
   （机制 B、登记簿救得回）。但三件 R. v. Smith 那例不是「笔误」形态，是共引拼组
   （`basis=cocitation`），登记簿够不着。
2. **§1 的实测规模**：任务书口径「`identity_basis=anchor_variant_typo_number` 且
   `self_citation_of` 为空」→ 主线 20 / 实验线 31。我复算同口径得 **主线 20（行级）／
   21（含跨院行的键级）**、实验线 31（行级）／35（含 `typo_year`）——**任务书的数字
   可复现**，差异只是我把 `typo_year` 与跨院行也算进来了（本报告统一按更宽的口径报）。
3. **§3 判据 9 的前提**：任务书说「仓库金标相对当前 HEAD 本就过期」。实测
   `data/` 根下的裁定/归并/选取产物与 `run_20260916_85date` **逐字节相同**，
   `python pipeline/tests/test_layers.py --golden` 打印「全量产出与金标一致」——
   **金标已被 #21 之后的某次运行重写过，现在是最新的**。所以「先写一次纯底座换代
   差分」这一步**没有可写的差分**（底座已经写过了）。

---

## 6. 判据 9（金标）：我停在这里，没写

理由：
* `--golden-write` 会把 `snapshot()` 读的 `data/` 根的四张产出 + 最终榜单前 25 组
  重新固化。本实现（`literal`）下裁定层产出与现状逐字节相同，所以**不需要**写；
  一旦采用 `registered_only`，需要**先把 `data/` 根重建成 `registered_only` 那一版**
  再写，否则金标会指向一个既不是旧版也不是新版的中间态；
* 该档的 dd 变化（Housen 602→570、39 个键的 occ/dd）属于「地标数字大幅变动」，
  按账本规定要先解释清楚才能接受——账我已经在 §3 逐条给出了，但**接受与否是你的决定**。

清单化地说：现在写金标 = 写「零变化」；采用新档后再写 = 写「Housen 570 + 39 键变化」。
两者都不是「先写底座、再写规则」的两步式，因为底座差分在上一次已经写掉了。

---

## 7. 需要你裁定的事（任务书 §4 三件 + 我在执行中发现的一件）

1. **`registered_only` 这一档要不要采用？**
   * 不采用（保持任务书字面）：判据 2/3/5 不过，登记簿是一套**零效应**的基础设施
     （但它把机制 A 从隐形变成可审，且天花板监测仪可用）。
   * 采用：主线机制 B 21 → 12、实验线 35 → 24；Housen dd 602 → **570**（脱离 6 键、
     差 32 是「判决数不是键数」的算术，逐条见表）；另有 39 个键的 occ/dd 变化。
     **代价**：爆炸半径比 9 个键的字面数字大得多，且判据 3 的两个「→0」都达不到。
   * 采用的话，我建议**同时**立项处理两类覆盖缺口：`--anchor-corpus` 之外的法院
     （BCCA/BCSC/FCA…）与零填充键形状不一致（§4）。
2. **Housen 的 dd 下降** 是否接受（只在采用 `registered_only` 时发生）。
3. **实验线的落地方式**：`D:\cases data analisis-exp-bcca-citt` 那份 checkout 与主线
   **不同步**（`pipeline/` 10 个文件、`decisions/` 3 张表都不同，含金标），拿它做
   A/B 会把「代码换代」混进「登记簿效应」。本轮实验线是**在主线工作区**用主线代码
   重跑第 2–3 层得到的（`data/exp_bcca_citt_ab/`，语料从 exp 只读引用）。
   要不要把 exp checkout 同步到主线、还是就把实验线固定成主线的 `--corpus-dir` 跑法？
4. **`--corpus-dir`**：任务书没提这个参数。我加它是为了让锚语料/实验线语料能被
   **只读引用**而不复制、不移动（沙箱与「语料只读」两条都满足）。若你希望严格按
   任务书，我可以在 exp checkout 里放一份 `SCC.parquet`（需要写仓库外的权限）。

> 任务书说「做到这里停下来报告」——我停在这里：默认档（`literal`）已落地、判据 1/4/8/10
> 通过、判据 2/3/5 不过，且不过的**原因**已定位到可复算的证据上。等你裁定第 1 条之后，
> 我再写金标、跑实验线的最终基线、以及 `PROBLEMS.md` #88/#89 的销账。

---

## 8. 复算入口与产物位置

**结论文件（机器可读，可直接复核）**
* `data/criteria_88_89/criteria_results.json` —— 判据 1 的 9 个 sha256、各档机制 B/A
  键数与键清单、天花板摘要、实验线两档
* `data/ab_88_89/ab_report.txt` —— 主线 A/B 的逐条比较输出
* `data/run_20260916_85date/registry/` —— 基线登记簿（15078 键，仅自引来源）、
  `registry_crosscheck.csv`（15078 行：两条路径只有自引一侧在场，故全部落
  `self_not_in_corpus`——这份不是真正的对照）、`ceiling.json`
* `data/smoke_88_89/registry/registry_crosscheck.csv` —— **真正的两路对照**：
  抽取两批（SCC/ONCA 各 1000 份）对 SCC 语料全量，SCC 侧 `self_keys 362 /
  corpus_keys 1708 / both_sides 8`，差集原因在 `registry/manifest.json` 的
  `corpus_stats.skipped_*` 与 `crosscheck_explanations` 里逐类列出
* `data/exp_bcca_citt_ab/` —— 实验线干净基线（noreg / self / scc / regonly 四档）
* `data/smoke_88_89/` —— 端到端冒烟（`--limit-batches 2 --anchor-corpus SCC`），
  证明 run_all 的 `build_registry` / `registry_report` 接线可用

**命令**

```powershell
# 基线登记簿（自引）+ 语料登记簿（SCC/ONCA 锚），并做两种来源的自校验
python pipeline/registry.py --run-dir data/run_20260916_85date --extracted-courts SCC,ONCA
python pipeline/registry.py --run-dir data/ab_88_89/reg_corpus --anchor-corpus SCC `
       --anchor-corpus ONCA --corpus-dir corpus
# 五次重放（只重跑裁定层，不吃抽取）+ 比较 → data/ab_88_89/ab_report.txt
python implementation/_ab_88_89.py  --base data/run_20260916_85date --ab data/ab_88_89
python implementation/_ab_compare.py --base data/run_20260916_85date --ab data/ab_88_89
# 判据 1 的两条不变性检查（自比 / 对提交版）
python implementation/_probe_decide_invariance.py data/run_20260916_85date
python implementation/_probe_decide_invariance.py data/run_20260916_85date --rev HEAD
# 实验线（主线代码 + exp 语料，只读引用）
python implementation/_exp_baseline.py `
       --candidates "<exp>\data\run_bcca_citt_post85\extract_out\candidates.csv" `
       --exp-corpus "<exp>\corpus" --out data/exp_bcca_citt_ab
python implementation/_exp_regonly.py
# 天花板 / 结果汇总
python pipeline/registry_report.py --run-dir data/run_20260916_85date
python implementation/_criteria_results.py
```

> **注意**：`--rev HEAD` 那条会报 9 处不同，这是**预期**的——仓库 `data/` 下的运行
> 产物是 HEAD **之后**（#85 日期修复）重跑并重写过金标的，所以「当前代码 vs HEAD 代码」
> 本来就不同源。它能回答的问题只有一个：这次改动相对提交版有没有额外改变输出；
> 这一点由「自比」那一条以更强的形式回答（连空登记簿都逐字节相同）。

**诊断探针**（只读，全部在 `implementation/`，可删）：`_probe_88_89.py`（#88/#89 键清单）、
`_probe_rule_variants.py`（三种规则对照）、`_probe_registry_membership.py`（登记簿覆盖率）、
`_probe_own_per_key.py`（own 到底空不空）、`_probe_scopes.py`（各 scope 的机制 B）、
`_probe_cluster.py` / `_probe_housen_pairs.py` / `_probe_scc_round_fix.py`（Housen 组结构
与逐对复算）、`_probe_registry_keys.py` / `_probe_corpus_shape.py`（语料构键口径）、
`_probe_dedup.py`（重叠去重形态）、`_probe_exp_sync.py`（两个 checkout 的同步状态）。
