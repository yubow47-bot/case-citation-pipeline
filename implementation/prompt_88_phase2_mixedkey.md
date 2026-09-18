# 执行计划（第二期）：混合键的折叠判据（PROBLEMS #88）

接第一期 `implementation/prompt_88_89_registry.md` 与 `implementation/report_88_89_registry.md`。
**第一期的登记簿方案已否决**（`registered_only` 不是解，见下）。本期换一条路。
§0 的九条铁律照旧适用，**判据动手前锁死，不得事后放宽**。

## 1. 复核第一期后确认的事实（勿重新论证）

* 我（规划方）前两版对 #88 的归因**都被推翻**：Chieu 自己的组在基线里**本就独立完好**（`2002||scc||3`，dd=31，basis=anchor，来自 SCC 轮）。「真判决被吃掉」不成立。
* 真实情况是**一个键承担两种身份**。ONCA 轮 `2002||scc||3` 的 10 条 counted 提及：

  | 提及印的案名 | 条数 | 性质 |
  |---|---|---|
  | `Housen v. Nikolaisen` | 4 | 真笔误（引用方把 Housen 的号码写错） |
  | `Chieu v. Canada` | 2 | 真引用 |
  | 无名 | 4 | 不明 |

  现状把 10 条全折进 Housen（对 4 条对、对 2 条错）；`registered_only` 把 10 条全挡在外（对 2 条对、对 4 条错）。**两者各错一半。**
* `registered_only` 还有第一期未检出的连锁：被挡下的键自成一组、**组名同样是 `Housen v. Nikolaisen`＋2002**，于是 name_year 平行挂靠遇到两个同名同年的组而失效，**Housen 自己的平行引证掉出组**——`2002|211|dlr|4d|577` 602→21 singleton、`2002||scj||31`→4、`2002|2|scr||236`→1，全表 kept 17,379→17,366。
* **范围红线（已实测）**：全量带案名证据的键 88,785 个，其中 **14,006 个（15.8%）带 ≥2 个不同案名类**（SCC 6,756／ONCA 7,250）。绝大多数与笔误无关（早年无年份键、长短名变体、同页码碰撞）。**因此严禁做「按案名拆键」这类通用改动**——本期规则只许在「笔误折叠那一刻」触发，作用域是机制 B 那 21／35 个键的量级。

## 2. 要实现的规则

触发点唯一：`decide.py` 决定把键 K 以 `typo_number` / `typo_year` 折进根 `big` 的那一刻（`decisions_of()` 内，第一期已在此加过 `registered` 量）。

判据全部来自**印在判决上的案名**（约束七），不引入阈值猜测：

1. 取 K 的 counted 提及里印出的案名类集合（`nk()` 归一，空名不计）。
2. 记 `hit_big` = 是否存在与 `big` 的组名同类的案名；`hit_other` = 是否存在与之不同类的案名。
3. 分三档：
   * `hit_big and not hit_other` → **照常折叠**（纯笔误，现状正确，不动）。
   * `not hit_big`（含完全无名）→ **照常折叠**（现状行为，本期不动；这是机制 A 与 #89 的地盘，另案）。
   * **`hit_big and hit_other` → 混合键：不折叠**，K 保持独立，**并且抑制它的案名**（写 `name_rejected_reason=mixed_identity`，`case_name_modal` 置空）。

第 3 档的案名抑制是本期的关键，理由有二：无证据就不主张（约束四）；不抑制就会产生同名同年的对手组，把 Housen 的平行引证挂靠打散（第一期实测过的那条连锁）。

留痕：`<scope>/mixed_identity_holdouts.csv`，字段 `merge_key, big_key, big_name, name_classes(类:条数), counted_mentions, dd_k, dd_big`。

开关：`decide.py` 新增 `--mixed-key-holdout`（默认 **off**，不传时输出与现在逐字节一致）。`run_all.py` 透传。

**严禁**：改 `merge_key` 的构造；改 `own` 的任何一处用途；对非笔误路径的分组做任何改动；引入任何计数阈值（如"少于 N 条就忽略"）。

供数：`decide.py` 拿不到提及级案名。由 `merge.py` 在 `merged.csv` 增一列 `name_classes`（形如 `nk1:4|nk2:2`，只统计 counted 提及、空名不计，按条数降序，**全量输出不截断**）。该列在 `--mixed-key-holdout` 关闭时也照常产出（纯信息列，不改任何判断），并在判据 1 里证明它不影响既有产物。

## 3. 判据（锁死；每条报实测值，不达标就停手报告，不得改判据）

