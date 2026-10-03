# 四方向独立审批

审核：gpt-6.1-sol，medium，2026-10-02。已纳入 head 25 + tail 25，全 50 项逐项审查。批准属于用户授权的代理审核，**不是 human-reviewed**。

50 项：**25 批准元数据、7 部分支持、18 暂缓**。批准只限每项列明的汇编身份／法域元数据，不证明具体案件来源、独占范围或所有同形用法。证据缺口不等于现有表错。

## 方向 1：partial

All 50 targets reviewed individually: 25 approved reporter metadata, 7 partial, 18 withheld.

依据：Both complete 25-row collections incorporated.；Independent opened exact authorities repair several collector gaps.；25 full approvals are bibliographic/jurisdiction metadata only.

限制：Some authorities were blocked; related-title substitutions rejected.；No numeric ranges or case_origin verified.

获准：Only listed eligible metadata updates; retain estimated confidence and semantic fields.

拒绝：Blanket upgrade of 50.；Use source summaries as opened evidence.；Automatic reporter-to-case_origin inheritance.

## 方向 2：partial

Retain existing NL and PE rows as two-province candidate reporting scope, backed by direct corpus samples. Approve external title identity only; full authoritative geographic coverage still unverified.

依据：Channel 1 directly records NL 227 and PE 52, with distinct provincial courts.；Law Society PEI catalogue confirms series title and holdings on PDF page 10.

限制：Catalogue does not describe territorial contents; title and publishing location alone cannot establish exclusivity.；Lawi transcription failed to open in independent review and is not official publisher-hosted.；No attribution of an individual case to NL or PE from reporter alone.

获准：Keep NL/PE rows unchanged; attach authority_identity_only evidence with explicit scope restriction.

拒绝：Mark exact NL or PE full metadata verified using folded CA.；Choose a case's province from this shared reporter.；Certify full/exclusive reporter coverage.

## 方向 3：partial

Retain QC and SK reporter rows. Approve exact Que.K.B. metadata; Saskatchewan title/Canada identity is partially supported. Reject propagated GB as evidence that either reporter is British, and reject a universal contamination explanation.

依据：Cardiff exact Que.K.B. -> Quebec Official Reports King's Bench -> Canada, Quebec.；Law Society Saskatchewan guide lists Sask LR under Law Reports (Canada).；Channel 4: Que.K.B. CA17/GB9 (hop1), CA18/GB9 (hop2); Sask.L.R. CA12/GB4.；Que.K.B. aggregate A.C.9 source linkage supports a plausible Privy Council route; Saskatchewan sources are WWR/DLR/WLR, not a proven AC chain.

限制：No underlying individual nine/four records traced.；No proof all mixed records are Privy Council appeals.；Saskatchewan exact province scope is not independently authority-confirmed by a jurisdiction field; country/title support is partial.

获准：Que.K.B. exact QC metadata update.；Sask.L.R. authority_country_only evidence, keep SK unchanged and explicitly unverified at province scope.；Preserve hop distributions; seek raw citation chains.

拒绝：Change QC/SK to GB.；Declare all 13 mixed items explained.；Use heuristic identity merging or two-hop inheritance as case_origin evidence.

## 方向 4：partial

Independently retain today's existing S.J. structural split as a corpus-supported rule: no-volume [year] S.J. No. -> SK; genuine volume -> GB. Approve GB journal metadata, qualify bounds and SK external-title verification.

依据：Opened Cardiff S.J./SJ maps Solicitors' Journal to United Kingdom.；ISSN record independently identifies SJ journal and archived numbered volumes.；Opened Law Society SK guide prints no-volume SJ No. alongside explicit Sask QB/CA parentheticals.；Channel 1: 81 SK parallels; existing mainline fix reported 211 SK, 19 GB and 3 unsupported year-as-volume cases in collection_special.

限制：Emond authoritative SJ expansion could not be reopened independently (502); its collected title claim is not independently certified here.；No proof 999 is a historical maximum.；Guide examples plus corpus are not proof every no-volume token in all data is SK, nor every volume token GB.；Collection counts refer to different corpus slices.

获准：Keep present split and ranges unchanged in this task.；Upgrade GB journal metadata only.；Keep three year-as-volume rows unsupported.；Any later confidence/structure change needs separate production tests with wrong-year/No./volume regression cases.

拒绝：Treat 1–999 as historical range.；Use dotted/undotted normalization to invent new identity inference.；Change estimated confidence now.；Report today's baseline S.J. fix as newly implemented here.

## 采集错误与审核修正

