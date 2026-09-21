# R3 会话变更报告：汇编式引证来源地继承 + 身份拆分修复

> ★**2026-09-14 追记（重要）**：本报告初版把 `r3c` 当作最终交付 run。**复核人随后发现
> r3c 有一个严重的身份回归**——Stage 3 的「连续编卷去年份」只改了键、没顾上裁定层
> 按「案名+年份」聚类的依赖，导致 C.C.C. 等平行引证被拆出所属案件（实测按案名最大组
> dd 下降 1,432 个、合计少 4,983）。**已修复并重跑**：交付 run 现为 **`r3e`**（见 §13），
> 本报告 §6/§7 的 r3c 数字**已被 r3e 取代**，保留仅作回归记录。修复内容、残余与验收口径
> 见 §13 与 `demo_repair_progress.md` R3-23/R3-24。

**范围**：本文件记录本次会话对工作区所做的**全部**变更（代码、决策表、仪器、审计产出、
运行、以及仓库外的工具配置），含每项的动机、证据与实测效果。
**权威记录**：逐步过程与账本在 `implementation/demo_repair_progress.md`（R3-0 … R3-24）。
**基线**：会话开始时的 HEAD = `475ca6f`；本轮产物结束于 `d8ed1e6`。
**免责**：本报告不作验收声明；「计数一致」不等于「语义正确」（见 §12）。

---

## 0. 一句话结论

计划（「来源地继承与身份拆分修复计划（修订版）」）的四个阶段全部执行完毕：
Stage 0 只读测量 → Stage 1 研究并建表 → Stage 2/3 先写测试再实现 → Stage 4 全量跑并独立复核。
**最终交付 run `data/run_20260913_r3c`（status=complete，指纹自核一致）**：
国内（DOMESTIC_CA）**组级覆盖 10,336 → 61,316（+50,980，约 5.9 倍，占 Stage 0 上限的 45%）**；
**产品门槛内（dd≥5）的国内组 2,784 → 6,961（+4,177）**；外国（FOREIGN）方向**零变化**。

---

## 1. 会话提交清单（10 笔，按时间序）

| # | commit | 内容 |
|---|---|---|
| 1 | `2db5666` | Stage 0 只读测量（M1a/M1b/M2/M3/M4）+ r2i 基线独立复算 + 七个探针 |
| 2 | `164104a` | Stage 1 目标清单生成器 + Stage 2/3 实现（decide 汇编排他来源地、身份修复），test-first |
| 3 | `78c5199` | Stage 4 爆半径仪器 + 两组研究结果（英国零可写行、`us`/`clr` 混合）+ 检索缺陷登记 |
| 4 | `2a479c9` | R3-18 检索能力审计（modsearch 路由实测） |
| 5 | `b213491` | Stage 1 合并：决策表首版 4 条可写行 + 真实表测试转绿（262 断言） |
| 6 | `a61dc03` | Stage 4：全量 run `r3a` + 覆盖/爆半径/原文追溯/一致性复核 |
| 7 | `5fba766` | R3-19 检索恢复（Exa 配置）+ 魁北克 S-20 与安省 O.R. 线索登记 |
| 8 | `3275b0b` | R3-21 合并加拿大组 findings：表 40 行 / 18 可写；Lead 三处改判 |
| 9 | `cdb70f7` | R3-22 Stage 4 最终复核（run `r3c`） |
| 10 | `3a0dfce` | 整理：把 5 个非本轮产出的 `audit/` 草稿移出版本控制（文件保留在磁盘） |

`git diff --stat 475ca6f..HEAD`：**35 个文件，+70,629 / −10 行**（新增为主；体积大头是
`audit/findings/r3_stage1_targets.json` 1.1 MB 与三份 findings / 进度记录）。

---

## 2. 生产代码变更（4 个文件）

### 2.1 `pipeline/decide.py`（+176 行附近，核心变更）

**新增能力**：排他汇编的来源地作为**正面证据**，且**完全不读分类层的 jurisdiction**。

