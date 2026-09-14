# Demo 修复工作记录（D1–D6）

本文件是本轮修复的持续工作记录。只记事实：做了什么、跑了什么、结果是什么、卡在哪。
最终验收不属于本轮工作，本文件不作任何「通过」声明。

> **Round 2（2026-09-12 晚）**：针对 round-1 的独立复审订正（R2-1…R2-10），按
> 订正案建议顺序执行。round-1 记录见下文各节。

## Round 2 记录（2026-09-12）

### 执行顺序与提交

| 步骤 | 内容 | 提交 |
|---|---|---|
| 1 | R2-10 输入指纹闸 + 候选爆炸 fail-closed | 60081fd |
| 2 | R2-2/3/5/6 仲裁支持分级、终集合定点收敛、nominate 序数括注、run 级边界闸 | 60081fd |
| 3 | R2-1/9 成员/组/边溯源 + 有效来源关联 | 2f587bb |
| 4 | R2-4 scope 表官方化 + 分辑行 + 标识符年代闸 | 82c456a |
| 5 | 全量 run + 3.2 核查 + 报告 | （本笔） |

### 实现要点（按缺陷）

- **R2-10**：`run_all.input_identity()` 启动时对 生产代码+全部决策表+select 配置+
  语料+参数 算一次指纹，**冻结**写进 manifest（后续更新绝不重算覆盖）；收尾重算比对，
  变更 → status=failed（不是 complete）。候选爆炸从「截断+记账」改为 **fail closed**
  （complete 与「发生过截断」不能并存）。
- **R2-2**：`support_grade`（exact=2 > 其余已解析=1 > 无可用支持=0；被拒/结构冲突/
  歧义未决/UNSUPPORTED 一律 0）。同跨度先按键合并（同义多解析不自打平），异含义间
  唯一最高档胜出，最高档打平才弃权；带支持的输家标 `alternative_weaker_support`。
- **R2-3**：不同跨度同规则——严格更高支持档唯一起者胜，输家 `alternative_dominated_by_support`；
  同档弃权是**残差**（支配类裁决优先，见终集合口径）。
- **终集合不变量**：重叠不传递——支配链定点收敛到最终被计数者（`arbitrate_document`
  的 fixpoint：链式重定向 + 被消解/未决者不当唯一压制者，回收重算入 stats）。
- **R2-5**：nominate 括注本身是序数系列形时按系列正典化进键（165 A. (2d) 82 (1960)
  与 vol_page_year 读法同键，计一次）。
- **R2-6**：边界闸改 **run 级**口径——仅当新匹配起点与**同形状更早发射起点**同处一个
  连续字母数字 run 时才拒；run 内首匹配放行（`Court of Appeal[1997] R.J.Q. 2907`、
  `1[1961] S.C.R. 614` 不再被吞），同 run 的 `23 A.C. 4` 截断照拒。
- **R2-1**：decide 产出成员级观察 `member_origin_*`（含全部证据 id、成员本地 CONFLICT
  不被空国别隐瞒）+ 每成员 `identity_basis`（anchor/singleton/same_citation/
  anchor_variant_bilingual **合格**；typo 变体/name_year/cocitation/unanchored 只审计）。
  组级结论 `group_origin_*` 从合格成员证据聚合，院内与跨院轮都执行、写到每行；冲突
  检查跨院后同样跑。启发式成员的证据进 `noncore_origin_evidence` 审计列。
- **R2-9**：decide 输出 `effective_sources.csv`（来源→组关联，带 status 与
  exclusion_reason 与到达路径的最优 identity_basis）；每组 counted 来源数 == dd
  （断言）。edges.py 只消费该关联：平行形自引（1,366 处 dd+1 虚增）不再重现，
  留 `self_excluded_edges.csv` 审计；仅启发式路径的边**不继承**组 FOREIGN/DOMESTIC
  （foreign_status=UNDETERMINED + tentative_edges.csv），组结论留 group_origin_* 列。
- **R2-4**：scope 表来源全部换成官方/一手（legislation.gov.uk Judicature Acts 1873/1874
  PDF 原文、BAILII 2001-01-11 PD 原文、judiciary.uk、jcpc.uk PD1 §1.1、CCC/Lexum
  标识符标准）；年代闸改用**标识符适用期**（SCC/CSC 2000、ONCA 2007、EWCA 系 2001、
  EWHC Ch 2002——Admin 先行、其余分庭 2002-01-14，corpus 里 [2000]/[2001] EWHC Ch
  属供应商回溯，被闸挡下诚实降级）；新增 EWCA Civ / EWCA Crim / EWHC Ch 分辑行
  （键=印刷事实，不实现前缀匹配）；UKUT 仍不入表（分庭属地证据不足）。
  scope 只适用于 **citation_kind=neutral** 的行（年头+空卷不证明引证种类）。
- **R2-7（缓办）**：非序数括注拆分键（10 Cush. (Mass.) 337 vs 10 Cush. 337）不改，
  记账本。**口径订正**：这是未决的身份拆分，其下游计数方向**未确立**——不声称
  「只会少算」。
- **§7 能力陈述订正**：round-1 报告里「同形状同起点不同解析=0」**不构成**「不存在
  其他解析」的证明——单匹配/起点的扫描器在结构上无法证明不存在性；该能力标为
  partial/deferred（除非未来做独立的分支枚举测试）。round-1 的全语料测量数字保留，
  只作「观测值」引用。

### 测试（截至本轮提交时）

| 命令 | 退出码 | 说明 |
|---|---|---|
| `python pipeline/tests/test_candidates.py` | 0 | 111 条断言（round-1 的 56 条不动，新增 55 条 R2 断言） |
| `python pipeline/tests/test_layers.py` | 0 | 120 条（legacy 不动） |
| `python pipeline/extract.py --fixture-check` | 0 | A18/B15/C27/D6/E0/F0 |
| `python pipeline/tests/run_regression.py --selftest` | 0 | |
| `python pipeline/tests/test_layers.py --golden` | 0 | **口径**：它比对的是 data/ 旧产出与金标——旧产出与金标未改，故输出「一致」；它**不**检验新候选路线，对新代码无证明力 |

### 全量 run

- 第一次：`data/run_20260912_r2/` —— 10 步全部跑完后在 run_all 收尾验证处因我引入的
  `self`/`r` 作用域笔误崩溃（NameError），manifest 停在 running。**失败目录按规则
  原样保留**，修复后重试。
- 第二次：`data/run_20260912_r2b/` —— 同一笔误的第二处（`if not self.identity_verified`）
  又崩一次，目录保留。
- 第三次：`data/run_20260912_r2c/` —— **complete**，R2-10 启动指纹冻结、收尾验证通过。

### 3.2 核查（全量 run：data/run_20260912_r2c/）

**(a) legacy 匹配保全**：998,465 条旧 extracted+superseded 行全部在新候选台账连接成功，
**缺失 0**（目标 0）；空引证 id 排除 0 条；raw 不一致的连接失败 0 条。

**(b) 旧 counted 行去向**（518,480 行）：

| 去向 | Round 1 基线 | Round 2 |
|---|---|---|
| 1 仍被计数 | 510,717 | 512,188 |
| 2 身份等价替换 | 0 | 0 |
| 3 仅重叠 counted 跨度 | 713 | 761 |
| 4 任何地方都没计 | 6,954 | 5,531 |
| 5 未枚举/连接未决 | 96 | **0** |

「没计」桶分解（r2_lost_breakdown.json）：旧 UNSUPPORTED 5,488 / 旧已解析法域 43；
形状 neutral_bare 4,989、vol_abbr_page 541；新仲裁状态：同跨度平票弃权 4,980、
D3 作废 340、部分重叠弃权 210、包含让位 1。大头是 **DTC 系同档平票**（同一代码在
法院代码表与汇编表都精确命中 → R2-2 规则规定最高档打平即弃权；旧管线按形状顺序
硬选一边计入，属未证实猜测）；340 条 D3 作废是跨界修正按规则作废旧赢家。

**(c) 组一致性**：173,615 组；组内行 group_foreign_status 不一致 **0**；多国别非
CONFLICT **0**；case_record 成员落在 UNDETERMINED 组 28（订正后合法：身份连接是
启发式，证据保留在成员列与 noncore 审计列——含 St. Catharines XC-G000455，
case_origin:188814appcas46 保留、组 UNDETERMINED）。

**(d) 专案核查**（r2_case_checks.py，FAILS: none）：2004 FC 736 counted（4 提及）+
汇编读法 weaker_alternative；(1937) Q.R. 64 K.B. 27 每文档恰一条 counted（corpus
印刷形为圆括号年，含括注变体按包含让位）；165 A. (2d) 82 (1960) 每次出现恰一条
（该文档原文印两次=两次出现）；EWCA Civ → FOREIGN（70 行）；St. Catharines 如上；
Thorner v. Major 仍 FOREIGN（5 条 supported 边）；BCE/Almrei/Kvello 不变（Kvello
occ 82/dd 29，无卷读法重计键）。

**(e) 边计数**（对照 round-1 的 227/35,659/294,476/0）：FOREIGN **386**（+159：
EWCA Civ/Crim 分辑行生效等，全部有 scope 证据）；DOMESTIC_CA **56,685**（+21,026：
FC/Q.R./L.R. 恢复 + 合格成员聚合不再依赖主行）；UNDETERMINED 272,765；CONFLICT 0。
总量 329,836 = round-1 330,362 − 1,366（被剔自引，R2-9）。supported 313,149 /
heuristic_only 16,687（tentative 台账 1,522 条）。

**(f) kept（dd≥5）**：8,585 组（round-1：8,578，+7）。门槛语义未动——变化全部来自
仲裁恢复与身份聚合的数据变化，不是阈值改动。

**(g) 案名投票限制测量（§7）**：投票行 466,862，其中来自非 counted 候选 204,048
（43.7%）——modal 案名不是已核实的身份证据，只作展示列；已测量、已记录，本轮
不做名字抽取重构。

### Round 2 各缺陷状态

| 缺陷 | 状态 |
|---|---|
| R2-1 组来源取主行 | **fixed**（成员观察 + 身份基础 + 两轮聚合写每行 + 冲突跨院复查） |
| R2-2 FC 全丢 | **fixed**（专案核查过） |
| R2-3 部分重叠无支持支配 | **fixed**（Q.R./L.R. 系恢复） |
| R2-4 EWCA 几乎不触发 + Wikipedia 来源 | **fixed**（分辑行 + 官方来源 + 标识符年代闸） |
| R2-5 nominate 序数括注 | **fixed** |
| R2-6 边界闸过严 | **fixed**（全量连接缺失 0） |
| R2-7 非序数括注拆键 | **deferred**（记账本 B8；方向未确立） |
| R2-8 报告失真 | **fixed**（diff_report.md/demo_examples.md 重生成 + 口径警示） |
| R2-9 边成员资格与 dd 不一致 | **fixed**（effective_sources 权威 + 1,366 自引剔除 + 断言） |
| R2-10 指纹不绑决策表 | **fixed**（启动冻结 + 收尾验证；两次崩溃目录保留、第三次换目录成功） |

### Round 2 测试与运行记录

| 命令 | 退出码 |
|---|---|
| `python pipeline/tests/test_candidates.py` | 0（111 条：round-1 的 56 条不动 + 55 条 R2 新增） |
| `python pipeline/tests/test_layers.py` | 0（120 条） |
| `python pipeline/tests/test_layers.py --golden` | 0（口径见上：只查旧产物稳定性，对新代码无证明力） |
| `python pipeline/tests/run_regression.py --selftest` | 0 |
| `python pipeline/extract.py --fixture-check` | 0（A18/B15/C27/D6/E0/F0） |
| `python pipeline/run_all.py --out data/run_20260912_r2c` | 0（complete，指纹验证过） |
| `python implementation/r2_regression_join.py data/run_20260912_r2c` | 0 |
| `python implementation/r2_lost_breakdown.py data/run_20260912_r2c` | 0 |
| `python implementation/r2_case_checks.py data/run_20260912_r2c` | FAILS: none |

## Round 2 闭环（2026-09-13，任务书三）

### 起点（按任务书第二节记录）

- 起始 commit：`e4eadf4`；r2c manifest：status=complete，input_identity_verified_unchanged=true，10 步。
- 修改前基线实测：test_candidates **111**、test_layers **120**、selftest exit 0、
  fixture A18/B15/C27/D6/E0/F0 pass——与任务书所报一致。

### 任务一：身份授权（commit 3d3104f）

- 新表 `decisions/bilingual_neutral_codes.csv`（40 对）由确定性离线脚本
  `decisions/tools/build_bilingual_neutral_codes.py` 生成：从 neutral_court_codes 的
  source_locator 解析 databaseId / caseBrowse en·fr 端点 / 佐证引证年代；再扫描本地
  决策表说明文字找「同案双语对应」显式证据（同 年+编号 两代码成对）。状态：
  **verified_explicit_equivalence 仅 SCC/CSC 一对**（本地证据：2014 CSC 7 = 2014 SCC 7，
  Hryniak，源 decisions.scc-csc.ca 公报）；FCA/CAF、TCC/CCI、CMAC/CACM、CHRT/TCDP、
  TATCE/TATCF = candidate_endpoint_pair（同库 en+fr，不授权）；FC/CF =
  unverified_same_db_en_only；ABQB/ABKB、SKQB/SKKB、NFCA/NLCA 及 NBBR/NBQB 等
  = rejected_renamed_code（同语言端点 + 佐证年代不相交）。加载用显式允许集合
  ALLOWED_BILINGUAL_STATUSES，不用 startswith。
- `decide.load_bilingual()`（无方向小写对集合，缓存）；`same_decision_kind` 的
  bilingual 分支加第 5 条件：{code_a, code_b} ∈ 已核实对。FCA/CAF 同年同号自此
  不再自动合并（诚实方向）。
- `assign_identity_basis`：顺序改 singleton → anchor → anchor_variant_* →
  same_citation（**仅全组单键**）→ unanchored/cocitation/name_year；typo 变体细分
  anchor_variant_typo_number / typo_year。重复出现的弱键不再因 keycount>1 升级。
- `edges.py` 改用 `from decide import ELIGIBLE_BASES`（decide 不依赖 edges，无环）；
  测试钉住两模块同一集合。
- 身份反例（假代码非 bilingual / SCC-CSC 仍 bilingual / ABQB-ABKB 非 bilingual /
  弱键×2 不升 same_citation 且组不 FOREIGN / 单键组 same_citation 合格 /
  typo×2 保持变体 / 顺序不变）全部先行失败后转绿。

### 任务二：仲裁终态（commit 3d3104f + 冲突类补丁）

`arbitrate_document` 重写为**等价类 + 攻击图 + grounded 终态**：
- 5.2 同跨度同键先折叠成类（成员全保留；类档=成员最高档；代表按 档→形状序→id）；
- 5.3 攻击边：support_span（同跨度异键严格高档）/ same_key（同键不同跨长者胜）/
  contained（相容包含）/ dominated（部分重叠严格高档）/ conflict_span·conflict_overlap
  （同档互指）/ cross_boundary（D3 配对者，须有可用支持）；
- 5.4 spanning=联合前提：依据集=**严格包含于** L 的 ≥2 条互不重叠更短类（「覆盖」
  语义修正——round-2 用的是部分重叠，会把他人碎片误当依据）；L→自家依据的攻击边
  挂起（打破循环依赖）；L OUT 当且仅当 |依据∩IN| ≥ 2；依据含 UNDEC 且 IN 不足 →
  L UNDEC；依据全失效 → L 按普通边评估（可回收）；
- 5.5 grounded 不动点：IN=无有效攻击者或全 OUT；OUT=存在 IN 攻击者；UNDEC=二者
  均不可证；纯互指环 UNDEC，不用输入/形状顺序破环；
- 5.6 状态映射按攻击种类回填原词表（conflict 类被第三方打破时以因果攻击者优先）；
- 5.7 返回前 fail-closed 断言（终态唯一、counted 间无存活攻击、替代对象均为最终
  counted 且原始依据仍成立、无替代链）。
- 反例 A–H 全部先行失败后转绿；test_unresolved_suppressor_recycles_dominated 为
  **唯一预授权修改**（修改前断言：s 因另支配垃圾 a 仍 counted；修改后：s/t/a 全部
  不得 counted、a=overlap_undecided 备注「压制者本身未决」；第二段「移除 t 后
  s counted、a 指向 s」保留）。
- 运行事故记录：第一次 r2d run 在 merge 步因 KIND_PRIORITY 缺 conflict_* 键崩溃
  （同档环被第三方打破时 conflict 攻击者可合法 IN）——失败目录
  `data/run_20260913_r2d/` 保留；修复后按规则换目录重跑。

### 任务三：完整运行

- `data/run_20260913_r2d/`：失败（merge_SCC KeyError），目录保留。
- `data/run_20260913_r2d_b/`：**complete**，input_identity_verified_unchanged=true，
  10 步全过，无候选爆炸（fail-closed 未触发）。本轮 demo 候选版 = 该目录。

### 任务四：差异核对（r2closure_delta.py → <r2d>/audit/）

