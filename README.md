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
├── corpus\                        gitignore，只读语料
│   ├── SCC.parquet
│   └── ONCA.parquet
├── decisions\                     进 git，唯一事实源
│   ├── README.md
│   ├── reporter_jurisdiction.csv
│   ├── neutral_court_codes.csv
│   ├── series_prefix.csv
│   └── case_origin.csv
├── pipeline\                      进 git
│   ├── normalize.py
│   ├── shapes.py
│   ├── extract.py
│   ├── classify.py
│   ├── merge.py
│   ├── decide.py
│   ├── select.py
│   └── coverage_report.py
├── data\                          gitignore，派生产物
│   ├── extract_out/{SCC,ONCA}
│   ├── classify_out/{SCC,ONCA}
│   ├── merge_out/{SCC,ONCA}
│   ├── decide_out/{SCC,ONCA,cross_court}
│   └── select_out/
└── _legacy\                       旧管线产物，仅供人工对照
    └── README.md
```

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
