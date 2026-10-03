# 第 1 层 抽取

## 这一层做什么

对每份判决全文，用**结构形状**（正则）找出所有像引证的片段，全量输出，**不筛、不判、不查表**。看一段文本就够做的事，只有这些。

- 输入：`corpus/<法院>.parquet` 的 `unofficial_text_en`（按列投影、流式读，`iter_batches(500)`）。
- 输出（下游唯一输入是全候选路线）：
  - `extract_out/candidates.csv`：schema `candidates-2.2`，每个重叠命中都保留。
  - `extract_out/extracted.csv` 与 `extracted_superseded.csv`：旧“去重”路线，**降级为诊断产物**；金标（`--golden`）读的是它，不要和全候选路线的数字混用。
- 候选行关键字段【已核实：`candidates.csv` 表头】：`candidate_id`、`source_decision_citation`（`{法院}_{nk(citation_en)}`）、`raw_string`、`shape_name`、`match_start_offset`/`match_end_offset`、`token`/`leading_abbr`/`abbr`、`serial_marker`、`vol`、`page`（`page_prefix`/`page_roman`/`page_suffix`）、`series`（`series_paren`/`paren_note`）、`year_raw`/`year_start`、`trailing_paren`、`court_designation_raw`、`preceding_text`（引证前 120 字符）、`structural_conflict`、`parse_signature`。

## 形状（代码里现在是八个，不是规格写的七个）【已核实：`pipeline/shapes.py`，`SHAPE_ORDER`】

顺序：`shape_bracket`、`shape_vol_page_year`、`shape_year_vol_page`、`shape_nominate`、`shape_neutral_bare`、`shape_vol_abbr_page`、`shape_leading_abbr`，第八个是 **`shape_paren_year_abbr_page`**（2026-09-15，PROBLEMS #21 债 1 的修复）。

| 形状 | 结构 | 例子 |
|---|---|---|
| `shape_bracket` | `[年] (卷) 词 页` | `[1978] A.C. 728`、`[1868] UKHL 1` |
| `shape_vol_page_year` | `卷 词 页 (年)` | `389 U.S. 347 (1967)` |
| `shape_year_vol_page` | `(年) 卷 词 页` | `(1936), 83 F. 2d 212` |
| `shape_nominate` | `卷 词 (夹注) 页 (年)` | `2 Q.B. (N.S.) 100 (1893)` |
| `shape_neutral_bare` | `年 代码 (分辑词) 编号` | `2019 SCC 65`、`2003 EWCA Civ 1746` |
| `shape_vol_abbr_page` | `卷 词 (序数) 页`，无年份 | `93 E.R. 664`、`34 D.L.R. (2d) 451` |
| `shape_leading_abbr` | `(年)? 前缀 卷 词 页` | `L.R. 3 H.L. 330` |
| `shape_paren_year_abbr_page` | `(年) 缩写 页`，无卷号 | `(1924) A.C. 222` |

- 共享子式（`_ABBR`、`_YEAR`、`_SEP_COMMA`/`_SEP_TIGHT`、`_ORD`、`_SERP_SLOT`、`_SERIAL_SLOT`、`_PAGE`）集中在 `shapes.py`。
- 第八个是**兜底形状**：只允许在其他形状都不命中的位置生效，重叠抑制在 `extract._apply_fallback_semantics`（`extract.py:165`）做，不在去重里做。这是上次（v1.4）实施又回滚的原因的对症处理（守卫对真实排版失效，误解析压掉正确匹配）。规格正文 §7.1 仍写着“已回滚”，**以代码为准**。
- 形状顺序参与同跨度的最后决胜：`shape_neutral_bare` 必须排在 `shape_vol_abbr_page` 之前（否则 `2019 SCC 65` 被降级成自由缩写）。改顺序要连同回归基线一起重跑。

## 设计要点（改正则前必须知道）

1. **只看结构，不查表**（约束二）。`token` 的限定是“大写开头、无空格、2–12 位、含内部大写交替”，是结构约束，不是法院清单。判断“这个码是不是法院码”是分类层的事。
2. **字面量例外只有一个**：`_ABBR` 段起点 `(?!No\.)`（编号词 `No.` 不吸进缩写，改由 `serial_marker` 捕获，信息重定位）。第二个字面量例外要满足三条：自带可选槽把词挪进有类型字段、自带全套测量、证明信息重定位而非丢弃（规格 §7.2（六））。
3. **分隔符按槽位分配**：年份→卷、缩写→系列/括注/页用 `_SEP_COMMA`（容忍逗号）；前缀→卷、卷→缩写用 `_SEP_TIGHT`（不容逗号）。把逗号放进“前缀→卷”槽会造成案名吞噬（`R. v. Vu, 2013 SCC 60` 被粘成 `Vu, 2013 SCC 60`），实测 98.8% 的吞名来自这个槽（#18）。
4. **不要把逗号放进 `_ABBR` 段内**：`Howard, L.R.` 会被粘成一个缩写（案名吞噬）。`U, S. R.`、`C.B., N.S.,` 因此抽不到，是刻意保留的缺口（#12）。
5. **页码后缀显式捕获**：`212n` 的 `n` 进 `page_suffix`，断言 `(?![A-Za-z0-9])` 封死回溯（#7：旧写法会静默截断成 page=1）。
6. **年份范围统一 1600–2099，不设开关**。
7. **循环顺序：文本在外层、形状在内层**，反过来语料会被读七遍（现在是八遍）。
8. **去重判据是区间重叠、最长跨度优先**，不是起点相同；败者不删，进诊断文件。全候选路线本身保留所有重叠候选，由归并层的仲裁决定谁计数。
9. **字段一律取原始 match 对象的捕获组**，不得对已生成的字符串重新做正则解析。
10. **不设默认年份下限**；要限制就显式传 `--year-from` 并记入 manifest。
11. **`year_start` 恒等于 `year_raw`**。不要写 `year_raw.split("-")[0]`（跨年 `1893-94` 进不了捕获组，那段代码永远不执行，#1）。