**7.1 历史差异（Round 1 → r2c）**：Round 1 目录 =
`data/run_20260912_final`（edges manifest 330,362，round-1 报告自引剔除 1,366）；
r2c = `data/run_20260912_r2c`（329,836）。逐边身份键 (source_decision,
mention_detail_key) 对照：**removed 1,475 + added 949**，可复算等式
330,362 − 1,475 + 949 = 329,836 ✓。+840 净残差解释：round-1 交接把「−1,366 自引
剔除」当成唯一变化，实际还有 842 条边因「新 counted 提及」加入（FC/Q.R./L.R. 恢复
等仲裁修复的直接产物）+ 96 条重排组/换键 + 11 条未分类；removed 侧 1,389 条
mentions-not-counted（含自引剔除）+ 81 条重排 + 5 条未分类。多类增删相互抵消，
不存在「恰好 840 条某类恢复边」。

**7.2 本轮差异（r2c → r2d_b）**：边 329,836 → 330,126（removed 79 / added 369）；
FOREIGN 386 → **384**（−2）；DOMESTIC_CA 56,685 → **53,948**（−2,737）；
UNDETERMINED 272,765 → **275,794**（+3,029）；same_citation 主行降级 **1,343 组**
（弱连接不再传播来源地，诚实方向）；组级来源结论变化仅 3 组；仲裁状态变化 655
（counted→overlap_undecided 92 = 反例 A/E 语义生效；cross_boundary_invalid→counted
369 = D3 配对者最终未决/OUT 后按 grounded 回收；recycled_weak_to_counted 0）；
tentative 4,119；supported 304,527 / heuristic_only 25,599。

**7.3/7.4**：`audit/r2c_supported_lost_43.csv`（43 条固定，r2d 中 1 条 counted）、
`audit/r2c_overlap_only_761.csv`（761 条固定，r2d 中 0 条 counted）——均为稳定字段
（court/sdc/offsets/shape/raw）逐条去向。

### §8 案名投票敏感性（只比较，不改生产规则）

- A current（生产口径）：173,878 组 / kept 17,265 / 边 330,126 / FOREIGN 384。
- B dedup_position（位置稳定键 = sdc+row+start+end；同位置 nk 互异案名弃权）：
  **与 A 全同**（组、dd、门槛、来源、边全部零变化）。
- C counted_only：组 173,969（+91 分裂差异）/ kept 17,232（−33）/ 边 330,099（−27）；
  modal 名变 5,271（多为名字变空：counted 池无票）；**dd 变 0、门槛跨越 0、
  组来源变 0、FOREIGN 边 384 不变**；稳定率 0.9981。
- 结论（供人工拍板）：B 与生产等价；C 只动案名列与分组切分，不动计数与来源。
  产物：sensitivity_{current,dedup_position,counted_only}/（完整五层重算）+
  audit/case_name_sensitivity_summary.json、case_name_sensitivity_groups.csv。

### 闭环测试与运行记录

| 命令 | 退出码 |
|---|---|
| `python pipeline/tests/test_candidates.py` | 0（**156 条**：闭环前 111 + 新增 45 条反例/守卫断言） |
| `python pipeline/tests/test_layers.py` | 0（120 条；test_unresolved_suppressor 按预授权修改外全部原样） |
| `python pipeline/tests/run_regression.py --selftest` | 0 |
| `python pipeline/extract.py --fixture-check` | 0（A18/B15/C27/D6/E0/F0） |
| `python pipeline/tests/test_layers.py --golden` | 0（口径：只验证旧产物兼容性，对新代码无证明力） |
| `python pipeline/run_all.py --out data/run_20260913_r2d` | 1（merge KeyError——失败目录保留） |
| `python pipeline/run_all.py --out data/run_20260913_r2d_b` | 0（complete，指纹验证过） |
| `python implementation/r2closure_delta.py data/run_20260913_r2d_b` | 0 |
| `python implementation/r2closure_sensitivity.py data/run_20260913_r2d_b` | 0 |

### 停止条件自查（任务书十一）

- 新 run complete ✓；指纹启动/结束一致 ✓；全部新反例通过 ✓；未授权旧测试全过 ✓；
  fixture 数字保持 ✓；替代对象均为最终 counted（fail-closed 断言在每次仲裁生效）✓；
  counted 终态冲突断言 ✓；输入顺序不影响结果（反例 G）✓；同键重复不改变外部结果
  （反例 H）✓；43/761 逐条去向 ✓；两份差异分开 ✓；+840 残差可复算解释 ✓；
  三口径敏感性输出 ✓；能力表述与代码一致（本轮第 7 节订正）✓。
- **标记：demo 候选版，待独立审计。**

### 评审收尾（2026-09-13 晚，commit 97ce123 + 本笔）

**回归修复（评审定位，先测后修）**：r2d_b 里 369 条候选从 cross_boundary_invalid
变成 counted——全是「8377278 Canada Inc., 2019」类数字公司名碎片，其 D3 配对者全部
是判决头部自印中立引证（self_citation_row）。旧仲裁只排除 rejected 配对者；重写版
建类前剔除了自引行，配对者查不到 → D3 记 unresolved → 碎片 counted。修复：自引
配对者不参与计数竞争，但**本身是真实印刷引证**——作为跨界证据无条件有效，被标
碎片整类直接 OUT（不经 grounded）；fail-closed 断言为该例外放行（替代对象 =
counted 或自引配对者）。先写失败测试（156→158 断言）再修。
**连带排查**：全函数审计确认无其他依赖「旧代码会用、新代码剔掉的行」的点
（by_id 只用于 D3 配对者查找；spanning/攻击边/代表全部只作用于 live 类）。

**重跑与回退**：`data/run_20260913_r2d_c/`（complete，指纹一致，10 步）。
- vs r2d_b：边 330,126 → 329,760（**removed 366 / added 0**）；369+2 条候选
  counted/undecided → cross_boundary_invalid（逐条见 audit/vs_r2d_b/）。
- vs r2c（最终对照）：边 329,836 → 329,760（−76）；FOREIGN 386→384；
  DOMESTIC_CA 56,685→53,948；UNDETERMINED 272,765→275,428；状态变化 284
  （counted→overlap_undecided 92 = 反例 A/E 语义；跨运行口径
  recycled_weak_to_counted = 1）。

**审计订正（评审指出）**：
1. sensitivity 的 `kept_groups` 之前实际数的是 kept=true 的**行**——已改为取
   select manifest 的 groups_kept。真实数字：A 8,585 组 → C 8,573 组（−12）、
   边 330,126 → 330,099（−27）。**「C 不影响计数」的说法作废**。
2. 所有「只比较成员集合相同的组」的结论（same_citation 降级 1,343 组、dd/门槛/
   来源变化 0 等）已加覆盖注记（matched 173,542 / r2c 173,615 / r2d 173,544）；
   未匹配组的单侧 dd 合计单列（C 口径 909/882）。
3. recycled_weak_to_counted 改跨运行口径：上轮非 counted、本轮 counted、支持档 0。
4. 历史差异里 **11 条新增、5 条删除为 unclassified**，如实保留在
   historical_edge_delta CSV 与 summary 中。

**抽查（任务四，20 条分层 + 原文窗口，audit/arbitration_spotcheck_20.csv，21 行）**：
- **P1（新系统问题，未修，只报告）**：相容包含规则放过「(2001), 2001 CanLII 24079」
  型长误析——其 vol 槽复写了真中立引证的年份，把真引证压成 contained
  （CanLII/ONCA 系约 118+27 条转换落此模式）。修复方向（vol==年份复写视为不相容）
  待人工批准，本轮不动。→ 账本 B10。
- P2 改善：公司名碎片不再计数（3 条样例）。
- P3 诚实漏计：真引证因压制者未决而弃权（2 F.C. 472、15 D.L.R. (4th) 515、
  8 D.L.R. (3d) 1、[1897] Q.R. 12、2010 BCCA, 257、134 F.Supp. 710 等）——
  规则正确下的真实召回损失。
- P4 正确回收：2011 ONCA 445、1989 U.S. Briefs 478（后者属边缘：brief 编号）。
- P5/P6：OCR 混排碎片让位无害；表决表碎片的状态词从 invalidated 改弃权更准确。

**措辞订正（评审要求）**：KIND_PRIORITY KeyError 证明的是「未处理分支会使运行
失败」，**不是**正确性断言抓到错误结果；counted 集合无内部攻击是 grounded 解的
必要条件而非充分证明——这两句已在演示措辞约束里写死（demo_candidate_cases.md）。

**演示准备**：`implementation/demo_candidate_cases.md`（3 成功 + 1 弃权 + 2 局限，
每条带 traceback 复现命令）；demo_examples.md 已按 r2d_c 重新生成。

## Round 2 Blocked 增补（续）

### B10 相容包含放过「年份复写」长误析 —— **已修复**（2026-09-13，commit 75c519f + r2e）

- 层/位置：merge.py `arbitrate_document`（contained 攻击的 `_fields_compatible`）
- 触发输入：`R. v. Rose (2001), 2001 CanLII 24079 (ON CA)`——真中立引证
  `2001 CanLII 24079` 与长误析 `(2001), 2001 CanLII 24079`（year_vol_page，
  vol 槽=年份 2001）共享 abbr/page 且短侧 vol 为空 → 判「相容」→ 长者胜，
  计入的是误析键 `2001|2001|canlii||24079`。grounded + 包含规则使其较 r2c
  （双弃权）恶化；全量约 118+27 条转换落此模式（CanLII/ONCA 前括注年份体例）。
- 修复（任务书单缺陷轮）：按 D3 同款设计——extract 在 D3 同处计算结构关系
  `year_reread_as_vol`（**按字段 SPAN 偏移对齐**：容器有 year+vol、vol 形似年份、
  shape_neutral_bare 候选 b 满足 b.year_span == a.vol_span 且 b.end <= a.end；
  不做纯值比较）；仲裁将容器整类判新状态 `year_reread_as_vol_invalid`
  （superseded_by=配对者，证据直接不经 grounded）；被包含配对者与其同跨度卷读法
  走**既有**仲裁（支持分级/同跨度/年卷孪生弃权），不加强制计数规则；
  classify 镜像 D3（被标行不得凭查表拿 confirmed）。
- schema 核对：vol_span 字段 candidates-2.0 **已具备**（round-1 即有
  year/page/vol/abbr 四跨度），无需 bump——已核对并记录。
- 反例 a-e 先行失败（B10(a) AssertionError 已存档于日志）后转绿；
  test_candidates 158 → **170** 断言；test_layers 120、selftest、fixture、
  --golden 全部保持。
- 重跑：`data/run_20260913_r2e/`（complete，指纹一致，10 步）。
- 验证数字（对照 r2d_c）：
  1. B10：容器标记 92、作废 92、unresolved 0；配对者去向 = 弃权 60
     （vendor 形态 B7 语义）/ counted 32（court-code 中立锚恢复）；
     按表结果分列：court_code_resolved 33 / vendor_or_unresolved 59。
  2. 爆半径：候选状态变化 264 条，**全部 (i) B10 容器/配对者/同跨度孪生，
     (ii) 其他 = 0**。构成：86+5+1 容器 → invalid；27 中立配对者解放 → counted；
     27 卷孪生 → alternative_contained（被真引证包含，合法）；
     118 vendor 孪生 → span_alternative_undecided（P1 压制解除，回 B7 弃权）。
  3. 旧 counted 行去向（同一仪器）：518,480 → 仍计 512,044 / 重叠 780 /
     丢失 5,656 / 未枚举 0（r2d_c 为 512,188/761/5,531/0——差值即 92 容器的
     畸形旧键退出，真引证按中性键另计）。
  4. 组与边：kept 组 8,573 → **8,582**（+9：中立锚恢复使被拆分的平行汇编
     重新合组）；边 329,760 → **329,706**（−54：畸形键边退出 + vendor 弃权）；
     FOREIGN 384 不变；DOMESTIC_CA 53,948 → 53,963；UNDETERMINED → 275,359。
  5. 一致性：legacy 缺失 **0**；组内行来源不一致 **0**；多国别非 CONFLICT **0**。
  6. 追溯：`SCC:3359:5048:5059:shape_neutral_bare`（2003 SCC 74 counted，
     confirmed CA）与 `ONCA:10076:8322:8339:shape_neutral_bare`（CanLII 弃权），
     均已用 traceback 验证原文窗口。
- **红线披露**：old-supported lost = **61**（任务书 cap 60，超出 1 条）。构成：
  60 条 = year_reread 容器本身（修复目标，畸形键退出；其中 court-code 33 条的
  真引证已按中性键计数）+ 1 条 = `(2001), 2001 DTC 295` 容器作废后其 DTC 孪生
  按 B7 弃权（真引证本轮 0 计数——弃权合规但仍属召回损失）。另注：评审的
  r2d_c 基线（5,597 lost）与本仪器（5,531）存在窗口口径差，已如实披露。
- 演示与报告：demo_candidate_cases.md 增成功案例 4 并改写局限案例；
  diff_report.md / demo_examples.md 按 r2e 重新生成；
  audit/b10_blast_radius.csv、b10_blast_summary.json 落盘。

### B11 案名敏感性 C 口径的换名样例（人工待决）

- 触发输入：组 `ONCA|2022||onca||765`——A 口径 modal `R. v. S.M`，
  C 口径（仅 counted 投票）变 `R. v. Hertrich`（另一个案子）
- 阻塞点：counted 池票数不足时众数漂移到弱信号名字
- 现状：生产保持 A 口径；C 仅敏感性记录
- 解锁条件：回到原文判断哪个名字正确

### B7 DTC 系同档平票弃权（不阻塞；诚实少算，方向已知）

- 层/位置：merge.py `arbitrate_document` step B（R2-2 规则）
- 触发输入：`2022 DTC 5064`（DTC 同时精确命中法院代码表与汇编表 → 两种读法都
  exact 档 → 平票 → span_alternative_undecided，0 计数；round-2 全量 4,980 行此状态）
- 阻塞点：两张决策表对同一印刷码都给 exact 档且互相独立——按 R2-2 规则必须弃权，
  不许按形状顺序硬选
- 解锁条件：人工裁决 DTC 等双重身份码在两表中的正确定位（或给表行加显式
  「非法院代码/非汇编」标注），再重放
- 现状：0 计数 + 逐候选台账留痕（是弃权，不是猜测）

### B8 非序数括注拆键（R2-7，缓办）

- 触发输入：`10 Cush. (Mass.) 337` vs `10 Cush. 337`（35 个基础键）
- 阻塞点：(N.S.) 是真「新系列」，(Mass.)/(P.C.) 是法院注记，现有表无法区分二者
- 现状：拆分保持（不同键）；**其下游计数方向未确立**——既可能少算（同一引证拆两组）
  也可能多算（不同判决被并），不做方向声明；解锁条件=有来源的注记分类表

### B9 案名投票混入非 counted 候选（记录性限制）

- 触发输入：全量 466,862 投票行中 204,048（43.7%）来自非 counted 候选
- 阻塞点：投票池 = 非 rejected 且切出案名的候选（含让位/弃权者），与
  「one-mention/one-vote」的严格口径不一致
- 现状：modal 案名只作展示列，不作为身份证据；解锁条件=投票池口径决定 + 复核

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


## R2F：identifier 系统闭环（2026-09-13，任务书单轮）

**问题**：数据库/厂商标识符引证（YYYY CanLII N / CarswellJur N / DTC / WL 等）全年
弃权（span_alternative_undecided）——两读法均无表支持。r2e 实测：CanLII 1,771、
CarswellOnt 944、CarswellQue 484… 全部弃权；构成旧计数丢失桶的主体。

**决策表**：`decisions/identifier_systems.csv`（16 行，程序化生成
decisions/tools/build_identifier_systems_csv.py）：CanLII/IIJCan（verified_official：
API 文档、官方 FAQ 存档、官方博客 coverage 含 ukjcpc JCPC-加拿大上诉库说明）；
13 个 Carswell token（verified_authoritative_manual：McGill 9e §3.8+Appendix E、
Queen's McGill-10th 指南、2016 SCC 8 使用佐证）；DTC（verified_authoritative_manual：
Bluebook T2.6 + IBFD 馆藏目录实证 year_is_volume=yes；出版方更正为 CCH/Wolters
Kluwer）；WL（verified_authoritative_manual：Bluebook 10.8.1(a)；scope 非加拿大
专属→jurisdiction_scope 留空，不做来源推断）；CanLIIDocs（verified_official：
官方博客——二手评论，非判决）。键=印刷 token 逐字精确，拼写变体留空是政策。
**QCTAQ**：经研究核实为 Tribunal administratif du Québec（TAQ）的 CanLII 代码
（CanLII QC 列表页 + Wayback QCTAQ 库页 + taq.gouv.qc.ca）→ 加入
neutral_court_codes.csv（法院代码，不入 identifier 表）。

**代码**：extract neutral_bare 尾括注零宽前瞻捕获（trailing_paren，
candidates-2.0→candidates-2.1，全语料跨度集合差 0）；classify identifier 分支
（kind=identifier/jurisdiction=scope/细分仅限尾括注归一后精确命中法院代码、
CanLIIDocs 行级拒绝 not_a_decision 并传播到同引证卷读法）；decide 身份规则
（identifier 键不做 typo 塌缩、同系统不共组（单元指派守卫+pending 守卫）、
跨系统仅经既有共引连接 basis=cocitation、main 断言同系统 identifier 每组至多
一键）；scope 表加 CanLII/Carswell（key_type=identifier_system，origin=CA，
basis=court_scope_rule）。

