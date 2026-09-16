# #21（债 1）修复报告：无卷号圆括号年份引证 —— shape_paren_year_abbr_page

**执行者**：zcode（research agent；2026-09-15）。
**任务书**：`implementation/prompt_21_fix.md`。**基线 run**：`data/run_20260914_r4c`（交付 run，指纹 `92bd2840…`；改动前四道门实测全绿，见 §3.0）。**验证 run**：`data/run_20260915_r21a`（本次全量重跑新建目录，`status=complete`，指纹 `2175558c…`；**交付 run 是否切换由人决定**，代码未提交）。

---

## 1. 改了什么

| 文件 | 改动 |
|---|---|
| `pipeline/shapes.py` | 新增第 8 形状 **`shape_paren_year_abbr_page`**（SHAPES 末位）：`\((?P<year>…)\)` + 缩写（段间必须有句点、≤4 段、末段可带尾点）+ 共享 `_SERIAL_SLOT` + `_PAGE`。 |
| `pipeline/extract.py` | ① `FALLBACK_SHAPE` 常量 + `_n21_structural_ok()`（行级结构谓词）+ `_suppress_overlapping_fallback()` 等价的行内抑制；② `extract_candidates` / `extract_rows`（两路线同判据）：兜底匹配先过结构谓词、再对既有 7 形状候选做**重叠抑制**（生成处不存在即不存在）；③ 抑制计数分两档写入 run stats（`fallback_suppressed_structural` / `fallback_suppressed_overlap`）；④ manifest `shapes_version` 注记。 |
| `pipeline/merge.py` | `SHAPE_RANK` 末位加兜底形状（确定性保险，实际不可达——兜底候选与既有候选不可能重叠）。 |
| `pipeline/tests/test_shape_21.py` | **76 条断言**（新文件）：§5.4 六条回归用例 + 35 条真实原文守卫断言 + 兜底语义/结构谓词/双路线一致断言。 |
| `audit/r21_diff.py`、`audit/r21_new_shape_counted.csv` | 差分仪器 + 新形状 635 条 counted 行逐条清单（供人工分类）。 |

classify.py / normalize.py / decide.py / select.py **未改**（新形状行走 step1 通用 reporter 分支 → step3 查表；无卷号走 §8.6 `novol_year` 消歧；merge 键 `year||abbr||page` 与既有无卷号行同构）。

## 2. 为什么这样改（§5 设计的落地）

1. **兜底语义（§5.1，生成处过滤）**：任务书首选「新形状只在七个既有形状都不命中的位置生效」。实现为 extract 层的行内抑制——兜底匹配与任何既有形状候选（区间相交）重叠时**不产生候选行**（与 `scan_overlapping` 的 run 闸同性质：生成处不存在即不存在）。
   **与 candidates-2.0「全量输出」原则的张力（任务书 §5.1 要求说明）**：该原则指的是抽取层不做**语义**筛选（不查表、不判性质）；本抑制是**形状间跨度的几何规则**（位置上已有形状占位），与 #16 三闸同属结构层。判据不查任何表、不含词表（约束二）。**须人复核**：这是实现者补的生成处过滤，若人认为仍须走仲裁路线（兜底候选全部落 `alternative_*`、永不攻击），改动点只在 extract 层的两处抑制调用，语义等价。
