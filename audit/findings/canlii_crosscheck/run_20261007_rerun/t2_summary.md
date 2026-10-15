# T2 边级对比（自动部分）

口径：CanLII 覆盖率 = 我们配上的 CanLII 被引案 / CanLII 被引案；CanLII 对我们的覆盖 = 被 CanLII 配上的我们的边 / 我们的边中「来源地未判定为境外」者（来源地取生产数据 foreign_status；UNDETERMINED 计入分母，因为它可能是加拿大案）。Wilson 95% CI。

未配上的我们的边按来源地：境外（已判定）/ 加拿大（已判定）/ 未判定——未判定者再按汇编法域拆：印在加拿大汇编 / 外国汇编 / 无法域。

| 层 | 判决 | 零出边 | CanLII 被引 | 我们配上（强+弱+宽） | 我们对 CanLII 的覆盖 | 我们的边 | 未配上·来源境外 | 未配上·来源加拿大 | 未配上·来源未判定（加汇编/外汇编/无） | CanLII 对我们的覆盖 | A2AJ 也有 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SCC_1875-1949 | 40 | 1 | 107 | 21+5+13 | 36.4% [27.9–45.9] | 338 | 0 | 50 | 248（70/123/55） | 11.6% [8.6–15.4] | 0 |
| SCC_1950-1999 | 40 | 1 | 382 | 202+48+55 | 79.8% [75.5–83.6] | 699 | 2 | 120 | 271（132/101/38） | 43.8% [40.2–47.5] | 0 |
| SCC_2000-2026 | 40 | 0 | 1159 | 975+79+74 | 97.3% [96.2–98.1] | 1854 | 10 | 147 | 558（307/101/150） | 61.5% [59.3–63.7] | 586 |
| ONCA_1998-2006 | 40 | 17 | 104 | 28+33+12 | 70.2% [60.8–78.1] | 126 | 1 | 22 | 33（24/1/8） | 57.0% [48.4–65.3] | 0 |
| ONCA_2007-2015 | 40 | 16 | 165 | 82+45+14 | 85.5% [79.3–90.0] | 216 | 0 | 19 | 57（39/11/7） | 65.0% [58.4–71.0] | 31 |
| ONCA_2016-2026 | 40 | 6 | 352 | 303+32+6 | 96.9% [94.5–98.2] | 483 | 4 | 86 | 50（35/7/8） | 71.5% [67.3–75.4] | 255 |
| BCCA_1999-2007 | 40 | 9 | 200 | 108+41+17 | 83.0% [77.2–87.6] | 375 | 0 | 41 | 167（105/40/22） | 44.4% [39.4–49.5] | 40 |
| BCCA_2008-2016 | 40 | 3 | 379 | 304+34+17 | 93.7% [90.8–95.7] | 520 | 0 | 44 | 116（91/15/10） | 68.9% [64.8–72.8] | 238 |
| BCCA_2017-2026 | 40 | 0 | 625 | 554+27+18 | 95.8% [94.0–97.1] | 699 | 1 | 20 | 76（60/9/7） | 86.2% [83.4–88.6] | 489 |
| NSCA_1993-2002 | 40 | 10 | 167 | 41+35+35 | 66.5% [59.0–73.2] | 261 | 0 | 44 | 104（66/21/17） | 42.9% [37.0–48.9] | 0 |
| NSCA_2003-2012 | 40 | 6 | 261 | 177+18+31 | 86.6% [81.9–90.2] | 364 | 1 | 34 | 100（72/14/14） | 62.8% [57.7–67.6] | 78 |
| NSCA_2013-2026 | 40 | 2 | 568 | 493+39+9 | 95.2% [93.2–96.7] | 696 | 1 | 32 | 110（87/5/18） | 79.2% [76.0–82.1] | 409 |

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
| NSCA_1993-2002 | 56 | 1 | 2 | 0 | 38 | 15 |
| NSCA_2003-2012 | 35 | 0 | 1 | 0 | 25 | 9 |
| NSCA_2013-2026 | 27 | 1 | 0 | 0 | 19 | 7 |

## 我们的边按 edge_support：被 CanLII 配上的比例

