# PROBLEMS #52：同形异义消歧的三道验证

仪器：`audit/disambiguation_audit.py`（可重放）。

## 一、前缀后随的缩写族（前缀法域的印刷证据）

| 前缀 | 表内法域 | 后随族（前 10） | 年份 |
|---|---|---|---|
| LR | GB | hl 695, qb 682, cp 588, eq 439, ex 432, pc 366, chapp 118, ch 76, hlsc 64, pd 52 | 1864–1979 |
| MLR | QC | qb 174, sc 114, se 2, kb 1, cs 1, s 1, qp 1, q 1 | 1878–1890 |
| QOR | QC | kb 28, sc 21, qb 3 | 1893–1928 |
| QR | QC | kb 1036, sc 669, qb 274, lcj 7, cs 4, pr 3, br 3, hl 3, cc 2, so 2 | 1866–1941 |

## 二、区间规则 vs 前缀标注（遮住前缀、只用卷号/年份判）

| 族 | 一致 | 不一致 | 判不出 |
|---|---:|---:|---:|
| cp | 587 | 2 | 1 |
| kb | 1056 | 6 | 5 |
| p | 0 | 0 | 2 |
| qb | 230 | 4 | 899 |
| sc | 804 | 0 | 0 |

合计：一致 2677、不一致 12（**区间判出者中的错误率 0.45%**）。

不一致的例：

- `Q.R. 2 K.B. 585`：前缀说 QC，区间判 GB
- `Q.R. 2 K.B. 514`：前缀说 QC，区间判 GB
- `Q.R. 2 K.B. 266`：前缀说 QC，区间判 GB
- `Q.R. 4 K.B. 216`：前缀说 QC，区间判 GB
- `Q.R. 18 Q.B. 419`：前缀说 QC，区间判 GB
- `Q.R. 2 C.P. 311`：前缀说 QC，区间判 GB
- `Q.R. 10 C.P. 733`：前缀说 QC，区间判 GB
- `Q. R. 12 Q. B. 298`：前缀说 QC，区间判 GB
- `Q. R. 12 Q. B 298`：前缀说 QC，区间判 GB
- `(1892) L.R. 7 Q.B. 387`：前缀说 GB，区间判 QC

## 三、同组旁证（组里其他汇编中，表内只有单一法域者）

| 族 | 消歧方式 | 旁证一致 | 旁证冲突 | 无旁证 |
|---|---|---:|---:|---:|
| alr | vol_only | 0 | 0 | 11 |
| alr | vol_year | 0 | 0 | 13 |
| clr | vol_only | 0 | 0 | 25 |
| clr | vol_year | 9 | 0 | 326 |
| cp | novol_year | 0 | 0 | 9 |
| cp | series_prefix | 0 | 0 | 306 |
| cp | vol_only | 0 | 0 | 20 |
| cp | vol_year | 0 | 0 | 4 |
| kb | novol_year | 0 | 0 | 10 |
| kb | series_prefix | 1 | 0 | 692 |
| kb | vol_only | 0 | 0 | 48 |
| kb | vol_year | 25 | 1 | 1023 |
| p | novol_year | 3 | 0 | 136 |
| p | series_prefix | 0 | 0 | 2 |
| p | vol_only | 0 | 0 | 159 |
| p | vol_year | 0 | 0 | 153 |
| qb | novol_year | 14 | 0 | 81 |
| qb | series_prefix | 0 | 0 | 572 |
| qb | vol_only | 0 | 0 | 96 |
| qb | vol_year | 35 | 0 | 517 |
| sc | novol_year | 0 | 0 | 23 |
| sc | series_prefix | 0 | 0 | 583 |
| sc | vol_only | 0 | 0 | 22 |
| sc | vol_year | 0 | 0 | 40 |
| wlr | novol_year | 0 | 0 | 3 |
| wlr | vol_only | 0 | 0 | 30 |
| wlr | vol_year | 48 | 2 | 348 |

旁证冲突的例：

- `[1954] 1 W.L.R. 228` 判 GB，旁证 CA；组内：[1954] 1 W.L.R. 228 / (1955), 21 C.R. 263
- `[1985] 1 WLR 816` 判 GB，旁证 CA；组内：[1984] 1 C.N.L.R. 122 / [1985] 1 WLR 816
- `[1950] 1 K.B. 26` 判 GB，旁证 ON；组内：[1950] 1 K.B. 26 / [1951] O.R. 422
