# r2d closure report — demo 候选版（2026-09-13）

Run: `data/run_20260913_r2d_b/`（manifest status=complete，input_identity_verified_unchanged=true，
10 步全过；候选爆炸 fail-closed 未触发）。
前次失败运行 `data/run_20260913_r2d/`（merge 步 KIND_PRIORITY KeyError）按规则保留未删。

## 本轮修复（对应两个已确认反例问题）

1. **身份授权**（commit 3d3104f）：显式双语代码表（`decisions/bilingual_neutral_codes.csv`，
   生成器 `decisions/tools/build_bilingual_neutral_codes.py`，verified_explicit_equivalence
   白名单——仅 SCC/CSC）；`same_citation` 仅限全组单键；ELIGIBLE_BASES 由 decide/edges
   共享；反例先行失败后转绿。
2. **仲裁终态**（同 commit）：`arbitrate_document` 重写为等价类 + 攻击图 + grounded
   语义；spanning 为联合前提（依据=严格包含、互不重叠、≥2）；D3 配对者须最终 IN
   才使跨界候选 OUT；互指同档环保持 UNDEC；返回前 fail-closed 断言。
   唯一预授权修改的旧测试：`test_unresolved_suppressor_recycles_dominated`
   （修改前断言与本轮新断言的对照写在该测试 docstring 里）。

## 差异核对

### 7.1 历史差异（Round 1 = `data/run_20260912_final` → r2c = `data/run_20260912_r2c`）

- 逐边身份键 (source_decision, mention_detail_key)：**removed 1,475 / added 949**；
  可复算等式 **330,362 − 1,475 + 949 = 329,836** ✓（与 r2c 实际一致）。
- +840 净残差解释：round-1 交接把「−1,366 自引剔除」当作唯一变化；实际 added 949
  中 **842 条来自新 counted 提及**（FC/Q.R./L.R. 等仲裁恢复的直接产物），另有
  96 条重排组/换键、11 条未分类；removed 侧 1,389 mentions-not-counted（含自引
  剔除）+ 81 重排 + 5 未分类。多类增删相互抵消，**不存在恰好 840 条某类恢复边**。
- 产物：`historical_edge_delta_round1_to_r2c.csv`（逐边方向+成因类）。

### 7.2 本轮差异（r2c → r2d_b）

- 边 329,836 → 330,126（removed 79 / added 369）；FOREIGN 386→384；
  DOMESTIC_CA 56,685→53,948；UNDETERMINED 272,765→275,794；CONFLICT 0→0。
- same_citation 主行降级 **1,343 组**（弱连接不再传播来源地——诚实方向，
  见 identity_basis_downgrades.csv）；组级来源结论变化 3 组
  （group_origin_changes.csv）。
- 仲裁状态变化 655（arbitration_status_changes.csv）：
  cross_boundary_invalid→counted 369（D3 配对者最终未决/OUT 的 grounded 回收）；
  counted→overlap_undecided 92（同档冲突不再被中间胜者掩盖，反例 A/E 语义）；
  span_alternative_undecided→alternative_contained 118；其余零星。
  **recycled_weak_to_counted（压制者 OUT 后弱读法重新 counted）= 0**。
- spanning 联合依据变化：r2c 1 条 spanning_mismatch → r2d 0
  （spanning_joint_basis_changes.csv）。

### 7.3 / 7.4 固定追踪集

- `r2c_supported_lost_43.csv`：43 条（稳定字段 court/sdc/offsets/shape/raw），
  r2d 中 **1 条 counted**、42 条仍未计（mostly 同档平票弃权 DTC 系）。
- `r2c_overlap_only_761.csv`：761 条，r2d 中 **0 条 counted**。
  两表均注明：**重叠覆盖 ≠ 身份等价恢复**；无身份证据不得使用
  recovered-equivalent 标签。

## §8 案名投票敏感性（只比较，不改生产规则）

case_name_modal 路径：merge 两级投票（池口径=本轮唯一自变量）→
decide.cluster_same_case 以 nk(case_name_modal) 聚类（**实际参与案件分组**）。

| 口径 | 组数 | kept 组 (dd≥5) | 边 | FOREIGN | 与 A 的差异 |
|---|---|---|---|---|---|
| A current（生产） | 173,878 | 17,265 | 330,126 | 384 | — |
| B dedup_position | 173,878 | 17,265 | 330,126 | 384 | **全同**（0 变化） |
| C counted_only | 173,969 | 17,232 | 330,099 | 384 | modal 变 5,271；组成员变 241/332；dd 变 0；门槛跨越 0；来源变 0 |

结论（供人工拍板，不自动改规则）：B 口径在本语料上与生产口径完全等价；
C 口径只影响案名列与分组切分，不影响 dd/门槛/来源地/FOREIGN 边。
明细：case_name_sensitivity_summary.json、case_name_sensitivity_groups.csv。

## 边界（不得越界解读）

1. 同起点扫描器不能证明枚举了所有可能解析；D2 通用多解析能力 partial/deferred。
2. 传统 reporter 引证的召回无独立金标验证；43/761 追踪 ≠ 总体召回评估。
3. 案名敏感性 ≠ 案件合并准确率；FOREIGN 边内部一致 ≠ 研究级准确。
4. case_name_modal 实际参与聚类（见上），不是纯展示列。
5. golden 只验证旧产物兼容性；scope 表证据不足的行（candidate_endpoint_pair 等）
   不是 fully verified。
6. 本目录是 **demo 候选版，待独立审计**——不是最终验收，不是研究数据集。
