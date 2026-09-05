# -*- coding: utf-8 -*-
"""truth.py — 夹具真值表

【整体状态：待核实】——由本轮 agent 逐条枚举，尚未经人复核。
用途：run_regression.py 以本表计算"对真值的召回"。在人工复核确认本表之前，
召回数字一律不得写为已核实（规格 §0 证据标注约定、约束九）。
span 为相对 fixtures.py 对应夹具 text 的 0 基字符区间 [start, end)。
E_prose_negative 与 F_statute_biblio_negative 的真值为空表：
  - E：人工确认为纯散文说理段（本次 agent 初核无引证，待复核确认）
  - F：制定法与书目混合段，其中不含案例引证；书目中的期刊卷页
    （如 53 Alb. L. Rev. 95）被抽取层命中时按误报列账
"""

import json

TRUTH = json.loads(r'''{
 "_meta": {
  "status": "待核实",
  "enumerated_by": "agent（本轮，未经人复核）",
  "method": "逐段人工枚举印出的引证串；span 由字面量在夹具文本内定位生成（重复字面量按出现序号取位）",
  "reminder": "召回率在真值表经人复核前不视为已核实"
 },
 "fixtures": {
  "A_1877_1899_footnotes": {
   "kind": "footnotes_19c",
   "items": [
    {
     "span": [
      4,
      21
     ],
     "what": "4 Can. S.C.R. 605",
     "note": ""
    },
    {
     "span": [
      27,
      44
     ],
     "what": "4 Can. S.C.R. 605",
     "note": ""
    },
    {
     "span": [
      320,
      337
     ],
     "what": "4 Can. S.C.R. 605",
     "note": ""
    },
    {
     "span": [
      488,
      505
     ],
     "what": "4 Can. S.C.R. 605",
     "note": ""
    },
    {
     "span": [
      62,
      78
     ],
     "what": "3 Can. S.C.R. 16",
     "note": ""
    },
    {
     "span": [
      95,
      113
     ],
     "what": "24 (U.C.) C.P. 275",
     "note": "非序数括注 (U.C.)，v2 已知抽不到（登记在 PROBLEMS 非序数括注缺口）"
    },
    {
     "span": [
      125,
      140
     ],
     "what": "3 Can. S.C.R. 9",
     "note": ""
    },
    {
     "span": [
      146,
      162
     ],
     "what": "5 App. Cases 409",
     "note": ""
    },
    {
     "span": [
      297,
      313
     ],
     "what": "5 App. Cases 409",
     "note": ""
    },
    {
     "span": [
      181,
      195
     ],
     "what": "1 B. & Ad. 284",
     "note": ""
    },
    {
     "span": [
      202,
      214
     ],
     "what": "5 CI. & F. 1",
     "note": "OCR: Cl. 误为 CI.；随后钉注页 13,14,15 不在捕获范围"
    },
    {
     "span": [
      233,
      252
     ],
     "what": "2 Can. L. Times 206",
     "note": ""
    },
    {
     "span": [
      259,
      268
     ],
     "what": "10 Ex. 84",
     "note": ""
    },
    {
     "span": [
      275,
      290
     ],
     "what": "3 Can. S.C.R. 1",
     "note": ""
    },
    {
     "span": [
      344,
      356
     ],
     "what": "4 H.L.C. 939",
     "note": ""
    },
    {
     "span": [
      376,
      387
     ],
     "what": "8 Exch. 361",
     "note": ""
    },
    {
     "span": [
      394,
      413
     ],
     "what": "1 Moo. P.C.N.S. 471",
     "note": ""
    },
    {
     "span": [
      420,
      432
     ],
     "what": "4 Cranch 241",
     "note": ""
    },
    {
     "span": [
      439,
      447
     ],
     "what": "Swab. 96",
     "note": "无卷号 nominate reporter，v1/v2 结构上都不覆盖"
    },
    {
     "span": [
      454,
      469
     ],
     "what": "L.R. 5 P.C. 179",
     "note": ""
    }
   ]
  },
  "B_1930_1940_footnotes": {
   "kind": "footnotes_mid20c",
   "items": [
    {
     "span": [
      4,
      23
     ],
     "what": "[1935] Ex. C.R. 190",
     "note": ""
    },
    {
     "span": [
      29,
      48
     ],
     "what": "(1889) 6 R.P.C. 518",
     "note": ""
    },
    {
     "span": [
      60,
      80
     ],
     "what": "(1896) 14 R.P.C. 105",
     "note": ""
    },
    {
     "span": [
      345,
      365
     ],
     "what": "(1896) 14 R.P.C. 105",
     "note": ""
    },
    {
     "span": [
      101,
      121
     ],
     "what": "[1928] Can. S.C.R. 8",
     "note": ""
    },
    {
     "span": [
      127,
      149
     ],
     "what": "[1932] Can. S.C.R. 724",
     "note": ""
    },
    {
     "span": [
      163,
      185
     ],
     "what": "[1933] Can. S.C.R. 371",
     "note": ""
    },
    {
     "span": [
      209,
      231
     ],
     "what": "[1933] Can. S.C.R. 230",
     "note": ""
    },
    {
     "span": [
      250,
      270
     ],
     "what": "(1865) 11 H.L.C. 654",
     "note": ""
    },
    {
     "span": [
      276,
      295
     ],
     "what": "(1890) 7 R.P.C. 131",
     "note": ""
    },
    {
     "span": [
      310,
      330
     ],
     "what": "(1896) 13 R.P.C. 730",
     "note": ""
    },
    {
     "span": [
      372,
      392
     ],
     "what": "(1934) 51 R.P.C. 349",
     "note": ""
    },
    {
     "span": [
      407,
      433
     ],
     "what": "(1866) L.R. 2 Ch. App. 127",
     "note": "v2 以子串 L.R. 2 Ch. App. 127 命中（shape_leading_abbr），年份前缀不进匹配"
    },
    {
     "span": [
      445,
      463
     ],
     "what": "(1920) 38 R.P.C. 1",
     "note": ""
    },
    {
     "span": [
      477,
      497
     ],
     "what": "(1929) 46 R.P.C. 241",
     "note": ""
    }
   ]
  },
  "C_1960s_parallel_cites": {
   "kind": "footnotes_parallel_60s",
   "items": [
    {
     "span": [
      4,
      24
     ],
     "what": "[1963] Que. Q.B. 623",
     "note": ""
    },
    {
     "span": [
      65,
      85
     ],
     "what": "[1963] Que. Q.B. 623",
     "note": ""
    },
    {
     "span": [
      386,
      406
     ],
     "what": "[1963] Que. Q.B. 623",
     "note": ""
    },
    {
     "span": [
      26,
      43
     ],
     "what": "[1963] C.T.C. 201",
     "note": ""
    },
    {
     "span": [
      87,
      104
     ],
     "what": "[1963] C.T.C. 201",
     "note": ""
    },
    {
     "span": [
      408,
      425
     ],
     "what": "[1963] C.T.C. 201",
     "note": ""
    },
    {
     "span": [
      45,
      59
     ],
     "what": "63 D.T.C. 1098",
     "note": ""
    },
    {
     "span": [
      106,
      120
     ],
     "what": "63 D.T.C. 1098",
     "note": ""
    },
    {
     "span": [
      427,
      441
     ],
     "what": "63 D.T.C. 1098",
     "note": ""
    },
    {
     "span": [
      126,
      141
     ],
     "what": "[1911] A.C. 179",
     "note": ""
    },
    {
     "span": [
      150,
      165
     ],
     "what": "80 L.J.K.B. 769",
     "note": ""
    },
    {
     "span": [
      171,
      186
     ],
     "what": "[1906] A.C. 535",
     "note": ""
    },
    {
     "span": [
      195,
      209
     ],
     "what": "75 L.J.P.C. 73",
     "note": ""
    },
    {
     "span": [
      223,
      237
     ],
     "what": "L.R. 9 Ex. 192",
     "note": "v2 以子串命中（缺前置 (1874),），(年) 与缩写同现时 v2 无此形状"
    },
    {
     "span": [
      246,
      261
     ],
     "what": "43 L.J. Ex. 153",
     "note": ""
    },
    {
     "span": [
      267,
      286
     ],
     "what": "[1953] 2 S.C.R. 140",
     "note": ""
    },
    {
     "span": [
      295,
      309
     ],
     "what": "107 C.C.C. 183",
     "note": ""
    },
    {
     "span": [
      311,
      323
     ],
     "what": "4 D.L.R. 161",
     "note": ""
    },
    {
     "span": [
      329,
      344
     ],
     "what": "[1962] O.R. 572",
     "note": ""
    },
    {
     "span": [
      346,
      360
     ],
     "what": "133 C.C.C. 116",
     "note": ""
    },
    {
     "span": [
      362,
      380
     ],
     "what": "34 D.L.R. (2d) 451",
     "note": ""
    },
    {
     "span": [
      447,
      464
     ],
     "what": "[1935] S.C.R. 441",
     "note": ""
    },
    {
     "span": [
      499,
      516
     ],
     "what": "[1935] S.C.R. 441",
     "note": ""
    },
    {
     "span": [
      466,
      478
     ],
     "what": "3 D.L.R. 465",
     "note": ""
    },
    {
     "span": [
      518,
      530
     ],
     "what": "3 D.L.R. 465",
     "note": ""
    },
    {
     "span": [
      480,
      492
     ],
     "what": "64 C.C.C. 90",
     "note": ""
    },
    {
     "span": [
      532,
      544
     ],
     "what": "64 C.C.C. 90",
     "note": ""
    }
   ]
  },
  "D_cases_cited_block": {
   "kind": "cases_cited_block",
   "items": [
    {
     "span": [
      57,
      75
     ],
     "what": "[1990] 2 S.C.R. 85",
     "note": ""
    },
    {
     "span": [
      102,
      120
     ],
     "what": "[1983] 1 S.C.R. 29",
     "note": ""
    },
    {
     "span": [
      164,
      181
     ],
     "what": "[1979] 1 F.C. 103",
     "note": ""
    },
    {
     "span": [
      230,
      246
     ],
     "what": "[1924] 2 Ch. 101",
     "note": ""
    },
    {
     "span": [
      317,
      335
     ],
     "what": "[1991] 2 S.C.R. 22",
     "note": ""
    },
    {
     "span": [
      393,
      413
     ],
     "what": "[1989] 1 S.C.R. 1532",
     "note": ""
    }
   ]
  },
  "E_prose_negative": {
   "kind": "prose",
   "items": []
  },
  "F_statute_biblio_negative": {
   "kind": "statute_biblio",
   "items": []
  }
 }
}''')