| 新增/改动 | 说明 |
|---|---|
| `REPORTER_ORIGIN_ALLOWED_STATUSES` | 只有 `verified_exclusive_statute` / `verified_exclusive_publisher` 参与推断；`verified_mixed` 只作档案 |
| `load_reporter_origin()` | 读 `decisions/reporter_origin_scope.csv`，键 = `nk(printed_abbreviation)` |
| `_reporter_window_ok()` / `_in_span()` | **维度式包含**：仅当引证与表行该维度都有值时才可判、才可否决；两维都不可比 = 无约束 |
| `_reporter_origin(row, reporter_idx, stats)` | 窗口匹配即消歧：恰一行命中 → 该行来源地；≥2 行且**国别一致** → 取该国（P2′）；≥2 行且**国别不同** → UNDETERMINED + 审计列 `member_origin_ambiguous_basis=exclusive_reporter_scope_ambiguous`；零行命中 → 普通 UNDETERMINED。**白名单在规则内部再筛一遍**，不只依赖 loader |
| `decide_case_origin(..., reporter_idx=None)` | 优先级 P2：`case_record > court_scope_rule > 汇编排他`；前两者与第三者在 `citation_kind` 上**结构互斥**（neutral/identifier 走 scope、reporter 走汇编表），故「二者同时适用」不会发生。两档汇编排他性只在**同一行多条命中且国别一致**时选证据，**绝不裁决国别冲突** |
| 新列 | `member_origin_exclusivity`（证据行档位）、`member_origin_ambiguous_basis`（审计，与「无证据」分开）；跨法院轮用 `setdefault` 沿用院内轮 |
| 初始列 | 每个成员行都初始化上述两列（保证 in-court 产出列集稳定） |

**为什么这样切**：计划 §1 的缺陷是「用 classify 的未核实消歧当来源地键」——那会把猜测洗成
有出处的结论。本实现里 `_reporter_origin` 对 `row["jurisdiction"]` **零引用**；有专门的
测试用「同一引证分别喂 classify 法域 GB 与 QC，结果必须逐字段相同」来钉住这条独立性。

### 2.2 `pipeline/classify.py`（+38 行附近）

- `NEW_COLUMNS` 增 `volume_system`；
- 新增 `load_volume_systems()`：读新表的 `volume_system` 列（只收已核实行；同一缩写多行
  **不一致则不给值**，保守）；
- `run_row()` 给每行盖 `volume_system`（与 `jurisdiction` 同源，都是「已核实决策表 → 行字段」）。
- **为什么放在分类层**：`pipeline/merge.py` 的层规是**不加载 `decisions/` 下任何文件**
  （`merge.py` 头部注释明写）。归并层要用 `volume_system`，只能由分类层盖章上传，不能自己查表。

### 2.3 `pipeline/merge.py`（+58 行附近）

新增 `apply_reporter_identity_fixes(docs, stats)` + `fam_of(row)`，在**逐判决仲裁之前**运行：

- **A. `continuous`（卷号跨年连续）**：年槽不是身份的一部分 → **结构性零化年槽**
  （`34 D.L.R. (2d) 451` 与 `(1970) 34 D.L.R. (2d) 451` 自此同键）；
- **B. `year_volume` 且年槽为空**：按族 `(vol, abbr, series, page)` 统计**本 run 内**非空年，
  恰一个 → 补年；**≥2 个 → 弃权**；**按 run 计算、不持久化**；
- 未盖 `volume_system` 的行**一律不动**；
- 记账进 manifest：`reporter_identity_year_{zeroed,filled}_rows` / `_fill_families` /
  `_fill_families_abstained`。

### 2.4 `pipeline/tests/test_candidates.py`（+351 行；断言 200 → **345**）

新增 15 项测试（9 项规则 + 3 项 Stage 3 + 1 项真实表 + 2 项随行数增长的遍历断言）：

- **§1 强制测试**：构造 GB-K.B. 与 QC-K.B. **故意重叠**的窗口 → UNDETERMINED +
  `exclusive_reporter_scope_ambiguous`，且 classify 喂 GB 与 QC 两次结果**逐字段相同**；
- 唯一命中窗且 **classify 法域故意喂错**（GB/QC/ZZ）仍取窗口来源地；
- 窗口外 / 无表行 → 普通 UNDETERMINED（ambiguous 列为空）；
- 非 `reporter` 解析（neutral/identifier/ambiguous）不走该规则；
- `case_record 优先于 exclusive_reporter_scope`；
- 两档：国别一致时取 `exclusive_statute` 证据行；**国别不一致时不得用档位破平局** → UNDETERMINED；
- P2′：多行命中同国 → 取国、细分留空；
- 表行顺序不变性；未核实/`verified_mixed` 行不参与；
- Stage 3：continuous 零化年槽（带年/不带年同键）、year_volume 族内唯一年补年 + **≥2 年反例族弃权**、
  输入顺序不变性 + **幂等**；
