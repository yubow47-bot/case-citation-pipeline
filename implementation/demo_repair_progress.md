# Demo 修复工作记录（D1–D6）

本文件是本轮修复的持续工作记录。只记事实：做了什么、跑了什么、结果是什么、卡在哪。
最终验收不属于本轮工作，本文件不作任何「通过」声明。

## 目标与范围

把现有五层管线（extract → classify → merge → decide → select）修到能端到端演示：

来源判决 → 引证候选 → 分类与重叠仲裁 → 案件身份 → 案件来源地 → 去重后的外国引证边及频次 → 返回原文与判断依据。

允许 UNKNOWN / UNDETERMINED / CONFLICT；不得用未经核实的判断填满未知项。

本轮修复项：D1（去重按最长占位）、D2（非重叠扫描漏候选）、D3（跨界解析 `2011 ONCA, 2011`）、
D4（括注系列不捕获）、D5（罗马页码丢出键）、D6（来源地只能产出 CA）。
暂缓：D8（历史脚注案名关联）、D9（大规模人工标注）。

方案 A：extract 保留全部候选 → classify 逐候选 → merge 先做判决内重叠仲裁再跨行聚合 →
decide 管身份与来源 → select 保持原 dd 门槛语义。

## 起始状态（2026-09-12）

- 起始提交：`cde643ec8c17a97662da13f44860b9611af5a974`（master）
- 工作区：5 个用户未提交文件，本轮不碰、不提交：
  `audit/glm_prep.py`、`audit/glm_verify.py`、`audit/zcode_recheck.py`、`audit/zcode_recheck2.py`、`audit/zcode_recheck3.py`
- 未找到 AGENTS.md；适用说明为 README.md、USAGE.md、decisions/README.md、技术规格 §12
- 环境：Python 3.11.9（`C:\Users\hp\AppData\Local\Programs\Python\Python311`），pyarrow 25.0.0，PyYAML 6.0.3
- 语料指纹（旧 extract manifest 所记，运行时重新计算）：
  SCC `8e79cd40…6da6`，ONCA `58c31f93…3775`

### 基线测试（改动前，均退出码 0）

| 命令 | 结果 |
|---|---|
| `python pipeline/tests/run_regression.py --selftest` | exit 0，normalize_equivalence 三例 identical |
| `python pipeline/extract.py --fixture-check` | exit 0，A18 / B15 / C27 / D6 / E0 / F0，pass |
| `python pipeline/tests/test_layers.py` | exit 0，120 条断言全部通过 |
| `python pipeline/tests/test_layers.py --golden` | exit 0，与金标一致 |

## 阶段状态

| 阶段 | 内容 | 状态 |
|---|---|---|
| 0 | 隔离运行入口 + run manifest | **完成**（commit c66d51e） |
| 1 | 候选全量枚举、逐候选分类、判决内重叠仲裁（D1/D2/D3） | **完成**（见「阶段 1」三节） |
| 2 | 系列与页码身份字段（D4/D5），全量重跑 + 新旧差分 | **完成**（见「阶段 2」） |
| 3 | 来源地最小闭环（D6） | **完成**（见「阶段 3」） |
| 4 | 外国边输出、追溯工具、演示样例、交接 | 未开始 |

## 续跑记录（2026-09-12，第二次会话）

- 本文件与 `pipeline/shapes.py` 的一处未提交修改（D4 捕获组：`series_paren`/`paren_note`，
  只加捕获组不改匹配集合）由上一会话建立；shapes.py 该修改有「2026-09 demo 修复 D4」标记，
  属本任务自己的工作，随后续阶段提交。`audit/` 下 5 个文件属用户，不碰、不提交。
- 基线复测（含 shapes.py 修改后）：
  - `python pipeline/tests/run_regression.py --selftest` → exit 0
  - `python pipeline/extract.py --fixture-check` → exit 0，A18/B15/C27/D6/E0/F0 pass
  - `python pipeline/tests/test_layers.py` → exit 0，120 条断言全部通过
- 依赖版本实测：Python 3.11.9（MSC v.1938 AMD64）、pyarrow 25.0.0、PyYAML 6.0.3。
  本轮**不新增依赖**，故不建 venv：全局环境是用户既有环境，本轮只读不改（隔离手段=
  输出目录隔离，见阶段 0 决定一）。

## 决定记录

（按阶段追加）

### 阶段 0

