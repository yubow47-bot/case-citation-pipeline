# PROBLEMS #50 量化：同一判决因案名写法不同而没合到一起

仪器：`audit/name_variant_audit.py`（可重放）。数据：`data/decide_out/cross_court/`。

判据与读法见仪器文件头。**全部数字是上界**：共引分不开平行引证与审级历史，只有「S.C.R.->最高法院锚」一档可信度高。

## 计数

| 项 | 数 |
|---|---:|
| F 候选（无中立引用且 dd>=5） | 5986 |
| 同名（#49 残余） | S.C.R.->最高法院锚 | 7 |
| 同名（#49 残余） | S.C.R.->最高法院锚 —— 可补给锚的 dd | 11 |
| 并列，不连 | 15 |
| 异名（#50） | S.C.R.->最高法院锚 | 19 |
| 异名（#50） | S.C.R.->最高法院锚 —— 可补给锚的 dd | 331 |
| 异名（#50） | S.C.R.->非最高法院锚 | 3 |
| 异名（#50） | S.C.R.->非最高法院锚 —— 可补给锚的 dd | 74 |
| 异名（#50） | 全国性/联邦汇编 | 12 |
| 异名（#50） | 全国性/联邦汇编 —— 可补给锚的 dd | 35 |
| 异名（#50） | 法域未知 | 4 |
| 异名（#50） | 法域未知 —— 可补给锚的 dd | 5 |
| 异名（#50） | 省级汇编（可能是一审/审级历史） | 9 |
| 异名（#50） | 省级汇编（可能是一审/审级历史） —— 可补给锚的 dd | 126 |
| 无可连的锚 | 5917 |

## 连接明细（按 F 的 dd 降序，前 30）