- **真实表项**（`test_reporter_origin_real_table_stage1_rows`）：逐可写行检查「≥1 个窗口 +
  `origin_country` + 合法 `exclusivity` + `exclusive_publisher` 必带反例搜寻 + `source`/
  `source_locator` + 键口径 `nk(normalized_key)==nk(printed_abbreviation)`」，并钉三条具体判定。

---

## 3. 新决策表：`decisions/reporter_origin_scope.csv`（新增，40 行）

列（17）：`printed_abbreviation, normalized_key, origin_country, origin_subdivision,
exclusivity, volume_system, vol_range_start, vol_range_end, year_range_start, year_range_end,
source, source_locator, verification_status, counter_example_check, notes, reviewer, reviewed_at`

**18 条可写行**（参与推断）：

| 档 | 行 |
|---|---|
| `exclusive_statute`（5） | `S.C.R.`(1876–) · `Can. S.C.R.`(1876–) · `F.C.`(1971–) · `F.C.R.`(1971–) · `R.J.Q.`(1986–2013) |
| `exclusive_publisher`（13） | `O.R.`(1882–) · `D.L.R.`(1912–) · `C.C.C.`(1898–) · `W.W.R.`(1911–) · `A.R.`(1976–) · `Alta. L.R.`(1908–) · `Man. R.`(1979–) · `Sask. R.`(1979–) · `N.S.R.`(1965–) · `N.B.R.`(1969–) · `N.R.`(1974–) · `Ex. C.R.`(1877–1970) · `R.F.L.`(1970–) |

**22 条 `verified_mixed` 档案行**（不参与推断，写死「不可作来源证据」以免下轮重查）：
`A.C.` `App. Cas.` `E.R.` `W.L.R.` `K.B.` `Q.B.` `Ch.` `Ch. D.` `Q.B.D.` `All E.R.`
`Cr. App. R.` `L.R. (H.L.)` `L.R. (Q.B.)` `Ch. App.` `L.R. (P.C.)` `U.S.` `C.L.R.` `P.`
`A.L.R.` `N.Z.L.R.` `F.` `F. Supp.`

**证据形态**：每行带 `source` + `source_locator`（URL + 条款/页 + 取用日期）；两档判定的
核心引文例如：
- `S.C.R.`：Supreme Court Act s.3（"a general court of appeal for **Canada**"）+ s.17（Registrar
  "shall report and publish **the judgments of the Court**"）；
- `R.J.Q.`：Légis Québec **S-20 s.21**（"les jugements rendus par les tribunaux judiciaires
  **siégeant au Québec**"）+ SOQUIJ 自己的汇编表 `R.J.Q. 1986 à 2013`；
- `O.R.`：LexisNexis 产品页逐字「Published by the Law Society of Ontario through LexisNexis
  Canada … leading cases decided at **all levels of Ontario courts**」；
- `D.L.R.`/`C.C.C.`：出版方**卷内题名页**（"every case reported in the courts of every
  province … and the **Canadian** cases appealed to the Privy Council" / "in Canada … in all
  the provinces"）。

---

## 4. 新增仪器（21 个 `implementation/` 文件 + 1 个 `audit/`）

| 文件 | 作用 | 备注 |
|---|---|---|
| `implementation/coverage_metric.py`（677 行） | **Stage 0 四测量**：M1a/M1b（含净新增组、按 basis×组状态分层、被闸门挡住的池、反向冲突风险、无年变体族 M3、同形区间重叠 M4） | `ELIGIBLE_BASES` **从 `pipeline/decide.py` import**，不硬编码；输出 JSON + stdout 摘要 |
| `audit/stage1_targets.py`（263 行） | 生成 Stage 1 研究目标清单（按语料提及量排序 + 附语料实测 vol/年区间与高频组合） | 审计环（产出是提案）；输出 3 份 MD + 1 份 JSON |
| `implementation/r3_blast_radius.py`（284 行） | **Stage 4 爆半径**：提及/成员行/组/边/选取五层逐条比较并归因 | 用**组内容签名**而非 `merged_group_id`（组号跨版本会变）；含 ambiguous 单独计数 |
| `implementation/r3_fingerprint_check.py`（135 行） | **独立指纹**（自算，不采信 manifest 自述）+ 一致性三元组 | 逐字复刻 `run_all.input_identity` 的哈希口径 |
| 18 个 `implementation/_probe_*.py` | 一次性只读探针：层 schema、mentions 分布、决策表结构、Stage 0 明细、简报数字对账、边计数独立复算、表校验、dd/kept 签名比较、印刷形抽样、样本挑选 | 每个被引用的数字都能重放 |