| 层 | supported | heuristic_only |
|---|---|---|
| SCC_1875-1949 | 10.1% [7.3–13.9] (n=326) | 58.3% [32.0–80.7] (n=12) |
| SCC_1950-1999 | 43.1% [39.3–46.9] (n=652) | 53.2% [39.2–66.7] (n=47) |
| SCC_2000-2026 | 61.4% [59.2–63.7] (n=1774) | 61.3% [50.3–71.2] (n=80) |
| ONCA_1998-2006 | 42.7% [32.9–53.1] (n=89) | 86.5% [72.0–94.1] (n=37) |
| ONCA_2007-2015 | 57.1% [49.4–64.4] (n=163) | 88.7% [77.4–94.7] (n=53) |
| ONCA_2016-2026 | 70.2% [65.8–74.2] (n=453) | 83.3% [66.4–92.7] (n=30) |
| BCCA_1999-2007 | 39.8% [34.5–45.4] (n=304) | 64.8% [53.2–74.9] (n=71) |
| BCCA_2008-2016 | 68.9% [64.6–73.0] (n=470) | 72.0% [58.3–82.5] (n=50) |
| BCCA_2017-2026 | 87.2% [84.5–89.5] (n=665) | 64.7% [47.9–78.5] (n=34) |
| NSCA_1993-2002 | 41.0% [34.8–47.5] (n=227) | 58.8% [42.2–73.6] (n=34) |
| NSCA_2003-2012 | 58.5% [52.8–63.9] (n=301) | 84.1% [73.2–91.1] (n=63) |
| NSCA_2013-2026 | 79.8% [76.5–82.7] (n=657) | 74.4% [58.9–85.4] (n=39) |

原始计数：

