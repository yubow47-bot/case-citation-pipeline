# 旧 vs 新 差分报告（demo 修复轮 + Round 2 订正，2026-09-12）

- 旧 = `data/`（v1.4 管线产出，金标钉住，未改）
- 新 = `data/run_20260912_r2c/`（candidates-2.0 + R2 订正后的仲裁/溯源/键 v2）
- 金标 `golden_layers.json` 未重写。**口径警示（R2-8）**：`test_layers.py --golden`比对的是 `data/` 旧产出与金标——两者都未改动，故输出「一致」；它检验的是旧产物的稳定性，**对新代码没有任何证明力**。

## 1. 各层计数对照

| 层 | 旧 | 新 | 说明 |
|---|---|---|---|
| extract kept（旧去重路线） | 582408 | — | 新路线 kept/superseded 概念退役：
| extract candidates | — | 1013948 | 全候选（重叠枚举+边界闸；旧 raw≈998465） |
| merge SCC | 126608 keys / occ 347388 | 122650 keys / occ 357975（counted 候选） | 键 v2 + 仲裁 |
| merge ONCA | 79605 keys / occ 171092 | 66438 keys / occ 169739（counted 候选） | 键 v2 + 仲裁 |
| decide 跨院组 | 190153 | 173615 | |
| select 组 kept (dd≥5) | 8610 | 8585 | 门槛语义未动 |

## 2. 新路线仲裁去向（逐候选台账合计）

| 状态 | 候选数 | 说明 |
|---|---|---|
| counted | 527714 | |
| alternative_contained | 251447 | |
| alternative_unsupported_reading | 101848 | |
| span_alternative_undecided | 10340 | |
| overlap_undecided | 1115 | |
| alternative_spanning_mismatch | 1 | |
| alternative_same_key | 15 | |
| cross_boundary_invalid | 1181 | |
| self_citation_row | 101204 | |
| rejected_row | 17659 | |

弃权类（不硬猜，0 计数）：span_alternative_undecided 10340 + overlap_undecided 1115。跨界误解析（D3）作废 1181 条。

## 3. D4/D5 键拆分账

- SCC：旧键 179648 个，其中 666 个拆成多个新键（系列括注/罗马页身份）；映射见 merge_out/SCC/key_mapping.csv
- ONCA：旧键 131072 个，其中 485 个拆成多个新键（系列括注/罗马页身份）；映射见 merge_out/ONCA/key_mapping.csv

## 4. 专案核查（D1–D5 代表案例在两版的落点）


| 核查项 | 结果 | 明细 |
|---|---|---|
| D3 Almrei：误解析页=2011 键不在新表 | PASS | 命中 0 行 |
| D3 Almrei：2011 ONCA 779 在新表 | PASS | occ=4 dd=4 |
| Kvello：2009 SCC 51 单键存在（不按卷读法重计） | PASS | keys=1 occ=21 |
| D4：键含系列槽 2d/3d 的组存在（拆分生效） | PASS | |2d| 8000 组, |3d| 7450 组 |
| D5：罗马页键（ro:*）存在 | PASS | 474 组 |
| 防双计数：每键 counted 候选数 == occurrence_count（两院全表） | PASS | 逐行核对通过 |

## 5. dd 榜首对照（金标 top25 旧 vs 新 top15）

| dd | occ | 案名 |
|---|---|---|
| 694 | 776 | R. v. W.(D.) |
| 601 | 1429 | Housen v. Nikolaisen |
| 414 | 661 | Rizzo & Rizzo Shoes Ltd. (Re) |
| 399 | 485 | Palmer v. The Queen |
| 396 | 872 | R. v. Lacasse |
| 349 | 763 | Sattva Capital Corp. v. Creston Moly Corp |
| 341 | 915 | R. v. Grant |
| 292 | 642 | Hunter v. Southam Inc |
| 291 | 739 | R. v. Oakes |
| 281 | 765 | Bell ExpressVu Limited Partnership v. Rex |
| 274 | 276 | R. v. Kienapple |
| 264 | 549 | R. v. Sheppard |
| 239 | 488 | R. v. Collins |
| 234 | 567 | R. v. Big M Drug Mart Ltd |
| 226 | 502 | R. v. Biniaris |

（旧金标 top25 见 pipeline/tests/golden_layers.json；两版组数不同，逐组对照以 key_mapping.csv 为准。）

## 6. Round 2 全量回归连接（3.2）

### 6.1 legacy 匹配保全（3.2a，目标缺失=0）

| 项 | 数 |
|---|---|
| 旧 extracted+superseded 行连接成功 | 998465 |
| **缺失（目标 0）** | **0** |
| 空引证 id {COURT}_ 排除 | 0 |
| raw 不一致的连接失败 | 0 |

### 6.2 旧 counted 行去向（3.2b；round-1 基线 510,717/713/6,954/96）

| 去向 | Round 1 | Round 2 |
|---|---|---|
| 1 仍被计数 | 510,717 | 512188 |
| 2 身份等价替换（v2 键相同） | 0* | 0 |
| 3 仅重叠 counted 跨度（语义未核实） | 713 | 761 |
| 4 任何地方都没计 | 6,954 | 5531 |
| 5 未枚举/连接未决 | 96 | 0 |
| 合计 | 518,480 | 518480 |

「没计」桶（5531 行）的分解：旧 UNSUPPORTED 5488 / 旧已解析法域 43；新仲裁状态 {"span_alternative_undecided": 4980, "cross_boundary_invalid": 340, "overlap_undecided": 210, "alternative_contained": 1}。
大头是同跨度两读法在两张表里**同档**命中的平票弃权（如 DTC 系：代码在法院代码表与汇编表都精确命中，R2-2 规则规定最高档打平即弃权）——旧管线此时按形状顺序硬选一边计入，属未证实的猜测；新路线按规则弃权并留下台账。340 条 cross_boundary_invalid 是 D3 跨界修正按规则作废的旧赢家。

### 6.3 组级一致性（3.2c）

| 核查 | 数 | 目标/口径 |
|---|---|---|
| 组数 | 173615 | |
| 组内行 group_foreign_status 不一致 | 0 | 0（R2-1 组结论写每行）|
| 多国别却非 CONFLICT 的组 | 0 | 0 |
| case_record 成员落在 UNDETERMINED 组 | 28 | 订正后合法：身份连接是启发式，证据保留不传播（样例含 St. Catharines XC-G000455）|

### 6.4 边计数对照（3.2c 末项）

| foreign_status | Round 1 | Round 2 |
|---|---|---|
| FOREIGN | 227 | 386 |
| DOMESTIC_CA | 35659 | 56685 |
| UNDETERMINED | 294476 | 272765 |
| CONFLICT | 0 | 0 |

增减解释：FOREIGN +159（EWCA Civ/Crim 分辑行生效、R2-2 修好的 FC 等使更多组有锚）；DOMESTIC_CA +21,026（FC/Q.R./L.R. 恢复 + 合格成员聚合不再依赖主行）；UNDETERMINED −21,711 为同一枚举的另一面。增量都有正证据；无「不在表→外国」推断。

### 6.5 案名投票限制测量（R2 §7）

投票行 466862，其中来自非 counted 候选 204048（43.7%）——modal 案名**不是**已核实的身份证据，只作展示列。已测量、已记录；本轮不做名字抽取重构。