**为什么单独做仪器**：计划的 Stage 0 与 Stage 4 都要求「数字可重放、不采信产出自述」；
这些脚本是**只读**的，不改管线、不写 `decisions/`（唯一例外是 `audit/stage1_targets.py`
按审计环规则写提案文件）。

---

## 5. 审计环产出（研究提案，7 个文件）

| 文件 | 内容 |
|---|---|
| `audit/findings/r3_stage1_targets_{canadian,british,other}.md` + `.json` | 研究目标清单（三级分层；tier1–2 全字段、tier3 压缩） |
| `audit/findings/r3_reporter_origin_british.md` | 英国组：15 目标**全部 mixed/第三方**，**零可写行**；`A.C.` 卷首题名页坐实上院+枢密院混印 |
| `audit/findings/r3_reporter_origin_other.md` | 美国及其他：`us`/`clr` 判 mixed（具体反例）、`f`/`fsupp` 建议降级、50 个 not_a_reporter |
| `audit/findings/r3_reporter_origin_canadian.md` | 加拿大组：23 目标、12 条建议可写行、逐条引文+反例记录、省级「官方汇编法条」全国排查（只有魁北克有） |

三名子代理均为**只读**、产出提案；**表由 Lead 手工整理**（`audit/README.md` 的膜规则：
审计环→生产线只允许「确定性形状 / PROBLEMS 登记项 / 带 source+locator 的决策表行」）。

---

## 6. 运行与产物

| run | 用的表 | 结果 |
|---|---|---|
| `data/run_20260913_r3a` | 4 条可写（S.C.R./Can. S.C.R./F.C./F.C.R.） | complete；指纹 `a0656868…` |
| `data/run_20260913_r3b` | 6 条（+`R.J.Q.`/`O.R.`） | complete；指纹 `db24db9b…`；**被 r3c 取代**（表随后又扩充） |
| `data/run_20260913_r3c` | **18 条** | complete；指纹 `7610ace4…`；**最终交付** |

三个 run 目录都在 `data/`（gitignore，不进 git）。`decisions/` 与 `pipeline/` 的任何改动都会
使旧 run 的指纹失配——`r2i`/`r3a`/`r3b` 因此**不可由当前 HEAD 重放**，这属于预期，且正是
`r3_fingerprint_check.py` 能测出来的东西。

---

## 7. 实测效果（r2i 基线 → r3c 最终）

### 7.1 覆盖

| 量 | r2i | r3c | Δ |
|---|---:|---:|---:|
| 组总数 | 177,136 | 176,975 | −161（身份合并） |
| 组·UNDETERMINED | 166,474 | 115,333 | −51,141 |
| 组·**DOMESTIC_CA** | 10,336 | **61,316** | **+50,980（约 5.9 倍）** |
| 组·FOREIGN | 326 | 326 | **0** |
| **kept 组（dd≥5）·DOMESTIC_CA** | **2,784** | **6,961** | **+4,177** |
| kept 组·UNDETERMINED | 5,800 | 1,827 | −3,973 |
| kept 组合计 | 8,586 | 8,790 | +204 |
| 边·DOMESTIC_CA | 55,237 | **176,945** | +121,708 |
| 边·FOREIGN | 384 | 384 | **0** |
| 边·UNDETERMINED | 277,866 | 153,286 | −124,580 |
| supported / heuristic 边 | 308,026 / 25,461 | 315,474 / 15,141 | 更多边走 supported |

**头条要两句一起说**：组级国内覆盖 **+50,980 组**；**产品门槛内（dd≥5）的国内组 +4,177
（2,784 → 6,961，约 2.5 倍）**。后者才是产品影响——总数只 +204，是因为 3,973 个原
「未决的 kept 组」转成了已判定，同时身份合并减少了组数。**外国方向零变化。**

### 7.2 爆半径（`r2i → r3c`，0 未解释）

