# Demo 候选案例（run_20260913_r2d_c，全部真实数据，均可用 traceback 追到原文）

准备用途：向教授演示。每条给出结论、证据链、复现命令。
措辞边界：断言只能证明「已编码的冲突关系没有被违反」，不能证明「原文里真是引证」；
弃权合规不等于没有漏计。

---

## 成功案例 1：外国来源边（FOREIGN，scope 规则 + 平行汇编合并）

**Thorner v. Major** [2009] UKHL 18——组 `XC-G026547`（组号以最终 run 为准）。
- foreign_status=FOREIGN，origin_country=GB，basis=`court_scope_rule`，
  evidence=`scope:UKHL`（decisions/court_or_reporter_scope.csv：UKHL 中立引用
  2001-01-11 起由法院签发，2009 在窗内；证据链见表内 source_locator）。
- 同组平行汇编：`2009|1|wlr||776`、`2009|3|aller||945`、`2009||aller||945`
  （身份由裁定层合并；dd=5，occ=20）。
- 引用方（前 3）：SCC_2017scc61（提及 8 次）、SCC_2014scc53（4）、SCC_2021scc47（4）。
- 复现：
  `python pipeline/traceback.py --run-dir data/run_20260913_r2d_c --search Thorner`

## 成功案例 2：国内来源（DOMESTIC_CA，SCC 排他规则）

**R. v. Lacasse**——组 `XC-G032199`：foreign_status=DOMESTIC_CA，
origin_country=CA，evidence=`scope:SCC`（Supreme Court Act ss. 3/35/40/52：
管辖限于加拿大法院体系）；组内键 `2015||scc||64`；dd=396。
- 复现：
  `python pipeline/traceback.py --run-dir data/run_20260913_r2d_c --search Lacasse`

## 成功案例 3：坏解析的完整修正（D1/D2/D3 + R2 闭环回归修复）

引证文本 `…Almrei v. Canada (Attorney General) 2011 ONCA, 2011 ONCA 779…`
（引用方 2013 ONCA 375，语料行 19881）：
- 旧管线 winner `2011 ONCA, 2011`（把下一引证的年份误当页码）曾坐进最终表；
- 新路线台账：两个形状读法 → **cross_boundary_invalid**（D3 配对者 = 真引证
  `2011 ONCA 779`，counted）；误析键 `2011||onca||2011` 不在最终表。
- 复现：
  `python pipeline/traceback.py --run-dir data/run_20260913_r2d_c --candidate-id ONCA:19881:8555:8570:shape_neutral_bare`
  （窗口里 `<<2011 ONCA, 2011>>` 即被作废跨度；同命令换
  `ONCA:19881:8566:8579:shape_neutral_bare` 看真引证 counted + 原文窗口）

## 弃权案例：同档平票弃权（UNKNOWN ≠ 错误，也 ≠ 外国）

- **R. v. W.(D.)**（组 dd=693）：只有 S.C.R./C.C.C. 汇编引证、无中立代码、
  不在 case_origin 表 → **UNDETERMINED**（约束四：不填默认值）。
  复现：`python pipeline/traceback.py --run-dir data/run_20260913_r2d_c --search W.(D.)`
- **DTC 系同档平票**（账本 B7）：`2022 DTC 5064` 类——代码在法院代码表与汇编表
  都精确命中 → 两种读法同档 → 全组弃权 0 计数（台账 span_alternative_undecided）。
  这是**规则正确的弃权**，但真实引证仍可能漏计——弃权合规 ≠ 数据完整。
  复现：`python pipeline/traceback.py --run-dir data/run_20260913_r2d_c --search DTC 5064`

## 局限案例（两个，展示已知边界而非隐藏）

1. **P1 相容包含误压（本轮抽查新发现，账本 B10，未修）**：`2007 ONCA 492`
   （Pilot Insurance Co. v. Sutherland）——真中立引证被「(2007), 2007 ONCA 492」
   长误析（vol 槽=年份）以相容包含压制，counted 的是误析键。round-2 之前两读法
   同为弃权；grounded + 包含规则使其恶化。**已知系统性问题，待人工裁表后修**。
   复现：`python pipeline/traceback.py --run-dir data/run_20260913_r2d_c --candidate-id ONCA:10064:20485:20498:shape_vol_abbr_page`
2. **43 条旧 supported lost 的残余**（账本 B7）：42 条仍弃权（同档平票为主）。
   样例 `3 C.C.C. 152`（SCC_1972scr889）——部分重叠、同档、无第三方证据 → 弃权。
   复现：`python pipeline/traceback.py --run-dir data/run_20260913_r2d_c --search 3 C.C.C. 152`
   （逐条清单：`implementation/r2closure_audit/r2c_supported_lost_43.csv`）

## 汇报措辞约束（展示时必说）

1. 仲裁 fail-closed 断言只证明「已编码的冲突关系没有被违反、替代对象最终 counted」，
   **不能**证明原文里真是引证。
2. counted 集合无内部攻击是 grounded 解的**必要条件**，非充分条件。
3. 弃权合规 ≠ 没有漏计；43 条中 42 条弃权是规则正确下的真实召回损失。
4. 本目录是 **demo 候选版，待独立审计**，不是研究数据集验收。
