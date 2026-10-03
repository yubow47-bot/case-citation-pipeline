# F.C.A. 的澳大利亚含义：独立权威来源核实

核实日期：2026-10-02。任务：给 AU 候选含义补独立来源，区分权威解释与语料写法用例。

## 结论与定位

1. Australian Guide to Legal Citation 第四版（AGLC4），r 2.3.1，印刷页 55（PDF 第 80 页）列明 FCA 对应 Federal Court of Australia。该表另列合议庭使用 FCA 的中立码年代为 1999–2001，2002 年起使用 FCAFC。因此 AU 候选规范名采用 Federal Court of Australia，不把裸缩写自动细分为合议庭。
2. AGLC4 r 1.6.1，印刷页 22（PDF 第 47 页）要求缩写省略句点。这为 F.C.A. 与 FCA 的标点归一提供规则依据；它没有逐字定义历史括注 F.C.A.。将带点括注对应到该法院，是结合规则与已发现的语料用例所作的项目推导，已在 AU 行中明确标识。
3. 澳大利亚联邦法院官网 Judgments FAQs 的 What is medium neutral citation? 和 MNC elements 两节明确说明该院的法院标识 FCA，Full Court judgments 一节说明 FCAFC 自 2002-01-01 使用，2002 年 1–4 月存在并列中立码。

## 来源

- 发布机构：Melbourne University Law Review Association 与 Melbourne Journal of International Law。官方出版物：[AGLC4](https://law.unimelb.edu.au/__data/assets/pdf_file/0005/3181325/AGLC4-with-Bookmarks-1.pdf)；[出版机构介绍](https://law.unimelb.edu.au/mulr/aglc/about)。官方 PDF 版权页列第四版 2018，2019、2020 年有小幅修订。
- 法院自行说明：[Federal Court of Australia — Judgments FAQs](https://www.fedcourt.gov.au/digital-law-library/judgments/judgments-faq)。
- CA 含义的独立来源：[加拿大司法部网站所载著作缩写表](https://www.justice.gc.ca/eng/rp-pr/csj-sjc/harmonization/denau/abbrevia.html)，F.C.A. 解释为 Federal Court of Appeal。

## 记录与适用边界

- AU 行保存于 `court_designations_fca_au_proposal.csv`，自带 source、source_locator、source_printed_designation 与 evidence_status。
- source_printed_designation=FCA；printed_designation=F.C.A.；normalized_key=fca；court_country=AU；status=verified_meaning_only。
- 既有语料实例 128 A.L.R. 540 (F.C.A.)、172 A.L.R. 185 (F.C.A.)、53 A.L.R. 373 (F.C.A.) 保留为写法用例，不据它们独立授权法院含义，也未在本次重新核对这些案件的合议庭身份。
- AGLC 的中立码起用年代不等于历史括注起用年代。
- CA 与 AU 同键仍需消歧。本次完成的是 AU 权威来源补证，不更改生产分类逻辑或重跑产出，也不把 AU 行追加到只有单值索引的生产表而覆盖 CA 含义。

## 核对方式

已通过网页工具读取官方 PDF 的相关条文和完整法院标识表，并与法院官网说明交叉核对。官方 PDF 截图请求未在当前工具输出中返回可视图像；本地下载受网络沙箱限制，因此不宣称已完成本地渲染目视检查。
