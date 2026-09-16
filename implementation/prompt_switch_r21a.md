# 任务：交付 run 切换到 r21a（2026-09-15）

**执行者：zcode。**

## 背景

`implementation/r21_fix_report.md` 记录的 #21（债 1）修复已由用户和 Claude 独立核对：
六道门各自重跑均 exit 0；提及级差分独立复算（不依赖 `audit/r21_diff.py`）：
计数提及 532,101→532,736（+635）、**消失 0、身份变化 0**、七个既有形状逐字节不变。
用户已决定：**交付 run 切换到 `data/run_20260915_r21a`**。

## 已知的两处需要如实记录的问题（不是要你重新论证，是要写进交接材料）

1. **`--golden` 不是有效验证**：它只比对 `data/` 下的旧产出，对新代码没有证明力
   （`implementation/r2closure_audit/r2d_closure_report.md` 已有此说法）。`r21_fix_report.md`
   把它列为"闸③"，交接材料里改写为参考项，不算证据。
2. **组级成员重组**：独立复核发现 29 个 merge_key 的共组集合发生变化，涉及 8 对
   （旧组,新组）、13 个过门槛组的键。例如 R. v. Hamilton：r4c 里 `[2005] 2 S.C.R. 432`
   （2005 SCC 47）与 `(2004), 72 O.R. (3d) 1`（2004 ONCA）是两个独立组（dd 11 / dd 50），
   r21a 里前者被并入后者（dd 56）——这是两个不同判决（上诉关系）被合并，是错的；
   同一次重组里 `2003 BCCA 490` 被正确地移出了原组。
   **这不是本次修复引入的新缺陷**：过门槛组里"含弱依据成员"的比例在 r4c 与 r21a
   均为 36.5%（3,156 → 3,158 组），这类重组本来就会随任何抽取层变动而洗牌，
   根因已登记在 `implementation/demo_repair_progress.md` 的 **B21**（单锚簇搭车，
   R4 Stage 1 测量：4,035 组/5,249 搭车成员，拟议收紧规则因超红线+低效未采纳）。
   用户已决定：**不因此推迟切换，但要求把这 8 对组的前后对照列清楚，记入 B21**。

## 要做的事

### 1. 列出 8 对重组的前后对照（人工判断，30 分钟量级）

用独立复核用的方法（不是 `audit/r21_diff.py`，那个只报了"51 个键并组换名 + 1 例拆分"，
口径与本次发现的 29 键/8 对不一致，需要先弄清楚为什么两个数不一样，再出清单）：

```python
# 对 r4c 和 r21a 的 select_out/selected.csv，按 merge_key 建 (group -> {其余组内 merge_key 集合})，
# 交集比较，找出共组集合变化的 merge_key，按 (旧组, 新组) 聚合。
```

产出 `audit/findings/r21_group_reshuffle_8pairs.md`：每一对给出——
- 旧组、新组的 `merged_group_id`、`canonical_string`、`case_name_modal`、dd
- 涉及的 merge_key 列表
- 人工判断：**并对了 / 并错了 / 看不出**（不确定的写"看不出"，不要猜）
- 如果并错了，说明是哪两个不同判决被合并、上诉关系是什么

**已知的一对**（R. v. Hamilton）直接写"并错了：2005 SCC 47 是 2004 ONCA 判决的上诉审，
两个不同判决"，不用重新判断。

### 2. 把这份清单挂进 B21，不要开新债

在 `implementation/demo_repair_progress.md` 的 B21 条目后面加一段"2026-09-15 新证据"，
引用这份清单，写明：#21 修复触发的组级重组规模（29 键/8 对/0.016%）与 B21 已测的
搭车规模（4,035 组/5,249 成员）同源，不是新增缺陷。

**同时核实一件事**：DEBT_LEDGER.md 现在没有列 B21（它属于 `demo_repair_progress.md`
的另一本账，不在 PROBLEMS.md 的 62 条编号体系里）。这次先不合并两本账（用户已决定
另开一次做），但请在 DEBT_LEDGER.md 顶部加一行短注：「另有 demo 专属的 B1–B21 账本，
在 `implementation/demo_repair_progress.md`，尚未与本表合并」，避免下次有人以为
62 条就是全部。

### 3. 切换交付 run

- `implementation/run_registry.csv`：`run_20260914_r4c` 的 disposition 从 `keep_whole`
  改注记为"上一交付 run，保留供对照"；`run_20260915_r21a` 的 disposition 改 `keep_whole`
  并注明"交付 run（2026-09-15 起，见 r21_fix_report.md + r21_group_reshuffle_8pairs.md）"。
- `README.md:49` 那行目录树注释指向 r4c 的"★ 交付 run"，改指向 r21a；r4c 那行改注"上一交付 run"。
- 检查 `USAGE.md`、`DEBT_LEDGER.md` 里是否还有写死 `run_20260914_r4c` 路径或数字的地方
  （之前的 792 万交叉表、8,646 过门槛组数等），凡是引用了具体数字的地方，
  同步改成 r21a 的对应值（过门槛组 8,657、FOREIGN 边不变仍为 629 等——不变量不用改，
  变了的数字要改）。
- `PROBLEMS.md` #21 的表述已经在这次改动里写了"已修（须人复核）"，把"须人复核"
  去掉，改成"已修（用户 2026-09-15 复核通过，交付 run 已切换）"。
- `DEBT_LEDGER.md` §1 开头的"真债 8 条"部分不用再改（已经是 zcode 上次改的状态）。

### 4. 代码是否提交，由你按项目惯例判断并在报告里说明理由

`pipeline/shapes.py`、`extract.py`、`merge.py` 的改动目前在工作区未提交。
交付 run 切换意味着这是生产代码的既定状态，通常应当提交；但提交前确认：
- `git status` 干净，没有其他未预期的改动混进来
- commit message 需说明这是 #21/债 1 的修复，交付 run 从 r4c 切到 r21a，
  并引用独立复核的差分结果（+635/消失0/身份变化0）与 B21 关联说明
- 按 CLAUDE 项目惯例，commit message 结尾需要 `Co-Authored-By` 行——这次的执行链路
  较复杂（zcode 执行、Claude 复核、用户拍板），归属方式请在报告里说明你的选择，
  不要自己下最终结论，等用户确认后再推送（如果有远程仓库的话，本仓库看起来是本地库，
  不涉及 push）。

## 验收

- `audit/findings/r21_group_reshuffle_8pairs.md` 存在，8 对全部有判断结论。
- `implementation/demo_repair_progress.md` 的 B21 条目更新。
- `DEBT_LEDGER.md` 顶部加了两本账未合并的提示。
- `README.md`、`implementation/run_registry.csv` 指向的交付 run 改为 r21a。
- 报告 300 字以内：8 对的判断结果分布（几对对、几对错、几对看不出）、
  是否提交了代码及理由、还有什么没做完。
