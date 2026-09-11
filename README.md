# 外国引证数据整理抽取管线

从加拿大法院判决全文语料中，抽取被引用的外国判例引证，整理成带案名、法域、引用频次的结构化表格。

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
├── PROBLEMS.md                    进 git，纯记录，不得被脚本读取
├── select_config.yaml
├── download_corpus.sh             语料快照下载脚本（HF 枚举、断点续传、SHA256 校验；bash/WSL）
├── corpus\                        gitignore，只读快照；下载日期与指纹登记于技术规格 §1.3
│   ├── SCC.parquet
│   └── ONCA.parquet
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
├── data\                          gitignore，派生产物
│   ├── extract_out/{SCC,ONCA}
│   ├── classify_out/{SCC,ONCA}
│   ├── merge_out/{SCC,ONCA}
│   ├── decide_out/{SCC,ONCA,cross_court}
│   ├── select_out/
│   └── coverage_out/
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