| 层 | 变化 | 归因 |
|---|---:|---|
| 提及（candidate_id） | 70,997 | **100% 单类** `alternative_contained → alternative_same_key`（Stage 3 同键化），全为 `reporter` |
| 成员行 origin 字段 | 45,248 | `reporter_scope`；另有新增行 12,815 → 本规则实际判定 **58,063** 行（`exclusive_publisher` 39,386 + `exclusive_statute` 18,677） |
| 组签名变化 | 3,622 | `identity`（Stage 3 合并/重键） |
| 组结论变而自身证据未变 | 146 | **全部**归因：所在组有同组 `reporter_scope` 成员 → **未解释 0** |
| 一致性三元组 | **0 / 0 / 0** | 行来源不一致 / 多国别非 CONFLICT / 同系统多键 |

`occurrence_total`（SCC 360,950 + ONCA 171,151 = **532,101**）在 r2i、r3a、r3b、r3c
**四轮完全一致** → 身份修复没有虚增或丢失计数。

### 7.3 dd / kept（按组内容签名；不用组号、不用 `(court,merge_key)`）

- 共同签名 162,178：**dd 升 1,263 / 降 0**；kept **false→true 295 / true→false 0**；
- 签名只在新 run 14,797（kept 1,203）、只在旧 run 14,958（kept 1,294）——对称 churn，
  来自 Stage 3 重键；
- `kept` 在组内**一律性检查 0 违反**。

> 方法教训：`(court, merge_key)` **不是**跨轮可比的键（同一键可被按判决拆成多组），
> 用它比较会报出 528 行「dd 变化」并误报 55 行「dd 下降」；组内容签名才是正确口径
> （修正后降幅为 0）。这条已写进仪器注释。

### 7.4 Stage 3 实际修复

| 量 | r3a/r3b（6 行表前） | **r3c（18 行表）** |
|---|---:|---:|
| A：continuous 零化年槽（行） | 1,577 | **30,716** |
| B：族内唯一年补空年槽（族） | 6,162 | **8,447** |
| B：补年（提及行） | 45,233 | 49,128 |
| B：弃权族（≥2 年） | 2,167 | 2,575 |
| 被合并掉的 merge key | 1,607 | ~3,173 |

### 7.5 独立指纹与测试

- `r3_fingerprint_check.py` 自算 r3c 指纹 = manifest 值，**22 文件 0 不匹配**，新表在指纹内；
- `test_candidates.py` **345 条断言 exit 0**；`test_layers.py` 120 条 exit 0；
  `run_regression.py --selftest` exit 0；`extract.py --fixture-check` exit 0；
- 新表机械校验（`_probe_table_check.py`）：40 行 × 17 列、**0 问题**。

### 7.6 人工原文追溯（11 例）

| 判定 | 原文节选 |
|---|---|
| `scr` | 1897 年 SCC 判决注脚 `[5] <<26 Can. S. C. R. 595>>.` |
| `fcr` | `APPEAL from a judgment of the Federal Court of Appeal …, 2014 FCA 113, <<[2015] 1 F.C.R. 335>>, …` |
| `fc` | `APPEAL from a judgment of the Federal Court of Appeal, <<[1991] 1 F.C. 428>>, 124 N.R. 379 …` |
| **`rjq`** | `Applied: R. v. Prince, [1986] 2 S.C.R. 480.` ＋ `APPEAL from a judgment of the **Quebec Court of Appeal**, <<[1986] R.J.Q. 2162>>, 29 C.C.C. (3d) 498 …` |
| `dlr` | `… McIntosh v. Parent, <<[1924] 4 D.L.R. 420>>; …` |

另 12 个新缩写的 dd≥5 样本逐条打印印刷形与案名（`ccc` R. v. W. (W.)、`or` Kenny v.
Lockwood、`ar` R. v. Ferris、`rfl` Molodowich v. Penttinen、`nsr` Ross v. Ross、`manr` King v.
Operating Engineers…、`saskr` R. v. B. (G.)、`nr` Canada v. South Yukon Forest Corp.、
`excr` 11 Ex. C.R. 119、`wwr` 30 W.W.R. 241 等），与各省法院一致。

---

## 8. 与计划的偏离 / Lead 改判（6 条，全部留痕）

