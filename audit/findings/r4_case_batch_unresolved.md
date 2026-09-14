# R4 Stage 3：案件级核验批次——未决清单（unresolved within this round's budget）

**批次上限**：50 个引证身份 / 200 次查询（~4/案）。**本批次实际核验 32 个引证身份**
（`decisions/case_origin_manual.csv`），**未决 18 个**——按下段逐条登记，
**不降低来源标准、不猜**（约束四）。

## 执行说明（如实）

- 本轮原计划用 3 个并行研究子代理（各约 17 案）承担检索，**三个子代理全部在启动阶段失败**
  （无产出文件）。改由 Lead 直接核验：单案 1–2 次查询，走 BAILII UKPC（标题自带管辖地）、
  AustLII/CommonLII、vLex、Scottish Council of Law Reporting、DPLA 判决原件等
  **优先级 1–4** 的来源；Wikipedia 只作线索、不作唯一支撑（逐行 notes 可查）。
- 未决 18 案**不是**「查不到」，而是**本轮查询预算与上下文预算耗尽**（每案仍需 1–2 次
  定向检索 + 逐案读源）。它们全部有明确的下一步检索路径（见下），留待下一轮或下一批次。

## 未决 18 案（按队列槽位）

| # | 印刷引证 | 槽 | dd | 拟查路径（下一步） |
|---|---|---|---|---|
| 1 | [1899] A.C. 367 | A | 43 | BAILII UKPC/1899 索引：CPR v. Notre Dame de Grâce（魁北克教区案） |
| 2 | [1891] A.C. 325 | A | 28 | BAILII UKHL：Smith v. Baker & Sons（英格兰上诉） |
| 3 | 3 App. Cas. 1155 | A | 27 | BAILII UKPC/1877–78 索引：Flannery v. Waterford & Limerick Rly（爱尔兰） |
| 4 | (1846), 18 E.R. 667 | B | 1 | English Reports 卷 18 目次（须先确认是否真为枢密院案——`P.C.` 标注可能是语料伪迹） |
| 5 | (1881), 9 A.C. 371 | B | 2 | 与 (1884) 9 App. Cas. 371（Letterstedt）的关系需辨（疑为**误拼/异年**的同一引证） |
| 6 | (1888), 13 App. Cas. 222 | B | 1 | BAILII UKPC/1887–88：Victorian Railways Commissioners v. Coulton（维多利亚殖民地） |
| 7 | [1893] A.C. 150 | B | 1 | BAILII UKPC/1892–93 索引 |
| 8 | [1895] A.C. 425 | B | 5 | BAILII UKPC/1895 索引（该卷多案；须逐案比对印刷形） |
| 9 | [1903] A.C. 151 | B | 15 | BAILII UKPC/1902–03 索引 |
| 10 | [1907] A.C. 179 | B | 6 | BAILII UKPC/1906–07 索引 |
| 11 | [1920] A.C. 509 | C | 1 | 边界案：BAILII UKHL/1920 索引 + 上院管辖史 |
| 12 | (1921), 2 A.C. 41 | C | 3 | BAILII UKHL/1921：British & Foreign Marine Insurance |
| 13 | [1921] 2 A.C. 438 | C | 3 | BAILII UKHL/1921：Russian Commercial & Industrial Bank |
| 14 | [1923] A.C. 48 | C | 6 | BAILII UKHL/1922–23：British & Beningtons v. North Western Cachar Tea |
| 15 | [1924] A.C. 980 | C | 2 | BAILII UKHL/1924 索引 |
| 16 | (1931), 46 C.L.R. 41 | C | 1 | AustLII HCA/1931 索引 |
| 17 | (1940), 64 C.L.R. 221 | C | 1 | AustLII HCA/1940 索引 |
| 18 | [1949] 78 C.L.R. 313 | C | 1 | AustLII HCA/1949 索引（注意：`[1949] 78 C.L.R.` 印刷形异常，疑似**年槽/卷槽颠倒**——顺带验证） |

## 已核验批次的观察（供下一轮）

1. **语料案名错误一处（真发现）**：`[1914] A.C. 599` 的语料案名是「Boudreau v. The King」，
   而该引证实为 **Ibrahim v. The King**（P.C.，上诉自香港）——案名携带/投票错误的实例，
   与本轮 B20 残差同源。已写入人工表 notes。
2. **报告年 ≠ 判决年 8 例**：Anns（1977→1978）、Salomon（1896→1897）、Makin（1893→1894）、
   City of Toronto（1904→1905）、Grand Trunk（1906→1907）、Tennant（1893→1894）、
   AG Manitoba（1901→1902）、Hedley Byrne（1963→1964）——**这正是「报告年不得当判决年」
   的实证**，人工表逐行分列两栏。
3. **BAILII UKPC 的标题自带管辖地**（如 `(Quebec)`/`(New South Wales)`/`(Cape of Good Hope)`）
   ——这是本批次最有效的**权威「上诉来源」证据形态**；索引为 `(Canada)` 时省别不写
   （只按明示省名填省），避免把索引粗粒度当省别证据。
4. **来源地分布**（32 行）：CA 18、GB 8、AU 3、HK 1、ZA 1、NZ 1——即本批次将为
   语料新增 **18 个 DOMESTIC_CA** 与 **14 个 FOREIGN** 的**案件级**判定。
