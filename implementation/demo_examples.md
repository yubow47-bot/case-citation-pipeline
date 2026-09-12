# 演示样例（真实运行产物，data/run_20260912_final）

全部来自本轮全量运行的真实语料数据；测试用合成数据只在 pipeline/tests/ 并明确标注。

## 1. 外国来源案件 + 引用它的判决

**Thorner v. Major** [2009] UKHL 18（英国上议院）——组 `XC-G026547`
- foreign_status=FOREIGN，origin_country=GB，basis=`court_scope_rule`，evidence=`scope:UKHL`（decisions/court_or_reporter_scope.csv：UKHL 中立引用 2001 年起由法院签发；本例 2009 在窗内）
- 同组平行汇编（身份由裁定层合并）：`2009|1|wlr||776`, `2009|3|aller||945`, `2009||aller||945`, `2009||ukhl||18`
- dd=5，occurrence=20；引用它的判决（按提及次数前 3）：
  - `SCC_2017scc61`：提及 8 次（mention_detail_key 可回连逐候选台账）
  - `SCC_2014scc53`：提及 4 次（mention_detail_key 可回连逐候选台账）
  - `SCC_2021scc47`：提及 4 次（mention_detail_key 可回连逐候选台账）

## 2. 国内来源案件（DOMESTIC_CA）

**R. v. Lacasse**（组 `XC-G032199`）：foreign_status=DOMESTIC_CA，origin_country=CA，basis=`court_scope_rule`，evidence=`scope:SCC`；dd=396
- 来源地证据：组内中立引用键 `2015||scc||64` 落 SCC 排他规则（加拿大最高法院只审理源自加拿大法院体系的案件）
  - 引用方 `SCC_2021scc46`：提及 12 次
  - 引用方 `SCC_2022scc37`：提及 10 次

## 3. 显式未知（UNKNOWN ≠ 错误，也 ≠ 外国）

**R. v. W.(D.)**（组 `XC-G009597`，dd=693）：foreign_status=**UNDETERMINED**。该案 1991 年判决，引用它的判决只有 S.C.R./C.C.C. 汇编式引证（无中立代码），不在 case_origin 表、也不适用任何 scope 规则——按约束四不填默认值，显式留未知。

## 4. 已知坏解析的完整修正轨迹（D1/D2/D3）

引证文本 `…Almrei v. Canada (Attorney General) 2011 ONCA, 2011 ONCA 779…`（引用方判决：ONCA_2013onca375，语料行 19881）。旧管线（非重叠扫描 + 最长跨度去重）的winner 是 `2011 ONCA, 2011`（把下一个引证的年份误当自己的页码），曾以 dd=1、kept=false 坐进最终表。新路线的仲裁台账：
  - `ONCA:19881:8555:8570:shape_neutral_bare`：raw='2011 ONCA, 2011' shape=shape_neutral_bare → **cross_boundary_invalid**（D3 旗 cross_boundary_year_page；让位于 ONCA:19881:8566:8579:shape_neutral_bare）
  - `ONCA:19881:8555:8570:shape_vol_abbr_page`：raw='2011 ONCA, 2011' shape=shape_vol_abbr_page → **cross_boundary_invalid**（D3 旗 cross_boundary_year_page；让位于 ONCA:19881:8566:8579:shape_neutral_bare）
  - `ONCA:19881:8566:8579:shape_neutral_bare`：raw='2011 ONCA 779' shape=shape_neutral_bare → **counted**（真引证，键 `2011||onca||779`进最终表；同跨度的卷读法 alternative_unsupported_reading）
  - 复现命令：`python pipeline/traceback.py --run-dir data/run_20260912_final --candidate-id ONCA:19881:8566:8579:shape_neutral_bare`

## 5. 从最终结果回到原文与判断依据

```
# 粗搜（按案名/原文串找 candidate_id）
python pipeline/traceback.py --run-dir data/run_20260912_final --search Thorner
# 深查：回显分类证据 + 仲裁状态 + 原文窗口（<<…>> 标出候选跨度）
python pipeline/traceback.py --run-dir data/run_20260912_final \
    --candidate-id <台账里的 candidate_id>
# 台账：merge_out/{SCC,ONCA}/mentions_candidates.csv（逐候选仲裁状态）
# 边：edges/citation_edges.csv；mention_detail_key 回连上表
```