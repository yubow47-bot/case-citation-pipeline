# 实验线 exp/bcca-citt：BCCA + CITT 首跑发现（2026-09-17）

run：`data/run_bcca_citt_full`（`PIPELINE_COURTS=BCCA,CITT`，complete）。语料来自 a2aj/canadian-case-law：
BCCA 14,703 份、CITT 5,356 份。口径：merge_out/*/mentions_candidates.csv 中 arbitration_status=counted。

| 法院 | counted | 自引行 | 法域可判定 | 日期误抽（UNSUPPORTED 且含月份） |
|---|---|---|---|---|
| SCC（主线 r21a） | 361,455 | 30,109 | 89.4% | 0.5% |
| ONCA（主线 r21a） | 171,281 | 71,098 | 96.4% | 0.7% |
| BCCA | 218,601 | 52,064 | 83.5% | **13.8%** |
| CITT | 43,606 | **0** | **11.6%** | **60.9%** |

选取层 dd≥5 保留 10,884 组，其中 2,694 组 UNSUPPORTED，**2,495 组是日期**（BCCA 1,771、CITT 724），
排进前列：`1 January 1994` dd=517、`18 July 1994` dd=472、`17 December 1992` dd=433。

## E1 日期被当成 vol-abbr-page（抽取层，真缺陷，主线也有但被掩盖）
`1 June 2007` 结构上等于 `vol abbr page`（日 月 年）。ONCA/SCC 写 `June 1, 2007`，不撞形状，所以主线
只有 0.5–0.7%；BCCA 判决头写 `Vancouver, British Columbia 1 June 2007`，CITT 满篇协定日期。
按约束一应在抽取/分类层修；约束二禁缩写表，但月份名是封闭的日历词而非缩写，需用户裁定能否作为结构性排除。

## E2 CITT 自引为 0（#54/#55 身份机制失效）
CITT 的 `citation_en` 是案卷号（`CITT PR-2009-010`），不是中立引证，判决头也不印可抽取的引证，
所以自引标记和"语料判决自身引证=身份锚"都没有输入。影响面待测。

## E3 CITT 表格数据被当成引证
关税/产品规格表：`2 X 3`、`4 CXC 11`、`007 BTM FRAME 49`（约 5,000+ 行 counted，72 组进 kept）。

## E4 CITT 专门报告集不在决策表
`T.B.R.`（Tariff Board Reports）、`C.E.R.`（Canadian Customs and Excise Reports）、`Can. T.S.`、`T.C.T.` → UNSUPPORTED。
正确行为（约束四），需要补表。

## E5 WTO 引证不可见
152/5,342 份 CITT 判决出现 `WT/DS…`，没有对应形状，抽取层看不到——"外国引证"在 CITT 上被系统性低估。

## BCCA 其余正常
BC 81,828 / CA 78,189 为主，自引识别正常；非日期的 UNSUPPORTED 分布（No./Rev./L.J./P.E.I.R.）与 ONCA 一致。