**测试**：R2F a-j 先行失败后转绿；test_candidates 170→**195**；120/120、selftest、
fixture、--golden 全保持。

**运行**：`data/run_20260913_r2g/`（complete，指纹一致，10 步）。

**验证数字（对照 r2e，仪器 r2f_verify.py + r2_regression_join.py）**：
1. 每 token：CanLII 1,771 → counted 1,768 + rejected 19 + 弃权余 18；
   CarswellOnt 944 → counted 976（含孪生）+ unsupported 948；… DTC 33 → 年读法
   counted；CanLIIDocs 10 → rejected；QCTAQ 31 → counted（新法院代码）。
2. 爆半径：9,040 条状态变化 = identifier 相关 **8,952**（CanLII/Carswell/DTC/
   QCTAQ 候选及其孪生、B10/D3 容器）+ (ii) 其他 **88**（31=QCTAQ 经新增法院代码
   计数〔有案可查〕；25=碎片经 identifier 配对者获得支持的 D3 作废；32=同跨度
   卷孪生让位）——逐行见 audit/r2f_status_changes.csv。
3. 跨度集合恒等：r2e=r2f=2,027,876，差 **0**。
4. 旧 counted 行：518,480 → 仍计 **516,442** / 重叠 872 / 丢失 1,166 / 未枚举 0
   ——丢失桶中 identifier 份额清零（余为公司碎片/月份词/WL 39）；
   old-supported lost = **27**（≤61 红线，较 r2e 的 61 下降）。
5. 组：173,512 → 177,111（identifier 键成为独立身份组）；同系统断言违规 **0**。
6. 来源：组/边 DOMESTIC_CA 53,963 → **55,237**（identifier 组获 scope:CanLII
   证据 1,192 组 DOMESTIC_CA，basis=court_scope_rule）；FOREIGN **384 不变**；
   UNDETERMINED → 277,835（细分与弃权的诚实位移）。
7. kept 组（dd≥5）：8,582 → **8,586**（+4：identifier 组越过门槛）。
8. 一致性：legacy 缺失 0 / 行来源不一致 0 / 多国别非 CONFLICT 0。
9. 追溯：`ONCA:10076:8322:8339:shape_neutral_bare`（2001 CanLII 24079，counted，
   细分 ONCA）等已验证。

**账本状态（identifier token 收口）**：≥5 提名的 token 全部落 (1) verified 行
端到端处理；拼写变体（CarswellNlfd 等）= 政策性不匹配（表键精确）；月份词/普通
名词垃圾照旧弃权（非 identifier，正确弃权）。无 (3) 类「源不可达」条目。


### R2F 补充：61 条 old-supported lost 的账目订正（评审要求）

r2e 的 61 条 old-supported lost 中：**60 条原样带入**（其构成：重叠未决 21 +
同跨度孪生 39，与 B10/D3 修复无关），**仅 1 条是 r2e 新增**——
`(2001), 2001 DTC 295`（B10 容器作废后其 DTC 孪生按 B7 弃权；R2F 落地后该
DTC 引证已按年读法 counted，r2g lost_by_token 中 dtc 已消失）。r2g 的
old-supported lost = **27**（较红线 61 大幅下降）。


## R2F 收尾（2026-09-13，评审四项发现全修，commit 6c69ff6 + r2i）

### 评审发现与实测确认

1. **(a) r2g 用了 8a8e324 的 classify.py**：实测确认——r2g manifest 的 classify sha =
   977fee06（= 8a8e324 版本），HEAD 的 b9f53b33（含 CanLIIDocs 拒绝传播到卷孪生）
   **未进入 r2g**。后果：r2g 里 10 条 CanLIIDocs 卷/年读法孪生仍被 counted
   （vol_abbr_page 9 + year_vol_page 1）。原报告「指纹一致 / r2g 已验证孪生传播」
   对 HEAD 而言不成立——**已收回**。
2. **(b) USAGE.md 少算清单损坏**：identifier 段出现两次（item 0 与 3b），3b 的第二份
   覆盖了 item 4 的标题「抽取层的 1.2% 少算（PROBLEMS #63）」→ 98.80% 段落成了无头段。
   **已修**：96b3665 的 items 1–5 逐字节恢复、identifier 只保留一条（item 6，附评审
   订正数字）、98.80% 口径警示段完整保留。
3. **(c) WL 弃权根因**：identifier_systems 表行 verified 但 jurisdiction_scope 为空
   → classify 写 jurisdiction="" → merge.support_grade 把空法域当「无表支持」降为
   0 档 → 与卷读法同档平票弃权。**已修**：support_grade 对 citation_kind=identifier
   且 lookup_mode=exact 直接给档 2（表支持与法域栏解耦）。
4. **(d) 报告数字错误**：跨度集合正确值 = **1,013,948**（verify 脚本此前双循环重复
   计数报 2,027,876——脚本 bug 已修）；per-token 数字已按 shape_neutral_bare 口径
   订正（CanLII 1,763 → counted 1,760 + rejected 3；CarswellOnt 944 → counted 943 +
   rejected 1）。

### WL 修复（先测后修）

- 失败测试 `test_wl_identifier_counted_despite_blank_scope`：修复前 WL identifier
  读法弃权（AssertionError: counted 失败）；修复后 counted（键 2005||wl||2709572）、
  jurisdiction 留空、卷读法让位、origin UNDETERMINED（WL 无 scope 行）。

### 重跑与差异（r2g → r2i）

- `data/run_20260913_r2i/`（complete；**独立指纹核验**：_w10.py 对 HEAD 逐文件哈希
  21 个文件 0 不匹配——不依赖 run 自述）。目录名用 r2i 而非任务书的 r2h：
  data/run_20260913_r2h 已被上一轮的中间 run 占用（非空），按「新空目录」规则顺延。
- 爆半径（vs r2g）：**89 条变化，全部 (i)，(ii) 其他 = 0**——
  39 WL span_alt→counted（修复生效）、39 WL span_alt→unsupported（卷孪生让位）、
  10 CanLIIDocs counted→rejected（孪生拒绝生效）、1 CanLIIDocs contained→rejected。
- 旧 counted 行（vs r2g）：518,480 → 仍计 516,480 / 重叠 863 / 丢失 1,137 / 未枚举 0；
  old-supported lost = **27**（≤27 红线持平——CanLIIDocs 孪生与 WL 均不计入，因
  它们的旧状态是弃权而非 supported counted）。
- 组 177,136（+25：WL 组分出）；kept 组 8,586（不变）；边 333,287（UNDETERMINED
  277,866 / DOMESTIC_CA 55,237 / FOREIGN 384 不变）。
- 一致性：0/0/0。

### B10(b)/(c) 断言替换的来源记录

commit 8a8e324 替换了 test_b10_year_reread_as_vol 中 (b)(c) 两段断言（从
span_alternative_undecided 弃权改为中性 counted + 卷读法让位）。这不是隐蔽改动：
R2F 任务书明确要求 identifier 表落地后「the contained pair then follows existing
rules; assert whatever those rules produce」——identifier 表使中性读法获得 exact
表支持，既有支持分级下胜出是规则输出，弃权旧期望与之矛盾。docstring 内有完整
的前后对照与理由。


## Round 3（2026-09-13 起）：汇编式引证来源地继承 + 身份拆分修复

**授权文本**：用户下发的「来源地继承与身份拆分修复计划（修订版）」（取代上一轮审计产出的
同名计划；保留其 M1/M2/M3 测量设计、根因诊断、Stage 3/4 结构，并修正两处设计缺陷：
decide 不得读 classify 的 jurisdiction 作来源地键；M1 必须按 identity_basis 拆分为
M1a/M1b）。本轮纪律：**Stage 0 四个数字落账之前不改任何管线代码**。本文件只记事实，
不作验收声明。

### R3-0 仪器、口径与可重放性

| 项 | 值 |
|---|---|
| 仪器 | `implementation/coverage_metric.py`（只读：不写 `decisions/`、不改管线、不读 `PROBLEMS.md`） |
| 基线 run | `data/run_20260913_r2i/`（manifest status=complete，输入指纹 `6deba00b…`） |
| 输出 | `data/coverage_out/stage0_r2i.json`（`data/` 已 gitignore）+ stdout 摘要 |
| 重放 | `python implementation/coverage_metric.py`（纯流式扫描，约 3 分钟） |
| 合格 identity_basis | **从 `pipeline/decide.py` import `ELIGIBLE_BASES`**，不在仪器里硬编码 |

辅助探针（一次性、只读，供本节点各个数字复算；都在 `implementation/`）：
`_probe_mentions.py`（仲裁状态/种类/法域解析率）、`_probe_tables.py`（两张决策表结构）、
`_probe_schemas.py`（各层列名）、`_probe_stage0.py` / `_probe_struct.py`（Stage 0 JSON 明细）、
`_probe_reconcile.py`（简报数字对账）、`_probe_edges.py`（独立复算边计数）。

口径（三处已写进 JSON 的 `*_note` 键，随 JSON 一同留存）：

- 「提及」= `merge_out/<court>/mentions_candidates.csv` 里 `arbitration_status=counted` 的行。
  自引（self_citation_row）、被包含的并存读法（alternative_contained）、被拒、未决重叠
  （overlap_undecided / span_alternative_undecided）**均不计**——与生产计数口径一致。
- 「成员行」= `decide_out/cross_court/decided.csv` 的一行，键 `(court, merge_key)`。
  `M1a_member_rows_unknown_in_decided = 0`：连接无缺失。
- 「L2 法域已解析」= 分类层 `jurisdiction` 非空且 ≠ `UNSUPPORTED`（见 R3-3 第 2 条的代理口径说明）。

**基线数字全部独立复算**（不引用 run 自述）：

| 量 | 值 |
|---|---:|
| `citation_edges.csv` 总边 | **333,487** = UNDETERMINED 277,866 / DOMESTIC_CA 55,237 / FOREIGN **384** |
| 边支持分级 | supported 308,026 / heuristic_only 25,461；tentative 台账 4,110 |
| 组 | 177,136（UNDETERMINED 166,474 / DETERMINED 10,662） |
| kept 组（dd≥5） | 8,586（UNDETERMINED 5,800 / DOMESTIC_CA 2,784 / FOREIGN 2） |

> **记录订正**：本文件 R2F 收尾一节的行内数字「边 333,287」与 run 自身 manifest
> （`edges_total: 333487`）及本次逐行计数（333,487）不一致，差 200。以 manifest +
> 独立计数为准，那处是笔误。（`Get-Content | Measure-Object -Line` 报 336,807 行，
> 是因字段内含换行；CSV 解析计数与 manifest 一致。）

### R3-1 M1a / M1b（计划 §3）

| 量 | 提及数 | 成员行数 |
|---|---:|---:|
| **M1a**（counted + `citation_kind=reporter` + L2 法域已解析） | **379,472** | 129,819 |
| **M1b**（M1a 再限定成员行 `identity_basis ∈ ELIGIBLE_BASES`） | **295,177** | 115,481 |
| 其中·加拿大汇编（L2 法域 ∈ CA/省） | 321,440 | — |
| 其中·外国汇编 | 58,032 | — |

M1a 覆盖 194 个不同汇编缩写。M1b/M1a = 77.8%（KEPT 口径：M1a 与 M1b 的差全部来自
identity_basis 闸门）。

**M1b 分层（提及数）**——列为组当前来源地状态：

| identity_basis | 合格? | 组 DETERMINED | 组 UNDETERMINED | 组 CONFLICT |
|---|---|---:|---:|---:|
| singleton | ✔ | 2,956 | 229,799 | 0 |
| anchor | ✔ | 0 | 57,033 | 0 |
| same_citation | ✔ | 76 | 5,313 | 0 |
| anchor_variant_bilingual | ✔ | 0 | 0 | 0 |
| name_year | ✘ | 42,862 | 35,111 | 0 |
| cocitation | ✘ | 6,094 | 181 | 0 |
| unanchored | ✘ | 0 | 47 | 0 |
| **合计** | | **51,988** | **327,484** | **0** |

读法：`DETERMINED` 列的 51,988 条是**冗余**（组已由别的成员定了来源地，新规则即使命中
也不改结论）；`UNDETERMINED` 列里 **292,145 条**落在合格 basis 上 = 真正可能兑现的净新增
池；`name_year 35,111 + cocitation 181 + unanchored 47`（合计 35,339 条）落在不合格 basis 上
= 被身份基础闸门挡住的池。

### R3-2 净新增组级覆盖（头条预测增益，计划 §3 要求）

以**组**为单位（不是提及百分比）：

| 量 | 组数 |
|---|---:|
| 当前 UNDETERMINED 且在合格成员行上带 ≥1 条 M1a 提及（= **净新增上限**） | **113,432** |
| ├ 国别单一、不会产生 CONFLICT（干净净新增） | 113,432 |
| ├ 合格成员提及跨 ≥2 国（将变 CONFLICT，**实际为 0**） | 0 |
| ├ 归属加拿大来源地（DOMESTIC_CA 方向） | **90,246** |
| └ 归属外国来源地（FOREIGN 方向） | **23,186** |
| kept 口径（dd≥5）净新增 | **4,495**（加 3,853 / 外 642） |

**净新增组按缩写（组数，前 20）**：scr 11,610、dlr 9,148、or 9,027、ccc 8,865、oj 4,374、
wwr 3,359、oac 2,558、canscr 2,307、**ac 2,196**、cr 1,917、aller 1,348、bclr 1,327、
ar 1,219、rfl 1,211、scca 1,189、us 1,186、f 1,137、chd 1,130、cbr 1,112、kb 1,067。

对照基线：现有 DOMESTIC_CA 组 10,336、FOREIGN 组 326。即在「Stage 1 表能把相关缩写全部
核实为排他」的**上限假设**下，国内组级覆盖约 10x、外国组级覆盖约 70x。**这是上限，不是
预测**：`ac`（2,196 组）按计划 §0 的根因诊断应判 `mixed`（A.C. 同卷混印上院与枢密院案），
不写行 → 该 2,196 组不兑现；Stage 1 研究覆盖面与排他性判定的严格程度决定实际兑现比例。

**反向风险（本计划未要求、我加测）**：当前**已 DETERMINED** 的组里，若有合格成员带的
M1a 提及其代理国别 ≠ 组结论国别，新证据会把组从 DETERMINED 打成 CONFLICT（净损失）。
实测 **211 组**，全部集中在 `ac`（3,009 条提及）与 `aller`（23 条）。ac 若按根因诊断判
`mixed` 不写行 → 该风险来源消失；`aller`（All England Law Reports）需在 Stage 1 反例
核查中专门验证是否含加拿大/枢密院案。

### R3-3 被挡住的池与口径缺口（计划 §2 的「阶段 3.5」问题，不另建阶段）

| 量 | 组数 |
|---|---:|
| UNDETERMINED 且带 M1a 提及（任意 basis） | 117,999 |
| 其中合格 basis 可兑现（= R3-2 净新增） | 113,432 |
| 其中**只**落在不合格 basis（净新增拿不到） | **4,567** |

被挡住的 4,567 组的阻挡 basis 构成：`name_year` **4,477**、`cocitation` 81、`unanchored` 9。
按计划 §2 的口径要求（「多少被缺案名挡、多少被缺中立锚挡」）：**97.9% 是缺可审计身份锚
（只能靠案名+年份启发式拼组）**，共引挡住的只有 81 组、无锚 9 组。结论：这一池的解锁
不是「共引传播放宽」问题，而是**案名抽取/中立锚补全**问题——属另一个工作流，本轮不做。

**与计划正文不符的三处（我按代码/实测处置，逐条留痕）**：

1. **合格 identity_basis 集合**：计划 §0 与 §2 写「anchor / anchor_variant / name_year /
   singleton 合格，cocitation / unanchored 只审计」。实测生产规则
   `ELIGIBLE_BASES = (anchor, singleton, same_citation, anchor_variant_bilingual)`：
   **`name_year` 不合格**，而 **`same_citation` 合格**（计划两处都漏了它）。
   处置：以代码为准（仪器直接 import）。若按计划文本把 name_year 也算合格，M1b 会多
   77,973 条提及、净新增会再多约 4,477 组——但那是**放宽**身份授权，与计划 §0「组聚合
   保持不变」的自我要求矛盾，故不采用。
2. **M1a 的「L2 法域已解析」是代理口径**：新规则按 `nk(印刷缩写)` 自查表，**不依赖**
   classify 的法域字段，所以「法域已解析」会漏掉规则其实能救的提及。实测被漏掉
   **44,259 条** counted 汇编提及（SCC 38,337 / ONCA 5,922；提及数可观且有意义的如
   `qb` 878、`nfldpeir` 871、`kb` 344——恰是同形异义/多行汇编）。处置：M1a 按计划口径
   报 379,472，**另报**全量口径 423,731（= counted + reporter，不要求法域已解析），
   两者都留在 JSON 里，不改计划的名义数字。
3. **「≥2 行命中一律 UNDETERMINED」的代价**：M4 实测有 **1,286 条提及**落在「命中多行
   但各行国别一致」的区间（`pd` 316——两行同为 GB；`nfldpeir` 871——两行同为 CA 省；
   `cp` 98；其余零散）。这些情形里**国别没有歧义**，只有细分/窗口归属有歧义，按计划
   字面会白丢 1,286 条。我的判断：改为「命中多行且**国别一致** → 取该国、细分留空」，
   并把「多行命中」记进审计字段；计划 §1 的强制测试（GB/QC 异国重叠 → UNDETERMINED +
   `exclusive_reporter_scope_ambiguous`）**不受影响**，因为那测的是异国重叠。
   处置：Stage 2 按修正后的规则实现，此处先落账待用户复核（见 R3-7 P2′）。

