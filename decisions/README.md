# decisions/ — 人工判断，唯一事实源

四张表是整个项目里唯一不可再生的东西，全部进 git。

| 表 | 用途 |
|---|---|
| `reporter_jurisdiction.csv` | 缩写到法域（分类层主要事实源） |
| `neutral_court_codes.csv` | 中立引用法院代码（封闭穷举） |
| `series_prefix.csv` | 系列汇编前缀（L.R. 家族） |
| `case_origin.csv` | 案件真实来源地（主要针对 JCPC 案件） |

## 规则

- 每一行必须带 `source` 和 `source_locator` 两列
- 判定不得写在代码里
- 键必须是印刷事实（缩写、法院代码、引证串本身），不得使用管线计算出的分组标识