1. **隔离手段 = 输出目录隔离，不建 venv**：本轮零新增依赖（pyarrow 25.0.0、PyYAML 6.0.3
   已在用户既有环境里），建 venv 只会复制既有解释器、还得重装 550MB 的 pyarrow。
   隔离的实际风险是「新旧批次混跑」，由 run_all 的输出目录规则承担（下条）。
2. **续跑规则**：`--out` 目录必须不存在或为空，否则拒绝启动（绝不把已有目录当可续跑）；
   失败 run 目录原样保留、状态记 failed；重试用新目录。extract 的 progress.json 续跑
   机制在全新目录里天然从零开始。
3. **代码指纹**：`code_fingerprint()` 对 pipeline/*.py（不含 tests/）逐文件 SHA-256 后
   再总哈希——未提交的修改进指纹，git HEAD 单独不够。
4. run_manifest.json 里 status ∈ {running, complete, failed}；非 complete 对下游不是
   完整批次。各层 stdout/stderr 落 step_*.log。

## 运行记录

（按阶段追加：命令、退出码、输出目录）

### 阶段 0

| 命令 | 退出码 | 产物 |
|---|---|---|
| `python pipeline/run_all.py --out data/stage0_smoke --limit-batches 1` | 0 | `data/stage0_smoke/`（run_manifest.json status=complete，9 步全过） |

第一次试跑抓到一个自己的 bug：run_all 定义了 extract 命令却没调 run_step（classify 报
FileNotFoundError 暴露）；修后全过。失败目录两次均已删除重建（规则 2 的重试用新目录）。

## 阶段 4 记录（2026-09-12）

### 实现内容

- `pipeline/edges.py`：引证边输出——边 = (source_decision, resolved_cited_case=
  merged_group_id)，同一判决对同一案件身份的全部提及折成一条；mention_detail_key
  回连逐候选台账（提及级细节不丢）。输出 citation_edges.csv（国内/外国/未知/冲突
  全保留）+ foreign_edges.csv（foreign_status=FOREIGN 的过滤视图，唯一差异就是筛选）
  + manifest。不读 select、不设 kept（约束六）。
- `pipeline/traceback.py`：最终结果 → 原文追溯。`--search` 粗搜台账；`--candidate-id`
  深查：语料行号 + 未改动文本的绝对偏移 → 带 `<<…>>` 跨度标记的原文窗口 + 解析/
  分类/仲裁状态/让位对象/D3 旗。
- `pipeline/run_all.py` 末尾追加 edges 步（全链 10 步）。
- `USAGE.md`：加 §6b（新路线读法）并给 98.80% 加口径警示（= 上游自动中立引证对覆盖率，
  **不是**外国引证召回率）。
- `implementation/demo_examples.md`（build_demo_examples.py 生成，真实数据）：外国案
  Thorner v. Major [2009] UKHL 18（dd 5/occ 20，basis=court_scope_rule:UKHL，引用方
  SCC_2017scc61 提及 8 次等）；国内案 R. v. Lacasse（dd 396）；显式未知案 R. v. W.(D.)
  （dd 693，只有 S.C.R./C.C.C. 汇编引证，无证据 → UNDETERMINED 不猜）；Almrei 坏解析
  完整轨迹（2013 ONCA 375 原文窗口 + 两条 candidate 的仲裁状态对照）。

## 最终交接（2026-09-12）

### 1. 各阶段状态

| 阶段 | 状态 |
|---|---|
| 0 隔离运行入口 + manifest | 完成（c66d51e） |
| 1 候选全枚举 + 逐候选分类 + 判决内仲裁（D1/D2/D3） | 完成（8823274） |
| 2 键 v2 系列/页码身份（D4/D5）+ 全量重跑 + 差分 | 完成（3978fa3） |
| 3 来源地最小闭环（D6） | 完成（8cf6c60） |
| 4 边输出 + 追溯 + 演示 + 交接 | 完成（见 git log 最后一笔） |

### 2. 关键契约变更

- extract 新增 candidates.csv（candidates-2.0，21 列含 candidate_id/行号/字段跨度/
  parse_signature/D3 标注）；extracted.csv 降为诊断产物；classify 新增 parse_status/
  year_vol_ambiguity；merge 双路线（表头分派，legacy 逐字保留）；decide 新增
  foreign_status/origin_country/origin_subdivision/origin_basis/origin_evidence_id；
  新增 court_or_reporter_scope.csv 决策表；run_all/edges/traceback 三个新入口。

### 3. 测试（实际命令与退出码）

| 命令 | 退出码 |
|---|---|
| `python pipeline/tests/test_layers.py` | 0（120 条，legacy 期望值未动） |
| `python pipeline/tests/test_candidates.py` | 0（56 条，新路线） |
| `python pipeline/extract.py --fixture-check` | 0（A18/B15/C27/D6/E0/F0 旧路线档） |
| `python pipeline/tests/run_regression.py --selftest` | 0 |

### 4. 完整运行命令与产物

```
python pipeline/run_all.py --out <新的空目录>
```

- data/run_20260912_final/ —— 10 步全链（extract→classify→merge→decide→select→edges）
  的最终完整 run，run_manifest.json status=complete（含语料 SHA-256、代码指纹、依赖版本）。
  实测：候选 1,013,819；counted 526,156；跨院组 172,916；kept 组 8,578（dd≥5）；
  边 330,362（FOREIGN 227 / DOMESTIC_CA 35,659 / UNDETERMINED 294,476 / CONFLICT 0），
  526,156 条 counted 提及全部入边、0 条无组（mentions_without_group=0）。
- 早期分目录 run（保留供对照）：data/run_20260912_stage2/ + data/run_20260912_stage3/。
- demo_examples.md 与 diff_report.md 均已改指 run_20260912_final，六项专案核查全 PASS。

### 5. 新旧差分

- implementation/diff_report.md（diff_old_new.py 生成）：层级计数对照、仲裁去向账、
  键拆分账（旧键 1,160 个拆成多键）、六项专案核查全 PASS、dd 榜对照。
- 金标 pipeline/tests/golden_layers.json **未改写**；`test_layers.py --golden` 的差分
  即本轮预期 schema/口径变更。

### 6. 提交历史（本轮）

- c66d51e 阶段0：run_all + run manifest
- 8823274 阶段1：candidates-2.0 全候选 + 仲裁
- 3978fa3 阶段2：键 v2（D4/D5）+ 差分
- 8cf6c60 阶段3：来源地闭环（D6）
- （本笔）阶段4：edges + traceback + 演示 + 交接

## Blocked（§5 账本）

### B1 汇编式引证的来源地不可推断（不阻塞演示闭环，长期残项）

- 层/位置：decide.py `_scope_origin`（decisions/court_or_reporter_scope.csv）
- 触发输入：`1991|1|scr||742`（R. v. W.(D.) 的 S.C.R. 引证）——带卷号的汇编键，
  中立码规则结构性不适用
- 阻塞点：reporter_jurisdiction.csv 196 行 100% 是 estimated/name_inference，约束
  明令不得升级为来源地事实；本项目没有已核实的「reporter → 排他法域」证据
- 解锁条件：对 S.C.R./C.C.C./D.L.R. 等逐一做 source-verified、年代有界的排他性核查
  （或用案件级人工表逐案核）
- 现状：这些键 foreign_status=UNDETERMINED（10,895 行国内判定全部来自中立码规则与
  案件表；绝不由「不在例外表 → 外国」倒推）。影响：国内案的汇编引证大量留未知——
  这是约束下的诚实行为，不是错误

### B2 D3 无配对者的极端相邻结构（不阻塞）

- 层/位置：extract.py `annotate_cross_boundary` / merge.py 仲裁 A 步
- 触发输入（构造性）：`[2009] 2 S.C.R. 2009 2009 SCC 51`（页码 token 与后随中立
  引用年份直接相邻、无分隔符）——真引证 a 会被误作废
- 阻塞点：D3 关系旗无第三证据可分辨「a 的页恰是 b 的年」与「a 吞了 b 的年」
- 解锁条件：语料实测出现此类相邻结构（本轮测量未发现真实例）
- 现状：全语料 D3 旗 1,233 条全部有配对者且按规则消解；未发现本例结构

### B3 跨法域法院（UKPC/JCPC）来源地（不阻塞）

- 层/位置：decisions/court_or_reporter_scope.csv（刻意不收 UKPC）
- 触发输入：任何 `[1925] UKPC 11` / A.C. 枢密院案引证
- 阻塞点：跨法域法院的案子必须案件级证据，规则层面无排他来源（§9.3）
- 解锁条件：逐案人工核（case_origin.csv 已有 203 行加拿大 JCPC 案）
- 现状：UNDETERMINED

### B4 美国来源地本轮不可达（不阻塞）

- 层/位置：同 B1
- 触发输入：`389 U.S. 347 (1967)` 类美式引证（reporter 路线，且 U.S. 表行为估计档）
- 阻塞点：US 最高法院历史上有菲律宾上诉期，排他规则须年代有界核实；本轮未做
- 解锁条件：B1 同款核查（美卷）或案件种子人工表
- 现状：UNDETERMINED

### B5 同案传播（co-citation propagation）未实现（不阻塞）

- 层/位置：decide.py（§9.4 第 4 条）
- 触发输入：同组内已定源案件与未定源案件的同案身份链
- 阻塞点：只允许在「已受支持的同一案件身份关系」上传播；本轮最小闭环未建该链
- 解锁条件：身份关系图（decision_ids + 笔误/双语合并）上做受支持的传播并留痕
- 现状：组内不同来源地证据 → 整组 CONFLICT（保守方向）

### B6 D8/D9（任务书明确缓办）

- D8 历史脚注案名关联未做；preceding_text 仍是 120 字符窗口，**不是**完整上下文。
- D9 未做任何人工标注；98.80% 已在 USAGE.md 加口径警示（上游自动中立引证对覆盖率，
  不是外国引证召回率）；本轮不主张任何总体精确率/召回率。

## 阶段 3 记录（2026-09-12）

### 实现内容

- `decisions/court_or_reporter_scope.csv`（新表，7 条 verified 规则）：SCC、CSC、ONCA、
  EWCA、EWHC、UKSC、UKHL。每行带 source/source_locator/verification_status=
  verified_scope_rule/年代窗（valid_from/to）。法域核查由三个只读研究子代理完成：
  - SCC/CSC：Supreme Court Act ss. 3/35/40/52（管辖限于加拿大法院体系），1875 年设；
    「2014 CSC 7 = 2014 SCC 7」官方实例。1875–1949 outbound（可上诉英国枢密院）不影响
    inbound 来源地。
  - ONCA：ontariocourts.ca + Courts of Justice Act s.6(1)（上诉来源全为 Ontario 法院）；
    年份 1867 为标准记载（官网未载，已在表内注明）。
  - UK：UKSC 2009（CRA 2005 s.23/s.40）；EWCA/EWHC 1875（Judicature Acts；殖民地上诉
    走 JCPC 不走 E&W 法院）；UKHL 中立引用 2001-01-11 才启用，此前年份的 UKHL 号是
    BAILII 回溯产物（实测例：Rylands v Fletcher [1868] UKHL 1）——年代闸 valid_from=
    2001 把回溯号与 1922 年前爱尔兰上诉例外全部挡在规则外。
- `pipeline/decide.py`：decide_case_origin 两级证据——①案件级直接证据（basis=
  case_record）；②法院排他来源地规则（basis=court_scope_rule，仅当无直接证据、键是
  结构性中立引用〔有年份、无卷号〕、代码在表、年代在窗内；「已过仲裁」由上游结构
  保证——merged 只聚 counted 候选）。成色分档、绝不混称。新增字段 foreign_status/
  origin_country/origin_subdivision/origin_basis/origin_evidence_id；组内来源地证据
  互斥 → 整组 CONFLICT（证据保留，不由主行/多数票抹平）。约束七：FOREIGN 只来自
  正面排他规则；UKPC/JCPC 不入规则表 → UNDETERMINED。

### 运行记录（decide/select 两层在 stage2 merge 产物上重跑，输出隔离目录）

| 命令 | 结果 |
|---|---|
| `python pipeline/decide.py --court SCC --input …/stage2/merge_out/SCC/merged.csv … --output data/run_20260912_stage3/decide_out/SCC` | scope 2,666 / case_record 215 / UNDETERMINED 119,191 |
| 同 ONCA | scope 8,217 / case_record 40 / UNDETERMINED 58,003 |
| `--cross-court … --output data/run_20260912_stage3/decide_out/cross_court` | 172,916 组 |
| `python pipeline/select.py --input …/cross_court/decided.csv …` | dd 分布与 stage2 完全一致（来源地不影响 kept，符合约束六） |

跨院产出：DOMESTIC_CA 10,895 行（7,905 组）；FOREIGN 243 行（175 组，全部 GB/UKHL·UKSC·
EWCA，basis=court_scope_rule）；CONFLICT 0；年代闸排除 10 条（pre-2001 UKHL 回溯号）。
外国组榜首（真案、证据在 scope 表）：Thorner v. Major [2009] UKHL 18（dd 5/occ 20）、
Jameel v. WSJE [2006] UKHL 44（dd 5）。

### 测试记录

`test_candidates.py` 增至 56 条（scope 7 条：GB 外国 / CA 国内 / 年代闸 / UKPC 不推断 /
卷号结构不适用 / 直接证据优先 / 冲突 CONFLICT）；test_layers 120 条不动全过。

## 阶段 2 记录（2026-09-12）

### 实现内容

- `pipeline/merge.py`：`build_merge_key_v2`（candidates 路线专用；legacy 键与
  mini-chain 测试期望逐字不动）——
  - D4 系列槽：裸「4th」/粘连「4d」/括注「(4d)」正典化为同一值；2≠3；缺失系列
    与显式系列不同键；非序数括注 (N.S.) 以 `n:ns` 独立进键、永不清成序数；
    shape_nominate 的宽口径括注（法院标注）不进键。原写法保留在候选字段。
  - D5 页码槽：罗马页加 `ro:` 前缀（xiii≠xiv、罗马不与缺失同键、不与阿拉伯同键）；
    page_prefix/page_suffix 不进键、随候选字段与 mentions 台账保留。
  - 仲裁的「同含义」判定同步改用 v2（83 F. 2d 212 与 83 F. (2d) 212 现在判同义）。
  - `key_mapping.csv`：旧键→新键逐对映射 + 候选数；计数全部从新成员重建，绝不
    把旧键 dd 拷到拆分出的新键（manifest 记 old_keys / old_keys_split_into_multiple）。
- decide/select 未改（v2 键 5 槽同构，decide 的按槽解析不受影响）。

### 全量五层重跑（隔离目录 data/run_20260912_stage2/，manifest status=complete）

| 层 | 数字 |
|---|---|
| extract 候选 | 1,013,819（SCC 638,330 / ONCA 375,489 进 classify） |
| 仲裁（两院合计） | counted 526,156；contained 让位 250,884；表裁决同跨度 101,848；弃权 8,819；D3 作废 1,233；自引 101,204；行级拒绝 17,657 |
| merge 键 | SCC 122,072 / ONCA 66,260；旧键拆分 671+489 |
| decide 跨院 | 172,916 组 |
| select dd≥5 | 8,578 组 kept（门槛语义未动，仍标 uncalibrated_placeholder） |

### 新旧差分（implementation/diff_report.md，工具 diff_old_new.py）

六项专案核查全 PASS：Almrei 误解析键不在新表而 2011 ONCA 779 在（occ 4/dd 4）；
Kvello 2009 SCC 51 单键（occ 21）；|2d| 7,997 组 / |3d| 7,445 组拆键生效；
罗马页键 474 组；全表逐行核对「每键 counted 数 == occurrence_count」（无双计数）。
金标未改写；`test_layers.py --golden` 的差分即本轮 schema/口径变更，属预期。

### 测试记录

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python pipeline/tests/test_candidates.py` | 0 | 48 条断言（含 D4/D5 六条新断言） |
| `python pipeline/tests/test_layers.py` | 0 | 120 条（legacy 不动） |
| `python pipeline/run_all.py --out data/run_20260912_stage2` | 0 | 全链 complete |

## 阶段 1 记录（2026-09-12）

### 实现内容

- `pipeline/extract.py`：新增 candidates-2.0 路线——`scan_overlapping`（D2 重叠枚举，
  下一匹配从 `match.start()+1` 重找）+ 边界闸（新匹配不得起于字母数字串中部，防
  「23 A.C. 4」类截断垃圾）；`extract_candidates` 输出全候选（candidate_id、
  corpus_row_index、字段跨度 year/page/vol/abbr_span、parse_signature）；D4 捕获组
  series_paren/paren_note 入 schema；`annotate_cross_boundary`（D3，extract 有判决内
  跨候选视野，在此算关系、逐候选带标注，classify 只读本行）；候选爆炸上限 20000
  （超限记 cand_limits.csv + manifest 统计，绝不静默截断）。旧 kept/superseded 输出
  与 `--fixture-check` 原样保留，降为诊断产物。
- `pipeline/classify.py`：新增 parse_status（valid / structurally_conflicted /
  ambiguous_year_vol）与 year_vol_ambiguity 两列——解析判定与查表结果分列；
  D3 旗候选不得凭查表拿 unambiguous confirmed（confirmed → table_hit_conflicted）。
- `pipeline/merge.py`：双路线按表头分派。legacy 路线（无 candidate_id 列）逐字保留，
  迷你全链 120 条断言不动全过；candidates 路线先**判决内**仲裁（分组键 =
  (source_decision_citation, corpus_row_index)，62 份共享 `{COURT}_` 的文档互不串），
  再跨行聚合。仲裁状态机：counted / alternative_same_key / alternative_contained /
  alternative_unsupported_reading / span_alternative_undecided / overlap_undecided /
  alternative_spanning_mismatch / cross_boundary_invalid / rejected_row /
  self_citation_row；逐候选台账 mentions_candidates.csv 是追溯主干。
- `pipeline/run_all.py`：classify 输入改 candidates.csv。
- `pipeline/tests/test_candidates.py`：新路线 36 条断言（Kvello / BCE / Almrei /
  同跨度计一次 / 包含消解 / 合成横跨 / 弃权 / 顺序不变性 / 行分组 / 边界闸 /
  夹具对照——正夹具 exact 不得低于旧路线、负夹具误报上限实测钉住）。

### 决定记录（规格未定处，均须人复核）

1. **同跨度异含义的计数归属**（§7.1C 规则的落地口径）：表证据唯一支持一读 → 归它；
   双方都有支持且冲突、或全无支持 → 整组 span_alternative_undecided，0 计数（弃权，
   不是默认）。依据约束四。
2. **4 位数字年/卷之争**：代码在表中 → 表裁决（Kvello 类）；代码不在任何表 →
   形状特异性**不**当结构证据，标 ambiguous_year_vol + unresolved，不默认年读法。
   ——这是本规格未settled的判断点，**显式留给人复核**（§7.1C 要求记录）。
3. **D3 旗是关系旗**：a.page 形似年份 ∧ a.page_span==b.year_span ∧ b 是完整 neutral
   且 a.start<b.start<a.end<b.end 才打旗；无 b 不打旗（真 4 位页码不受伤）。
   配对者有效 → a 仲裁为 cross_boundary_invalid；配对者缺席/无效 → unresolved，
   候选保留计数但永不 confirmed（classification 已降级）。
4. **横跨长候选规则**：X 与 ≥2 条更短、互不重叠的候选重叠 → X 让位（不硬选最长），
   短候选保留——重叠组不要求唯一赢家。
5. **边界闸同样作用于首遍命中**：旧 finditer 偶有起于字母数字串中部的命中
   （如 "R1500 A.C. 400" 里的 1500），新路线一律不收（实测损失见下）。

### 全语料测量（implementation/measure_alt_parses.json，34,782 份判决，176.5s）

| 项 | 数 |
|---|---|
| 旧 finditer 原始命中 | 998,465 |
| 新全候选（重叠+闸） | 1,013,819（+1.54%） |
| 边界闸拦下 | 708,828（全为字母数字串中部起点的截断垃圾；样例核过） |
| 同起点多候选组 | 154,260 |
| **同形状同起点不同解析** | **0**（§7.1B 允许以测量代展开的依据） |
| 同跨度异形状对 / 嵌套异形状对 | 149,641 / 4,651 |
| D3 跨界旗样例 | "154995 Canada Inc., 2005"（公司名+年份被误读为卷名页）、"20 A. Federal Court, 2020"（标题结构） |

注：任务书给的样本估计 +5.6% 未含边界闸；闸后净增 1.54%，闸拦下的 70.9 万条
正是「重叠扫描会制造的垃圾」——两数并读才完整。

### 测试与运行记录

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python pipeline/tests/test_layers.py` | 0 | 120 条断言（legacy 路线不变） |
| `python pipeline/extract.py --fixture-check` | 0 | A18/B15/C27/D6/E0/F0（旧路线诊断档） |
| `python pipeline/tests/run_regression.py --selftest` | 0 | normalize_equivalence identical |
| `python pipeline/tests/test_candidates.py` | 0 | 36 条断言（新路线） |
| `python pipeline/run_all.py --out data/stage1_smoke --limit-batches 1` | 0 | 新路线全链烟雾通过 |
