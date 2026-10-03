# T2 边级对比（自动部分）

口径：CanLII 覆盖率 = 我们配上的 CanLII 被引案 / CanLII 被引案；CanLII 对我们的覆盖 = 被 CanLII 配上的我们的边 / 我们的边中「来源地未判定为境外」者（来源地取生产数据 foreign_status；UNDETERMINED 计入分母，因为它可能是加拿大案）。Wilson 95% CI。

未配上的我们的边按来源地：境外（已判定）/ 加拿大（已判定）/ 未判定——未判定者再按汇编法域拆：印在加拿大汇编 / 外国汇编 / 无法域。

| 层 | 判决 | 零出边 | CanLII 被引 | 我们配上（强+弱+宽） | 我们对 CanLII 的覆盖 | 我们的边 | 未配上·来源境外 | 未配上·来源加拿大 | 未配上·来源未判定（加汇编/外汇编/无） | CanLII 对我们的覆盖 | A2AJ 也有 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SCC_1875-1949 | 40 | 1 | 107 | 21+5+13 | 36.4% [27.9–45.9] | 340 | 0 | 50 | 250（70/123/57） | 11.5% [8.5–15.3] | 0 |
| SCC_1950-1999 | 40 | 1 | 382 | 201+49+55 | 79.8% [75.5–83.6] | 715 | 2 | 120 | 287（132/101/54） | 42.8% [39.3–46.5] | 0 |
| SCC_2000-2026 | 40 | 0 | 1159 | 974+80+74 | 97.3% [96.2–98.1] | 1889 | 10 | 150 | 592（302/100/190） | 60.3% [58.1–62.5] | 586 |
| ONCA_1998-2006 | 40 | 17 | 104 | 28+33+12 | 70.2% [60.8–78.1] | 126 | 1 | 22 | 33（24/1/8） | 57.0% [48.4–65.3] | 0 |
| ONCA_2007-2015 | 40 | 16 | 165 | 80+47+14 | 85.5% [79.3–90.0] | 217 | 0 | 19 | 57（39/11/7） | 65.0% [58.4–71.0] | 31 |
| ONCA_2016-2026 | 40 | 6 | 352 | 302+33+6 | 96.9% [94.5–98.2] | 485 | 4 | 86 | 55（35/7/13） | 70.7% [66.5–74.6] | 255 |
| BCCA_1999-2007 | 40 | 9 | 200 | 108+41+17 | 83.0% [77.2–87.6] | 378 | 0 | 41 | 170（107/40/23） | 44.0% [39.1–49.1] | 40 |
| BCCA_2008-2016 | 40 | 3 | 379 | 304+34+17 | 93.7% [90.8–95.7] | 522 | 0 | 44 | 117（91/15/11） | 68.8% [64.7–72.6] | 238 |
| BCCA_2017-2026 | 40 | 0 | 625 | 554+26+19 | 95.8% [94.0–97.1] | 701 | 1 | 20 | 79（60/9/10） | 85.8% [83.0–88.2] | 489 |

## CanLII 有、我们没有：自动初裁

| 层 | canlii_only | C1 原文有·未抽到 | C4 抽到·归到别处 | C5 抽到·被规则排除 | Q 仅首个实义词 | Q 原文找不到 |
|---|---|---|---|---|---|---|
| SCC_1875-1949 | 68 | 0 | 5 | 0 | 53 | 10 |
| SCC_1950-1999 | 77 | 0 | 2 | 0 | 51 | 24 |
| SCC_2000-2026 | 31 | 0 | 0 | 0 | 12 | 19 |
| ONCA_1998-2006 | 31 | 0 | 0 | 0 | 22 | 9 |
| ONCA_2007-2015 | 24 | 0 | 0 | 0 | 22 | 2 |
| ONCA_2016-2026 | 11 | 0 | 0 | 0 | 8 | 3 |
| BCCA_1999-2007 | 34 | 0 | 0 | 0 | 28 | 6 |
| BCCA_2008-2016 | 24 | 1 | 0 | 0 | 20 | 3 |
| BCCA_2017-2026 | 26 | 0 | 0 | 0 | 16 | 10 |

## 我们的边按 edge_support：被 CanLII 配上的比例

