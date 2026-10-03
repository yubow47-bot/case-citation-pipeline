# 第 4 层 裁定

## 这一层做什么

唯一需要“先知道这是哪个案子”才能做的判断，所以排在归并之后。**DD 最终就是在这里数出来的**，案件身份（哪些印刷串是同一个案子）也在这里认定。

- 输入：各法院归并层产物（`merged.csv`、`folded_log.csv`、`decision_ids.csv`）。
- 先每个法院内部跑一轮（`--court X`），再跨法院跑一轮（`--cross-court --inputs ...`）。
- 输出（`decide_out/<法院>/` 和 `decide_out/cross_court/`）【已核实：目录清单和 `decided.csv` 表头】：
  - `decided.csv`：在归并层列之上加 `court`、`key_occurrence_count`、`identity_basis`、`member_origin_*`、`merged_group_id`、`is_primary`、`split_flag`/`split_seq`/`split_reason`、`same_name_near_year_peers`、`group_origin_*`、`group_foreign_status`、`foreign_status`、`origin_country`、`case_origin` 等；
  - `effective_sources.csv`：**组 → 来源判决的权威关联**（`status=counted` 或 `excluded_self`），`edges.py` 只消费它；
  - `decision_ids.csv`、`mixed_identity_holdouts.csv`、`typo_over_registered.csv`（留痕）、`manifest.json`。
- 约束六：裁定层可以**否定**归并层的折叠结论并拆开，但**不回改归并层的输出文件**。

## 它负责的几件事

### 1. 案件身份（哪些键是同一个案子）

- **身份锚**：中立引证，或“语料某判决自己头部印的引证”（`self_citation_of`，#55）。汇编锚只与同键合并，不走 `same_decision()`（后者按中立引证解析、不看卷号）。
- **按名+年份判同**（`nk(case_name_modal)` 相等且年份相差 ≤1，§10.3）：平行汇编合并。这是**启发式**。
- **拆分**：
  - 链式合并会串出跨数十年的嵌合体（`R. v. Smith` 2001–2023 共 93 个成员，#48）→ 年份跨度 >1 的链按 ±1 年窗口拆；
  - 同名当事人的不同判决不能合并（#49）：同一法院同一年只有一件判决、同号同年的双语代码合并、号码差一位且被引量悬殊才当笔误、共引系数 ≥0.8 才分派；
  - 同一印刷串被两件不同语料判决共用 → 按判决拆开（#55）。
- **语料法院的“起用中立引证年份”**：该年之前的“中立引证”不当身份锚（`1994 SCC 80` 是噪声，#56）。判据要两头都有正证据，都取自该院判决自己头部印的引证。
- **笔误折叠**（号码差一位、被引量悬殊）：由 `mixed_identity()` 三档判据把关（#88，默认开启，`--no-mixed-key-holdout` 可关）：
  - 提及只印折叠目标的名字 → 照并；
  - 无名或无一同名 → 不动；
  - 既印目标名又印别的名 → **扣留**（不并，抑制其案名，退出身份根竞争）。
  - 缺一条就会复现回归（`211 D.L.R. (4th) 577` 从 DD 602 掉成 21）。
- **成员的 `identity_basis`**【已核实：`decide.py:1160`】：`anchor`、`singleton`（6），`same_citation`（5），`anchor_variant_bilingual`（4），`anchor_variant_typo_number/year`（3），`name_year`（2），`cocitation`、`unanchored`（1）。
  - **只有前四种（`ELIGIBLE_BASES`）授权组级结论传播**；`name_year`、笔误变体、`cocitation`、`unanchored` 是启发式，保持可见、保持暂定，不得把成员证据升成组结论。

### 2. DD 的数法

- DD = 组内所有成员键的**判决 id 并集**的基数，**剔除自引**。
- 自引的剔除有三层：
  1. 分类层打 `self_citation` 标记，归并层不计（行级）；
  2. 裁定层剔**身份根自己的判决 id**（#54）；被当笔误并进来的键，其判决若引了本组仍是真引用；
  3. 新增（#105，2026-10-03）：`decision_own_citations.csv`（每件判决自己的 `citation_en`+`citation2_en` 构键）加 `own_citation_self_ids()`（`decide.py:579`）：**只经由自己印的键提及本组**的来源判决 → 当作提及自己，不计。只要还经由别的键提及（例：SCC 判决引用自己上诉自的下级判决）就**保留**。
- **DD 口径（用户裁定 2026-10-03）**：DD = 提及该案件的不同来源判决数，**不限于援引先例**。审理历史关系计入 DD，另按关系类型标记（`tools/foundation/relations.py`：`same_case_history` / `other_judgment`，按身份而不是措辞标）。
- 一个来源判决对一个组只贡献一次 DD。

### 3. 案件级来源地（`case_origin`）：三级优先级瀑布

查表在**成员串级别**进行，不在归并组级别（拆分后的各条记录各查各的）。三级：

1. `case_record`：`case_origin.csv`（204 行，CanLII 枢密院库）加 `case_origin_manual.csv`（逐案人工核验）；
2. `court_scope_rule`：`court_or_reporter_scope.csv`（法院/标识符的排他来源地规则），仅当本行是已接受的中立解析，且年代落在 `valid_from`–`valid_to` 窗内；
3. `reporter_origin_scope`：`reporter_origin_scope.csv`（排他汇编范围），仅当 `citation_kind=reporter`；`exclusive_statute` 与 `exclusive_publisher` 两档不同。

