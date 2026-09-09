# decisions/ — 人工判断，唯一事实源

四张表是整个项目里唯一不可再生的东西，全部进 git。

| 表 | 用途 |
|---|---|
| `reporter_jurisdiction.csv` | 缩写到法域（分类层主要事实源） |
| `neutral_court_codes.csv` | 中立引用法院代码（封闭穷举）——**已填，300 行**，源 CanLII API v1 caseBrowse，覆盖语料中立引用 96.5%，见规格 §5.2 |
| `series_prefix.csv` | 系列汇编前缀（L.R. 家族） |
| `case_origin.csv` | 案件真实来源地（主要针对 JCPC 案件） |

## 规则

- 每一行必须带 `source` 和 `source_locator` 两列
- 判定不得写在代码里
- 键必须是印刷事实（缩写、法院代码、引证串本身），不得使用管线计算出的分组标识

## `tools/`

建表工具，**不属于生产线**（膜的规则见 `audit/README.md`）：它产出的是决策表行，不是管线数据。
管线只读 `decisions/*.csv`，从不调用这些脚本，也从不联网。只在人决定重建/扩充某张表时手动运行。

| 脚本 | 产出 |
|---|---|
| `build_neutral_court_codes.py` | `neutral_court_codes.csv`（源：CanLII API v1 caseBrowse） |

```
set CANLII_API_KEY=...
python decisions/tools/build_neutral_court_codes.py --cache-dir <缓存目录>
python decisions/tools/build_neutral_court_codes.py --cache-dir <缓存目录> --offline   # 只重建表
```

API key 走环境变量或 `--key-file`，**不进仓库、不写进任何输出**。抓取限速 1 秒/次。
缓存是机器产物，不进 git——每一行的 `source_locator` 自带可重放的端点 URL，逐行可独立复核。