| F dd | 档 | F 案名 | F 成员串 | → 锚案名 | 锚成员串 | 可补 dd |
|---:|---|---|---|---|---|---:|
| 196 | 异名（#50） | S.C.R.->最高法院锚 | R. v. M. (C.A.) | (1996), 105 C.C.C. (3d) 327 / [1996] 1 S.C.R. 500 / [1996] S |  | 1996 SCC 230 | 195 |
| 77 | 异名（#50） | 省级汇编（可能是一审/审级历史） | Boucher v. Public Accountants Council fo | (2004), 71 O.R. (3d) 291 / (2004), 71 O.R. (3d) 391 / [2004] | Risorto v. State Farm Mutual Automobile  | 2003 ONSC 43566 | 76 |
| 70 | 异名（#50） | S.C.R.->最高法院锚 | Law v. Canada (Minister of Employment an | [1999] 1 S.C.R. 497 | Lovelace v. Ontario | 2000 SCC 37 / [2000] 1 S.C.R. 950 | 52 |
| 44 | 异名（#50） | S.C.R.->非最高法院锚 | Rothman v. The Queen | [1981] 1 S.C.R. 640 | R. v. Mamarika | [1982] FCA 94 | 43 |
| 28 | 异名（#50） | S.C.R.->非最高法院锚 | Wells v. Newfoundland | (1999), 177 D.L.R. (4th) 73 / (2000), 94 L.A.C. (4th) 56 / [ | Fédération Franco‑ténoise v. Canada | 2001 FCA 220 / [2001] 3 F.C. 641 | 27 |
| 26 | 异名（#50） | S.C.R.->最高法院锚 | Delisle v. Canada (Deputy Attorney Gener | [1999] 2 S.C.R. 989 |  | 2000 SCC 57 | 25 |
| 19 | 异名（#50） | S.C.R.->最高法院锚 | R. v. Bissonnette | [2004] 3 S.C.R. 698 | R. v. Tessling | 2004 SCC 79 | 0 |
| 18 | 异名（#50） | S.C.R.->最高法院锚 | Castillo v. Castillo | [2000] 1 S.C.R. 783 |  | 2000 SCC 31 | 8 |
| 18 | 异名（#50） | 省级汇编（可能是一审/审级历史） | Prescott-Russell Services for Children a | (2006), 82 O.R. (3d) 686 |  | 2006 ONCJ 28 | 17 |
| 18 | 异名（#50） | S.C.R.->最高法院锚 | R. v. Pauls | [2021] 1 S.C.R. 5 | R. v. Yusuf | 2021 SCC 2 | 14 |
| 17 | 异名（#50） | S.C.R.->最高法院锚 | Bell ExpressVu Limited Partnership v. Re | [2006] 1 S.C.R. 865 |  | 2006 SCC 24 | 12 |
| 16 | 异名（#50） | S.C.R.->最高法院锚 | The Vancouver Sun v. A.G. (Can.) | [2004] 2 S.C.R. 332 | Canadian Broadcasting Corp. v. Manitoba | 2004 SCC 43 | 7 |
| 14 | 异名（#50） | 全国性/联邦汇编 | Das v. George Weston Limited | [2019] S.C.C.A. No. 69 | SNC-Lavalin Group Inc. v. Canada (Public | 2019 FC 282 / [2019] 3 F.C.R. 327 | 13 |
| 12 | 同名（#49 残余） | S.C.R.->最高法院锚 |  | [2004] 2 S.C.R. 248 |  | 2004 SCC 42 | 5 |
| 12 | 异名（#50） | S.C.R.->最高法院锚 | Applying the principles in Sherman Estat | [2021] 2 S.C.R. 75 | Sherman Estate v. Donovan | 2021 SCC 25 / [2021] 2 S.C.R. 521 / [2021] 2 S.C.R. 75 | 0 |
| 11 | 异名（#50） | S.C.R.->最高法院锚 | Greater Toronto Airports Authority v. Mi | [2001] 1 S.C.R. ix | Westec Aerospace Inc. v. Raytheon Aircra | 2001 SCC 26 | 10 |
| 10 | 异名（#50） | S.C.R.->最高法院锚 | Greater Vancouver Transportation Authori | [2009] 2 S.C.R. 295 | Greater Vancouver Transportation Authori | 2009 SCC 31 / [2009] 2 S.C.R. 295 | 1 |
| 10 | 异名（#50） | S.C.R.->最高法院锚 |  | [2010] 3 S.C.R. 457 | Ward v. Canada (Attorney General) | 2010 SCC 61 | 0 |
| 10 | 同名（#49 残余） | S.C.R.->最高法院锚 |  | [2015] 2 S.C.R. 789 |  | 2015 SCC 39 | 0 |
| 9 | 异名（#50） | 全国性/联邦汇编 | R. v. Currie | (2002), 166 C.C.C. (3d) 190 / [2003] S.C.C.A. No. 410 | R. v. Cinous | (2002), 162 C.C.C. (3d) 129 / 2002 SCC 29 / [2001] 2 S.C.R.  | 1 |
| 9 | 异名（#50） | 全国性/联邦汇编 | Dowling v. Ontario (Workplace Safety and | (2004), 246 D.L.R. (4th) 65 | Lepire v. National Bank of Canada | 2004 FC 155 | 8 |
| 9 | 异名（#50） | 省级汇编（可能是一审/审级历史） | Wildman v. Wildman | (2006), 82 O.R. (3d) 401 / [2006] O.J. No. 3966 |  | 2007 ONCJ 744 | 8 |
| 9 | 异名（#50） | S.C.R.->最高法院锚 | United States of America v. Sriskandaraj | [2012] 3 S.C.R. 609 | Sriskandarajah v. United States of Ameri | 2012 SCC 70 / [2012] 3 S.C.R. 609 | 0 |
| 8 | 异名（#50） | 全国性/联邦汇编 | R. v. Woodcock | (2003), 14 C.R. (6th) 155 / (2003), 177 C.C.C. (3d) 346 | R. v. Handy | (2002), 164 C.C.C. (3d) 481 / (2003), 68 O.R. (3d) 75 / 2002 | 1 |
| 7 | 异名（#50） | S.C.R.->最高法院锚 | Ward, at paras 16-18. As observed in Dou | [2003] 2 S.C.R. 3 | he had also been placed under arrest for | 2003 SCC 38 | 4 |
| 7 | 同名（#49 残余） | S.C.R.->最高法院锚 |  | [2004] 1 S.C.R. 727 |  | 2004 SCC 28 | 6 |
| 7 | 异名（#50） | 省级汇编（可能是一审/审级历史） | York Condominium Corp. No. 382 v. Jay-M  | (2007), 84 O.R. (3d) 414 | Toronto Economic Development Corporation | 2008 ONCA 366 | 6 |
| 7 | 异名（#50） | 省级汇编（可能是一审/审级历史） | R. v. Kwok | 2007 CanLII 2942 / [2007] O.J. No. 457 / [2008] O.J. No. 241 | R. v. J.P | 2008 ONCJ 484 | 5 |
| 6 | 异名（#50） | 全国性/联邦汇编 | Pacificador v. Canada (Minister of Justi | (2002), 166 C.C.C. (3d) 321 / [2002] S.C.C.A. No. 390 |  | 2003 FC 1514 | 5 |
| 6 | 异名（#50） | 省级汇编（可能是一审/审级历史） | Lowndes v. Summit Ford Sales Ltd | (2006), 206 O.A.C. 55 / [2006] O.J. No. 1438 |  | 2005 HRTO 53 | 5 |

## Vavilov（#50 登记时【待核实】的 dd 41 组）

- dd 176，有中立锚，成员：2019 SCC 65 / [2019] 4 S.C.R. 465 / [2019] 4 S.C.R. 563 / [2019] 4 S.C.R. 653；未连 
- dd 41，无中立锚，成员：441 D.L.R. (4th) 1；未连 
- dd 9，有中立锚，成员：2020 ONCA 169；未连 
- dd 4，有中立锚，成员：2016 ONCA 646；未连 
- dd 2，有中立锚，成员：2021 ONCA 524；未连 
- dd 2，无中立锚，成员：76 R.P.R. (5th) 104；未连 
