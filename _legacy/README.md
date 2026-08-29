# _legacy — 旧管线产物（仅供人工对照）

本目录存放旧管线的全部输出与判断，仅供新表建好后的**逐条差异对照**。

## 规则

1. **新管线的任何脚本不得读取本目录中的任何文件。**
2. 本目录不进 git（`.gitignore` 未排除它，但其内容不应被纳入版本控制）。
3. 旧文件在这里的唯一用途：新表建好后逐条对比，一致的提高可信度，不一致的优先人工复核。

## 文件清单

| 文件 | 说明 |
|------|------|
| `abbreviations_final.csv` | 旧最终缩写法域表 |
| `canonical_abbreviations_v2.csv` | 规范缩写 v2 |
| `canonical_abbreviations.csv` | 规范缩写 v1 |
| `_pre1900_layer1_inferred.csv` | pre-1900 缩写推断层 |
| `_pre1900_unclassified_abbrevs.csv` | pre-1900 未分类缩写 |
| `spelling_variants.txt` | 拼写变体对照 |
| `foreign_citations_ranked_v2.csv` | 外引排名表（分类层输出） |
| `citations_with_case_names_SCC.csv` | SCC 带案名引用明细 |
| `citations_with_case_names_ONCA.csv` | ONCA 带案名引用明细 |
| `citations_with_case_names_SCC_widened.csv` | SCC widened 实验产物 |
| `citations_with_case_names_ONCA_widened.csv` | ONCA widened 实验产物 |
| `citations_with_case_names_root.csv` | 根目录不明来源合并件 |
| `product_candidates_v4.csv` | 最终产品候选表 v4 |
