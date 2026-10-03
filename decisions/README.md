# decisions/ — 人工判断，唯一事实源

四张表是整个项目里唯一不可再生的东西，全部进 git。

| 表 | 用途 |
|---|---|
| `reporter_jurisdiction.csv` | 缩写到法域（分类层主要事实源） |
| `neutral_court_codes.csv` | 中立引用法院代码（封闭穷举）——**已填，300 行**，源 CanLII API v1 caseBrowse，覆盖语料中立引用 96.5%，见规格 §5.2 |
| `series_prefix.csv` | 系列汇编前缀（L.R. 家族） |
| `case_origin.csv` | 案件真实来源地（主要针对 JCPC 案件）——**已填 203 行**：CanLII `ukpc` 库（枢密院对加拿大上诉）1888–1959 年内的对上者；库外一律 UNDETERMINED，见 PROBLEMS #59 |

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
| `build_case_origin.py` | `case_origin.csv` 的枢密院部分（源：CanLII API v1 caseBrowse `ukpc`，枢密院对加拿大上诉）＋报告 `audit/findings/case_origin_review.md`（可重放） |

```
set CANLII_API_KEY=...
python decisions/tools/build_neutral_court_codes.py --cache-dir <缓存目录>
python decisions/tools/build_neutral_court_codes.py --cache-dir <缓存目录> --offline   # 只重建表

python decisions/tools/build_case_origin.py --key-file <key 文件>     # 抓 ukpc 全表并重建
python decisions/tools/build_case_origin.py --offline                  # 只用缓存重建（缓存默认 data/canlii_cache）
```

API key 走环境变量或 `--key-file`，**不进仓库、不写进任何输出**。抓取限速 1 秒/次。
缓存是机器产物，不进 git——每一行的 `source_locator` 自带可重放的端点 URL，逐行可独立复核。
`build_case_origin.py` 的缓存固定落在 `data/canlii_cache/ukpc_list.json`（仓库内、gitignore）：
缓存留在会话临时目录会让 `--offline` 只在一台机器上可复现（PROBLEMS #59）。

## `reporter_jurisdiction.csv` 的 `verification_level`

管线**不读**这一列，它只记这一行的法域判断有多硬的证据。

| 值 | 含义 |
|---|---|
| `name_inference` | 据缩写全称推断，未核对任何来源 |
| `verified_print_evidence` | 语料印刷证据支持（六渠道，`audit/findings/jurisdiction_channels/`；机器整理，未人工复核） |
| `verified_authority` | 外部权威资料列明该汇编的身份与表列法域（2026-10-02 代理审批，非人工复核）；不证明逐案来源或独占范围 |
| `authority_identity_only` | 外部资料只支持汇编身份，表列法域/省份范围未经该资料确认（如 `Nfld. & P.E.I.R.`） |
| `authority_country_only` | 外部资料只支持到国家层，省级未核（如 `Sask. L.R.`） |

`S.J.` 按卷号拆两行（PROBLEMS #100）：有卷号归英国 Solicitors' Journal，无卷号 `[YYYY] S.J. No. N` 归萨斯喀彻温（Quicklaw）。