## 加新法院时

- **通常不用改抽取层。** 七（八）个形状按结构匹配，对没见过的法院也成立。新法院的引证写法落在已有形状里，缺的是分类层的表。
- **只有“抽不到某种写法”才动抽取层**。找缺口用 `python audit/residual_mining.py --court <码> --out audit/findings/<目录>`（找像引证但没被候选覆盖的字符串，按模板归类，例如 `AZ-50234567`、`J.E. 2004-1234`、`WT/DS58`、`CUB 12345` 这类标识符体系）。
- 新形状的准入判据（PROBLEMS #16 加规格 §4.3）：
  1. 审计环发现缺口，写死判据；
  2. 原型实测收益对误伤比；
  3. 在冻结散文样本上，误报逐条人工归类，**不得出现已知类之外的新误报类**；
  4. `run_regression.py --field-audit` 的字段不变量不违反；
  5. **门 1 零破坏**：全量 kept 差分不破坏任何既有行；
  6. 夹具 exact 档零退化；
  7. 过线才建形状，然后全量重跑、出新 manifest。
- “封版”的含义是“冻结到审计环给出理由为止”，不是永久冻结。全量抽取约 100 秒（SCC+ONCA 单核），真正贵的是 schema 变更而下游已依赖。
- 判决头部的自身引证：SCC、ONCA 每份都印，抽取层会全抽出来，由分类层打 `self_citation` 标记（见 `02_classification.md`）。**新法院要先测头部是否印自身引证**。

## 验证

- `python pipeline/tests/run_regression.py --selftest`（合成判例、去重等价断言）
- `python pipeline/tests/run_regression.py --field-audit`（五条字段不变量）
- `python pipeline/tests/run_regression.py --verify`（按行重读 parquet，核对夹具切片逐字一致）
- `python pipeline/extract.py --fixture-check`（夹具验收门，exact 档 A18/B15/C27/D6）
- 任何 `shapes.py` 改动：回归和 `--field-audit` 两个都必须跑；负对照误报数增加或夹具漏项增加，修改退回重议。
- 召回：`audit/extraction_recall_audit.py` 对语料自带的上游真值 `cases_cited_en` 量召回（SCC/ONCA 主线 98.80%，漏的绝大多数是去重输给粘连案名的更长 span，不是没抽到，#63）。

## 已知的坑和刻意保留的缺口

| # | 内容 | 状态 |
|---|---|---|
| 1 | 跨年年份 `1893-94` 不支持 | 明确不支持 |
| 7 | 页码后缀 `12n` 静默截断成 page=1 | 已修（显式捕获） |
| 12 | `_ABBR` 段内不含逗号：`U, S. R.`、`C.B., N.S.,` 抽不到 | 刻意保留，防案名吞噬 |
| 17 | `shape_neutral_bare` 年份无左侧数字守卫 | 已量化，【待核实】是否处置 |
| 18 | 案名吞噬（leading_abbr 粘成 `Vu, 2013 SCC 60`） | 已修（分隔符按槽位分配） |
| 19 | `F.2d` 序数紧贴缩写零命中 | 已修（粘连变体 `series_glued`） |
| 20 | 页码格式家族：`D/2948`、罗马页 | 已修（`page_prefix`、`page_roman`） |
| 21 | 无卷号圆括号年份 `(1938) S.C.R. 423` | 先回滚，**2026-09-15 以兜底形状重新实现** |
| 22/23 | `CanLII`/`CarswellOnt` 混合大小写码；`O.J. No.` 的 token 被污染 | 已修（token 放宽；`serial_marker`） |
| 24/25 | leading_abbr 的年份前缀；`serial_marker` 作用域 | 已修 |
| 26/27 | leading_abbr 不加序数槽、nominate 不加系列槽 | 刻意保留（实测 40 次全是案名吞噬、0 次） |
| 28–30 | 法语 `no`、撇号 reporter、单字符罗马页 | v1.5 已修 |
| 63 | 召回 98.80% | 已量化 |
| 98 | F6：页码延后形式；F7：制定法方括号年份 | 低频，登记观测 |
| 31 | `CanLII` 伪代码的尾括注法域（`2026 CanLII 88302 (PE IWCAT)`） | 抽取层已加尾括注零宽捕获 `trailing_paren`（candidates-2.1） |

## 来源

规格 §4.3、§7；PROBLEMS #1、#7、#12、#16–#31、#63、#98；代码 `pipeline/shapes.py`、`pipeline/extract.py`、测试 `pipeline/tests/run_regression.py`。

核实状态：形状清单、字段、命令、兜底机制对照代码和 manifest（2026-10-03）【已核实】；设计要点和坑的状态【按规格】。