三级都未命中 → **`UNDETERMINED`**。`FOREIGN` 只能来自正面排他规则，**绝不来自“不在加拿大例外表”**。UKPC/JCPC 这类跨法域法院不在任何规则表，来源地一律 `UNDETERMINED`（#66）。同键两表给出不同国家 → 成员级 `CONFLICT`，方向保守。

## 登记簿（注意用途很窄）

- 全局判决登记簿 `registry/decision_registry.csv`：所有已知真判决自己印的引证，只授权**笔误闸**使用（规格 2.3）。**不得把它混进 `own`**（`own` 另有三处用途：身份锚资格、DD 自引排除、起用年份判据）。
- 默认 `--registry-gate literal`，实测与现状等价；`--anchor-corpus` 默认关闭。
- 登记簿依赖语料在场（#89）：缺某法院语料时，该院判决全部无锚，同名真判决会融成一组。`--anchor-corpus` 只生成登记簿，不抽取、不计数。
- **天花板监测仪** `registry_report.py`：外国法院判决的原文在语料里不存在，补语料补不出来。

## 加新法院时

1. **新法院的判决要在语料里**，裁定层才能用它们自己头部印的引证做身份锚和 DD 自引剔除。法院的 `citation_en` 若不是引证（CITT 的案卷号），自引识别失效，**每份判决 DD 会多算一**。
2. **该院的中立引证起用年份**由它自己判决的头部推出（`neutral_start`，#56）。新法院没有早年语料时不适用。
3. 新法院引用的外国案、枢密院案：来源地靠 `case_origin*`、范围规则表；没有规则就是 `UNDETERMINED`，**不要补默认值**。
4. 加了法院后重新审：同名同年的**不同判决**会不会被并（`R. v. Smith` 类）；跨法院合并（§10.6）是否把两院各引若干次的同一外国案合到一起了。
5. 引用别的案子时的零填充号码（#90）仍会自成一键，可能让同一个案子分成两个组。

## 验证

- `python pipeline/tests/test_layers.py`：含裁定层单元断言、`own_citation_self_ids` 的 6 条断言、迷你全链、Housen/MacKay/Oland/Gladue/Imoro/Wewaykum/Beaver 等真实案例的身份断言。
- 硬不变量：任何一组不含两个不同的语料判决（按裁定层同一判据复算）；各组 occurrence 之和 == 计数行总数。
- 改裁定层规则后，**同输入同底座做 A/B**，核对新增键、消失键、既有键变化、`kept` 行变化（实验：#88 修复新增键 0、消失键 0、既有键变化 28）。
- `--golden` 只证明旧产出没变，不证明新规则对（#98）。

## 已知的坑

| # | 内容 | 状态 |
|---|---|---|
| 46 | DD 要取并集 | 已修 |
| 47 | 跨院轮 occurrence 虚高 | 已修 |
| 48 | 链式合并串出嵌合体 | 已修（±1 年窗口拆） |
| 49 | 案名+年份判同的盲区：同名当事人不同判决被并 | 已修（多道判据），残余见 #55 |
| 50 | 案名长短两种写法导致平行引证合不到一起 | 【待核实】 |
| 54 | 自引：每件判决自带 DD+1 | 已修 |
| 55 | 语料里两件不同判决被合成一组 | 已修；残余 56 个单元（DD 合计 262）落 `unanchored` |
| 56 | 语料法院起用中立引证之前的“中立引证”被当身份 | 已修 |
| 59 | 枢密院上诉的加拿大案被标成英国案 | 已填 `case_origin`（1888–1959 年覆盖） |
| 62 | 同名、年份相差 ≤1 的组 | 只标记不合并（`same_name_near_year_peers`） |
| 64–68、77、84（B 系列） | 来源地不可推断、同案传播未实现、单锚簇无条件吸收等 | 登记，多为未修；【待核实】逐条状态 |
| 75（B12） | 单锚簇搭车吸收不同实例判决 | 测过，拟议规则被否 |
| 88 | 同一印刷串同时承担两种身份 | 已修（混合键扣留，默认开启） |
| 89 | 登记簿依赖语料在场 | 未修，`--anchor-corpus` 接口已有 |
| 91 | 压制者本身未决时，被压制的真引证一并弃权 | 未修（规则副作用，已披露） |
| 97 | 决策表列名不一致导致“加载成功但零生效” | 已修；验收清单加“抽样反查下游字段被填了” |
| 105 | 自引漏网（补零、头部并行引证） | 已修（2026-10-03） |
| 106 | 案件身份按“案件”而非“判决”，老案各级被并成一组 | **未修**，需单独设计 |

## 来源

规格 §10；代码 `pipeline/decide.py`（`decisions_of`、`same_decision`、`mixed_identity`、`assign_identity_basis`、`own_citation_self_ids`、`build_effective_sources`、`BASIS_RANK`、`ELIGIBLE_BASES`）、`pipeline/registry.py`；PROBLEMS #46–#49、#54–#56、#59、#62、#64–#68、#75、#77、#84、#88、#89、#91、#97、#105、#106。

核实状态：输出文件、列、身份基础等级、`own_citation_self_ids` 对照代码和 run（2026-10-03）【已核实】；其余规则【按规格】，规格标“待复核”的不另外核实。
