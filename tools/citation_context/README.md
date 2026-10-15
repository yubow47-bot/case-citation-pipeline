# 引文上下文实验工具 v3

把现有引用边展开成可查看的原文提及、短引候选和处理词语信号，并支持可复跑的多法院探索批次。
输入来自当前 `data/active_run.json` 指向的研究数据库、运行账本及原始 Parquet 文本。
只读这些输入，结果另存为独立实验包；不改生产 DD、案件身份决定或人工标签。

以当前已计数引用边的完整引文作为解析种子，给这些边补充上下文、短引和案名提及。
未链接的完整引文保留为阻断先行词的记录；未解析、歧义和被阻断的短引也全部保留。
它不会通过短引建立新的生产案件身份或新增生产引用边。

在仓库根目录运行，使用现有 Python 环境即可；除项目已有的 `pyarrow` 外，无需新增 pip 依赖。

## 先做一个小实验

以下命令适用于 PowerShell；输出目录必须尚不存在。

```powershell
# 1. sources：按已记录的案名或引文查找来源判决
python tools/citation_context/context.py sources "2002 SCC 33"
python tools/citation_context/context.py sources "2007 BCCA 234"

# 2. build：选两份来源判决，生成一个实验包
python tools/citation_context/context.py build --source "2002 SCC 33" --source "2007 BCCA 234" --output-dir audit/findings/citation_context_try1

# 3. inspect：查看实验包中的未解析、歧义或被阻断短引
python tools/citation_context/context.py inspect audit/findings/citation_context_try1 --unresolved --limit 20

# 查看处理词语信号、目标组汇总或来源文档
python tools/citation_context/context.py inspect audit/findings/citation_context_try1 --table observations --limit 20
python tools/citation_context/context.py inspect audit/findings/citation_context_try1 --table edges --limit 20
python tools/citation_context/context.py inspect audit/findings/citation_context_try1 --table documents
```

完成后用浏览器打开输出目录内的 `report.html`，可搜索案名、原文、状态和目标组，并展开各来源文档。
报告完全离线；页面只显示片段，完整实验记录以 JSONL 为准。

`sources` 可加 `--court SCC`、`--limit 20`。`build --source` 接受精确引文或来源 ID，可重复使用；
`build --group` 则选择引用某个当前运行目标组的来源判决，可配合重复的 `--court` 和 `--limit`。
不指定来源时默认取 24 个来源，按法院轮流选取各自最前面的语料行；这是探索批次，不是概率样本或统计评估。
`--limit` 范围为 1–200，显式 `--source` 不会按它截断；同一来源的重复语料行仍分别保留。

按这轮关心的规则缩小检查范围：

```powershell
python tools/citation_context/context.py inspect data/experiments/context_batch120 --kind ibid --unresolved --summary-only
python tools/citation_context/context.py inspect data/experiments/context_batch120 --kind supra --quoted --limit 20
python tools/citation_context/context.py inspect data/experiments/context_batch120 --table observations --speaker reported_case --limit 20
```

`--kind` 和 `--status` 可重复指定；`--basis` 精确匹配短引解析依据。`--summary-only` 对全部匹配记录统计，
不受显示条数影响；`--quoted` 依赖 v3 的引号范围元数据，包含可靠和边界存疑的范围。

例如另建一个六份判决的小批次：

```powershell
python tools/citation_context/context.py build --court SCC --court BCCA --limit 6 --output-dir data/experiments/citation_context_try2
```

扩大到 120 份真实判决，并保存可复跑的来源名单：

```powershell
python tools/citation_context/context.py cohort --limit 120 --seed 20261015 --output data/experiments/context_cohort.json
python tools/citation_context/context.py build --sources-file data/experiments/context_cohort.json --output-dir data/experiments/context_batch120
```

`cohort --include-package data/experiments/citation_context_try2` 可以把之前的案例保留进新批次。
扫描本地原始语料后，按法院、实际选取的英法文本字段和 ibid/id/supra/précité 形态轮流选取来源，
每个桶内部按 seed 与来源 ID 的稳定哈希排序，同时纳入没有这些标记的文档。
这是为了发现规则缺口而有意平衡的探索批次，不能据此估计总体准确率。
名单绑定当前运行和输入指纹；换运行后会拒绝直接复用。`--sources-file` 与 `--source` 二选一。

输出只允许放在 `audit/findings/` 或 `data/experiments/` 下的新子目录，已有目录不会覆盖。
单个实验包最多 96 MiB；过大时减少来源数量。`inspect` 直接读取实验包，无需重新读取语料；
可用 `--table`、`--source`、`--group` 筛选，其中 `--source` 必须是来源 ID；`--unresolved` 仅适用于 `mentions`。

## 输出文件

| 文件 | 内容 |
| --- | --- |
| `manifest.json` | 运行 ID、输入指纹、选取方式、规则版本、代码与输出文件哈希、汇总及限制 |
| `documents.jsonl` | 来源 ID、语料行、实际文本字段、文本 SHA-256、引号范围和逐文档计数 |
| `mentions.jsonl` | 完整引文、短引候选与案名提及、原文偏移、别名证据、解析依据和关联信号 |
| `observations.jsonl` | 每个处理词语信号、原文证据、候选目标、状态和语境提示 |
| `edges.jsonl` | 每个文档—目标组的提及与词语建议汇总，同时转述生产边信息 |
| `report.html` | 可搜索、展开的中文离线查看器 |

