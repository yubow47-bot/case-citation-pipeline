# 旧 vs 新 差分报告（demo 修复轮，2026-09-12）

- 旧 = `data/`（v1.4 管线产出，金标钉住，未改）
- 新 = `data/run_20260912_stage2/`（candidates-2.0 + 判决内仲裁 + 键 v2）
- 金标 `golden_layers.json` 未重写；与本报告并存，--golden 的差分即预期中的 schema/口径变更，逐项见下。

## 1. 各层计数对照

| 层 | 旧 | 新 | 说明 |
|---|---|---|---|
| extract kept（旧去重路线） | 582408 | — | 新路线 kept/superseded 概念退役：
| extract candidates | — | 1013819 | 全候选（重叠枚举+边界闸；旧 raw≈998465） |
| merge SCC | 126608 keys / occ 347388 | 122072 keys / occ 356630（counted 候选） | 键 v2 + 仲裁 |
| merge ONCA | 79605 keys / occ 171092 | 66260 keys / occ 169526（counted 候选） | 键 v2 + 仲裁 |
| decide 跨院组 | 190153 | 172916 | |
| select 组 kept (dd≥5) | 8610 | 8578 | 门槛语义未动 |

## 2. 新路线仲裁去向（逐候选台账合计）

| 状态 | 候选数 | 说明 |
|---|---|---|
| counted | 526156 | |
| alternative_contained | 250884 | |
| alternative_unsupported_reading | 101848 | |
| span_alternative_undecided | 12032 | |
| overlap_undecided | 2803 | |
| alternative_spanning_mismatch | 1 | |
| alternative_same_key | 1 | |
| cross_boundary_invalid | 1233 | |
| self_citation_row | 101204 | |
| rejected_row | 17657 | |

弃权类（不硬猜，0 计数）：span_alternative_undecided 12032 + overlap_undecided 2803。跨界误解析（D3）作废 1233 条。

## 3. D4/D5 键拆分账

- SCC：旧键 179617 个，其中 671 个拆成多个新键（系列括注/罗马页身份）；映射见 merge_out/SCC/key_mapping.csv
- ONCA：旧键 131009 个，其中 489 个拆成多个新键（系列括注/罗马页身份）；映射见 merge_out/ONCA/key_mapping.csv

## 4. 专案核查（D1–D5 代表案例在两版的落点）


| 核查项 | 结果 | 明细 |
|---|---|---|
| D3 Almrei：误解析页=2011 键不在新表 | PASS | 命中 0 行 |
| D3 Almrei：2011 ONCA 779 在新表 | PASS | occ=4 dd=4 |
| Kvello：2009 SCC 51 单键存在（不按卷读法重计） | PASS | keys=1 occ=21 |
| D4：键含系列槽 2d/3d 的组存在（拆分生效） | PASS | |2d| 7997 组, |3d| 7445 组 |
| D5：罗马页键（ro:*）存在 | PASS | 474 组 |
| 防双计数：每键 counted 候选数 == occurrence_count（两院全表） | PASS | 逐行核对通过 |

## 5. dd 榜首对照（金标 top25 旧 vs 新 top15）

| dd | occ | 案名 |
|---|---|---|
| 693 | 775 | R. v. W.(D.) |
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