| # | 计划原文 | 实际处置 | 理由 |
|---|---|---|---|
| 1 | §0/§2：合格 `identity_basis` = anchor / anchor_variant / **name_year** / singleton | **以代码为准**：`ELIGIBLE_BASES = anchor, singleton, same_citation, anchor_variant_bilingual`（`name_year` 不合格、`same_citation` 合格） | 计划文本与代码不符；§0 自己要求「组聚合不变」，且放宽 name_year 会新增约 4,477 组**未授权**证据 |
| 2 | §6 测试：`(1930), 45 K.B. 129` 唯一命中 QC 窗 → CA | 改成 **UNDETERMINED**（断言内写明理由）；规则本身由夹具测试覆盖 | 该期望基于**未核实**区间表（vol 5–100/1892–1941）；已溯源的魁北克 K.B. 窗是 1892–1898/卷 1–7 |
| 3 | §1：`≥2` 行命中一律 UNDETERMINED | 采纳 **P2′**（你已签收）：多行命中但**国别一致** → 取国、细分留空；异国重叠仍 UNDETERMINED + ambiguous | 同国多行不制造错误国别；代价对比见 R3-3 |
| 4 | §1 测试命名：`origin_basis=exclusive_reporter_scope` | basis 值**保持**该字符串，档位另放 `member_origin_exclusivity` 列 | 若把档位烘进 basis，计划自己的测试按字面就红 |
| 5 | — | **加拿大组的 `dlr`/`ccc`/`rfl` 由子代理的 `mixed` 改判为可写**（国别 CA、细分留空，约 1.9 万组） | 子代理判 mixed 的依据是「跨**省**」；本项目的判定字段是 `origin_country`，而这些汇编的每件来源都在加拿大之内（含按 `case_origin.csv` 语义=CA 的枢密院加拿大上诉）。**这是本会话最大的一次判断，若你要求「省别也须排他」则这三行应回退** |
| 6 | — | `excr` 由子代理的 `exclusive_statute` **降为 `exclusive_publisher`** | 子代理自陈法定链不完整（未取得 Exchequer Court Act 出版条款）；改用其卷首「PUBLISHED UNDER AUTHORITY BY THE REGISTRAR OF THE COURT」这一出版方自述 |

**另有两处工程性偏离**：`series` 槽不作匹配维度（理由：增加命中只会推向 UNDETERMINED，
不会凭空造国别；且避免为多系列汇编建窗口矩阵）；M1a 的「L2 法域已解析」是代理口径，
另报全量口径 423,731。

---

## 9. 未兑现部分（下一轮施工图）

Stage 0 上限 113,432 组；本轮实测兑现 50,980（45%）。剩余三类：

1. **已研究但按 P2 不可写**（约 3.4 万组）：英国组全部（`ac`/`appcas`/`kb`/`qb`/`ch`/`chd`/
   `qbd`/`wlr`/`er`/`aller`…）；`us`、`clr`（真混合）；`f`/`fsupp`（只有第三方来源）；
   `bclr`（唯一范围语来自大学图书馆）；`crr`（第三方+键身份存疑）；`oac` 2,558、`cbr` 1,112、
   `bcac` 790、`olr` 630、`ontlr` 768（只有第三方馆藏/索引表）。
2. **未研究**：`qr.kb` 671、`queqb` 403、`ucqb` 543、`cs` 312、`mpr`、`cpc` 845（魁北克早期
   官方分辑**法条已在手**，差键身份与系列窗口）；`scca` 1,189、`oj` 4,374（供应商标识符 →
   应走 R2F 已有的 `identifier_systems` 路线，不进本表）。
3. **身份基础闸门**：`name_year` 4,468 组被挡（B14）——这是「案名/中立锚补全」问题，
   不是来源地规则问题。

---

## 10. 仓库之外的变更（环境/配置）