C.B.N.S. 被错配为 Canadian Bankruptcy Reports；独立打开 [JustCite 原生引证格式表](https://www.justcite.com/kb/search-technology/english-reports-reference-formats/) 确认 Common Bench New Series。A. & E. 被建议替换为 Admiralty and Ecclesiastical Cases，但基线为 Adolphus & Ellis；精确缩写未核，暂缓。R.D.J. 的采集扩展 Revue de jurisprudence 与基线 Revue de droit judiciaire 不同；不得替换。C.A.R. 采集为 Court of Appeal Reports 与基线 Criminal Appeal Reports 不同，暂缓。Can.S.C.R. 的原 DOJ 来源不足；独立 [Cardiff 379页](https://legalabbrevs.cardiff.ac.uk/page/379/?paged=379) 补齐精确身份和 Canada。Ont.L.R. 的 O.R. 来源无效。F.Supp2d 单条不能核实裸 FSUPP；独立 [Sacramento 公共法律图书馆](https://saclaw.org/resource_library/federal-primary-law/) 补齐裸 F.Supp. 及美国法院覆盖。

## 50 项记录

|归一键|缩写|结论|批准范围／缺口|
|---|---|---|---|
|canscr|Can. S.C.R.|approved|Exact Can.S.C.R. alternative and Canada jurisdiction are present; missing collector URL repaired independently.|
|us|U.S.|approved|Court confirms official series; library explicitly identifies U.S. form.|
|chd|Ch. D.|approved|Official England and Wales report guide and court library agree on form.|
|qbd|Q.B.D.|approved|Official England and Wales report guide and court library agree on form.|
|f|F.|approved|Supplemental opened library source expressly maps F. and US federal appellate coverage; repairs collector gap.|
|ontlr|Ont. L.R.|withheld|Head collector cites O.R., a different abbreviation; OLR in Law Society guide also does not establish exact Ont.L.R.|
|ontappr|Ont. App. R.|withheld|No exact Ont.App.R. authoritative record opened.|
|ucqb|U.C.Q.B.|approved|Exact U.C.Q.B. and Canada, Ontario jurisdiction fields.|
|lcjur|L. C. Jur.|approved|Exact L.C.Jur. alternative supports normalized printed form; repairs head collection gap.|
|uccp|U.C.C.P.|approved|Exact U.C.C.P. mapped with Canada, Ontario.|
|bcrep|B.C. Rep.|withheld|Exact B.C.Rep. remains unverified; BCR/BCLR cannot substitute. Cardiff also lists B.C.Rep. for Lowndes & Maxwell in England, so initials are ambiguous.|
|chapp|Ch. App.|approved|Court library gives Ch App and style guide gives England and Wales series.|
|gr|Gr.|withheld|Bare Gr. is unresolved; baseline Grant's Chancery attribution lacks an exact opened match.|
|qlr|Q.L.R.|approved|Exact Q.L.R. with Canada, Quebec.|
|nzlr|N.Z.L.R.|withheld|No exact N.Z.L.R. authority opened in the collection or independent review.|
|rl|R.L.|withheld|Exact R.L. unresolved; baseline Revue légale is not verified by a related source.|
|hlcas|H.L. Cas.|approved|Publisher's English Reports formats lists exact H.L.Cas.; repairs collector's unrelated bare H.L. source.|
|ny|N.Y.|approved|Exact N.Y. and United States, New York field supports existing country row.|
|cbns|C.B.N.S.|approved|Exact C.B. N.S. appears in publisher English Reports formats. Collector's Canadian Bankruptcy Reports substitution is rejected.|
|pd|P.D.|approved|Official England and Wales report guide and court library agree on form.|
|timeslr|Times L.R.|withheld|TLR in an opened England guide identifies a related abbreviation, not exact Times L.R.|
|nsrep|N.S. Rep.|withheld|Exact N.S.Rep. unresolved; Nova Scotia title catalogue cannot establish an alias also resembling new-series notation.|
|a|A.|partial|Exact A form identifies reporter, but opened evidence does not directly establish its US territory.|
|ne|N.E.|approved|Exact N.E. and United States jurisdiction fields.|
|usr|U.S.R.|withheld|Official U.S. page does not establish exact U.S.R. alias.|
|fsupp|F. Supp.|approved|Opened public law library explicitly supports bare F. Supp. and US district court coverage; second-series-only inference is not used.|
|rdj|R.D.J.|withheld|Collector substitutes Revue de jurisprudence for baseline Revue de droit judiciaire. These are distinct titles; exact R.D.J. evidence missing.|
|eb|E. & B.|approved|Exact E. & B. in publisher English Reports formats.|
|tt|T.T.|withheld|No exact authoritative Tribunal du travail/reporting-role record opened.|
|ljch|L.J. Ch.|approved|Law Society guide places LJCh explicitly under Law Reports (England).|
|sct|S.Ct.|approved|Exact S.Ct. and United States jurisdiction.|
|cpd|C.P.D.|approved|Official England and Wales report guide and court library agree on form.|
|mass|Mass.|withheld|Massachusetts official page was blocked (403); exact title/form and territory remain independently unverified.|
|br|B.R.|partial|Opened Cardiff resolves B.R. reporter title, unlike collector's court-only source. Court designation usage still needs context.|
|nbrep|N.B. Rep.|withheld|Exact Cardiff record fetch failed; source summary alone is insufficient.|
|lcj|L.C.J.|approved|Exact L.C.J. alternative and Quebec jurisdiction.|
|ae|A. & E.|withheld|Collector proposes Admiralty and Ecclesiastical Cases but baseline is Adolphus & Ellis. Opened JustCite only Ad.&E.; exact A.&E. attribution remains unresolved.|
|ltns|L. T. N. S.|partial|LTNS supports the title family; geographic scope not separately established on opened exact entry.|
|nw|N.W.|partial|Exact N.W. reporter identity; collector's secondary territorial claim is not authority-reviewed.|
|ontwn|Ont. W.N.|approved|Exact Ont.W.N. with Canada, Ontario.|
|car|C.A.R.|withheld|Collector proposes Court of Appeal Reports but baseline is Criminal Appeal Reports. Exact C.A.R. remains unverified; other CAR uses exist.|
|omh|O'M. & H.|approved|Exact abbreviation and England & Wales jurisdiction fields.|
|cancrcas|Can. Cr. Cas.|withheld|CCC source is a different form; exact Can.Cr.Cas. alias is unsupported.|
|grant|Grant|withheld|Bare Grant not verified; unrelated Russell election report source must not substitute.|
|exd|Ex. D.|approved|Official England and Wales report guide and court library agree on form.|
|sc|S.C.|withheld|Normalized S.C. has Quebec and Scotland rows. No independently opened exact series evidence resolves each row; preserve ambiguity.|
|p|P.|partial|Opened guide verifies P Probate GB. UC Davis verifies P Pacific identity but does not give territory. Preserve both rows and guards.|
|hl|H.L.|partial|Baseline also covers Clark H.L.; collected LR HL evidence does not verify all meanings. Court marker role remains ambiguous.|
|eq|Eq.|approved|Eq mapped by court library; LR Eq territorial context supplied by England and Wales guide.|
|pc|P.C.|partial|Both guides support reporter series; parenthetical P.C. may name tribunal. No case-origin or bare-token exclusivity approval.|

## 精确应用边界

final_review.json 列出逐行 eligible_table_updates 和 special_table_updates。仅修改来源、定位、核验标签和追加说明；confidence=estimated、法域、区间、行数及归一键均不改。P. 按 GB/US 两行分别审批；H.L./P.C./B.R. 保留角色限制；Nfld/PE 不准用 folded CA 升级精确省。S.J. SK 现有核验标签不得降级或替换，本次仅独立保留结构规则。

本轮不准建立新身份推断、启发式归并、case_origin、exclusive_scope_rule 或多跳继承。日后若要改 confidence 或结构规则，应另测生产分类，含 No.、真正卷号、年份误作卷号及同形边界。三个年份误作卷号的 S.J. 仍 UNSUPPORTED。没有声称重跑或验证全流程。

## 独立来源查阅

- [来源](https://legalabbrevs.cardiff.ac.uk/page/379/?paged=379)：Exact Can.S.C.R. and S.Ct. title/jurisdiction；Opened; both explicit mappings confirmed.
- [来源](https://legalabbrevs.cardiff.ac.uk/page/254/?paged=254)：L.C.J./L.C.Jur. exact aliases and Quebec；Opened; confirmed. Also B.C.Rep. is a Lowndes & Maxwell alternative, challenging unqualified BC attribution.
- [来源](https://legalabbrevs.cardiff.ac.uk/page/325/?paged=325)：QLR, Que.K.B., B.R. metadata；Opened; Quebec jurisdiction explicit.
- [来源](https://legalabbrevs.cardiff.ac.uk/page/403/?paged=403)：UCCP provincial metadata；Opened; Ontario explicit.
- [来源](https://legalabbrevs.cardiff.ac.uk/record/upper-canada-queens-bench-reports-new-series/)：UCQB provincial metadata；Opened; Ontario explicit.
- [来源](https://legalabbrevs.cardiff.ac.uk/page/287/?paged=287)：NY country metadata；Opened; United States, New York explicit.
- [来源](https://legalabbrevs.cardiff.ac.uk/page/303/?paged=303)：OntWN exact alias/province；Opened; confirmed.
- [来源](https://legalabbrevs.cardiff.ac.uk/record/omalley-hardcastle-election-cases/)：OMH exact identity/territory；Opened; England & Wales explicit.
- [来源](https://lawfoundation.org.nz/style-guide2018/appendix-4.html)：English LR forms and territory；Opened; ChD/QBD/CPD/PD/ExD/P/LR Eq/LR ChApp/LR HL/LR PC supported. No range changes authorized.
- [来源](https://dcj.nsw.gov.au/content/dcj/ctsd/courtsandtribunals/courts-and-tribunals/resources/law-courts-library/law-reports-online.html)：Forms for historic series and contextual roles；Opened; forms confirmed. Bare H.L./P.C. still require reporter/court-role distinction.
- [来源](https://www.justcite.com/kb/search-technology/english-reports-reference-formats/)：CBNS/E&B/HLcas; AE mismatch；Opened publisher format documentation; first three confirmed, exact AE unconfirmed. Collector bankruptcy substitution rejected.
- [来源](https://saclaw.org/resource_library/federal-primary-law/)：F./F.Supp. country and base-series evidence；Opened; exact forms with US federal court coverage, resolving second-series-only deficit.
- [来源](https://law.ucdavis.edu/library/course-support/common-abbreviations)：A/NW/P identity；Opened; title identities confirmed; territorial claims not established by exact entries alone.
- [来源](https://legalabbrevs.cardiff.ac.uk/record/north-eastern-reporter/)：NE exact form and country；Opened; United States explicit.
- [来源](https://www.lawsociety.sk.ca/wp-content/uploads/KBRA2022-STUDENTS.pdf)：LJCh England, SaskLR Canada, SJ citation structure；Opened; confirms mappings and no-volume SJ No. alongside provincial court labels. No exact SJ expansion field.
- [来源](https://lawsocietypei.ca/media/files/Law%20Library%20Catalogue%20Print%20Serials%20April%2028,%202016.pdf)：Nfld PEI series identity and scope；Opened PDF; title/holdings confirmed; complete territorial coverage not described.
- [来源](https://legalabbrevs.cardiff.ac.uk/page/368/?paged=368)：SJ journal exact form and jurisdiction；Opened; S.J./SJ -> Solicitors' Journal -> United Kingdom.
- [来源](https://portal.issn.org/resource/ISSN/0038-1047)：SJ numbered-volume history；Opened; bibliographic identity and numbered archive entries; no 999 ceiling.
- [来源](https://jcpc.uk/cases)：Exact mixed nine/four records；Opened official case portal; lacks matching case identifiers, no exact corpus trace established.
- [来源](https://style.emond.ca/references/mcgill-examples-applications-10)：SJ Saskatchewan title expansion；Independent opens failed (502/internal error); collector claim not independently authority-certified.
- [来源](https://www.mass.gov/info-details/about-the-reporters-office)：Mass identity and scope；Blocked 403; no independent full approval.
- [来源](https://legalabbrevs.cardiff.ac.uk/page/282/?paged=282)：NBRep exact form and province；Independent fetch failed; full approval withheld.
- [来源](https://books.lawi.ca/how-to-use-our-indexes/)：NfldPEI full territory description；Independent fetch failed; publisher-description transcription not authority confirmation.
- [来源](https://www.mcgill.ca/library/files/library/Legal_Abbreviations.pdf)：P homonyms；404; independent Probate mapping from other source, Pacific identity only.
- [来源](https://www.bibl.ulaval.ca/disciplines/droit/je-veux/trouver-des-abreviations-juridiques)：Various exact forms；502; search snippets not accepted as opened source.

应用预检订正：去除一条重复的 P.D./GB 更新意图；现为 33 条逐项元数据意图 + 5 条特殊元数据意图 = 38 条。50 个目标键逐项唯一且与清单完全一致；联合更新意图无重复，全部有基线匹配，五条特殊意图各唯一匹配。基线 P.D./GB 有两条物理记录，同一元数据意图适用于两条，不能把更新意图再重复登记。 substantive verdicts unchanged.