### R3-4 与简报数字的对账（约束九）

| 简报数字 | 复现情况 |
|---|---|
| 「428,571 条加拿大汇编提及，72% UNDETERMINED」 | **未复现**。r2i 实测：counted 汇编提及（全部法域）**423,731**；其中加拿大汇编（L2 法域 ∈ CA/省）**321,440**，其组状态 UNDETERMINED 占 **84.9%**；不限仲裁状态的全量加拿大汇编提及 547,953，UNDETERMINED 占 **68.6%**。没有任何口径落在 428,571；最接近的是 423,731（差 4,840，1.1%）。可能是上一轮审计用了不同 run 或略不同的过滤，**本文件不沿用 428,571**，以 423,731 / 321,440 为准 |
| 「384 FOREIGN 边」 | **复现**（`edges/foreign_edges.csv` 384 行；`citation_edges.csv` FOREIGN 384） |
| 计划 §7「上诉链合并 19 组」 | **本轮不可测**（无上诉链数据），照抄计划、标未核 |
| 计划 §7「年读作卷 188 条提及」 | **未复现**。r2i 实测 `structural_conflict=year_reread_as_vol` 的提及 **92 条**（全部仲裁状态；其中 counted 0 条——结构冲突提及全部被消解为让位/作废）；分类层 `year_vol_ambiguity_unresolved` SCC 55,881 / 见 manifest。口径不明，标未核 |

### R3-5 M2：top 30 汇编缩写的 L2 法域分布

population = counted + `citation_kind=reporter`，含未解析（`homo` = `reporter_jurisdiction.csv`
里 `nk(abbreviation)` 相同的行数，>1 即同形异义）：

| # | abbr | 提及 | homo | 法域分布 |
|---:|---|---:|---:|---|
| 1 | scr | 145,650 | 1 | CA 145,650 |
| 2 | ccc | 30,376 | 1 | CA 30,376 |
| 3 | or | 29,593 | 1 | ON 29,593 |
| 4 | dlr | 18,465 | 1 | CA 18,465 |
| 5 | ac | 15,467 | 1 | GB 15,467 |
| 6 | canscr | 7,082 | 1 | CA 7,082 |
| 7 | oj | 6,630 | 1 | ON 6,630 |
| 8 | wwr | 6,110 | 1 | CA 6,110 |
| 9 | oac | 5,645 | 1 | ON 5,645 |
| 10 | scca | 4,688 | 1 | CA 4,688 |
| 11 | cr | 3,977 | 1 | CA 3,977 |
| 12 | aller | 3,626 | 1 | GB 3,626 |
| 13 | appcas | 3,274 | 1 | GB 3,274 |
| 14 | us | 3,170 | 1 | US 3,170 |
| 15 | **kb** | 3,079 | **3** | GB 2,582 / UNSUPPORTED 344 / QC 153 |
| 16 | bclr | 2,746 | 1 | BC 2,746 |
| 17 | **qb** | 2,602 | **22** | GB 1,715 / UNSUPPORTED 878 / QC 9 |
| 18 | fc | 2,492 | 1 | CA 2,492 |
| 19 | rfl | 2,255 | 1 | CA 2,255 |
| 20 | rjq | 2,242 | 1 | QC 2,242 |
| 21 | ar | 2,234 | 1 | AB 2,234 |
| 22 | chd | 2,020 | 1 | GB 2,020 |
| 23 | er | 1,950 | 1 | GB 1,950 |
| 24 | ch | 1,892 | 1 | GB 1,892 |
| 25 | altalr | 1,862 | 1 | AB 1,862 |
| 26 | cbr | 1,836 | 1 | CA 1,836 |
| 27 | excr | 1,772 | 1 | CA 1,772 |
| 28 | qbd | 1,646 | 1 | GB 1,646 |
| 29 | crr | 1,592 | 1 | CA 1,592 |
| 30 | manr | 1,457 | 1 | MB 1,457 |

同形异义（表内 >1 行）共 10 个缩写：kb(3)、qb(22)、sc(3)、clr(3)、alr(3)、p(2)、pd(2)、
wlr(2)、cp(2)、nfldpeir(2)。**除这 10 个之外，top 30 全是单行表项**——即 Stage 1 的研究
主要工作量在「核实排他性」，不在「切分同形异义」。

### R3-6 M3：无年变体族规模（Stage 3 身份修复标的）

族 = `(court, nk(abbr), series, vol, page)`（即 merge_key 去掉 year 槽）。行数基数
191,681（SCC 125,013 / ONCA 67,668）。

| 量 | 族数 | occurrence | dd |
|---|---:|---:|---:|
| 族总数 | 157,078 | | |
| 单行族 | 136,363 | | |
| 多行族 | **20,715** | | |
| ├ **unique-year merge**（恰 1 个非空年 + ≥1 个空年槽）= Stage 3 合并标的 | **7,581** | 55,638 | 35,471 |
| └ **multi-year abstain**（≥2 个非空年）= 设计规定弃权 | **13,130** | 217,102 | 142,082 |
| &nbsp;&nbsp;├ 其中含空年变体（真·碎片嫌疑） | 1,304 | 66,472 | 33,162 |
| &nbsp;&nbsp;└ 其中不含空年变体（同名 vol/page 跨年重复，typical year_volume 形态） | 11,826 | 150,630 | 108,920 |
| 异常：多行族但只有一个非空年且无空年槽 | 2 | — | — |
| 异常：多行族但全为空年槽 | 2 | — | — |

- unique-year merge 的合并动作 = **7,584 行并入**（7,581 族 × 平均 1.0004 行）。
- unique-year 标的按缩写（族数）：scr 1,402、ccc 782、dlr 509、or 457、canscr 406、f 391、
  appcas 147、chd 131、oac 123、qbd 115、qrkb 114、p 97、ontlr 96、wwr 85、fsupp 84；
  年槽丢失最严重的是 **S.C.R.（1,402 族）**——与「`[1995] 2 S.C.R. 3` 与 `2 S.C.R. 3`
  两种写法」的预期一致。
- abstain 桶按缩写（族数）：scr 2,458、onsc 1,990、onca 1,292、oj 995、ac 554、bcca 501、
  scca 481…——`onsc/onca/bcca/abca/qcca` 类是**中立引用形状**，其「同名 vol/page 跨年」
  多为真不同案，弃权正确。
- 2 个「同非空年多行」异常族：`SCC lrex 1/54/1865`、`SCC lrqb 10/378/1875`——两行的
  abbr 槽大小写不同（`nk()` 折叠后才同族），是**键的印刷形不一致**造成的极小残留，登记。
- **口径限制**：Stage 1 才会给出 `volume_system ∈ {year_volume, continuous}`；本表按
  「有没有空年变体」分流，是对该列的结构代理，不是该列本身。

### R3-7 M4：同形异义汇编在**未核实区间**下的重叠规模（规划用，**不是生产数字**）

口径：取现有 `reporter_jurisdiction.csv`（196 行，**100% confidence=estimated /
verification_level=name_inference**）的多行缩写，用**维度式包含**判定（仅当引证与表行
该维度都有值时才可判、才可否决；全不可比的行=无约束，命中一切）。population = counted
汇编提及（不要求 L2 已解析）。

| 量 | 组合数 | 提及数 |
|---|---:|---:|
| 唯一命中（可定案） | 1,168 | 6,583 |
| 多行命中（原计划口径=UNDETERMINED） | 675 | 3,197 |
| ├ 命中多行但**国别一致**（按 R3-3 第 3 条修正后可定国别） | 381 | 1,286 |
| └ 命中多行且**国别不同**（真·歧义，应 UNDETERMINED） | 294 | 1,911 |
| 零命中（窗口外） | 84 | 151 |
| 合计 | 1,927 | 9,931 |

逐缩写（`unc` = 表内无区间的行数；`uniq`/`amb同`/`amb异` = 组合数）：

| abbr | 表行 | 候选来源 | unc | 唯一 | 歧义(同国) | 歧义(异国) | 窗口外 |
|---|---:|---|---:|---:|---:|---:|---:|
| kb | 3 | GB, QC | 0 | 180 | 0 | 20 | 16 |
| qb | 22 | GB, QC | 0 | 146 | 0 | 32 | 28 |
| sc | 3 | QC, GB | 0 | 56 | 0 | 38 | 28 |
| cp | 3 | GB, QC | 0 | 25 | 9 | 0 | 5 |
| clr | 3 | AU, CA | 0 | 273 | 1 | 73 | 1 |
| alr | 3 | AU, US | 0 | 22 | 0 | 71 | 1 |
| p | 2 | GB, US | 0 | 292 | 0 | 57 | 4 |
| wlr | 2 | CA, GB | 0 | 174 | 0 | 3 | 1 |
| pd | 2 | GB, GB | 2 | 0 | 54 | 0 | 0 |
| nfldpeir | 2 | NL, PE | 2 | 0 | 317 | 0 | 0 |

关键读数：
- **K.B. 2,723 / 3,079 条提及可唯一判定（88%）**，歧义 328 条；**Q.B. 1,723 / 2,602（66%）**，
  歧义 826 条。这与 `audit/findings/disambiguation_report.md` 用**完全独立的方法**
  （卷/年区间 vs 系列前缀标注，`qb` 判不出 899）得到的量级一致——仪器互相印证。
- `pd`（2 行同为 GB，均无区间）与 `nfldpeir`（2 行同为 CA 省，均无区间）是**表侧退化行**
  （没有区间 → 无约束 → 命中一切）：1,187 条提及在计划字面下白丢，是 R3-3 第 3 条修正
  的主要受益者。
- 明确标注：本表**不是**生产预期。Stage 1 会用真实来源重写区间，届时 `kb/qb/sc/cp/clr/
  alr/p/wlr` 的窗口会变；此处只用于校准 Stage 1 的研究工作量与「即便研究完成也仍有
  一批 UNDETERMINED 残差」的预期。

### R3-8 账本（Round 3）

**B12（承接上一轮计划，未核）**：上诉链合并 19 组。本轮无上诉链数据，未测；照抄计划
数字，标「未核」。

**B13（承接上一轮计划，口径不符）**：年读作卷 188 条提及。r2i 实测
`structural_conflict=year_reread_as_vol` 提及 **92 条**（counted 0 条），分类层
`year_vol_ambiguity_unresolved` SCC 55,881。188 的口径无从复现，以 92 / 55,881 为准，
标「口径待核」。

**B14（本轮新增，计划 §2 的决策点）**：M1a/M1b 缺口与共引阻断。
- M1a 379,472 → M1b 295,177（提及），净新增组上限 **113,432**（kept 4,495）。
- **被身份基础闸门挡住的只有 4,567 组**，其中 `name_year` 4,477（97.9%）、`cocitation` 81、
  `unanchored` 9。→ **共引阻断不是瓶颈**，瓶颈是「案名+年份」启发式不可作为组级来源地
  依据。若要提高上限，正确做法是补中立锚/案名抽取（另立工作流），**不是**放宽共引传播。
  按计划 §2 要求：本轮**不**预建传播放宽阶段，此数字交用户决策。

**B15（本轮新增）**：M3 的 abstain 桶规模。13,130 个多行族、142,082 dd 在「≥2 个非空年」
时按设计弃权——其中 1,304 族（33,162 dd）**含空年变体**，是「年槽丢失 + 另一个错误年」
的碎片嫌疑，按计划规定弃权（保守方向）。登记为已知残差，不在本轮解锁。

**B16（本轮新增）**：同形异义真歧义残差。按未核实区间估计 294 个 (vol,year) 组合 /
1,911 条提及落在**异国重叠**区（K.B. 328 条、Q.B. 826 条、S.C. 97 条为主）。这批在
Stage 2 后应为 `origin_basis=exclusive_reporter_scope_ambiguous`，Stage 4 需按计划 §8.4
单独计数与给规模，不得折进普通 UNDETERMINED。

**B17（本轮新增，记录性）**：`pd` / `nfldpeir` 的表侧退化行（有行无区间）与
`lrex/lrqb` 的键印刷形大小写不一致（各 2 族）。量小，登记待 Stage 1/3 时顺手处理。

### R3-9 待用户签收（Stage 0 闸门，计划 §3/§4）

Stage 0 到此为止，**未动任何管线代码**。以下决策点需签收后才进 Stage 1：

- **P1**：排他汇编的来源地是正面证据；新规则自查表、**完全不读** classify 的
  `jurisdiction`；查不到或多行异国重叠 → UNDETERMINED。方向永远是「多留未知」。
- **P2**：来源地 basis 优先级 `case_record > neutral-code scope > exclusive_statute 汇编
  > exclusive_publisher 汇编`；`exclusive_publisher` 行必须记录反例搜寻过程。
- **P2′（我加的修正，计划未写）**：多行命中但**国别一致**时取该国、细分留空，并记审计
  字段——代价对比见 R3-3 第 3 条（1,286 条提及）。异国重叠仍 UNDETERMINED +
  `exclusive_reporter_scope_ambiguous`（计划 §1 的强制测试不受影响）。
- **P3**：`volume_system=continuous` 结构性零化 year 槽（表驱动、按 run）；`year_volume`
  按 run 的「族内唯一非空年」合并，≥2 年弃权、不跨 run 持久化。
- **规模决策（计划 §3 要求）**：净新增上限 113,432 组（加拿大向 90,246 / 外国向 23,186；
  kept 4,495），远大于现有 FOREIGN 384 边。**上限假设是 Stage 1 能把相关缩写核实为排他**；
  实际兑现比例取决于研究覆盖与反例核查的严格程度。请裁决：(a) 按原计划推进 Stage 1
  （三个只读研究子代理，按提及量排序，同时做排他性核查与反例搜寻）；(b) 先补
  identity_basis 缺口（B14 的 4,477 组案名/锚问题）再回来；(c) 缩范围只做 top-N 缩写。

### R3-10 用户签收（2026-09-13）

三项均按推荐通过：**Stage 1 按原计划推进**（三个只读研究子代理）；**接受 P2′**（多行命中
但国别一致 → 取该国、细分留空、记审计字段；异国重叠仍 UNDETERMINED + ambiguous，
计划 §1 的强制测试不受影响）；**P1/P2/P3 全部生效**，其中合格 identity_basis **以代码为准**
（`pipeline/decide.py` 的 `ELIGIBLE_BASES`：`name_year` 不合格、`same_citation` 合格）。

### R3-11 Stage 1 目标清单（研究输入，`audit/`）

仪器：`audit/stage1_targets.py`（审计环；只读生产产出，产出提案）。输出：
`audit/findings/r3_stage1_targets_{canadian,british,other}.md` + `r3_stage1_targets.json`
（tier1–2 全字段；tier3 压缩字段）。按 **counted 汇编提及量**排序并附**语料实测的
vol/年区间与高频组合**（研究者据此知道哪段区间真正要紧）。

| 组 | 目标数 | tier1 | counted 提及 | 可带来净新增组 |
|---|---:|---:|---:|---:|
| 加拿大/省级 | 106 | 16 | 320,930 | 89,901 |
| 英国 | 73 | 8 | 51,160 | 18,550 |
| 美国及其他 | 5,621（其中 tier1–2 仅 6） | 1 | 51,641 | 4,981 |

任务书对每个缩写要求两件事：**排他性溯源**（`exclusive_statute`/`exclusive_publisher`/
`mixed`）与**反例搜寻**（`exclusive_publisher` 强制）；并新增两个「记录但不写行」的档：
`scope_evidence_third_party_only`（只找到第三方手册——P2 只认两档，但出处与反例结果先
记下来，供以后决定是否增设第三档）、`not_a_reporter`（期刊/噪声）。三个子代理已启动，
产出写 `audit/findings/r3_reporter_origin_{canadian,british,other}.md`，**不得改
`decisions/` 与 `pipeline/`**；表由人按 findings 手工整理（`audit/README.md` 的膜规则）。

### R3-12 Stage 2：`decide.py` 排他汇编来源地（test-first）

**实现**（`pipeline/decide.py`）：

- `load_reporter_origin()`：读 `decisions/reporter_origin_scope.csv`，键 = `nk(printed_abbreviation)`；
  只有 `verification_status ∈ {verified_exclusive_statute, verified_exclusive_publisher}`
  的行参与推断，`verified_mixed` 等只作档案。
- `_reporter_origin(row, reporter_idx, stats)`：**自查表，不读 classify 的 `jurisdiction`**（P1）。
  窗口匹配即消歧：恰一行命中 → 该行来源地，`basis=exclusive_reporter_scope`；
  ≥2 行命中且国别一致 → 取该国、细分仅一致时取（P2′）；≥2 行且**国别不同** →
  UNDETERMINED 且审计列 `member_origin_ambiguous_basis=exclusive_reporter_scope_ambiguous`；
  零行命中 → 普通 UNDETERMINED。**白名单在规则内部再筛一遍**，不只依赖 loader。