## 怎么读结果

`mentions` 的 `kind` 包括 `full / ibid / id / supra / precite / case_name`。
`case_name` 是从同一判决已知完整引文产生的案名提及，与短引标记分开计数。
短引的 `resolution_status` 为 `resolved / ambiguous / unresolved / blocked`；只有 `resolved` 带已链接目标。
核查时结合 `target_group_id`、`candidate_target_ids`、`antecedent_mention_ids`、`resolution_basis` 和 `notes`，
不要把候选目标当成已确认链接。`identity_status`、`edge_support`、`counted_edge` 继承现有生产证据，机器短引链接不提升身份可信度。

`observations.status=suggested` 表示有局部语法方向支持目标的词语建议，仍待人工判断。
主动态宾语、被动态主语等规则把实际被评价的目标与同句其他案例区分开；只处在同一分句不足以指派。
`target_mention_ids` 记录实际目标提及，`candidate_mention_ids` 保留候选，`context_mention_ids` 保留同句语境，
`attribution_basis` 记录所用方向和原文跨度。`mention_ids` 保留兼容的局部候选集合，不能当作实际被评价提及。
`context_required` 保留需要结合语境解释的信号，如否定、当事人主张、引用转述、异议意见或缺少局部引文；
`ambiguous` 表示多个目标或未解析提及妨碍指派。`flags`、`negated`、`assignment_reason` 保留原因。
`speaker_attribution / speaker_evidence` 仅根据明确原文记录发言者类型及证据，缺少证据时为 `unknown`。
`context_owner_group_id / context_owner_mention_ids / context_owner_basis` 表示被转述的来源案例，
与实际受到评价的 `target_group_id` 分开；一个案例被当作引述来源，不等于当前判决对它作了 Treatment。
边上的 `reported_source_observation_ids / reported_source_signals` 保留这种来源关系，不计入处理标签或提及覆盖。
词表涵盖 applied、followed、adopted、distinguished、criticized、overruled、considered、discussed、mentioned、affirmed、reversed 及部分法语词形。
affirmed/reversed 是程序性信号，不能直接视为对先例效力的判断。

`edges.treatment_suggestions` 只汇总未否定的实质 `suggested` 信号；需语境复核的词语另放在 `context_required_labels` 和 `context_required_signals`。
affirmed/reversed 独立进入 `procedural_labels / procedural_signals`。
同一目标可以保留多种建议；`machine_summary` 汇集证据，`label_conflicts` 显示可能互相冲突的信号，不选一个标签覆盖其他证据。
`mention_treatments` 区分已指派建议、需语境复核、仅程序信号与未知；`unknown_mention_ids / unknown_mention_count` 统计尚无已指派信号的提及。
`coverage_status` 和未覆盖提及只描述词语覆盖，未检出不表示“中性处理”。
提及、观察与边都有稳定 ID；`assigned_observation_ids / candidate_observation_ids` 和 `edge_id` 支持双向追溯。
HTML 可点击先行提及、信号和目标边；没有局部引文的通用信号每篇最多展示 50 条，完整记录仍在 JSONL 中。
`production_dd` 保持原值；重复来源语料行的汇总不能相加当作新的 DD。

## 规则窗口与已知边界

- 偏移是原始 Python Unicode 字符串的 `[start,end)`，不是字节位置；文本未经归一化。展示窗口为前 220、后 240 字符。
- ibid/id 的基础规则接受最近引文簇或已安全解析短引之后、最多 220 字符的引文式间隔。补充的引述桥接规则必须有明确来源证据；普通叙述、未知权威或跨引述范围不能仅凭距离链接。
- 命名 supra/précité 搜索同文档内全部较早完整引文，检查标记前最多 180 字符的名称；同名目标冲突保留歧义，通用王室名称不单独用作别名。
- 允许显式当事人别名去掉平衡括号限定语和末尾 Inc/Ltd/Limited/Corp/Corporation，记录依据；不任取首词或姓氏，不改变全局案件身份。
- v2 从完整引文前的本地案名、引文后明确声明的简称补充别名，保留原文跨度；不猜测英法译名。明确的论文/书籍来源不能成为短引案件种子，原生产记录仍保留。
- 案名提及只使用已出现的案件种子，排除通用地名、王室名称和重叠引文；同名冲突仍保留候选。
- 引用列表的连接词只在前面已有完整引用边界时解析，不把真正的双案名自动压成一个目标；边界原文另存为 `list_boundary_evidence`。支持法语 `à la p.` 和 `aux pp. 67 à 70` 定位。
- 只向前找先行词；裸 supra/précité 不自动链接最近案件。数字行标可能是判决段号；仅凭它的脚注候选保留歧义，明确脚注区或独立名称证据才允许解析。
- 书籍、法条、普通名词的 précité、`20 id.226` 报告集简写和大写 ID 等可能保留为被阻断候选。
- 短引与 Treatment 共用引号范围，`quotation_scope / quote_scope` 记录原文起止、闭合状态、嵌套关系和边界依据。`scope_id` 在每个文档内使用。
- 不匹配或缺失的引号按语料段落边界截断并标为存疑，避免污染后续整篇判决。同一可靠引述范围内可以确认引用身份，但不因此确认当前法院的处理态度。
- 英法模式同时运行；实际内容语言未必与语料字段标签一致。
- 处理建议按句子/分句的词语规则产生；否定只检查信号前最多 75 字符内最后六个词，不能完整理解论证、发言者、引用或多数/异议意见。
- 明确的其他法院或下级法官行为保留目标、标记为转述；一般代词和 “the Court” 的指向仍可能不明。程序历史中 `, affirmed [后案引文]` 保留候选，避免把维持原判的案例误当作被维持的案例。
- `applying … is not analytically sound` 的拒绝适用表述和 `Court of Appeal erred in applying …` 的争议转述保留目标与精确证据，归入需语境复核；不把对“是否合理”的否定等同于“没有适用”的事实判断。
- 裸案名仍是实验性提及，常见司法角色、人名称谓和调查名称会被排除或阻断；其他同名实体可能仍需人工辨别。引号标题规则可能保守地阻断紧跟引述观点的真实案件种子，完整生产边仍保留。
- 记录选定原文的 SHA-256 并核验完整引文跨度；每次实验不重新哈希整个语料文件。当前生产身份的不确定性继续保留。