```
{
"SCC_1875-1949": {
"sources": 40,
"zero_edge_sources": 1,
"ours_total": 338,
"ours_supported": 326,
"ours_only_origin_undetermined": 248,
"ours_only_origin_undetermined_pubca": 70,
"ours_only_origin_undetermined_pubforeign": 123,
"canlii_total": 107,
"a2aj_has": 0,
"Q_first_word_only": 53,
"canlii_only": 68,
"ours_heuristic_only": 12,
"ours_only_origin_undetermined_pubnone": 55,
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
"ours_total": 699,
"ours_supported": 652,
"ours_only_origin_undetermined": 271,
"ours_only_origin_undetermined_pubca": 132,
"ours_only_origin_ca": 120,
"ours_only_origin_ca_pubca": 116,
"both_weak": 48,
"fragmented": 6,
"Q_not_found": 24,
"both_strong": 202,
"ours_matched_supported": 281,
"ours_only_origin_foreign": 2,
"ours_only_origin_foreign_pubforeign": 2,
"ours_heuristic_only": 47,
"ours_matched_heuristic_only": 25,
"ours_only_origin_undetermined_pubforeign": 101,
"ours_only_origin_undetermined_pubnone": 38,
"both_loose": 55,
"C4_extracted_but_elsewhere": 2,
"ours_only_origin_ca_pubforeign": 4
},
"SCC_2000-2026": {
"sources": 40,
"zero_edge_sources": 0,
"canlii_total": 1159,
"a2aj_has": 586,
"both_weak": 79,
"fragmented": 18,
"both_strong": 975,
"Q_not_found": 19,
"canlii_only": 31,
"ours_total": 1854,
"ours_supported": 1774,
"ours_matched_supported": 1090,
"ours_heuristic_only": 80,
"ours_only_origin_undetermined": 558,
"ours_only_origin_undetermined_pubca": 307,
"ours_matched_heuristic_only": 49,
"ours_only_origin_ca": 147,
"ours_only_origin_ca_pubca": 147,
"ours_only_origin_undetermined_pubforeign": 101,
"ours_only_origin_undetermined_pubnone": 150,
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
"ours_heuristic_only": 37,
"ours_matched_heuristic_only": 32,
"ours_supported": 89,
"ours_matched_supported": 38,
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
"fragmented": 2,
"both_weak": 45,
"Q_first_word_only": 22,
"canlii_only": 24,
"ours_total": 216,
"ours_heuristic_only": 53,
"ours_matched_heuristic_only": 47,
"ours_supported": 163,
"ours_matched_supported": 93,
"ours_only_origin_undetermined": 57,
"ours_only_origin_undetermined_pubca": 39,
"both_strong": 82,
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
"both_strong": 303,
"fragmented": 5,
"ours_total": 483,
"ours_supported": 453,
"ours_only_origin_undetermined": 50,
"ours_only_origin_undetermined_pubca": 35,
"ours_matched_supported": 318,
"ours_only_origin_ca": 86,
"ours_only_origin_ca_pubca": 86,
"both_weak": 32,
"ours_heuristic_only": 30,
"ours_matched_heuristic_only": 25,
"Q_first_word_only": 8,
"canlii_only": 11,
"both_loose": 6,
"ours_only_origin_undetermined_pubforeign": 7,
"ours_only_origin_foreign": 4,
"ours_only_origin_foreign_pubforeign": 4,
"ours_only_origin_undetermined_pubnone": 8,
"Q_not_found": 3
},
"BCCA_1999-2007": {
"sources": 40,
"zero_edge_sources": 9,
"canlii_total": 200,
"a2aj_has": 40,
"both_strong": 108,
"fragmented": 4,
"ours_total": 375,
"ours_heuristic_only": 71,
"ours_matched_heuristic_only": 46,
"both_loose": 17,
"Q_first_word_only": 28,
"canlii_only": 34,
"Q_not_found": 6,
"ours_supported": 304,
"ours_only_origin_undetermined": 167,
"ours_only_origin_undetermined_pubforeign": 40,
"ours_only_origin_undetermined_pubca": 105,
"ours_matched_supported": 121,
"ours_only_origin_ca": 41,
"ours_only_origin_ca_pubca": 41,
"ours_only_origin_undetermined_pubnone": 22,
"both_weak": 41
},
"BCCA_2008-2016": {
"sources": 40,
"zero_edge_sources": 3,
"canlii_total": 379,
"a2aj_has": 238,
"both_strong": 304,
"fragmented": 8,
"ours_total": 520,
"ours_supported": 470,
"ours_matched_supported": 324,
"Q_first_word_only": 20,
"canlii_only": 24,
"ours_only_origin_undetermined": 116,
"ours_only_origin_undetermined_pubforeign": 15,
"ours_heuristic_only": 50,
"ours_matched_heuristic_only": 36,
"ours_only_origin_undetermined_pubca": 91,
"ours_only_origin_ca": 44,
"ours_only_origin_ca_pubca": 44,
"both_weak": 34,
"Q_not_found": 3,
"ours_only_origin_undetermined_pubnone": 10,
"both_loose": 17,
"C1_not_extracted": 1
},
"BCCA_2017-2026": {
"sources": 40,
"zero_edge_sources": 0,
"canlii_total": 625,
"a2aj_has": 489,
"both_strong": 554,
"fragmented": 5,
"ours_total": 699,
"ours_supported": 665,
"ours_matched_supported": 580,
"both_loose": 18,
"Q_first_word_only": 16,
"canlii_only": 26,
"both_weak": 27,
"ours_only_origin_ca": 20,
"ours_only_origin_ca_pubca": 20,
"ours_heuristic_only": 34,
"ours_matched_heuristic_only": 22,
"ours_only_origin_undetermined": 76,
"ours_only_origin_undetermined_pubca": 60,
"ours_only_origin_undetermined_pubnone": 7,
"ours_only_origin_foreign": 1,
"ours_only_origin_foreign_pubforeign": 1,
"Q_not_found": 10,
"ours_only_origin_undetermined_pubforeign": 9
},
"NSCA_1993-2002": {
"sources": 40,
"zero_edge_sources": 10,
"canlii_total": 167,
"a2aj_has": 0,
"both_weak": 35,
"fragmented": 2,
"ours_total": 261,
"ours_supported": 227,
"ours_matched_supported": 93,
"both_strong": 41,
"both_loose": 35,
"Q_first_word_only": 38,
"canlii_only": 56,
"ours_heuristic_only": 34,
"ours_matched_heuristic_only": 20,
"ours_only_origin_undetermined": 104,
"ours_only_origin_undetermined_pubca": 66,
"ours_only_origin_ca": 44,
"ours_only_origin_ca_pubca": 44,
"ours_only_origin_undetermined_pubnone": 17,
"Q_not_found": 15,
"ours_only_origin_undetermined_pubforeign": 21,
"C1_not_extracted": 1,
"C4_extracted_but_elsewhere": 2
},
"NSCA_2003-2012": {
"sources": 40,
"zero_edge_sources": 6,
"canlii_total": 261,
"a2aj_has": 78,
"both_strong": 177,
"fragmented": 5,
"ours_total": 364,
"ours_supported": 301,
"ours_matched_supported": 176,
"ours_only_origin_undetermined": 100,
"ours_only_origin_undetermined_pubca": 72,
"Q_first_word_only": 25,
"canlii_only": 35,
"ours_only_origin_ca": 34,
"ours_only_origin_ca_pubca": 34,
"both_weak": 18,
"both_loose": 31,
"ours_heuristic_only": 63,
"ours_only_origin_undetermined_pubforeign": 14,
"ours_matched_heuristic_only": 53,
"ours_only_origin_undetermined_pubnone": 14,
"ours_only_origin_foreign": 1,
"ours_only_origin_foreign_pubforeign": 1,
"Q_not_found": 9,
"C4_extracted_but_elsewhere": 1
},
"NSCA_2013-2026": {
"sources": 40,
"zero_edge_sources": 2,
"canlii_total": 568,
"a2aj_has": 409,
"Q_first_word_only": 19,
"canlii_only": 27,
"both_strong": 493,
"fragmented": 13,
"ours_total": 696,
"ours_supported": 657,
"ours_matched_supported": 524,
"ours_only_origin_undetermined": 110,
"ours_only_origin_undetermined_pubca": 87,
"both_weak": 39,
"ours_only_origin_ca": 32,
"ours_only_origin_ca_pubca": 32,
"both_loose": 9,
"ours_heuristic_only": 39,
"ours_matched_heuristic_only": 29,
"Q_not_found": 7,
"ours_only_origin_undetermined_pubnone": 18,
"C1_not_extracted": 1,
"ours_only_origin_undetermined_pubforeign": 5,
"ours_only_origin_foreign": 1,
"ours_only_origin_foreign_pubforeign": 1
}
}
```