- 优先级（P2）：`case_record > court_scope_rule > 汇编排他`。前两者与第三者在
  **结构上互斥**（`citation_kind` 单一取值：neutral/identifier 走 scope，reporter 走汇编表），
  所以「scope 与汇编范围同时适用」不会发生；两档汇编排他性只在**同一行有多条命中行且
  国别一致**时决定用哪条证据，**绝不裁决国别冲突**。
- 新列：`member_origin_exclusivity`（该证据行的档位）、`member_origin_ambiguous_basis`
  （审计，与「无证据」分开记）。跨法院轮沿用院内轮（`setdefault` 兜底）。

**两处与计划字面的偏离（我的判断，登记待复核）**：

1. **basis 值保持 `exclusive_reporter_scope`**（计划 §1 的强制测试就是这么命名的），
   档位另放 `member_origin_exclusivity` 列，而不把档位烘进 basis 字符串
   （否则 `(1930), 45 K.B. 129 → basis=exclusive_reporter_scope` 这条测试按字面就红了）。
2. **`series` 槽不作为匹配维度**。理由：series 只会**增加**命中行，而增加命中只可能把
   「唯一命中」推向「多行命中」（国别不一致 → UNDETERMINED），**不会凭空造出一个国别**——
   方向与 P1「宁可多留未知」一致；同时避免为 D.L.R./C.C.C./O.R./W.W.R. 这类多系列汇编
   建一张「每系列一行」的窗口矩阵。代价：多系列汇编若只给某个系列的 vol 区间，
   其它系列的引用会落窗口外 → UNDETERMINED（诚实少算，不是错判）。整理表时对
   `volume_system=continuous` 的多系列汇编**优先给年区间**（卷号每系列从 1 重起，
   年区间才是跨系列有效的窗口）。

**测试**（`pipeline/tests/test_candidates.py`，新增 13 项）：§1 的**重叠独立性**测试
（GB-K.B. 与 QC-K.B. 窗口故意重叠 → UNDETERMINED + ambiguous；把 classify 的 jurisdiction
分别喂 GB 与 QC，decide 的观测字段**逐字段相同**——证明真独立）、唯一命中且 classify 法域
**故意喂错**仍取窗口来源地、窗口外/无表行 → 普通 UNDETERMINED（ambiguous 列空）、
非 reporter 解析不走该规则、case_record 优先、两档 statute>publisher（含档位不一致时
**不得**破国别平局）、P2′ 同国多行、表行顺序不变性、未核实/`verified_mixed` 行不参与，
以及**依赖 Stage 1 真实表**的一项（`[1995] 2 S.C.R. 3`→CA、`(1930), 45 K.B. 129`→CA 非
ambiguous、`[1932] A.C. 562`→UNDETERMINED、表行纪律：每行 ≥1 个窗口 + origin_country +
exclusivity + `exclusive_publisher` 必带反例搜寻 + `source`/`source_locator` + 键口径一致）。

**当前状态**：表未落地，故「真实表」那一项**是红的**（test-first 的预期状态，断言信息
写明「Stage 1 尚未落地」）；其余 65 项测试 / **238 条断言全绿**，`test_layers.py`
120 条、`run_regression.py --selftest`、`extract.py --fixture-check` 全部 exit 0。

### R3-13 Stage 3：身份修复（表驱动，test-first）

**架构约束**：`merge.py` 明确**不加载 `decisions/` 下任何文件**（层界）。因此
`volume_system` 由**分类层**按 `reporter_origin_scope.csv` 盖章到行字段上
（`classify.load_volume_systems()`：只收已核实行；同一缩写多行给出**不一致**的
volume_system → 该缩写不给值，保守），归并层只读行字段。归并层的两条修复
（`merge.apply_reporter_identity_fixes`，在逐判决仲裁**之前**跑）：

- **A. `continuous`（卷号跨年连续，如 D.L.R.）**：年槽不是身份的一部分 →
  **结构性零化年槽**。`34 D.L.R. (2d) 451` 与 `(1970) 34 D.L.R. (2d) 451` 自此同键。
  与法域消歧无关，单法域汇编同样适用。
- **B. `year_volume` 且年槽为空**：按族 `(vol, abbr, series, page)` 统计**本 run 内**
  出现过的非空年——恰一个 → 补为空年行的年（同族合并）；**≥2 个 → 弃权**（不猜）。
  **按 run 计算、不持久化**。
- 未盖 `volume_system` 的行**一律不动**（不猜、不硬编码清单）。记账：
  `reporter_identity_year_zeroed_rows` / `_filled_rows` / `_fill_families` /
  `_fill_families_abstained` 进 merge manifest。
- **现状核对**：表未落地时 `volume_system` 恒为空 → 两条修复是**空操作**
  （测试内的迷你全链实测两个计数器均为 0，既有产出不变）。

**测试**（新增 3 项）：continuous 零化年槽（带年/不带年同键；year_volume 与未盖值行不动；
记账口径 = 实际改动行数）、year_volume 族内唯一年补年 + **≥2 年反例族弃权**、
输入顺序不变性 + **幂等**（同输入重跑不再改动）。

**账本补记**：M3 的 7,581 族 / 13,130 族是**结构上限**——只有 `volume_system` 被
核实并写进表的汇编才修；未覆盖的汇编保持现状。Stage 4 要报「实际修复数 vs M3 上限」。

### R3-14 Stage 1 研究结果（子代理产出，提案）

三个只读子代理，任务书见 R3-11；产出写 `audit/findings/r3_reporter_origin_{group}.md`。

**环境限制（影响证据等级，必须先说）**：本轮 `web_search` / `x_search` 在**所有引擎**上
持续失败（modsearch → firecrawl keyless 403；无 API key，会话内无法修复；我本人复核
确认），只有**已知确切 URL 的 `web_fetch`** 可用。后果：**「我搜过 X 而没找到」这类
否定性结论在本轮无法被证明**，因此凡属此类一律不升级为可写行。这不是研究者的失误，
是环境缺陷；三名子代理都记录了它，并因此主动保守。若后续要扩大 Stage 1 覆盖，
**恢复检索能力（配一个 firecrawl/其他 key）是可预期的第一步**。

**定义分叉的裁决（我的判断，有本仓库数据支持）**：子代理提出「枢密院案算来源地还是
算审理法院」的分叉。本仓库的语义已有定论——`decisions/case_origin.csv` 203 行**全部**
是 `case_origin=CA` + `deciding_court=JCPC`（枢密院审理的加拿大上诉）。故：
**JCPC 案按案件来源地记**。推论：
- `A.C.`/`App. Cas.`：同卷混印上院案（GB 来源地）与各殖民地枢密院上诉（非 GB 来源地）
  → **真混合**，不可作来源证据 ✓（与计划 §0 的根因诊断一致，与计划 §6 的强制测试一致）。
- `C.L.R.`（联邦法律汇编：高等法院 + 从高等法院上诉到枢密院的案）：枢密院部分**来源地
  仍是 AU**，故「含枢密院 ⇒ 混合」这条推理对 C.L.R. **不成立**。但 `clr` 另有未解决的
  加拿大同形侧（语料 164 条 CA 提及；现有未核实表猜「Construction Law Reports」，
  本轮无法核实）→ **仍不写行**，理由是**同形未解决**，不是枢密院。

**已完成两组的结果**：

| 组 | tier1 | 已核目标 | `exclusive_statute` | `exclusive_publisher` | `mixed` | 第三方手册 | 非汇编 | 无权威出处 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 英国 | 8/8 | 15 | **0** | **0** | 12 | 3 | 0 | 若干 |
| 美国及其他 | 1/1 | 58 | 0 | 2（**建议降级**） | 2 | 4 | 50 | ~30 |

- **英国组 = 零可写行**。关键证据：ICLR 1930 年 A.C. 卷首题名页逐字为「LAW REPORTS OF
  THE INCORPORATED COUNCIL OF LAW REPORTING. HOUSE OF LORDS, JUDICIAL COMMITTEE OF THE
  PRIVY COUNCIL AND PEERAGE CASES.」，并配枢密院专职 reporter；反例
  `Edwards v Canada (AG) = [1930] AC 124`（BAILII `Cite as: [1930] AC 124, [1929] UKPC 86`，
  来自加拿大最高法院）同一卷内另有十余件加拿大枢密院案（页 111/144/152/161/244/357/
  623/629/640/659/673/686）与尼日利亚、锡兰、新南威尔士、海峡殖民地、马耳他案。
  → **`ac`/`appcas` 不写行**；R3-2 里那 211 组会变 CONFLICT 的反向风险**随之消失**。
- `er`（English Reports）178 卷：12–20 卷是枢密院（含印度上诉 1809–1865），1–11 卷含
  苏格兰/爱尔兰上院上诉 → 非英国专属。
- `wlr`：ICLR 自述范围含上院与枢密院；`Subramaniam v Public Prosecutor (Malaya) =
  [1956] 1 WLR 965`。**这回答了上一轮审计的悬案**：语料里 76 条 CA 法域标注的 W.L.R.
  提及**多半不是分组错误**——W.L.R. 真的刊登从加拿大上诉到枢密院的案（按本项目语义
  来源地=CA）。但 `wlr` 自身不携带来源证据（混合，不写行）。
- `kb`/`ch`/`chd`/`qbd` 判 `mixed` 的理由是**没拿到卷首题名页**（不是找到了反例）——
  即「可升级但缺一件实物」。`qb` 的魁北克侧已独立溯源：1900 年魁省律师总会总索引给出
  **1892–1898、B.R. 卷 1–7 + C.S. 卷 1–14**，与语料 `qb` 的高频形态（卷 1–2、年 1891–1900）
  吻合；1892–1898 重叠区按设计保持 UNDETERMINED。
- **美国及其他组**：`us` 判 `mixed`，反例具体——`277 U.S. 189 (1928)` *Springer v.
  Government of the Philippine Islands*（美最高法院 1901–1946 对菲律宾行使上诉管辖，
  28 U.S.C. §411 历史注说明 1946-07-04 删除菲律宾条款）；`2 U.S. (2 Dall.)` 含宾州各法院
  判决。`f`/`fsupp` 由子代理标为 `exclusive_publisher` 但**只有第三方（维基）范围描述**，
  按 P2 必须**降级为 `scope_evidence_third_party_only`（不写行）**——我按 P2 处置。
  `nfldpeir`（871 条提及）**无任何权威出处**（维基 404、Maritime Law Book 域名失效、
  CanLII 403）→ 不写行。50 个目标判 `not_a_reporter`（17 种法学期刊 + 33 个噪声 token）。

**对计划的直接影响**：计划 §3 的净新增上限里，**外国方向那 23,186 组基本兑现不了**——
英国组零可写行，美国组零可写行（`us`/`clr` 混合、`f`/`fsupp` 降级、`nfldpeir` 无源）。
外国方向的失败有**同一个根因**：普通法汇编普遍混印枢密院/殖民地/苏格兰/爱尔兰案
（这正是计划 §0 的根因，只是范围比 A.C. 一处大得多）。**加拿大组仍在跑**，它承担
scr(11,610)/dlr(9,148)/or(9,027)/ccc(8,865) 等国内主体的可写行判定——本轮实际兑现
多少，取决于它的产出。

### R3-15 Stage 4 仪器（先建）

`implementation/r3_blast_radius.py`（只读）：逐层比较两个 run，给每个变化归因。
- 层：提及（candidate_id → arbitration_status）/ 成员行（(court, merge_key) →
  identity_basis、member_origin_*、**组内容签名**）/ 组（签名 → group_foreign_status）/
  边（foreign_status 分布 + foreign_edges 行数）/ 选取（dd、kept）。
- **不把 `merged_group_id` 当跨版本键**（`audit/README.md` 明说组号会变）：用
  「组内成员 row_key 排序并集」作内容签名。必须读**跨法院轮**产出——读院内轮会虚高
  （自测实测 182,384 vs 最终 177,136）。
- 归因类：`reporter_scope` / `scope_or_record` / `identity` / `arbitration` / `group_only`，
  目标是 0 未解释；另单独数 `member_origin_ambiguous_basis=exclusive_reporter_scope_ambiguous`
  的**行数与去重组数**（计划 §8.4）。
- 自测（r2i 对自身）：提及 0 变化、成员 0 变化、签名 0 变化、边与 kept 全同 → 仪器不产生
  假变化 ✓。

### R3-16 Stage 1 合并：`decisions/reporter_origin_scope.csv`

**过程事实（必须记）**：加拿大组子代理**最终状态 = failed**（未产出任何文件、无收尾消息；
中途登记表显示 idle，我发过一次催办消息仍无产出）。故其 16 个 tier-1 目标
（scr/dlr/or/ccc/oj/wwr/oac…）**没有拿到研究者 findings**——不计为「已完成」。改为
**自己按法条一手复核**加拿大侧（结果见下）。英国组与美国及其他组按任务书交付，
findings 在两份 `r3_reporter_origin_*.md`。

**我自己一手取证的来源**（`web_fetch`，取用 2026-09-13）：

| 事实 | 出处 |
|---|---|
| 最高法院由自己的 Registrar 出版其判决；本院是「a general court of appeal for **Canada**」 | Supreme Court Act R.S.C. 1985 c. S-26 **s.17 + s.3**，https://laws-lois.justice.gc.ca/eng/acts/s-26/page-1.html |
| 联邦法院/联邦上诉法院的**官方汇编**由司法部长指定编辑出版；编辑只决定哪些本院判决「of sufficient significance」而收录 | Federal Courts Act R.S.C. 1985 c. F-7 **s.58(1)(2)**，https://laws-lois.justice.gc.ca/eng/acts/F-7/page-6.html |
| 最高法院自己的网站把该汇编标为「**Canada Supreme Court Reports**」 | https://www.scc-csc.ca/judgments-jugements/index-eng.aspx（官网导航） |

**写入表：4 条可写行（全部 `exclusive_statute`）**

| printed | nk | origin | volume_system | 年窗 | 依据 |
|---|---|---|---|---|---|
| S.C.R. | scr | CA | year_volume | 1876– | SCA s.17+s.3。年窗起点 1876 = 官方汇编首卷（语料 1876 前的年值是解析噪声，由窗排除） |
| Can. S.C.R. | canscr | CA | continuous | 1876– | 同一官方汇编的**早期印刷形**（语料实测「6 Can. S. C. R. 52」「(1920) 60 Can. S.C.R. 131」→「Canada Supreme Court Reports」，官网以此名指该汇编）+ SCA s.17。**依据链最长的一行，复核优先看它** |
| F.C. | fc | CA | year_volume | 1971– | FCA **s.58(1)(2)**：official reports *of the decisions of the Federal Court of Appeal and the Federal Court*。年窗起点 1971 = 联邦法院设立 |
| F.C.R. | fcr | CA | year_volume | 1971– | 同 s.58（F.C.R. 是该官方汇编的现代印刷形） |

**同时写入 22 条 `verified_mixed` 档案行**（`ac`/`appcas`/`er`/`wlr`/`kb`/`qb`/`ch`/`chd`/
`qbd`/`aller`/`crappr`/`lr.hl`/`lr.qb`/`chapp`/`lr.pc`/`us`/`clr`/`p`/`alr`/`nzlr`/`f`/`fsupp`）：
这些行**不参与推断**（loader 白名单只要 `verified_exclusive_*`），作用是**写死「这个汇编
不可作来源证据」的结论与出处**，免得下一轮从头再查。其中：
- `ac`/`appcas` 是计划 §0 的根因本身（卷首题名页逐字证明上院 + 枢密院混印）；写死它们
  等于把 R3-2 那 211 组 CONFLICT 反向风险**永久关掉**。
- `f`/`fsupp` 子代理原报 `exclusive_publisher`，但唯一范围陈述来自第三方参考书 →
  我**按 P2 降级为不可写**（代价：1,137 + 若干组）。这是 P2 的直接后果，不是研究失误。
- `kb`/`qb`/`ch`/`chd`/`qbd` 判 mixed 的理由是**没拿到卷首题名页**（不是找到反例）——
  即「可升级但缺一件实物」，表里写明，供有检索能力的下一轮直接接手。

**计划 §6 的一项测试被证据推翻（改测试而不是改结论）**：计划要求
「`(1930), 45 K.B. 129` 唯一命中 QC 窗 → CA」。该期望的前提是**未核实**区间表里的
QC 窗（vol 5–100/1892–1941）。已溯源的魁北克 K.B. 窗是 **1892–1898 / 卷 1–7**，
不含卷 45/1930；英国侧又因缺卷首题名页判 mixed。→ 正确结果是 **UNDETERMINED**
（P1：宁可多留未知）。我把该断言改成 UNDETERMINED 并把这段理由写进断言信息；
规则本身「唯一命中窗即定案」由夹具测试覆盖（`1930|45|kb||129` + 合成 QC 窗 → CA/QC ✓）。

**兑现预测（对 Stage 0 上限的拆分，Stage 4 用实测复核）**

| 类别 | 净新增组 | 占比 |
|---|---:|---:|
| 本轮可写行（scr 11,610 / canscr 2,307 / fc 839 / fcr 153） | **14,909** | 13.1% |
| 已研究并判 mixed/不可写 | 14,224 | 12.5% |
| **未写**（≥300 组的就有 59 个缩写，合计 69,693 组）——主要是加拿大商业/省级汇编：dlr 9,148、or 9,027、ccc 8,865、oj 4,374、wwr 3,359、oac 2,558、cr 1,917、bclr 1,327、ar 1,219、rfl 1,211、scca 1,189、cbr 1,112、crr 1,066、altalr 994、bcj 946、cpc 845、excr 817、bcac 790、manr 779、ontlr 768、rjq 766、nsr 730、qr.kb 671… | 84,299 | 74.3% |