2. **不变量 K 的证明**：兜底候选与既有候选**零重叠**（构造保证）→ `dedup_overlapping` 与 `arbitrate_document` 的全部规则（same_key/contained/dominated/…) 都以重叠为前提 → 既有候选的 (span, key, 字段, 状态) 不可能因新形状改变；新候选只能是**纯增量**。全量差分（§3）实证：消失 0、身份变化 0。
3. **守卫全部按真实排版写（§5.2，上次回滚的教训）**：vol 守卫容忍 `. , ;` 续接、允许 ≤3 字母小写连接词（and/of 类，结构判据非词表）、**罗马续接大小写都收**（首版只写 `[ivxlcdm]`，`(1763), R.S.C. 1985, App. II` 被全量原型当场抓出——「守卫必须对真实排版测」的第三次实证）；另有 p./page 续接守卫、斜杠续接守卫（`HCJ 5100/94` 流水号）、`page == year` 拒（`(1978), S.M. 1978` 制定法年份位）。
4. **结构排除非汇编（§5.3，无词表）**：段间必须有句点 + ≤8 字符段 + ≤4 段；行级谓词要求「点分形含单字母段」或「整段 2–8 位全大写」。`Chapter/Section/Study Paper/Working Paper`（无句点/超长段）、`Sup. Ct. Rev./App. Cas./Sel. Ca./Crim. L. Rev.?`（无单字母段——期刊与旧名义报告人）结构上不中。**代价（如实记）**：`CanLII`（混写大小写，7 条）、`AC.`（无单字母段，2 条）、`Sel. Ca.`（2 条）、无点名义报告人（`Vaughan/Dears/Kay/Sirey/Dalloz` 等，各 1–6 条）**继续不抽**——这些留在「真漏抽」清单里，属结构判据的既定代价（§5.3 允许）。

## 3. 验证（§6）

### 3.0 基线（改动前，r4c 时代）
`run_regression.py --selftest` exit 0；`test_layers.py` 120 断言全过；`test_candidates.py` 178 断言全过；`test_layers.py --golden` 全量金标逐项一致。

### 3.1 三道闸门 + 附加门（改动后，全部实测）
| 门 | 结果 |
|---|---|
| 闸①  `run_regression.py --selftest` | exit 0 |
| 闸①  `extract.py --fixture-check` | exit 0；exact A 18 / B 15 / C 27 / D 6 / E 0 / F 0 **零退化**（F 的 kept=6 为基线既有行为，已用「摘掉新形状重跑」对照确认） |
| 闸②  冻结散文锚（`corpus_counts.py --prose-sample`） | **83 → 83**，命中数与锚逐位持平（散文样本剔脚注行，兜底形状零新增）→ 无新误报类 |
| 闸③  `test_layers.py --golden` | 全量金标逐项一致（data/ 产出静态，未重写金标） |
| 附加  `test_candidates.py` | 178 断言全过 |
| 附加  `test_layers.py` | 120 断言全过 |
| 附加  `test_shape_21.py` | **76 断言全过**（§5.4 六条 + 真实原文守卫 + 兜底语义/双路线一致） |

### 3.2 §2 复算（全语料，改前）
合计 **2,684** ✓ 与任务书一致；分桶：A 卷号已覆盖 1,462 ✓、A 未覆盖 7 ✓、B 页码已覆盖 **578**（书 577，+1）、B 真漏抽 **585**（书 571，+14）、C 非汇编 **52**（书 67，−15）。差异如实记：测量口径全同（任务书脚本的逐字重放），差异来自任务书编写时的语料/形状基线与本日实测之间的漂移，量级一致（书自己写「571～578 量级」）。

### 3.3 全量重跑差分（§6.3 五组数字，`audit/r21_diff.py`，r4c → r21a）
1. **新增 counted 提及：635**（全部来自新形状；其余新增 **0**）。
2. **消失 counted 提及：0**。
3. **引用串身份变化：0**（匹配口径 = (court, corpus_row_index, merge_key, span) 逐字节配对）。
4. **dd / 门槛 / 榜单**：
   - 组 173,845 → 174,038；**过门槛（dd≥5）8,646 → 8,657（净 +11）**——14 个组首次过门槛（`(1726), Sel. Cas. T. King 61`（Keech v. Sandford）、`2008 SCC 20`、`2019 ONCA 638`、`(1903) A.C. 59`、`[1892] A.C. 309` 等），3 个旧键因并组换名退出；
   - dd 合计 125,485 → 125,649；**既有组 dd 上升 90、下降 0**（kept 集内）——头部如 `[1892] A.C. 437` 34→38、`[1899] A.C. 580` 49→52、`[1896] A.C. 348`（AG for Ontario v. AG for the Dominion）66→68、`(2004), 72 O.R. (3d) 1` 50→56；
   - **榜单前 25：无进无出**；唯一 dd 变化 `[2002] 2 S.C.R. 235` 601→602。
   - **组级换名的如实记**：51 个 (court, 规范串) 键消失 = **并组换名**（新引证把平行写法连进同一组，如 `(1726), 25 E.R. 223` 并入 Keech v. Sandford 组）——提及级零损失已证；另有 **1 例组拆分**：`2010 ONCA 899`（R. v. D. (R.)）——新增 ONCA 侧提及改变了案名投票，跨院按名合并失败，拆成 dd 2 + dd 2 两组（并集 4 ≥ 原 3，无提及损失）。这是组级切分口径的已知行为（同 §62 的「同名近年拆分」家族），非数据损失。