| # | 判据 | 通过条件 |
|---|---|---|
| 1 | 默认关闭 = 零效应 | 不传 `--mixed-key-holdout` 时，`decide_out`／`select_out` 全部产物与 `data/run_20260916_85date` **逐字节一致**（`name_classes` 新列只出现在 `merged.csv`，需单独说明它没进任何下游判断） |
| 2 | 规则确实触发 | **先在单键上证明**：`2002||scc||3`（ONCA 轮）落入第 3 档，`mixed_identity_holdouts.csv` 里有它，且 `name_classes` 与本文件 §1 的 4／2 分布一致。**这一条不过就停手**——第一期的教训是规则写完是空转 |
| 3 | 目标键 | `2002||scc||3`、`2002||scc||35` 不再带 `anchor_variant_typo_number`；它们的组 `case_name_modal` 为空且带 `mixed_identity` |
| 4 | **平行引证不得打散**（第一期踩过的坑） | Housen 组内 `2002|211|dlr|4d|577`、`2002|2|scr||235`、`2002||scr||235`、`2002|7|wwr||1` **仍在同一组**，basis 不退化为 `singleton`；`2002||scj||31`、`2002|2|scr||236` 的归属变化须逐条解释 |
| 5 | 地标解释 | Housen 的 dd 变化逐键归因、差额对得上（预期 602 → 570 附近） |
| 6 | 作用域没炸 | 全量触发第 3 档的键数**必须在 21／35 同一量级**；**> 100 即判定规则跑偏，停手报告**（红线见 §1 的 14,006） |
| 7 | 机制 A 不动 | 带 self_of 的 14 个键逐字不变 |
| 8 | 干净 A/B（全局） | 同一份 `candidates.csv`、只换开关。**必须同时枚举**：新增键、消失键、既有键 occ/dd 变化、新进 kept、跌出 kept——四类逐条列出并解释。（教训：#85 只查"既有键变大"漏掉 5 行腾位；第一期只在空转档跑 A/B，漏掉平行引证打散） |
| 9 | 测试 | 现有 155 条断言全过 + 新增断言钉三档判据（纯笔误照折、混合键挡住且抑制名、开关关闭时零效应）；`test_candidates.py` 378、`test_shape_21.py` 76 全过 |
| 10 | 金标 | 逐项复核后再 `--golden-write`。**第一期已查实 `data/` 与金标当前一致**，故本期差分即本期效应，不需要分两步 |

## 4. 顺带要做的收尾（第一期遗留）

1. **提交第一期基础设施**：`pipeline/registry.py`、`pipeline/registry_report.py`、`decide.py` 的 `--registry`/`typo_over_registered.csv`、`run_all.py` 的 `build_registry`/`--anchor-corpus`/`--corpus-dir`、`extract.py` 的 `--corpus-dir`。它们默认零效应且判据 1 已证，保留为仪器。
2. **改掉失效的帮助文本**：`--registry-gate` 现写着 `registered_only` 是「实测唯一能修 #88 的取值」——**该结论已被否决**，改为「三档均不能修 #88，见 PROBLEMS #88 与 report_88_89_registry.md；保留供后续测量」。默认仍是 `literal`。
3. **同步实验分支**：把 master 合并进 `exp/bcca-citt`（工作区 `D:\cases data analisis-exp-bcca-citt`），不要再用跨工作区跑主线代码的临时办法。`--corpus-dir` 保留（只读引用语料，不复制 178MB）。
4. `implementation/` 下第一期留的 `_probe_*.py` / `_ab_*.py` 等 20 个临时脚本：挑出判据复算要用的，改名归档到 `audit/`；其余删除。不要把一次性探针留在 `implementation/`。

## 5. 做完停下来等裁定

* Housen 的 dd 下降（预期 602→570）属「地标数字大幅变动」，须先解释后接受。
* 第 3 档对那 4 条真 Housen 笔误是**故意少算**（宁可漏，不可错——项目口径）。这个取舍要用户确认。
* 判据 6 若触发停手线，说明规则设计有误，报告而不是调参。

## 6. 工程注意

Windows；bash heredoc 嵌 Python 引号会破，脚本先 Write 到暂存目录再跑；多文件改动用打补丁脚本、每处断言恰好命中一次；`PROBLEMS.md` 任何脚本不得读取；语料只读（`pyarrow.ParquetFile.iter_batches` 按列投影，禁 `pd.read_parquet`）；`data/` 可重建，`decisions/` 是唯一不可再生资产。