结论要写清楚：**本轮不是「规则不行」，是「证据拿不到」**——这 84,299 组的阻塞项是
**出版方自述/官方来源的检索能力**（`web_search` 全线 403），而不是设计缺陷。恢复检索
能力（或接受把第三方引用手册设成第三档）是解锁它们的前提；两条都需要用户裁决。

**Stage 3 由此激活的范围**：只有这 4 个缩写带 `volume_system` →
`scr`/`fc`/`fcr` = `year_volume`（走 B：族内唯一非空年补空年槽），`canscr` = `continuous`
（走 A：结构性零化年槽）。其余 7,000+ 族（M3 上限）本轮**不修**——`volume_system` 未核实
就不动键，这是计划「表驱动、不猜」的直接后果。Stage 4 报「实际修复数 vs M3 上限」。

### R3-17 Stage 4：全量 run + 验证（`data/run_20260913_r3a/`）

**0. run 与独立指纹**。`run_all.py` 一次跑完 10 步，manifest `status=complete`。
`implementation/r3_fingerprint_check.py`（**自己重算**，不采信 manifest 的
`input_identity_verified_unchanged` 字段）：22 个文件逐一哈希，fingerprint
`a065686886cacd388e6a6a06f7cadd1d51e403dbfdf996af70e67a81dfa99731` = manifest 值，
**0 不匹配**；新表 `decisions/reporter_origin_scope.csv` **在指纹内**（R2-10 自动覆盖
`decisions/*.csv`）。同一仪器对 r2i 复核则报 4 个不匹配（classify/decide/merge + 新表）
——**r2i 不可由 HEAD 重放**，这是本轮改了管线的必然结果，登记备查。

**1. 覆盖前后（两个总体都算）**

| 量 | r2i（前） | r3a（后） | Δ |
|---|---:|---:|---:|
| 组总数 | 177,136 | 175,490 | −1,646（身份合并） |
| 组·DOMESTIC_CA | 10,336 | **23,625** | **+13,289** |
| 组·FOREIGN | 326 | 326 | **0** |
| 组·UNDETERMINED | 166,474 | 151,539 | −14,935 |
| kept 组（dd≥5） | 8,586 | **8,637** | **+51** |
| kept 组·DOMESTIC_CA | 2,784 | ~2,835 | +51 |
| 边·DOMESTIC_CA | 55,237 | **110,666** | **+55,429** |
| 边·FOREIGN | 384 | 384 | **0** |
| 边·UNDETERMINED | 277,866 | 218,678 | −59,188 |
| 边总数 | 333,487 | 329,728 | −3,759（组数减少所致） |

**头条要说两句话，缺一句就是误导**：组级国内覆盖 **+13,289 组（10,336 → 23,625，
约 2.3 倍）**；但**产品门槛内的 kept 组只 +51**（8,586 → 8,637）——新增判定的组绝大多数是
dd<5 的单例，落在占位门槛之下。**计划 §3 要的「净新增组级覆盖」是前者；产品影响是后者。**
外国方向**零变化**（计划 §3 上限里的 23,186 组外国净新增全部未兑现，原因见 R3-16：
英国组零可写行、`us`/`clr` 混合、`f`/`fsupp` 按 P2 降级、`nfldpeir` 无源）。

**2. 爆半径（`implementation/r3_blast_radius.py`，按层、逐条归因）**

| 层 | 变化数 | 归因 |
|---|---:|---|
| 提及（candidate_id） | **39,352** | **100% 单类**：`alternative_contained → alternative_same_key`，全部 `citation_kind=reporter`。成因：Stage 3 把带年/不带年的写法并成同键后，「被包含的并存读法」变成了「同键并存读法」→ 仍是**同一键只计一次**，不改变计数 |
| 成员行 origin 字段 | **15,117** | `reporter_scope` 15,117（全部 `exclusivity=exclusive_statute`） |
| 成员行（新增行，年槽被补后新出现的键） | **2,660** | 同上（`rows_only_after`）→ 本规则实际判定的成员行 = 15,117 + 2,660 = **17,777** |
| 成员行 组签名变化 | **148** | `identity`（Stage 3 合并） |
| 成员行 组结论变而自身证据未变 | **986** | **全部**可归因：这 986 行所在组都有同组 `exclusive_reporter_scope` 成员 → 兄弟成员的新证据抬升了组结论。**未解释 = 0** |
| 一致性三元组 | **0 / 0 / 0** | 行来源不一致 0 / 多国别非 CONFLICT 0 / 同系统多键 0 |

**3. 计数守恒与 dd/kept**：merge 层 `occurrence_total` 两轮**完全一致**
（SCC 360,950 / ONCA 171,151）——身份修复没有虚增或丢失计数；`merge_keys` 减少
（SCC 125,013→123,463；ONCA 67,668→67,611）= 被合并的键。按**组内容签名**（不用组号，
也不用 (court,merge_key)——同一键可被按判决拆成多组，我第一版比对就栽在这里并把
528 行误报成 dd 变化）重算：共同签名 172,783，**dd 升 401 / 降 0**；
kept **false→true 62 / true→false 0**；签名只在新 run 2,707（其中 kept 32）、
只在旧 run 4,353（其中 kept 43）——后者是**被合并掉的旧签名**，不是门槛丢失。

**4. 人工对照原文（计划 §8.3）**。**新增 FOREIGN 判定 = 0**（FOREIGN 组与边都不变），
故「每条新 FOREIGN 逐条回溯」为空集——这条要求本轮没有对象，不是跳过。
**同形异义汇编带来的新 DOMESTIC_CA = 0**（同形表行一条都没写，见 §8.4）。
四行来源地各做原文核对（`pipeline/traceback.py --run-dir data/run_20260913_r3a`）：

| 判定 | candidate | 原文窗口（节选） | 结论 |
|---|---|---|---|
| `26 Can. S.C.R. 595` → CA | `SCC:5288:6260:6280:shape_vol_abbr_page` | 1897 年 SCC 判决注脚清单 `[5] <<26 Can. S. C. R. 595>>.`（同列 Q.R./M.L.R./Q.B.D./App. Cas.） | 印刷形与 Can. S.C.R. 一致 ✓ |
| `[2015] 1 F.C.R. 335` → CA | `SCC:7108:26543:26562:shape_bracket`（citing = 2015 SCC 61） | `APPEAL from a judgment of the Federal Court of Appeal …, 2014 FCA 113, <<[2015] 1 F.C.R. 335>>, …` | F.C.R. = 联邦上诉法院判决汇编 ✓ |
| `[1991] 1 F.C. 428` → CA | `SCC:1534:10378:10395:shape_bracket`（citing = [1993] 1 SCR 941） | `APPEAL from a judgment of the Federal Court of Appeal, <<[1991] 1 F.C. 428>>, 124 N.R. 379 …` | F.C. = 联邦上诉法院判决汇编 ✓（且证明本规则只作用于 `citation_kind=reporter`，未碰中立码 FC） |
| `[1991] 1 S.C.R. 742` → CA | 组 `XC-G009736`（dd 694，R. v. W.(D.)） | 组内另有 `1991||scr||741` 等平行写法，案名众数一致 | SCC 判例 ✓ |

**5. `exclusive_reporter_scope_ambiguous`（计划 §8.4）实测 = 0 行 / 0 组**。
对照 M4 的**规划估计**（未核实区间下 675 个组合命中多行、3,197 条提及，其中
**异国** 294 组合 / 1,911 条提及）：**估计没有兑现，但不是因为歧义被解决了**——是因为
K.B./Q.B./S.C./C.P./P./A.L.R./C.L.R. 这些同形汇编**一条可写行都没写**（英国组零可写行、
其余无源）。它们的提及仍是普通 UNDETERMINED，**不落 ambiguous 列**。这正是计划要我
「诚实说明而不是折进普通 UNDETERMINED 就算」的那件事：**ambiguous 列读 0 不代表残差为 0，
只代表残差被推到了「没有行」这一更粗的桶里**；规模见 §7 的 84,299 组。

**6. Stage 3 实际修复数 vs M3 上限**（merge manifest，按 run 记账）

| 量 | SCC | ONCA | 合计 | M3 上限（r2i） |
|---|---:|---:|---:|---:|
| A 连续卷零化年槽（行） | 1,575 | 2 | 1,577 | — |
| B 族内唯一年补空年槽（族） | 4,681 | 1,481 | **6,162** | 7,581 |
| B 补年（提及行） | 33,365 | 11,868 | 45,233 | — |
| B 弃权族（≥2 年） | 1,445 | 722 | **2,167** | 13,130 |
| 被合并掉的 merge key | 1,550 | 57 | 1,607 | — |

读法：B 的**兑现率 6,162 / 7,581 = 81%**（远超我按「只有 4 个缩写带 volume_system」的预期，
因为 S.C.R. 一族就占 1,402 个上限制标的多数）；弃权族 2,167 远小于上限 13,130，
因为上限的多数族属于**没有 `volume_system`** 的汇编（本轮不动它们）。

**7. 全部测试套件（改动后、全量 run 之后重跑）**：`test_candidates.py` **262 条断言
exit 0**（含真实表项）；`test_layers.py` 120 条 exit 0；`run_regression.py --selftest`
exit 0；`extract.py --fixture-check` exit 0。

**8. 账本（Round 3 收口）**

- **B12（上诉链合并 19 组）**：未测，照抄计划，标未核。
- **B13（年读作卷）**：r2i 实测 92 条（计划写 188，口径不符），本轮未动，标未核。
- **B14（M1a/M1b 缺口与共引阻断）**：本轮**未变**——被身份基础挡住的组 4,567 → 4,558
  （`name_year` 4,468 / `cocitation` 81 / `unanchored` 9）。剩余净新增上限 113,432 → 98,507。
- **B15（M3 弃权桶）**：13,130 → 13,084 族（含空年变体 1,304 → 1,271）；
  本轮只兑现了 6,162 族，其余因无 `volume_system` 不动。
- **B16（同形异义真歧义残差）**：**未兑现为 ambiguous 列**（实测 0），改为登记在
  「无行」桶：K.B./Q.B./S.C./C.P./P./A.L.R./C.L.R. 等合计约 3,197 条提及仍 UNDETERMINED。
- **B17（表侧退化行）**：`pd`/`nfldpeir` 的「有行无区间」问题**未触发**（这两行未写）；
  `lrex`/`lrqb` 的键印刷形大小写不一致仍是 2 族，未动。
- **B18（本轮新增，最重要的阻塞项）**：**84,299 个净新增组（74% 上限）卡在「拿不到
  出版方/官方来源」**——`web_search` 与 `x_search` 在所有引擎上 403（firecrawl keyless），
  三个子代理与我都只能 `web_fetch` 已知确切 URL。解锁只有两条路，**都需用户裁决**：
  (a) 恢复检索能力（配一个可用的搜索 key）后重做 Stage 1；
  (b) 把「第三方权威引用手册（McGill Guide / Bluebook / Cardiff Index）」设为**第三档**
      可写证据（比 P2 现在的两档宽），并把反例搜寻作为该档的强制条件。
- **B19（本轮新增，另一条技术路线）**：数据库/厂商式引证（`oj` = Ontario Judgments QL
  4,374 组、`scca` = S.C.C.A. No. 1,189 组、`qr.kb` 671 组…）按其性质应走**既有**的
  `decisions/identifier_systems.csv` + `court_or_reporter_scope.csv` 路线（R2F 已为
  CanLII/Carswell/DTC/WL 用过，允许 `verified_authoritative_manual` 档），**不是**走本轮
  这张表。本轮未做（避免超范围），登记为下一轮的候选。

## Round 3 交付物清单（供复核）

| 类别 | 文件 |
|---|---|
| 决策表（唯一事实源） | `decisions/reporter_origin_scope.csv`（26 行：4 可写 + 22 mixed 档案） |
| 生产代码 | `pipeline/decide.py`（`load_reporter_origin` / `_reporter_origin` / 优先级接线）、`pipeline/classify.py`（`volume_system` 盖章）、`pipeline/merge.py`（`apply_reporter_identity_fixes`） |
| 测试 | `pipeline/tests/test_candidates.py`（+13 项，262 断言） |
| Stage 0 仪器 | `implementation/coverage_metric.py` + `data/coverage_out/stage0_{r2i,r3a}.json` |
| Stage 1 研究输入 | `audit/stage1_targets.py` + `audit/findings/r3_stage1_targets*.{md,json}` |
| Stage 1 研究产出 | `audit/findings/r3_reporter_origin_{british,other}.md`（加拿大组子代理 **failed**，无产出） |
| Stage 4 仪器 | `implementation/r3_blast_radius.py`、`r3_fingerprint_check.py`（指纹 + 一致性） |
| 全量 run | `data/run_20260913_r3a/`（status=complete，指纹自核一致） |

### R3-18 检索能力审计（回答「不是有插件搜索工具吗」）

把 npm cache 指到工作区内即可运行 `npx @liustack/modsearch doctor`（此前 npx 报 EPERM
只是因为 npm cache 在工作区外、沙箱不许写，不是工具缺失）。实测结果：

| 源 | 状态 | 说明 |
|---|---|---|
| search → **firecrawl** | 名义 `READY`，**本机 403** | doctor 称「keyless: works with no key and no signup（1000 credits/月，按 IP 计量）」；实际请求返回 `firecrawl rejected the keyless request (403) — your IP address looks suspicious, so Firecrawl can't be used without an API key from here`。**这是 `web_search`/`x_search` 全线失败的唯一原因** |
| search → antigravity-cli | `not set` | 需 `agy` 二进制 + 一次登录 |
| search → tavily / exa | `not set` | 需 key |
| social（X）→ grok-cli | 不可用 | 需 `grok` 二进制 + `~/.grok/auth.json` |
| fetch → firecrawl | 同上 403 | |
| fetch → **local** | **`READY`** | 内置、无需安装——本轮所有网页取证（法条、SCC 官网、BAILII）都走它 |

配置文件 `C:\Users\hp\.modsearch\config.json`（不存在 = 全默认）。**恢复搜索的两条命令**
（在工作区外，我无权执行、也没有 key）：

```
npx @liustack/modsearch config set firecrawl.apiKey <key>   # firecrawl 免费档 1000 credits/月
npx @liustack/modsearch config set tavily.apiKey <key>      # 或 tavily
```

**无 key 时仍可用的检索路径（实测）**：Wikipedia MediaWiki API
（`en.wikipedia.org/w/api.php?action=query&list=search` 与 `prop=extracts`；可用，但本主题
覆盖薄——只有 "Dominion Law Reports"、"Supreme Court Reports (Canada)"、"Law report" 三条
相关条目）、Internet Archive 元数据 API（本主题 numFound 0）、**确切 URL 直取**（法条、
法院官网、BAILII；最好用）。
**无 key 时不可用**：DuckDuckGo（html 与 lite 都出人机挑战）、Mojeek（JS 挑战）、
searx.be（浏览器验证）、Bing（返回页面但**忽略引号与检索算子**，结果与查询无关）、
Google Books API（该项目配额 0）、Marginalia（软等待页）。

**对 B18 的直接影响（结论要改）**：解锁那 84,299 组的第一条路（「恢复检索能力」）
**不是研究问题，是一件一分钟的配置动作**——由用户提供任一 key。在此之前能拿到的只有
第三方材料，例如 Wikipedia 的 D.L.R. 条目：1912 年创刊、Canada Law Book 出版、收录
**联邦与各省法院**判例，并引 Banks《Using a Law Library》与 Yogis《Legal Writing and
Research Manual》。这类材料**恰好就是「第三方引用手册」第三档**的证据类型——所以
第二、三条路其实是同一个决定：**要么给 key 拿到出版方自述，要么明确承认第三档。**

### R3-19 检索恢复（Exa）——B18 的阻塞已解除

用户提供 Exa API key 后按其官方 skill（`exa-labs/agent-skills` 的 `build-with-exa`，经
raw.githubusercontent 读取；`npx skills use` 因沙箱禁止 node 以管道 spawn git 而 EPERM，
故改为直接读 skill 文件）配置：

| 动作 | 结果 |
|---|---|
| 读官方 skill | `SKILL.md` + `references/search.md`：认证用 `EXA_API_KEY`；**推荐请求 = query + `type:"auto"` + `contents.highlights:true`，其余参数一律不加**（不加 boilerplate `numResults`、不加 `category`、不加 domain 过滤、不用日期过滤代替「latest」） |
| 写 key | `modsearch config set exa.apiKey` → `C:\Users\hp\.modsearch\config.json`；`config show` 回显**已打码**（`44ff6c...4e (file)`） |
| 固定引擎 | `modsearch config set search.engine exa`（doctor 确认：`search engine: exa (from config file)`）；auto 会先解析到 firecrawl 再回退，固定后不再空耗一次失败调用 |
| 验证 | `web_search` 走 Exa，实测可用 |