| 项 | 内容 |
|---|---|
| `C:\Users\hp\.modsearch\config.json` | 按你的指令写入 `exa.apiKey`（`config show` 回显**已打码** `44ff6c...4e`）并固定 `search.engine=exa`。**该文件在工作区之外**，两次写入各需要一次沙箱提权（第二次因本会话已拒绝过同一路径而前置提权） |
| `D:\cases data analisis\.npmcache` | 为运行 `npx @liustack/modsearch` 临时创建（工作区内），**已删除**（11.3 MB）；默认 npm cache 在 danger-full-access 下可用，不再需要 |
| git 索引 | 一笔整理提交把 5 个**非本轮产出**的 `audit/` 草稿脚本移出版本控制（`git rm --cached`，文件仍在磁盘）——它们是在 `git add -A` 时被误纳入的 |
| 检索能力现状 | **搜索（发现 URL）已恢复**（`web_search` 走 Exa）；**取页仍走本机出口**（`legisquebec`/`hathitrust`/`lso.ca`/`legalbluebook` 对本机 IP 403 → 用 Exa 服务端 highlights 取正文，已在表里逐处标注「二级取回」）；`x_search` 仍不可用（缺 `grok`） |

---

## 11. 复现命令（从当前 HEAD 重放这一轮）

```powershell
# 1) 测试（应全 exit 0：345 / 120 / selftest / fixture）
python pipeline/tests/test_candidates.py
python pipeline/tests/test_layers.py
python pipeline/tests/run_regression.py --selftest
python pipeline/extract.py --fixture-check

# 2) 决策表机械校验（应 problems: 0）
python implementation/_probe_table_check.py

# 3) 全量跑（新空目录；约 18 分钟）
python pipeline/run_all.py --out data/run_<new>

# 4) 独立复核：指纹 + 一致性三元组（应 fingerprint_match=true、0/0/0）
python implementation/r3_fingerprint_check.py --run data/run_<new>

# 5) 覆盖与上限
python implementation/coverage_metric.py --run-dir data/run_<new> `
    --json-out data/coverage_out/stage0_<new>.json

# 6) 爆半径（应 0 未解释）
python implementation/r3_blast_radius.py --before data/run_20260913_r2i `
    --after data/run_<new> --out data/coverage_out/r3_blast_<new>.json

# 7) 原文追溯
python pipeline/traceback.py --run-dir data/run_<new> --search "R.J.Q. 2162"
```

**基线比对**：本次基线与对照全部是 `data/run_20260913_r2i`（本会话未改动它）。

---

## 12. 声明

- 本报告与所引数字**不构成验收通过**；按计划要求，最终验收不在本轮。
- **「计数一致」不等于「语义正确」**：一致性三元组 0/0/0、`occurrence_total` 守恒、
  dd 只升不降，这些只说明**结构不变量没被破坏**，不说明每一条来源地判定都对。
  语义正确性只能由 §7.6 的人工原文追溯与后续独立复核逐步建立。
  ★r3c 回归正是这句话的实证：结构不变量全绿，身份却错了——**验收必须包含按案名的
  dd 口径与平行引证同组检查**（`r3_case_dd_diff.py`）。
- 本轮**所有** `decisions/` 行都可追到 `source` + `source_locator`；其中 4 处证据是
  「搜索引擎正文抽取」而非本机直取（域名对本机 403），已在表内逐处标注，是**复核优先级最高**的引文。
- 三名研究子代理的产出是**提案**；把提案变成表行的那一步（含 §8 的六处改判）由 Lead 完成，
  责任在我，不在子代理。

---

## 13. 追记：r3c 身份回归的发现、修复与最终数字（2026-09-14）

### 13.1 回归（复核人发现，我复现并确认）

Stage 3 的「连续编卷去年份」**只改了身份键，没有顾上裁定层聚类的依赖**。裁定层按
「案名 + 年份」连链聚类，而年份是从**键首槽**读的——键被零化后，同案的平行引证
（`[1991] 1 S.C.R. 742` 与 `(1991), 63 C.C.C. (3d) 1`）因后者键里没有年份而**各自成组**。

实测（仪器 `implementation/r3_case_dd_diff.py`，按**案名最大组 dd**）：
r2i → r3c 按案名最大组 dd **下降 1,432 个**（原 dd≥5 的 864 个），合计少 **4,983**；
孤立组（全成员键年槽空且全为连续编卷）9,449 → 19,880。降幅榜全是地标案：
`R. v. W.(D.)` 694→548、`R. v. Morrissey` 214→123、`R. v. Lifchus` 166→99、
`R. v. Sheppard` 264→220、`R. v. Proulx` 168→127、`R. v. Starr` 132→93、
`R. v. Collins` 239→204、`R. v. Biniaris` 226→192、`R. v. Stillman` 107→74、
`R. v. Handy` 178→146。

