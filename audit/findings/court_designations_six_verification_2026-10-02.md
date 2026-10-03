# 六个法院缩写提案的来源核验

核验日期：2026-10-02。范围仅为 court_designations_doj_proposal.csv 的六行；未更改生产决策表或运行管线。

来源：[加拿大司法部网站所载著作的缩写表（存档）](https://www.justice.gc.ca/eng/rp-pr/csj-sjc/harmonization/denau/abbrevia.html)。本次读取网页正文，非仅依赖搜索摘要。

| 印刷形 | 来源直接给出的含义 | 提案国家／省级字段 | 核验结论 |
|---|---|---|---|
| S.C.C. | Supreme Court of Canada | CA／CA | 含义已核实；recognized 提案有来源支持 |
| Ont.C.A. | Ontario Court of Appeal | CA／ON | 含义已核实；该条目位于 Law Journals and Law Reports 节，不能仅因节标题判为报告集 |
| B.C.C.A. | British Columbia Court of Appeal | CA／BC | 含义已核实；recognized 提案有来源支持 |
| B.C.S.C. | British Columbia Supreme Court | CA／BC | 含义已核实；recognized 提案有来源支持 |
| T.C.C. | Tax Court of Canada | CA／CA | 含义已核实；recognized 提案有来源支持 |
| S.C. | Statutes of Canada；Superior Court | 留空 | 同页自证多义；维持 ambiguous_designation，不指定法院或国家 |

上述国家／省级字段表示所列法院身份所属地域，并非由括注证明的具体案件来源地。五个明确项的加拿大含义得到直接支持；本核验未证明全球无同形缩写，也未核定适用年代。S.C. 即使在上下文中可排除成文法，Superior Court 仍不足以确定唯一法院。

带点法院名称与中立引证码必须分开处理：原页另外列 SCC 与 TCC 为中立引证；不能把带点缩写自动认作中立引证或改变解析类型。Ont. C.A. 与 Ont.C.A. 同键属于项目的标点／空格归一，不是原页另列别名；ON CA 不同键，不新增。

提案六行已补日期和精确条目定位。删去 S.C. 备注中「各省亦泛指 Supreme Court」的无来源断言。未采纳至 decisions/court_designations.csv。