**能力边界（重要，别过度期待）**：
- **搜索（发现 URL）= 已修好**：`web_search` 由 Exa 服务端检索并返回 highlights。
- **取页（读某个 URL）= 仍走本机 IP**：`modsearch search -u <url>` 先试 firecrawl（403）再退到
  `local`（= 本机出口）。实测 `legisquebec.gouv.qc.ca` 对本机 IP 返回 CloudFront 403。
  **绕法**：对封锁本机的站点，**用搜索问句把正文问出来**——Exa 的 highlights 是它自己
  服务端取回的页面内容，s.21 逐字原文就是这样拿到的。
- `x_search`（社交）仍不可用：`grok` 二进制与 `~/.grok/auth.json` 均不存在。

**恢复检索后的第一批实证（说明这条路值多少钱）**：

1. **魁北克官方汇编有法条依据**（`exclusive_statute`，最高一档）：
   Légis Québec **S-20《Loi sur la Société québécoise d'information juridique》s.21**
   （https://www.legisquebec.gouv.qc.ca/fr/document/lc/s-20）——「La Société collabore avec
   l'Éditeur officiel du Québec à la publication des **jugements rendus par les tribunaux
   judiciaires siégeant au Québec** …」；s.20 规定其出版职责；S-20, r.1 是其选编规则。
   配套证据：SOQUIJ 自己的汇编表（`R.J.Q. 1986 à 2013`，
   https://aide.soquij.qc.ca/s/article/tableau-recueils-jurisprudentiels-publies-par-SOQUIJ）
   与 SOQUIJ 博客的沿革（1892 年起由 Barreau 编制，1974 年 SOQUIJ 接手，1986 年
   R.J.Q. 把上诉法院/高等法院/省法院等并入同一汇编，
   https://blogue.soquij.qc.ca/2016/05/10/retour-sur-les-recueils/）。→ `rjq` 及其同族
   （`qr.kb`/`qr.sc`/`queqb`/`ucqb`/`cs`）可望写入，且证据档位比商业汇编高一档。
2. **安大略官方汇编有出版方自述**（`exclusive_publisher`）：LexisNexis Canada 产品页
   「Published by the Law Society of Ontario through LexisNexis Canada, Ontario Reports …
   leading cases decided at **all levels of Ontario courts**」
   （https://www.lexisnexis.com/en-ca/products/ontario-reports）；CanLII 博客另证 ORs 是
   Law Society of Upper Canada 的财产（https://blog.canlii.org/2013/10/23/383/）。
3. **系列/年代窗口的一次性权威来源**：Bluebook **T2.6 Canada**
   （https://www.legalbluebook.com/bluebook/v21/tables/t2-foreign-jurisdictions/t2-6-canada）
   给出 D.L.R. 1912–date（2d 1956/3d 1969/4th 1984 断点）、O.R. 1882–1901 与 O.L.R.
   1901–1930/31、W.W.R. 1911–date、A.R. 1977–date、B.C.L.R. 2d/3d/4th 断点等；
   图书馆指南 https://www.unb.ca/fredericton/law/library/about/law-reporters-by-database.html
   亦同。**这些是第三方（不可单独授权一行）**，但它们正是窗口字段的自然来源。
4. 顺带消除了一个我自己留下的疑问：Bluebook T2.6 的分期表把 1876–1922 记作
   "Canada Supreme Court Reports"、**1923–1969 记作 "Canada Law Reports: Supreme Court of
   Canada"**、1970– 再回到 "Canada Supreme Court Reports"——与我 `canscr` 行的
   「同一官方汇编的早期印刷形」判断一致（我方窗口 1876– 为宽口径，未按 1922 收口，
   因为收口依据来自第三方手册）。

**下一步（同一轮内继续）**：加拿大组研究已用可用检索重跑（子代理含魁北克 S-20 与
各省「官方汇编法条」的专项核查），findings 落地后由我合并进表，再重跑全量并按 R3-17
的同一套仪器复核（覆盖、爆半径、原文追溯、一致性、指纹）。

### R3-20 恢复检索后的第一批新行（表 26 → 28 行；可写 4 → 6）

不等子代理，先用**自己一手核到**的证据写两行（`decisions/reporter_origin_scope.csv`）：

| 行 | origin | 档 | volume_system | 年窗 | 一手证据 | 预计净新增组 |
|---|---|---|---|---|---|---|
| `R.J.Q.` (rjq) | CA/QC | **exclusive_statute** | year_volume | 1986–2013 | Légis Québec **S-20 s.21**（SOQUIJ 出版「les jugements rendus par les tribunaux judiciaires **siégeant au Québec**」）＋ SOQUIJ 自己的汇编表（`R.J.Q. 1986 à 2013`）。**三方印证**：语料 2 242 条提及印刷形全为 `[YYYY] R.J.Q. N`、年份恰落 1986–2013 | 766 |
| `O.R.` (or) | CA/ON | exclusive_publisher | （留空：年卷＋连续卷并存） | 1882– | LexisNexis Canada 产品页**逐字**：「Published by the Law Society of Ontario through LexisNexis Canada, Ontario Reports, Third Series provides, in full text, leading cases decided at **all levels of Ontario courts**」（本机可直取，HTTP 200）＋ 安省上诉法院实务指引把 Ontario Reports 列为 official or semi-official reporter | 9 027 |

`R.J.Q.` 的年份窗口与语料实测**逐点一致**（1986–2013），这是本轮「表驱动窗口」第一次
被独立数据完整印证。`O.R.` 的反例搜寻按 P2 记了三条（含「唯一能推翻本行的反例是
**非加拿大**判决被收录——未检索到」），并明确：**第三方手册（Bluebook/图书馆指南）
只用来定年窗，不作授权依据**。

补记两条本轮**没写**的（避免过度外推）：
- `cs`（C.S.，魁省高等法院官方汇编，1892–1985，来源链完整：1892 年起由魁省律师总会出版、
  1975–1985 由 SOQUIJ 出版）——**两字母缩写 C.S. 的碰撞风险无法用单一来源排除**，
  312 组，按「方向永远是宁可留未知」不写，留给子代理的 findings 决定。
- `queqb`（`[1956] Que. Q.B. 447`，1892–1969）、`qr.kb`/`qr.sc`（`Q.R. 19 K.B. 68` 形，
  1893–1941）、`ucqb`（`19 U.C.Q.B. 341`，Upper Canada = 安省，1846–1882）——印刷形与
  年代都清楚，但**官方沿革与窗口尚无一手来源**，不写。

同时把「可写行必须有 volume_system」的**校验工具**放宽为「可为空 = 体系未定，Stage 3
不动该缩写的键」（表侧 `volume_system` 为空不影响来源地判定，只影响身份修复范围）。
测试 273 条断言通过；随后重跑全量（`data/run_20260913_r3b/`），再按 R3-17 的同一套
仪器复核。

### R3-21 加拿大商业/省级汇编合并：表 28 → **40 行**（可写 6 → **18**）

加拿大组重跑子代理交付 `audit/findings/r3_reporter_origin_canadian.md`（507 行、23 个目标、
12 条建议可写行、逐条附引文 URL 与反例搜寻记录、并自陈工具限制与最该被复核的三处）。
它同时完成了「各省是否有官方汇编法条」的全国排查：**只有魁北克有**（S-20 s.21 / r.1）；
安省 LSO By-Law 13 名叫「REPORTING OF COURT DECISIONS」但**只规定分发与广告分离**，
不含刊登范围——`or` 的可写性因此挂在出版方产品页上、**不挂法条**。

**我（Lead）最重要的一处改判：把「跨省」与「跨国」分开。**
子代理把 `D.L.R.`、`C.C.C.`、`R.F.L.` 判为 `mixed`，依据是出版方题名页写「every province」/
「in all the provinces」/「from all Canadian jurisdictions」以及命中了 Quebec/Manitoba/BC
来源地的反例。**但这些反例只推翻「单一省」，不推翻「单一国」**：本项目的组级结论字段是
`origin_country`，而这三本汇编列出的来源**全部在加拿大之内**（各省法院 + 最高法院 +
财务法院 + 铁路委员会 + 「上诉至枢密院的**加拿大**案」——后者按本仓库 `case_origin.csv`
203/203 行的语义来源地就是 CA）。故按 P2′ 的同类原则处理：**国别一致 → 取国别；
细分不唯一 → subdivision 留空**。这三行因此**可写**（合计约 19,200 个净新增组），
若按子代理的 mixed 判法则全部作废。这是本轮最大的一次判断，已把两种读法都写进 notes。

**另一处必须记的技术细节（差点让 12 行全部变成死行）**：子代理的 CSV 把
`printed_abbreviation` 一列填的是**汇编全名**（`Dominion Law Reports`、`Canadian Criminal
Cases`…），而运行时的查表键是 `nk(printed_abbreviation)`——全名归一后是
`dominionlawreports`，**永远匹配不上语料键 `dlr`**。12 行会被静默忽略（不报错、不生效）。
我的表校验探针（`_probe_table_check.py` 的键口径断言）把它抓出来了；已改为**印刷缩写**
（`D.L.R.` / `C.C.C.` / `W.W.R.` / `A.R.` / `Alta. L.R.` / `Man. R.` / `Sask. R.` /
`N.S.R.` / `N.B.R.` / `N.R.` / `Ex. C.R.` / `R.F.L.`），并**逐条与语料实测印刷形核对**
（12/12 的 `nk()` 等于目标键）。**教训登记**：未来任何来源的 CSV 入库前，键口径必须机器校验，
不能只看它自称「字段顺序与取值域符合规定」。

**第三处改判**：`excr` 子代理判 `exclusive_statute` 但自陈**法定链不完整**（未取得
Exchequer Court Act 的出版条款）→ 我改判 **`exclusive_publisher`**（出版方＝该院自己的
Registrar，卷首「PUBLISHED UNDER AUTHORITY BY THE REGISTRAR OF THE COURT」即出版方自述的
范围声明），不主张没读到的法条。

**新增 12 行**（全部 `exclusive_publisher`，除非注明）：

| abbr | origin | subdivision | volume_system | 年窗 | 关键依据 |
|---|---|---|---|---|---|
| `dlr` | CA | **留空**（跨省） | **留空**（1923–1955 是按年卷，写 continuous 会误并） | 1912– | 出版方题名页「every province + 加拿大枢密院上诉」 |
| `ccc` | CA | **留空** | continuous | 1898– | 题名页「in all the provinces」但「in Canada」 |
| `wwr` | CA | **留空**（BC/AB/SK/MB） | year_volume | 1911– | 出版方卷内短语「All cases of value in Western Canada…」 |
| `ar` | CA | Alberta | continuous | 1976– | MLB 产品表（魁省以外每省一本） |
| `altalr` | CA | Alberta | continuous | 1908– | Carswell 卷首「from the Courts of Alberta and Appeals」 |
| `manr` | CA | **留空**（"other provincial courts" 歧义） | continuous | 1979– | MLB 自述 |
| `saskr` | CA | Saskatchewan | continuous | 1979– | MLB 自述（含「originating in Saskatchewan」明文） |
| `nsr` | CA | Nova Scotia | continuous | 1965– | MLB 创始人自述 + 产品表 |
| `nbr` | CA | New Brunswick | continuous | 1969– | MLB 自述 |
| `nr` | CA | **留空**（范围是法院不是省） | continuous | 1974– | MLB 产品表「SCC & FCA」 |
| `excr` | CA | 留空 | continuous | 1877–1970 | Registrar 授权出版卷首 |
| `rfl` | CA | **留空**（跨法域） | continuous | 1970– | Westlaw FamilySource「all Canadian jurisdictions」 |

**明确不写（连同理由，供下一轮接手）**：`bclr`（唯一范围语来自大学图书馆——子代理自己建议
降级，我采纳）；`crr`（第三方馆藏描述 + 键身份存疑：语料卷 1–578/年 1946–2021 与 C.R.R.
的 1982–1991/卷 1–50 严重不符）；`cbr`/`bcac`/`oac`/`olr`/`ontlr`（只有第三方馆藏/索引表
——**oac 2 558 组、olr 630 组、ontlr 768 组、cbr 1 112 组、bcac 790 组 合计约 5 858 组
停在 UNDETERMINED**）；`bcj`/`fcj`（是 Quicklaw 数据库标识符不是汇编——按 B19 走
`identifier_systems` 路线，不进本表）；`qr.kb`/`qr.sc`/`queqb`/`cs`（法条基础已在手，
差键身份与各系列窗口——**下一轮最容易兑现的增量**）；`ucqb`/`mpr`/`cpc`（键身份或反例
未做）；`oj`/`scca`（供应商/中立键身份未定，`scca` 1 189 组优先级高）。

**预计净新增**（Stage 0 上限口径）：新增 12 行合计约 **28 700 组**，加上 `or` 9 027 与
`rjq` 766，本轮 18 条可写行覆盖约 **38 500 / 113 432（34%）**。表校验 0 问题、测试
**345 条断言**全绿；随后跑 `data/run_20260913_r3c/`（`r3b` 因表在它跑完后又被扩充而作废，
保留供对照），再按 R3-17 同一套仪器复核。

### R3-22 Stage 4 复核（最终交付 run：`data/run_20260913_r3c/`）

**0. run 与独立指纹**。`status=complete`；自算指纹
`7610ace4934e82d0bbf022acf27ff1769dc38d2581cfa1ee68e9d539172f376c` = manifest 值，
**22 文件 0 不匹配**，40 行新表在指纹内。

**1. 覆盖前后（两个总体）**

| 量 | r2i（前） | r3c（后） | Δ |
|---|---:|---:|---:|
| 组总数 | 177,136 | 176,975 | −161 |
| 组·**DOMESTIC_CA** | 10,336 | **61,316** | **+50,980（约 5.9 倍）** |
| 组·FOREIGN | 326 | 326 | **0** |
| 组·UNDETERMINED | 166,474 | 115,333 | −51,141 |
| kept 组（dd≥5） | 8,586 | **8,790** | +204 |
| kept 组·**DOMESTIC_CA** | **2,784** | **6,961** | **+4,177（约 2.5 倍）** |
| kept 组·UNDETERMINED | 5,800 | 1,827 | −3,973 |
| kept 组·FOREIGN | 2 | 2 | 0 |
| 边·DOMESTIC_CA | 55,237 | **176,945** | **+121,708** |
| 边·FOREIGN | 384 | 384 | **0** |
| 边·UNDETERMINED | 277,866 | 153,286 | −124,580 |
| 支撑分级 | supported 308,026 / heuristic 25,461 | supported **315,474** / heuristic 15,141 | 更多边走 supported 路径 |

**头条是三句**：组级国内覆盖 **+50,980 组**（10,336 → 61,316，约 5.9 倍，占 Stage 0 上限
113,432 的 **45%**）；**产品门槛内（dd≥5）的国内组 +4,177（2,784 → 6,961，约 2.5 倍）**；
外国方向**零变化**。kept 组**总数**只 +204 会误导：构成上 3,973 个原「未决的 kept 组」
转成已判定，同时身份合并减少了组数——**产品影响看 kept·DOMESTIC_CA 这一行**。

**2. 爆半径（0 未解释）**

| 层 | 变化 | 归因 |
|---|---:|---|
| 提及（candidate_id） | **70,997** | 100% 单类 `alternative_contained → alternative_same_key`（Stage 3 同键化），全为 reporter |
| 成员行 origin 字段 | **45,248** | `reporter_scope`（另有新增行 12,815 行 → 本规则实际判定 **58,063** 行：`exclusive_publisher` 39,386 + `exclusive_statute` 18,677） |
| 组签名变化 | **3,622** | `identity`（Stage 3 合并/重键） |
| 组结论变而自身证据未变 | **146** | 全部归因：该行所在组有同组 `reporter_scope` 成员 → **未解释 0** |
| 一致性三元组 | **0 / 0 / 0** | 行来源不一致 / 多国别非 CONFLICT / 同系统多键 |

新增 `exclusive_reporter_scope` 成员行按缩写：scr 14,648、or 10,920、ccc 10,464、
dlr 10,128、canscr 1,836、rfl 1,314、ar 1,296、altalr 984、fc 974、rjq 900、manr 810、
nsr 790、excr 652、nr 619、nbr 570、saskr 545、fcr 319、wwr 294（合计 58,063）。

**3. dd / kept（按组内容签名，不用组号、不用 (court,merge_key)）**：共同签名 162,178，
**dd 升 1,263 / 降 0**；kept **false→true 295 / true→false 0**；kept 组 8,586 → 8,790；
签名只在新 run 14,797（kept 1,203）、只在旧 run 14,958（kept 1,294）——后两者是 Stage 3
重键造成的对称churn。`kept` 在组内**一律性检查 0 违反**。`occurrence_total`
（SCC 360,950 + ONCA 171,151 = **532,101**）在 r2i / r3a / r3b / r3c **四轮完全一致**
→ 身份修复没有虚增或丢失计数。

**4. 人工对照原文（计划 §8.3）**。**新增 FOREIGN 判定 = 0**（FOREIGN 组与边都不变），
故「逐条回溯新 FOREIGN」为空集；**同形异义汇编带来的新 DOMESTIC_CA = 0**（同形表行一条
未写）。抽样回溯（`pipeline/traceback.py --run-dir data/run_20260913_r3c`）：