| 层 | supported | heuristic_only |
|---|---|---|
| SCC_1875-1949 | 10.1% [7.3–13.8] (n=328) | 58.3% [32.0–80.7] (n=12) |
| SCC_1950-1999 | 42.0% [38.3–45.8] (n=669) | 54.3% [40.2–67.8] (n=46) |
| SCC_2000-2026 | 60.0% [57.8–62.3] (n=1819) | 64.3% [52.6–74.5] (n=70) |
| ONCA_1998-2006 | 44.6% [34.8–54.7] (n=92) | 85.3% [69.9–93.6] (n=34) |
| ONCA_2007-2015 | 57.1% [49.4–64.4] (n=163) | 88.9% [77.8–94.8] (n=54) |
| ONCA_2016-2026 | 69.3% [64.9–73.4] (n=456) | 82.8% [65.5–92.4] (n=29) |
| BCCA_1999-2007 | 39.6% [34.3–45.2] (n=308) | 64.3% [52.6–74.5] (n=70) |
| BCCA_2008-2016 | 68.9% [64.5–72.9] (n=472) | 72.0% [58.3–82.5] (n=50) |
| BCCA_2017-2026 | 86.8% [84.0–89.2] (n=668) | 63.6% [46.6–77.8] (n=33) |

原始计数：

