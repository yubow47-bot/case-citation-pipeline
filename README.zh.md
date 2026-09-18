# 判决引证全量统计管线

**中文** | [English](README.md)

从加拿大法院判决全文语料中，结构化抽取判决引用的**全部案例引证**——外国与国内、中立与汇编、数据库与厂商标识符均在范围内——整理成带案名、法域、来源地、引用频次的统计表格。用途是学术研究：对法庭历史中被引案件的完整图景做可审计的统计。

**语料来源：[`a2aj/canadian-case-law`](https://huggingface.co/datasets/a2aj/canadian-case-law)**（HuggingFace 数据集，Parquet），**不是本项目自行采集的语料**。截至 2026-09-18 含三个法院（BCCA 在 `exp/bcca-citt` 分支验证后并入——它在验证跑上达到的法域可判定率与 ONCA 持平，见 `implementation/exp_bcca_citt_findings.md`）：加拿大最高法院（SCC，10,891 份，1877–2026）、安大略上诉法院（ONCA，24,089 份，1998–2026）与卑诗上诉法院（BCCA，14,703 份，1999–2026）；省高等法院、除 ONCA/BCCA 外的上诉法院、联邦法院与行政裁判所均不在语料内（详见 [`USAGE.md`](USAGE.md) 第 1 节）。法院范围可配置（`PIPELINE_COURTS`，见 `pipeline/run_all.py --help`）；同一实验分支上还验证过一个联邦裁判所（CITT），但尚未并入默认范围——它的法域可判定率（28.4%）反映的是这类机构本身的结构差异（关税表格数据、专门报告集尚未入表），不是管线缺陷。

**读数据之前先读 [`USAGE.md`](USAGE.md)**：它写清了「被引 N 次」到底量的是什么、`dd` 与
`occurrence_count` 的区别、门槛值未校准、法域与来源地是两件事，以及一份完整的少算清单。

## 五层架构

1. **抽取** — 结构匹配，全量输出，不筛不判
2. **分类** — 逐行独立：查表定法域、切分案名候选、标记误报
3. **归并** — 跨行统计：同串合并、变体折叠、案名众数投票
4. **裁定** — 案件身份：来源地判定、平行汇编合并、跨法院合并、同名异案拆分
5. **选取** — 一道门槛，不删行，打标记

## 目录结构

```
D:\cases data analisis\
├── .gitignore
├── README.md
├── USAGE.md                       使用与解读说明（读数据前先读）
├── PROBLEMS.md                    进 git，纯记录，不得被脚本读取
├── select_config.yaml
├── download_corpus.sh             语料快照下载脚本（HF 枚举、断点续传、SHA256 校验；bash/WSL）
├── corpus\                        gitignore，只读快照；下载日期与指纹登记于技术规格 §1.3
│   ├── SCC.parquet
│   ├── ONCA.parquet
│   └── BCCA.parquet
├── decisions\                     进 git，唯一事实源
│   ├── README.md
│   ├── reporter_jurisdiction.csv
│   ├── neutral_court_codes.csv
│   ├── series_prefix.csv
│   └── case_origin.csv
├── audit\                         进 git，审计环：产出是提案不是数据（规则见 audit/README.md）
│   └── findings\                  分诊移交、溯源提案、排除清单
├── pipeline\                      进 git
│   ├── normalize.py
│   ├── shapes.py
│   ├── extract.py
│   ├── classify.py
│   ├── merge.py
│   ├── decide.py
│   ├── select.py
│   ├── coverage_report.py         填表优先级报告（§12.1）
│   └── tests\                      run_regression.py（抽取层）、test_layers.py（第 2–5 层）、golden_layers.json（全量金标）
├── implementation\                进 git，会话报告与探针；run_registry.csv + rebuild_run.py 管旧 run 的重建
├── data\                          gitignore，派生产物（每个目录是什么、保留规则：data/README.md）
│   ├── run_20260915_r21a\         ★ 交付 run（2026-09-15 起，#21/债 1 修复，见 implementation/r21_fix_report.md）
│   ├── run_20260914_r4c\          上一交付 run，保留供对照（切换前的交付物）
│   ├── run_20260913_r3e\          上一基线（R4 复核读它，完整保留）
│   ├── run_2026091x_*\            5 个历史 run，只留答案层或敏感性产物（不可重建，旧探针的输入）
│   ├── extract_out … coverage_out 老路线产出 6 个目录（--golden 金标门与 USAGE §8 的锚）
│   ├── audit\                     改前快照与测量输出
│   └── canlii_cache\              build_case_origin.py --offline 依赖
└── _legacy\                       旧管线产物，仅供人工对照
    └── README.md
```

## 运行

完整执行顺序与命令见技术规格 §12。改动任何一层之后：

```bash
python pipeline/tests/run_regression.py --selftest
python pipeline/tests/test_layers.py
python pipeline/tests/test_layers.py --golden
```

实现中对规格的补充与偏离都登记在 PROBLEMS.md，规格里以「实现注记（v1.6）」标出，待人复核。

## 约束

详见技术规格。核心几条：
- 问题必须在产生它的那一层修复
- 抽取层禁止使用固定缩写清单
- 法域判定不依赖周边文本关键词
- 查不到就是 UNSUPPORTED
- 不删行，只打标记
- 层与层单向，每层只跑一次
- 决策表的键必须是判决书上印着的事实
- 每一行必须带出处