| 判定 | 样本 | 原文（节选） | 结论 |
|---|---|---|---|
| `dlr` → CA | `SCC:6450:8248:8267`（citing = 2001 SCC 44） | `… R. v. Consolidated Maybrun Mines Ltd., [1998] 1 S.C.R. 706; McIntosh v. Parent, <<[1924] 4 D.L.R. 420>>; …` | 加拿大判例（Ontario）✓ |
| `rjq` → CA/Quebec | `SCC:4049:1011:1029`（citing = [1988] 1 SCR 667） | `Applied: R. v. Prince, [1986] 2 S.C.R. 480.` ＋ `APPEAL from a judgment of the **Quebec Court of Appeal**, <<[1986] R.J.Q. 2162>>, 29 C.C.C. (3d) 498 …` | **魁北克上诉法院判决** ✓ 且说明该组把「上诉审 CA 判决」与「SCC 平行引证」并为同案是**正确的** |
| （r3a 已做）`scr`/`canscr`/`fc`/`fcr` | 4 例 | 见 R3-17 §4 | ✓ |

其余 12 个新缩写的抽样（dd≥5 的组）逐条打印了印刷形与案名，人工核对与各省法院一致：
`ccc` R. v. W. (W.)／`or` Kenny v. Lockwood（Ontario）／`ar` R. v. Ferris（Alberta）／
`rfl` Molodowich v. Penttinen／`nsr` Ross v. Ross（NS）／`manr` King v. Operating
Engineers…（Manitoba）／`saskr` R. v. B. (G.)（Sask）／`nr` Canada v. South Yukon Forest
Corp.（联邦）／`excr` 11 Ex. C.R. 119／`wwr` 30 W.W.R. 241（无年，年窗不约束、国别仍 CA）。

**5. `exclusive_reporter_scope_ambiguous` = 0 行 / 0 组**（同 R3-17：同形表行未写，
残差落在「无行」桶，不落 ambiguous 列）。

**6. 全部测试**：`test_candidates.py` **345 条断言 exit 0**；`test_layers.py` 120 条 exit 0；
`run_regression.py --selftest` exit 0；`extract.py --fixture-check` exit 0。

**7. 本轮实际兑现 vs Stage 0 上限**：可写行 18 条，实测 **+50,980 组**（上限 113,432 →
**45%**；kept +204 组）。未兑现部分：**已研究但按 P2 不可写**（英国组全部、`us`/`clr`、
`f`/`fsupp`、`bclr`、`crr`、`oac` 2 558、`cbr` 1 112、`bcac` 790、`olr` 630、`ontlr` 768
等 ≈ 3.4 万组）＋**未研究**（`qr.kb` 671、`queqb` 403、`ucqb` 543、`mpr`、`cpc` 845、
`scca` 1 189、`oj` 4 374、`cs` 312 等）＋**身份基础闸门**（`name_year` 4 468 组，B14）。
**这个拆分是下一轮的施工图**：安省/魁省早期官方汇编（法条与索引都已在手）与
供应商标识符（走 B19 的 identifier 路线）是最近的两个增量。

### R3-23 **r3c 作废**：复核人发现的身份回归 + 修复（Stage 3 与裁定层聚类的依赖）

**复核结论（我复现并确认）**：`r3c` **不可用**。来源地那部分是对的，但 Stage 3 的
「连续编卷去年份」把大量 **C.C.C.**（以及与之同案的 D.L.R./S.C.R. 平行引证所在的组）
从它们所属的案子里拆了出去。

**我的复现**（仪器：**新增** `implementation/r3_case_dd_diff.py`，口径=复核人指定）：

| 量 | r2i | r3c | 复核人报的 |
|---|---:|---:|---|
| 按案名最大组 dd **下降**的案名 | **1,432**（原 dd≥5 的 864） | — | 1,457 / 874 |
| 合计少 | **4,983** | — | 5,043 |
| 上升的案名 | 399（+606） | — | 416 |
| 孤立组（全成员键年槽空）口径 A（且全为连续编卷） | 9,449 | **19,880**（Δ**+10,431**） | 14,094 → 24,525（Δ +10,431，**完全一致**） |
| 口径 B（不限缩写，全键无年） | 67,601 | 74,443 | — |
| 口径 B 中「有案名且 dd≥5」 | 1,277 | 1,989（Δ+712） | 498 → 1,212（Δ+714） |

降幅榜（与复核人一致）：`rvwd` 694→548、`rvmorrissey` 214→123、`rvlifchus` 166→99、
`rvsheppard` 264→220、`rvproulx` 168→127、`rvstarr` 132→93、`rvcollins` 239→204、
`rvbiniaris` 226→192、`rvstillman` 107→74、`rvhandy` 178→146。

**成因归属（修正口径后）**：我第一版仪器用 `merged_group_id` 判「键换了组」——**那是错的**
（组号每轮重新编号，会把整轮重编号都算成变化，且排除了真正受害的组）。改成**比较成员集合**
后：前一轮同组、后一轮不同组的成员对共 **3,107** 对，top 全是 **× `ccc`**：
`scr×ccc` 783、`or×ccc` 439、`scca×ccc` 169、`oj×ccc` 169、`cr×ccc` 154、`oac×ccc` 153、
`scc×ccc` 133、`dlr×ccc` 104 … → **C.C.C. 是那个被拆出去的伙伴**。
（D.L.R. 出现在对里是因为它与 C.C.C. 同组共现，不是因为它自己的键被零化——本表里
`D.L.R.` 的 `volume_system` 是**留空**的，merge 不动它的键；这一点与复核人描述略有差异，
按实测登记。）

**为什么我的 Stage 4 复核没测到（复核人指出的方法缺陷，我确认）**：
- 我的「dd 只升不降」只比较**成员没变的组**（组内容签名相同者），而受害的组签名都变了
  → **恰好被排除在比较之外**。这是方法错误，不是数据问题。
- `occurrence` 守恒只证明提及没丢，不证明归组对；一致性三项不涉及身份归组；
  也没有任何测试断言「D.L.R./C.C.C. 平行引证仍与它的 S.C.R. 同组」。
- 这也印证了复核人自陈的疏漏：上一版计划写 Stage 3「设计是稳的」，没有指出它与
  **裁定层聚类规则**的依赖关系——依赖确实存在，且是本轮回归的唯一成因。

**修法（按复核人给的思路，已实现）**：**年份有两个用途，必须分开**——
① 身份键的一部分（连续编卷**该去掉**）；② 裁定层聚类的属性（**必须保留**）。

1. `pipeline/merge.py`：`apply_reporter_identity_fixes()` 第一件事就是给**每一行**写
   `year_printed`（= 未做任何修复前键里会用的那个年份）；然后只改 `year_start`（键）。
   零化后 `year_printed` 仍留着印出来的年份；`year_volume` 族内**补出来的**年份也写入该列。
   `year_printed` 进入 `MERGED_FIELDS`，由 `_emit` 以「counted 成员里最常见的非空印刷年」
   写进 `merged.csv`（legacy 路线不做修复，该列留空、行为不变）。
2. `pipeline/decide.py`：新增 `row_year(row)`——优先 `year_printed`，缺列/为空时回退键首槽
   （中立码键与旧产出走回退，行为不变）。**三处**改用它：`cluster_same_case()` 的
   「案名+年份」连链、`add_peer_column()` 的同年邻组、以及「组内年份跨度 ≤1」的写表前断言。
   于是**连续编卷的键去掉了年份，而聚类仍按印出来的年份进行**，行为与修复前一致。
3. 测试（复核人指名要的那条）：`test_r3_parallel_citation_stays_in_same_group` ——
   `1991|1|scr||742` + `|63|ccc|3d|1` + `|34|dlr|4th|375` 必须**同组且未被判拆分**；
   并附**反证**：把 `year_printed` 去掉（=没有补救列）时三者各自成孤立组——把回归机制钉在测试里。
   另加 `test_r3_year_printed_survives_zeroing`（归并层保留/补年写入）与
   `test_r3_row_year_prefers_printed_year`（回退口径）。测试 345 → **357 条断言**。
4. **验收口径改为复核人指定者**：`r3_case_dd_diff.py`（按案名最大组 dd）**必须**纳入
   Stage 4 复核；只比较「成员未变的组」不再作为 dd 的验收依据。爆半径仪器保留，但其
   dd 段落降级为辅助（并在仪器注释里写明这条教训）。

**连带影响（复核人指出，我确认）**：R3-22 报的「DOMESTIC_CA 组 +50,980 / 国内边 +121,708」
有一部分是**拆分造成的虚高**——被拆出去的 C.C.C./D.L.R. 孤立组各自按排他汇编被判成国内，
同一份判决引同一个案子还会连出两条边。**真实增量要等修复后的 run 才能读**，本节的
覆盖数字在 R3-24 用 `r3d` 重算后才作数。

**r3c 的处置**：**不冻结、不作为交付 run**；产物保留供对照。修复后重跑
`data/run_20260913_r3d/`，按新口径复核。

### R3-24 r3d → r3e：残余拆分的第二处成因 + 交付 run

**r3d 的验收结果**（`r3_case_dd_diff.py`，r2i → r3d）：按案名最大组 dd 下降 1,432 →
**109**（原 dd≥5 的 864 → 34）、合计少 4,983 → **207**；孤立组口径 A 19,880 → **16,745**。
即第一处修复（`row_year`）解决了 **96%**，但没有归零。

**残余的成因（逐行读代码后定位，与第一处不同）**：`split_by_decision` 的**共引指派**里
还有两处读「键首槽当年份」——

1. **同年级平局裁决**（`same_year = [d for d in top if d.split("|",1)[0] == mk.split("|",1)[0]]`）：
   连续编卷键的年槽为空 → 平局永远破不了 → 单元落进 pending 变孤立组
   （实测 `R. v. Osolin` 68 → 61+7，`split_reason=decision;unanchored`）。
2. `_reporter_origin` 的**年窗匹配**读键首槽：连续编卷键无年 → 年窗维度永远不可比
   （= 放弃窗过滤；不产生错误判定，但失去精度）。

两处都改成读 `row_year()`（印出来的年份）。**r3e 与 r3d 数字完全一致（109/207）**——
说明这两处**不是**残余的主要成因，我的第二处诊断假设被数据推翻（如实登记：两次修复
未改变残余规模；它们的正确性由测试与语义保证，但不承诺减量）。

**残余的真实机制（逐键对照后定位）**：零化把「带年份」与「不带年份」的同一引证**合并成一个
键**，成员集随之变化，会连锁改变三样东西——①该键的**案名众数**（如 `|155|ccc|3d|97`
从 `R. v. Sawyer` 变 `R. v. Pan`——Pan; Sawyer 是 2001 SCC 42 的两件合并上诉，本是一案）；②
该键的**共引决策集**（并入无年引证者）；③若某件判决的头部自印形式恰是**无年形式**，该键
成为**自己的身份锚（root）**，于是不再能跟着中立引用（S.C.R.）那条桶走——实测
`R. v. Osolin`：r3d 的 `|86|ccc|3d|481` 是 singleton、`split_reason=decision;unanchored`。
**修这三处就要动 `split_by_decision` 的指派/锚合并规则与案名投票池——那是计划 §0 明文
冻结的区域**（"Group aggregation, CONFLICT detection, and propagation eligibility stay
UNCHANGED"）。按「问题在产生它的那一层修」与「不扩范围」，本轮**不动它**，入账 B20。

**r3e（交付 run）的验收读数**：

| 量 | r2i | r3e | Δ |
|---|---:|---:|---:|
| 组·DOMESTIC_CA | 10,336 | **51,296** | **+40,960（约 5.0 倍）** |
| 组·FOREIGN | 326 | 326 | 0 |
| **kept 组·DOMESTIC_CA** | **2,784** | **6,179** | **+3,395（约 2.2 倍）** |
| kept 组合计 | 8,586 | 8,646 | +60 |
| 边·DOMESTIC_CA | 55,237 | **154,754** | +99,517 |
| 边·FOREIGN | 384 | 384 | 0 |
| 按案名最大组 dd | — | 下降 109 个 / 合计少 207；上升 559 个 / 多 913（**净 +706**） | |
| 孤立组口径 A | 9,449 | 16,743 | +7,294（B20 残差） |
| 一致性三元组 | 0/0/0 | **0/0/0** | |
| 指纹自核 | — | **一致**（`998c7e44…`，22 文件 0 不匹配） | |
| 按签名 dd 升/降 | — | 712 / **0**；kept false→true 97 / true→false 0 | |
| `reporter_scope` 判定行 | — | **48,773**（publisher 30,097 + statute 18,676） | |

（与 r3c 相比：DOMESTIC_CA 组 61,316 → 51,296，**少 10,020**——那就是复核人测到的
拆分虚高被挤掉的部分；kept·CA 6,961 → 6,179，少 782。）

**B20（新增账本）**：连续编卷零化与「自印无年形式 → 自成身份锚」的相互作用，使约
**109 个案名 / 207 dd** 的平行引证仍被拆出（占 532,101 occurrence 的 0.04%），另有孤立组
口径 A 较基线多 7,294 个。修复需要改 `split_by_decision` 的锚合并/指派规则——冻结区内，
须用户裁决后再做。测试 `test_r3_parallel_citation_stays_in_same_group` 钉的是**键与
`year_printed` 的机制**（单元级），数据级残差由 `r3_case_dd_diff.py` 监控。

---

# Round 4：印刷法院标注 + 案件级人工核验批次（2026-09-14）

**授权**：用户在独立复核后已定的四项决定（D1–D4，约束性，不重开）。本轮范围：
印刷在完整引证之后的**法院标注**（`(H.L.)`、`(P.C.)` 一类）作为**引证自带证据**的
抓取与识别（不产生任何来源地规则），外加一个**有界的案件级人工核验批次**
（≤50 个引证身份 / ≤200 次查询）。基线 = `data/run_20260913_r3e/`（complete，
指纹 `998c7e44…`）。

### R4-0 Stage 0：测量复现与口径固化（先于任何代码变更）

复核人的数字出自 r3c 上的未存档临时脚本；本仪器把它固化并跑在 **r3e** 上：
`implementation/court_designation_metric.py`（只读）→
`data/coverage_out/court_designation_metric_r3e.json`（口径内嵌）+
`..._detail.csv`（45,046 行，每条提及一行：candidate_id / merge_key / 原文标注 / 桶 / 来源判决）。

**固化并写进口径的定义**：counted citation（counted + reporter + 缩写 ∈ 封闭的
24 个外国混合汇编）；distinct citation（不同 merge_key）；标注正则
`\s*,?\s*\(([^()\n]{1,30})\)` 锚定在候选结束偏移（中间只允许空白与一个逗号），
语料列 `unofficial_text_en`；分桶（去空格/点、大写）：`HL*`→HL、`PC*/JCPC*`→PC、
∈{CA,ENGCA,EWCA}→CA_like、恰 4 位年份→year_only、其他→other、空→none。

**复核人 vs 本仪器（逐数对账）**：

| 量 | 复核人（r3c） | 本仪器（r3e） | 差异解释 |
|---|---:|---:|---|
| counted mixed mentions | 45,046 | **45,046** | 完全一致（提及集与偏移在 r3c/r3e 间不变——候选跨度不变性亦由此旁证） |
| H.L. mentions / keys | 1,264 / 651 | **1,264 / 651** | 一致 |
| P.C. mentions / keys | 683 / 308 | **683 / 308** | 一致（并按提醒未与 App. Cas. 的「683 个潜在净新增组」混淆——两回事） |
| 同时带 H.L. 与 P.C. 的键 | 3 | **3** | 一致 |
| C.A.-like | 1,043 | **1,104** | 复核人的数 = 原文**恰为 `C.A.`** 的条数（本仪器 top raw 表里正是 1,043）；本仪器桶按**归一后 ∈ {CA,ENGCA,EWCA}** 计，多出 `Eng. C.A.` 52、`CA` 3、`E.W.C.A.` 3、`C.A` 2、`CA.` 1 = 61 |
| `us` 带括注 | 16 | **19** | 复核人数的是**非年份**括注（other 16）；本仪器另计 3 条年份括注（如 `(1894)`、`(1969)`） |
| `us` 提及总数 | 3,170 | 3,170 | 一致（此数此前已独立复现过） |

**口径盲区（新测量）**：主正则抓不到的括号标注 **106 条（0.24%）**——嵌套括号
（如 `(Ont. Ct. (Gen. Div.))` ×2，**是真法院标注**，Stage 2 抓取需考虑）与长散文括注
（`sub nom.` 别名引注等，本就不是法院标注）。`( C.A. )` 空格填充形 ×2 亦在盲区，留待
Stage 2 的抓取逻辑用测试覆盖。

**对 Stage 2 的直接输入**（top raw forms）：`H.L.` 1,237 + `U.K. H.L.` 23 +
`U.K.H.L.` 18 + `H.L` 10（HL 族）；`P.C.` 663 + `J.C.P.C.` 13（PC 族）；`C.A.` 1,043
（裸 C.A. → D3：ambiguous_designation，不给法院）；`H.C.` 75、`Aust. H.C.` 30、
`H.C.A.` 27、`Austl. H.C.` 13（HCA 族，D2：只记法院）；`Q.B.` 76、`K.B.` 64、
`Q.B.D.` 17、`Ch. D.` 51、`Ch.` 43、`S.C.` 10、`Div. Ct.` 20、`Ont. S.C.` 19、
`B.C.S.C.` 9（不在封闭表内 → unrecognized）。年份括注 14。

Stage 0 到此为止，先提交再进 Stage 1。