```
{
"SCC_1875-1949": {
"sources": 40,
"zero_edge_sources": 1,
"ours_total": 340,
"ours_supported": 328,
"ours_only_origin_undetermined": 250,
"ours_only_origin_undetermined_pubca": 70,
"ours_only_origin_undetermined_pubforeign": 123,
"canlii_total": 107,
"a2aj_has": 0,
"Q_first_word_only": 53,
"canlii_only": 68,
"ours_heuristic_only": 12,
"ours_only_origin_undetermined_pubnone": 57,
"ours_only_origin_ca": 50,
"ours_only_origin_ca_pubca": 46,
"both_loose": 13,
"fragmented": 2,
"ours_matched_supported": 33,
"C4_extracted_but_elsewhere": 5,
"both_strong": 21,
"ours_matched_heuristic_only": 7,
"Q_not_found": 10,
"both_weak": 5,
"ours_only_origin_ca_pubforeign": 4
},
"SCC_1950-1999": {
"sources": 40,
"zero_edge_sources": 1,
"canlii_total": 382,
"a2aj_has": 0,
"Q_first_word_only": 51,
"canlii_only": 77,
"ours_total": 715,
"ours_supported": 669,
"ours_only_origin_undetermined": 287,
"ours_only_origin_undetermined_pubca": 132,
"ours_only_origin_ca": 120,
"ours_only_origin_ca_pubca": 116,
"both_weak": 49,
"fragmented": 6,
"Q_not_found": 24,
"both_strong": 201,
"ours_matched_supported": 281,
"ours_only_origin_foreign": 2,
"ours_only_origin_foreign_pubforeign": 2,
"ours_heuristic_only": 46,
"ours_matched_heuristic_only": 25,
"ours_only_origin_undetermined_pubforeign": 101,
"ours_only_origin_undetermined_pubnone": 54,
"both_loose": 55,
"C4_extracted_but_elsewhere": 2,
"ours_only_origin_ca_pubforeign": 4
},
"SCC_2000-2026": {
"sources": 40,
"zero_edge_sources": 0,
"canlii_total": 1159,
"a2aj_has": 586,
"both_weak": 80,
"fragmented": 16,
"both_strong": 974,
"Q_not_found": 19,
"canlii_only": 31,
"ours_total": 1889,
"ours_supported": 1819,
"ours_matched_supported": 1092,
"ours_heuristic_only": 70,
"ours_only_origin_undetermined": 592,
"ours_only_origin_undetermined_pubca": 302,
"ours_matched_heuristic_only": 45,
"ours_only_origin_ca": 150,
"ours_only_origin_ca_pubca": 150,
"ours_only_origin_undetermined_pubforeign": 100,
"ours_only_origin_undetermined_pubnone": 190,
"both_loose": 74,
"Q_first_word_only": 12,
"ours_only_origin_foreign": 10,
"ours_only_origin_foreign_pubforeign": 10
},
"ONCA_1998-2006": {
"sources": 40,
"zero_edge_sources": 17,
"canlii_total": 104,
"a2aj_has": 0,
"both_weak": 33,
"fragmented": 1,
"both_strong": 28,
"Q_first_word_only": 22,
"canlii_only": 31,
"both_loose": 12,
"Q_not_found": 9,
"ours_total": 126,
"ours_heuristic_only": 34,
"ours_matched_heuristic_only": 29,
"ours_supported": 92,
"ours_matched_supported": 41,
"ours_only_origin_ca": 22,
"ours_only_origin_ca_pubca": 22,
"ours_only_origin_undetermined": 33,
"ours_only_origin_undetermined_pubca": 24,
"ours_only_origin_undetermined_pubnone": 8,
"ours_only_origin_foreign": 1,
"ours_only_origin_foreign_pubforeign": 1,
"ours_only_origin_undetermined_pubforeign": 1
},
"ONCA_2007-2015": {
"sources": 40,
"zero_edge_sources": 16,
"canlii_total": 165,
"a2aj_has": 31,
"both_loose": 14,
"fragmented": 3,
"both_weak": 47,
"Q_first_word_only": 22,
"canlii_only": 24,
"ours_total": 217,
"ours_heuristic_only": 54,
"ours_matched_heuristic_only": 48,
"ours_supported": 163,
"ours_matched_supported": 93,
"ours_only_origin_undetermined": 57,
"ours_only_origin_undetermined_pubca": 39,
"both_strong": 80,
"ours_only_origin_ca": 19,
"ours_only_origin_ca_pubca": 19,
"ours_only_origin_undetermined_pubforeign": 11,
"ours_only_origin_undetermined_pubnone": 7,
"Q_not_found": 2
},
"ONCA_2016-2026": {
"sources": 40,
"zero_edge_sources": 6,
"canlii_total": 352,
"a2aj_has": 255,
"both_strong": 302,
"fragmented": 2,
"ours_total": 485,
"ours_supported": 456,
"ours_only_origin_undetermined": 55,
"ours_only_origin_undetermined_pubca": 35,
"ours_matched_supported": 316,
"ours_only_origin_ca": 86,
"ours_only_origin_ca_pubca": 86,
"both_weak": 33,
"ours_heuristic_only": 29,
"ours_matched_heuristic_only": 24,
"Q_first_word_only": 8,
"canlii_only": 11,
"both_loose": 6,
"ours_only_origin_undetermined_pubforeign": 7,
"ours_only_origin_foreign": 4,
"ours_only_origin_foreign_pubforeign": 4,
"ours_only_origin_undetermined_pubnone": 13,
"Q_not_found": 3
},
"BCCA_1999-2007": {
"sources": 40,
"zero_edge_sources": 9,
"canlii_total": 200,
"a2aj_has": 40,
"both_strong": 108,
"fragmented": 4,
"ours_total": 378,
"ours_heuristic_only": 70,
"ours_matched_heuristic_only": 45,
"both_loose": 17,
"Q_first_word_only": 28,
"canlii_only": 34,
"Q_not_found": 6,
"ours_supported": 308,
"ours_only_origin_undetermined": 170,
"ours_only_origin_undetermined_pubforeign": 40,
"ours_only_origin_undetermined_pubca": 107,
"ours_matched_supported": 122,
"ours_only_origin_ca": 41,
"ours_only_origin_ca_pubca": 41,
"ours_only_origin_undetermined_pubnone": 23,
"both_weak": 41
},
"BCCA_2008-2016": {
"sources": 40,
"zero_edge_sources": 3,
"canlii_total": 379,
"a2aj_has": 238,
"both_strong": 304,
"fragmented": 9,
"ours_total": 522,
"ours_supported": 472,
"ours_matched_supported": 325,
"Q_first_word_only": 20,
"canlii_only": 24,
"ours_only_origin_undetermined": 117,
"ours_only_origin_undetermined_pubforeign": 15,
"ours_heuristic_only": 50,
"ours_matched_heuristic_only": 36,
"ours_only_origin_undetermined_pubca": 91,
"ours_only_origin_ca": 44,
"ours_only_origin_ca_pubca": 44,
"both_weak": 34,
"Q_not_found": 3,
"ours_only_origin_undetermined_pubnone": 11,
"both_loose": 17,
"C1_not_extracted": 1
},
"BCCA_2017-2026": {
"sources": 40,
"zero_edge_sources": 0,
"canlii_total": 625,
"a2aj_has": 489,
"both_strong": 554,
"fragmented": 4,
"ours_total": 701,
"ours_supported": 668,
"ours_matched_supported": 580,
"both_loose": 19,
"Q_first_word_only": 16,
"canlii_only": 26,
"both_weak": 26,
"ours_only_origin_ca": 20,
"ours_only_origin_ca_pubca": 20,
"ours_heuristic_only": 33,
"ours_matched_heuristic_only": 21,
"ours_only_origin_undetermined": 79,
"ours_only_origin_undetermined_pubca": 60,
"ours_only_origin_undetermined_pubnone": 10,
"ours_only_origin_foreign": 1,
"ours_only_origin_foreign_pubforeign": 1,
"Q_not_found": 10,
"ours_only_origin_undetermined_pubforeign": 9
}
}
```