## 本地开发

```powershell
python -m unittest discover -s tools/citation_context -p "test_*.py"
```

该模块直接只读当前研究 SQLite、gzip/CSV 账本和 Parquet，不依赖研究界面的辅助代码。
旧 v1/v2 实验包仍可用 `inspect` 读取。

## 2026-10-15 扩大试跑

本轮选取 120 份原始判决（SCC 54、ONCA 37、BCCA 29），其中 29 份使用法文文本字段。
578 个短引标记中，213 个已链接、198 个未解析、25 个有歧义、142 个被规则阻断。
同一批原始 16 份判决的 99 个短引标记，已链接数由 48 增至 57；另纠正两条 Baker 案误连到论文的关系。
这些是机器规则的输出数量，不是人工核验准确率；未解析项包含书籍、法条和语境不足的引用。

另记录 3,673 个案名候选、4,010 个词语观察和 2,698 条文档目标组汇总，原生产 DD 保持不变。
66 项针对性测试通过，实验包文件哈希、原文跨度、记录 ID 与报告内链接检查通过。
[结果摘要](../../audit/findings/citation_context_20261015/summary.json) 和 [120 份来源名单](../../audit/findings/citation_context_20261015/cohort120.json) 随代码保存；完整 JSONL/HTML 包保留在本地 `data/experiments/citation_context_expanded120_final_20261015/`。

```powershell
python tools/citation_context/context.py build --sources-file audit/findings/citation_context_20261015/cohort120.json --output-dir data/experiments/context_replay120
```

## 2026-10-15 引述范围与来源归属续建

同一批 120 份判决、同一组 578 个短引标记重跑后，已链接由 213 增至 301：新增 83 个 supra 和 5 个 ibid，原有 213 个目标保持不变。
5 个 ibid 分别接到 Cooper、Starson、Oakes（两处）和 Beaulac，依据是同段内明确的案例引述来源。
余下 198 个未解析、43 个被阻断、36 个有歧义，完整保留供后续推进。

这一轮修复了失配引号延伸到后续段落的范围问题，并补充首字母案名标点、通用共同当事人后缀和嵌套标题规则。
原先 100 个“引号内短引”阻断项中，56 个现已链接；这主要是修复引号范围误判，不能解释为解决了 56 个真正的引号内引用。
新范围规则下，这批语料仍有 2 个引号内短引，均保留阻断；同一可靠引述范围内的解析能力另由针对性案例覆盖。
旧式匿名报告集后的 `Id. p.` 继续保留候选，避免把另一页的报告引文误当作同案。

4,010 个 Treatment 观察中，109 个记录了明确的来源案例；报告可分别追溯来源案例、被评价目标和发言者证据。
原先 14 个词语建议中的 13 个改为需结合语境复核，目标关系保留；全批次现有 3 个词语建议。
来源案例关系单独汇总到边，不增加该案例的 Treatment 标签。2,698 条文档目标组的生产计数与 DD 保持不变。

104 项针对性测试通过，文件哈希、记录引用、引号范围和报告内链接检查通过。
[本轮结果与逐项变化](../../audit/findings/citation_context_20261015_round2/summary.json) 随代码保存；完整实验包在本地 `data/experiments/citation_context_quote_scope120_final_20261015/`。

```powershell
python tools/citation_context/context.py inspect data/experiments/citation_context_quote_scope120_final_20261015 --kind ibid --status resolved
python tools/citation_context/context.py inspect data/experiments/citation_context_quote_scope120_final_20261015 --table observations --speaker reported_case --summary-only
```