5. **新形状逐条清单**：`audit/r21_new_shape_counted.csv`，635 行（court、语料行号、原串、字段、法域、来源判决）。
   兜底抑制计数：SCC 结构拒 476 + 重叠抑 126；ONCA 结构拒 70 + 重叠抑 10。
   构成（按缩写）：A.C. 254 + A. C. 14、S.C.R. 73 + Can. S.C.R. 4、O.J. 24、P. 19、ONCA 15、S.C.C. 13、S.C. 13、SCC 9、O.R. 9、O.W.N. 8、S.A.E. 8、Q.R. 7、Sel. Cas. T. King 6、P.D. 5、Crim. L.R. 5、Crim. L. Rev. 4、其余零散。法域：GB 312、UNSUPPORTED 170、CA 89、ON 51、QC 5、NS 3、BC 2、NZ 1、AB 1、SK 1。
   **人工分类提示**：`Crim. L.R./Crim. L. Rev./S.A.E./L.S./Wis. L. Rev/N.Z.L.J./R.D. McGill/A.I.R. Madras/U.S. Av. R./C. Gaz./L.R.A./L.R.P./R.E.D./S. 81-4-23/S.C.C. File No./App. B./I.C.J.?（已拒）` 等约 60–80 条是期刊/书目/判例以外的形式——结构判据分不出来，**由人在清单上分类**；分类层对它们落 UNSUPPORTED（诚实拒绝），不影响 dd。

## 4. 未解决问题（如实记）

1. **交付 run 未切换**：r4c 仍是交付物；r21a 是验证 run。切换（并 `--golden-write`）由人决定。
2. **真漏抽的既定残余**（本设计不追）：`CanLII` 7、`AC.` 2、无点名义报告人（Vaughan/Dears/Kay/Sirey/Dalloz/Sel. Ca. 等）约 15–25、OCR 断号（`(1932) Q.R. 5 4 K.B. 10` 型）与西里尔 OCR（`К.Б.`）各 1–2、`(1866) L.R. 1. H. L. 254` 型双点 1——合计约 30–40 条，留 C 类观察。
3. **§2 复算与任务书的小差异**（585/578/52 vs 571/577/67，合计同为 2,684）：口径逐字同，疑为任务书数字的统计时点不同，已在 §3.2 记录。
4. **`S.C.C. File No. 26395` 型（案号）与 `App. B. In October 1980` 型（附录）各 1 条被捕获**——结构判据不可分，落 UNSUPPORTED，见清单待人分类；若人判定为误报类，可在结构谓词上加窄闸（本版不加）。
5. **B10（§6.2 的 `v. X[n]` 内联案名，债 2）不受本修复影响**——本形状只管引证串本身。

## 5. 复现命令

```
python pipeline/tests/test_shape_21.py
python pipeline/tests/run_regression.py --selftest
python pipeline/extract.py --fixture-check
python pipeline/tests/corpus_counts.py --prose-sample
python pipeline/tests/test_candidates.py
python pipeline/tests/test_layers.py
python pipeline/tests/test_layers.py --golden
python pipeline/run_all.py --out data/run_20260915_r21a     # 已跑，status=complete
python audit/r21_diff.py --base data/run_20260914_r4c --new data/run_20260915_r21a
```