**为什么我的 Stage 4 复核没测到（方法错误，已订正）**：爆半径仪器的 dd 段只比较
「签名未变的组」，而受害组签名恰恰都变了 → **恰好被排除**；occurrence 守恒只证明提及
没丢；一致性三项不涉及归组；也没有平行引证同组的测试。**教训已写进两个仪器的注释**：
dd/kept 的验收口径是 `r3_case_dd_diff.py`（案名口径 + 分离成员对），不是爆半径工具。

### 13.2 修复（三个文件，均已测试）

| 层 | 变更 |
|---|---|
| `merge.py` | `apply_reporter_identity_fixes()` 给**每一行**先写 `year_printed`（= 未修复前键里会用的年份）；然后只改 `year_start`（键）。连续编卷零化后 `year_printed` 保留印出来的年份；`year_volume` 补出的年份也写入。`year_printed` 进 `MERGED_FIELDS`，由 `_emit` 以「counted 成员最常见的非空印刷年」写入 merged.csv（legacy 路线留空、行为不变） |
| `decide.py` | 新增 `row_year(row)`：优先 `year_printed`，缺列/空则回退键首槽。**三处接线**：`cluster_same_case`（案名+年份连链）、`add_peer_column`（同年邻组）、写表前「组内年份跨度≤1」断言 |
| 后续两处 | 读代码时发现的**同类问题**：`split_by_decision` 的「同年级平局裁决」与 `_reporter_origin` 的年窗匹配也读键首槽 → 均改为 `row_year`。实测对残余规模**无减量**（r3d=r3e），但语义正确、由测试钉住 |

**测试**：新增 3 项（357 条断言）。指名要的那条是
`test_r3_parallel_citation_stays_in_same_group`：`1991|1|scr||742` + `|63|ccc|3d|1` +
`|34|dlr|4th|375` 必须**同组且未被判拆分**；并附**反证**（去掉 `year_printed` → 三者各自
成孤立组），把回归机制钉死在测试里。

### 13.3 修复效果与最终数字（`data/run_20260913_r3e`，交付 run）

| 量 | r2i | r3c（回归） | **r3e（修复后）** |
|---|---:|---:|---:|
| 按案名最大组 dd 下降 | — | 1,432 / 少 4,983 | **109 / 少 207** |
| 孤立组（口径 A） | 9,449 | 19,880 | 16,743 |
| 组·DOMESTIC_CA | 10,336 | 61,316（虚高） | **51,296（+40,960，约 5.0 倍）** |
| **kept 组·DOMESTIC_CA** | **2,784** | 6,961（虚高） | **6,179（+3,395，约 2.2 倍）** |
| 组·FOREIGN | 326 | 326 | 326 |
| 边·DOMESTIC_CA | 55,237 | 176,945（虚高） | **154,754** |
| `reporter_scope` 判定行 | — | 58,063 | 48,773 |
| 指纹自核 / 一致性 | — | ✓ / 0/0/0 | **✓ / 0/0/0** |

即：r3c 的覆盖数字**虚高约 1 万组**（拆分造成的），修复后回落；r3e 相对 r2i 的真实增量是
**+40,960 组（45%→36% 上限）与 kept·CA +3,395**。

**残余（B20，如实入账）**：仍有 **109 个案名 / 207 dd** 的平行引证被拆出（0.04%）。
逐键对照定位的机制：零化把带年/无年引证**合并成一个键**，成员集变化会连锁改变该键的
**案名众数**（如 `|155|ccc|3d|97` 从 `R. v. Sawyer` 变 `R. v. Pan`——Pan; Sawyer 是
2001 SCC 42 的两件合并上诉，本是一案）与**共引决策集**；且若某判决头部自印的是**无年
形式**，该键会成为**自己的身份锚**，于是不再跟着中立引用桶走（`R. v. Osolin`
68 → 61+7，`split_reason=decision;unanchored`）。修这要动 `split_by_decision` 的锚合并/
指派规则——**计划 §0 明文冻结的区域**，须用户裁决后再做。孤立组口径 A 较基线多
7,294 个也是同一机制。

### 13.4 追加提交

`d8ed1e6`（修复 + 357 测试 + r3e）、`f99bee4`（会话报告 + kept 构成订正）、
`3a0dfce`（整理误纳入的草稿）。**基线 r2i 未动**；`r3a`/`r3b`/`r3c`/`r3d` 保留供对照，
**交付 run = `r3e`**。
