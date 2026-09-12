# case_origin.csv 枢密院部分：逐条对照（PROBLEMS #59）

仪器：`decisions/tools/build_case_origin.py`（可重放，`--offline` 只用缓存）。

- CanLII ukpc 缓存覆盖：**1888–1959 年，624 条**（可解析出双方者）——这是来源的边界，不是匹配器的边界
- 本管线候选组（GB 法域、印在枢密院类汇编上）：5668
- 对上：211 组（其中过门槛 117）→ 表 203 行（每种印刷写法一行）
- 对上多条 CanLII 记录的组：18（同名不同年的系列案；库里全是加拿大来源，来源地不受影响）

## 已知案例核对

应对上（在缓存覆盖内、且库里确有此上诉）：

- `Toronto Electric Commissioners v. Snider`：对上（Toronto Electric Commissioners v. Snider）
- `John Deere Plow Co. v. Wharton`：对上（John Deere Plow Co. Ltd. v. Wharton）
- `St. Catharines Milling and Lumber Co. v. The Queen`：对上（St. Catherine's Milling and Lumber Company v. The Queen）
- `St. Catherine’s Milling and Lumber Co. v. The Queen`：对上（St. Catherine's Milling and Lumber Company v. The Queen）
- `Attorney-General for Ontario v. Attorney-General for the Dominion`：对上（Attorney-General for the Dominion of Canada v. Attorney-General for Ontario; Attorney-General for Quebec v. Attorney-General for Ontario）

### 对上的匹配分支留痕（看的不是「过了没有」，是走的哪一支）

- `Toronto Electric Commissioners v. Snider` × CanLII「Toronto Electric Commissioners v. Snider」（1925）
  - 本管线 commissioners | electric | toronto ⇄ snider ／ CanLII commissioners | electric | toronto ⇄ snider
  - 顺序分支 过；交错分支 不过 → 走**顺序**
- `John Deere Plow Co. v. Wharton` × CanLII「John Deere Plow Co. Ltd. v. Wharton」（1914）
  - 本管线 deere | john | plow ⇄ wharton ／ CanLII deere | john | plow ⇄ wharton
  - 顺序分支 过；交错分支 不过 → 走**顺序**
- `St. Catharines Milling and Lumber Co. v. The Queen` × CanLII「St. Catherine's Milling and Lumber Company v. The Queen」（1888）
  - 本管线 catharines | lumber | milling | st ⇄ ∅ ／ CanLII catherine | lumber | milling | st ⇄ ∅
  - 顺序分支 过；交错分支 不过 → 走**顺序**
- `St. Catherine’s Milling [St. Catherine’s Milling and Lumber Co. v. The Queen` × CanLII「St. Catherine's Milling and Lumber Company v. The Queen」（1888）
  - 本管线 catherine | lumber | milling | st ⇄ ∅ ／ CanLII catherine | lumber | milling | st ⇄ ∅
  - 顺序分支 过；交错分支 不过 → 走**顺序**
- `Attorney-General for Ontario v. Attorney-General for the Dominion` × CanLII「Attorney-General for the Dominion of Canada v. Attorney-General for Ontario; Attorney-General for Quebec v. Attorney-General for Ontario」（1896）
  - 本管线 ontario ⇄ canada ／ CanLII canada ⇄ ontario | quebec
  - 顺序分支 不过；交错分支 过 → 走**交错**

不应对上——1888 年前 / 库里没有这条上诉（**这是覆盖缺口，不是匹配失败**）：

- `Citizens Insurance Co. of Canada v. Parsons`：未对上（1881，早于 ukpc 库起点 1888）
- `Hodge v. The Queen`：未对上（1883，早于 1888）
- `Union Colliery Co. of British Columbia v. Bryden`：未对上（1899 在窗内，但这条上诉不在 ukpc 库里）

不应对上（英国本土 / 其他英联邦上诉）：

- `Donoghue`：未对上
- `Anns v. Merton`：未对上
- `Makin`：未对上
- `Hedley Byrne`：未对上
- `Salomon`：未对上
- `Woolmington`：未对上

## 对上的组（按 dd 降序，全列）

| dd | 过门槛 | 本管线案名 | 年份 | CanLII 标题（年） | 印刷写法 |
|---:|---|---|---|---|---|
| 66 | 是 | Attorney-General for Ontario v. Attorney-General for the Dominion | 1896 | Attorney-General for the Dominion of Canada v. Attorney-General for Ontario; Attorney-General for Quebec v. Attorney-General for Ontario（1896） | [1896] A.C. 348; [1896] A.C. 248 |
| 48 | 是 | John Deere Plow Co. v. Wharton | 1915 | John Deere Plow Co. Ltd. v. Wharton（1914） | [1915] A.C. 330 |
| 48 | 是 | Proprietary Articles Trade Association v. Attorney-General for Canada | 1931 | Proprietary Articles Trade Association v. Canada (Attorney General)（1931） | [1931] A.C. 310 |
| 41 | 是 | Toronto Electric Commissioners v. Snider | 1925 | Toronto Electric Commissioners v. Snider（1925） | [1925] A.C. 396; [1925] A.C. 396 |
| 40 | 是 | Attorney-General for Canada v. Attorneys-General for Ontario, Quebec and Nova Scotia | 1898 | Attorney-General for the Dominion of Canada v. Attorney-General for Ontario; Attorney-General for Quebec v. Attorney-General for Ontario（1896） | [1898] A.C. 700 |
| 40 | 是 | City of Montreal v. Montreal Street Railway | 1912 | City of Montreal v. Montreal Street Railway Company (The Attorney-General For the Dominion of Canada and the Attorney-General For the Province of Quebec Intervening)（1912） | [1912] A.C. 333 |
| 40 | 是 | Edwards v. Attorney‑General for Canada | 1930 | Edwards v. Canada (Attorney General)（1929） | [1930] A.C. 124 |
| 38 | 是 | Attorney‑General for Canada v. Attorney‑General for Ontario | 1937 | Ontario (Attorney General) v. Canada (Attorney General)（1937）; Canada (Attorney General) v. Ontario (Attorney General)（1937） | [1937] A.C. 326; [1937] A.C. 355 |
| 36 | 是 | Shannon v. Lower Mainland Dairy Products Board | 1938 | Shannon v. Lower Mainland Dairy Products Board（1938） | [1938] A.C. 708; [1938] A.C. 708 |
| 35 | 是 | R. v. Nat Bell Liquors Ltd | 1922 | R. v. Nat Bell Liquors Limited（1922） | [1922] 2 A.C. 128 |
| 34 | 是 | Cedars Rapids Manufacturing and Power Co. v. Lacoste | 1914 | Cedars Rapids MFG. and Power Co. v. Lacoste（1914） | [1914] A.C. 569 |
| 32 | 是 | St. Catherine’s Milling and Lumber Co. v. The Queen | 1888 | St. Catherine's Milling and Lumber Company v. The Queen（1888） | (1888), 14 A.C. 46; (1888), 14 App. Cas. 46 |
| 32 | 是 | Attorney-General for Alberta v. Attorney-General for Canada | 1939 | Alberta (Attorney General) v. Canada (Attorney General)（1938） | [1939] A.C. 117 |
| 30 | 是 | Attorney-General for Ontario v. Attorney-General for Canada | 1912 | Dominion of Canada v. Province of Ontario（1910）; Attorneys-General For the Provinces of Ontario, Quebec, Nova Scotia, New Brunswick, Manitoba, Prince Edward Island, and Alberta, v. Attorney-General For the Dominion of Canada and the Attorney-General For the Province of British Columbia（1912） | [1912] A.C. 571 |
| 30 | 是 | Attorney-General for Canada v. Attorney-General for Alberta | 1916 | Att'y-Gen'l for Alberta v. Att'y-Gen'l of Canada（1915）; Canada (Attorney-General) v. Alberta (Attorney-General)（1916） | [1916] 1 A.C. 588 |
| 30 | 是 | Great West Saddlery Co. v. The King | 1921 | R. v. Great West Saddlery Company（1921） | [1921] 2 A.C. 91 |
| 30 | 是 | Labour Relations Board of Saskatchewan v. John East Iron Works, Ltd | 1948/1949 | Labour Relations Board of Saskatchewan v. John East Iron Works Limited（1948） | [1949] A.C. 134 |
| 28 | 是 | Nance v. British Columbia Electric Railway Co | 1951 | Nance v. British Columbia Electric Railway Company（1951） | [1951] A.C. 601 |
| 26 | 是 | Attorney‑General for Alberta v. Attorney‑General for Canada | 1947 | Alberta (Attorney General) v. Canada (Attorney General)（1947） | [1947] A.C. 503; [1947] A.C. 503 |
| 24 | 是 | Ladore v. Bennett | 1939 | Ladore v. Bennett（1939） | [1939] A.C. 468 |
| 23 | 是 | Attorney‑General for Canada v. Attorney‑General for British Columbia | 1930 | Canada (Attorney General) v. British Columbia (Attorney General)（1929） | [1930] A.C. 111 |
| 22 | 是 | Lymburn v. Mayland | 1932 | Mayland v. Lymburn（1932） | [1932] A.C. 318 |
| 22 | 是 | Toronto Corporation v. York Corporation | 1938 | Toronto (City) v. York (Township)（1938） | [1938] A.C. 415 |
| 21 | 是 | Attorney-General for Ontario v. Canada Temperance Federation | 1946 | Ontario (Attorney General) v. Canada Temperance Federation（1946） | [1946] A.C. 193 |
| 20 | 是 | Canadian Federation of Agriculture v. Attorney‑General for Quebec | 1951 | Reference Re Validity of Section 5(a) of Tre Dairy Industry Act, Canadian Federation of Agriculture v. Attorney-General of Quebec et al. Margarine Case（1950） | [1951] A.C. 179 |
| 19 | 是 | Bonanza Creek Gold Mining Co. v. The King | 1915/1916 | The Bonanza Creek Gold Mining Co. v. The King（1916） | [1916] 1 A.C. 566 |
| 18 | 是 | Fort Frances Pulp and Power Co. v. Manitoba Free Press Co | 1923 | Fort Frances Pulp and Paper Co. v. Manitoba Free Press Co.（1923） | [1923] A.C. 695 |
| 18 | 是 | Atlantic Smoke Shops, Ltd. v. Conlon | 1943 | Atlantic Smoke Shops Limited v. Conlon（1943） | [1943] A.C. 550 |
| 17 | 是 | Attorney-General for Manitoba v. Attorney-General for Canada | 1929 | Manitoba (Attorney General) v. Canada (Attorney General)（1928） | [1929] A.C. 260 |
| 17 | 是 | Attorney-General for British Columbia v. Attorney-General for Canada (Natural Products Marketing Reference) | 1937 | British Columbia (Attorney General) v. Canada (Attorney General)（1937）; British Columbia (Attorney General) v. Canada (Attorney General)（1937） | [1937] A.C. 377 |
| 16 | 是 | Cotton v. The King | 1914 | The King v. Cotton. (Consolidated Appeals.)（1913） | [1914] A.C. 176 |
| 16 | 是 | Quebec Railway, Light, Heat and Power Co. v. Vandry | 1920 | Vandry v. Quebec Railway Light  Heat and Power Company（1920） | [1920] A.C. 662 |
| 16 | 是 | Shannon Realties Ltd. v. Ville de St-Michel | 1924 | Shannon Realties Ltd. v. Town of St. Michel; Pesant et al. v. Town of St. Michel et al.（1923） | [1924] A.C. 185 |
| 15 | 是 | Dominion Trust Co. v. New York Life Insurance Co | 1919 | Dominion Trust Company v. New York Life Insurance Company（1918） | [1919] A.C. 254 |
| 15 | 是 | City of Halifax v. Fairbanks Estate [ | 1928 | Halifax (City) v. Fairbanks Estate（1927） | [1928] A.C. 117 |
| 13 | 是 | A.G. for Manitoba v. A.G. for Canada | 1925 | Lord's Day Alliance of Canada v. Manitoba (Attorney General)（1924）; Manitoba (Attorney General) v. Canada (Attorney General)（1925） | [1925] A.C. 561 |
| 13 | 是 | Attorney‑General for British Columbia v. Kingcome Navigation Co | 1934 | British Columbia (Attorney General) v. Kingcome Navigation Company (No. 2)（1933） | [1934] A.C. 45 |
| 13 | 是 | Attorney-General for British Columbia v. Attorney-General for Canada | 1937 | British Columbia (Attorney General) v. Canada (Attorney General)（1937）; British Columbia (Attorney General) v. Canada (Attorney General)（1937） | [1937] A.C. 368 |
| 13 | 是 | Attorney General of Alberta v. Attorney General of Canada | 1943 | Reference Re the Debt Adjuistment Act, 1937 (Alberta). Attorney-General for Alberta v. Attorney-General for Canada et al.（1943） | [1943] A.C. 356 |
| 13 | 是 | Attorney General for Saskatchewan v. Attorney General for Canada | 1949 | Saskatchewan (Attorney General) v. Canada (Attorney General)（1948） | [1949] A.C. 110 |
| 12 | 是 | Royal Bank of Canada v. The King | 1913 | R. v. The Royal Bank of Canada（1913） | [1913] A.C. 283 |
| 12 | 是 | McHugh v. Union Bank of Canada | 1913 | Felix A. McHugh v. Union Bank of Canada（1913） | [1913] A.C. 299 |
| 12 | 是 | City of Victoria v. Bishop of Vancouver Island | 1921 | Bishop of Vancouver Island v. Victoria (City)（1921） | [1921] 2 A.C. 384 |
| 12 | 是 | Montreal (City) v. Watt and Scott Ltd | 1922 | City of Montreal v. Watt & Scott（1922） | [1922] 2 A.C. 555 |
| 12 | 是 | Nadan v. The King | 1926 | R. v. Nadan (Nos. 1 and 2)（1926） | [1926] A.C. 482 |
| 12 | 是 | Robins v. National Trust Co | 1927 | Robins v. National Trust Company（1927） | [1927] A.C. 515 |
| 12 | 是 | Provincial Treasurer of Alberta v. Kerr | 1933 | Kerr v. Alberta (Provincial Treasurer)（1933） | [1933] A.C. 710 |
| 12 | 是 | Noor Mohamed v. The King | 1949 | R. v. Noor Mohamed（1949） | [1949] A.C. 182 |
| 12 | 是 | Canada Steamship Lines Ltd. v. The King | 1952 | Canada Steamship Lines Limited v. R.（1952） | [1952] A.C. 192 |
| 11 | 是 | Ontario Mining Co. v. Seybold | 1903 | Ontario Mining Company, Limited and Attorney-General for Canada v. Seybold et al. and Attorney-General for Ontario（1902） | [1903] A.C. 73 |
| 11 | 是 | Board v. Board | 1919 | Board v. Board（1919） | [1919] A.C. 956 |
| 11 | 是 | Wilson v. Esquimalt and Nanaimo Railway Co | 1922 | Esquimalt & Nanaimo Railway Company v. Wilson（1921） | [1922] 1 A.C. 202 |
| 11 | 是 | Attorney-General for Quebec v. Nipissing Central Railway Co | 1926 | Quebec (Attorney General) v. Nipissing Central Railway Company（1926） | [1926] A.C. 715 |
| 11 | 是 | Winnipeg Electric Co. v. Geel | 1931/1932 | Geel v. Winnipeg Electric Company（1932） | [1932] A.C. 690 |
| 11 | 是 | Lower Mainland Dairy Products Sales Adjustment Committee v. Crystal Dairy Ltd | 1932/1933 | Lower Mainland Dairy Products Sales Adjustment Committee v. Crystal Dairy Limited（1932） | [1933] A.C. 168 |
| 10 | 是 | MacLaren v. Attorney‑General for Quebec | 1914 | MacLaren v. Attorney-General For Quebec（1914） | [1914] A.C. 258 |
| 10 | 是 | Ottawa Separate Schools Trustees v. Mackell | 1917 | Ottawa Separate School Trustees v. MacKell（1916） | [1917] A.C. 62 |
| 10 | 是 | Auger v. Beaudry | 1920 | Auger v. Beaudry（1919） | [1920] A.C. 1010 |
| 10 | 是 | City of Montreal v. Attorney‑General for Canada | 1923 | City of Montreal v. Att'y-Gen'l of Canada and Att'y-Gen'l of Quebec（1922） | [1923] A.C. 136 |
| 10 | 是 | R. v. Caledonian Collieries Limited | 1928 | R. v. Caledonian Collieries, Limited（1928） | [1928] A.C. 358 |
| 10 | 是 | Croft v. Dunphy | 1933 | Dunphy v. Croft（1932） | [1933] A.C. 156 |
| 10 | 是 | 4 Pioneer Laundry and Dry Cleaners, Ltd., v. Minister of National Revenue | 1940 | Pioneer Laundry & Dry Cleaners Limited v. Canada (National Revenue)（1939） | [1940] A.C. 127 |
| 10 | 是 | The King v. I.O.F. and the Attorney-General of Canada | 1940 | Canada Rice Mills Ltd. v. The King（1939） | [1940] A.C. 513 |
| 10 | 是 | Attorney-General for Canada v. Attorney-General for Quebec | 1946/1947 | Canada (Attorney General) v. Quebec (Attorney General)（1946） | [1946] A.C. 33; [1947] A.C. 33 |
| 10 | 是 | Attorney‑General for British Columbia v. Esquimalt and Nanaimo Railway Co | 1950 | Esquimalt & Nanaimo Railway Company v. British Columbia (Attorney General)（1949） | [1950] A.C. 87 |
| 9 | 是 | Canadian Pacific Railway Co. v. Parent | 1917 | Canadian Pacific R. Co. v. Parent（1917） | [1917] A.C. 195 |
| 9 | 是 | Luscar Collieries Ltd. v. McDonald | 1927 | McDonald v. Luscar Collieries Limited（1927） | [1927] A.C. 925 |
| 9 | 是 | Attorney‑General for British Columbia v. Canadian Pacific Railway Co | 1927 | British Columbia (Attorney General) v. Canadian Pacific Railway Company（1927） | [1927] A.C. 934 |
| 9 | 是 | British Coal Corporation v. The King | 1935 | R. v. British Coal Corporation（1935） | [1935] A.C. 500 |
| 8 | 是 | St. Catharines Milling and Lumber Co. v. The Queen | 1887/1888 | St. Catherine's Milling and Lumber Company v. The Queen（1888） | (1888), 14 App. Cas. 46 |
| 8 | 是 | Attorney-General of British Columbia v. Attorney-General of Canada | 1924 | British Columbia (Attorney-General) v. Canada (Attorney-General)（1923）; British Columbia (Attorney-General) v. Canada (Attorney-General)（1923） | [1924] A.C. 222 |
| 8 | 是 | Caron v. The King | 1924 | R. v. Caron（1924） | [1924] A.C. 999 |
| 8 | 是 | Brassard v. Smith | 1925 | Brassard v. Smith（1924） | [1925] A.C. 371 |
| 8 | 是 | Montreal City v. Montreal Harbour Commissioners | 1926 | Montreal Light, Heat and Power Co. v. City of Montreal（1924）; Montreal (City) v. Harbour Commissioners of Montreal（1925） | [1926] A.C. 299 |
| 8 | 是 | Letang v. Ottawa Electric Ry. Co | 1926 | Letang v. Ottawa Electric Railway Company（1926） | [1926] A.C. 725 |
| 8 | 是 | O. Martineau and Sons Ltd. v. City of Montreal | 1932 | Martineau & Sons Limited v. Montreal (City)（1931） | [1932] A.C. 113 |
| 8 | 是 | Dominion Building Corporation v. The King | 1933 | R. v. Dominion Building Corporation (No. 2)（1933） | [1933] A.C. 533 |
| 8 | 是 | Chung Chi Cheung v. The King | 1939 | R. v. Chung Chi Cheung（1938） | [1939] A.C. 160 |
| 8 | 是 | Canadian Pacific Railway Co. v. Lockhart | 1942 | Lockhart v. Canadian Pacific Railway Company（1942） | [1942] A.C. 591 |
| 8 | 是 | Montreal Coke and Manufacturing Co. v. Minister of National Revenue | 1944 | Montreal Coke & Manufacturing Co. v. Minister of National Revenue,; Montreal Light,; Heat & Power Consolidated v. Minister of National Revenue（1944） | [1944] A.C. 126; [1944] A.C. 127 |
| 7 | 是 | Province of Ontario v. Dominion of Canada | 1897 | Attorney-General for the Dominion of Canada v. Attorney-General for Ontario; Attorney-General for Quebec v. Attorney-General for Ontario（1896） | [1897] A.C. 199 |
| 7 | 是 | Fraser v. Fraserville | 1917 | Fraser v. City of Fraserville（1917） | [1917] A.C. 187 |
| 7 | 是 | Curtis’s & Harvey, Ltd. v. North British & Mercantile Ins. Co. ( | 1921 | Curtis's and Harvey Limited v. North British and Mercantile Insurance Company（1920） | [1921] 1 A.C. 303 |
| 7 | 是 | Attorney-General for Quebec v. Attorney-General for Canada | 1921 | Attorney-General for Canada v. Attorney-General for Quebec. Re Quebec Fisheries（1920）; Attorney-General for Quebec v. Attorney-General for Canada. Re Indian Lands（1920） | [1921] 1 A.C. 401 |
| 7 | 是 | Lord's Day Alliance of Canada v. Attorney‑General for Manitoba | 1925 | Lord's Day Alliance of Canada v. Manitoba (Attorney General)（1924）; Manitoba (Attorney General) v. Canada (Attorney General)（1925） | [1925] A.C. 384 |
| 7 | 是 | Toronto (City) v. Trustees of the Roman Catholic Separate Schools of Toronto | 1926 | City of Toronto v. Board of Trustees of R.C. Separate Schools for City of Toronto（1925） | [1926] A.C. 81 |
| 7 | 是 | A.-G. for British Columbia v. McDonald Murphy Lumber Co. Ltd | 1930 | Macdonald Murphy Lumber Company v. British Columbia (Attorney General)（1930） | [1930] A.C. 357 |
| 7 | 是 | Consolidated Distilleries, Ltd. v. The King | 1933 | R. v. Consolidated Distilleries, Limited（1933） | [1933] A.C. 508 |
| 7 | 是 | Vandepitte v. Preferred Accident Insurance Corp. of New York | 1933 | Vandepitte v. Preferred Accident Insurance Company of New York（1932） | [1933] A.C. 70 |
| 7 | 是 | Grant v. Australian Knitting Mills Ltd | 1936 | Grant v. Australian Knitting Mills（1935） | [1936] A.C. 85 |
| 7 | 是 | Forbes v. Attorney-General of Manitoba | 1937 | Manitoba (Attorney General) v. Forbes（1936） | [1937] A.C. 260 |
| 7 | 是 | A.G. for British Columbia v. A.G. for Canada | 1937 | British Columbia (Attorney General) v. Canada (Attorney General)（1937）; British Columbia (Attorney General) v. Canada (Attorney General)（1937） | [1937] A.C. 391 |
| 7 | 是 | Attorney-General for Ontario v. Attorney-General for Canada | 1937 | Ontario (Attorney General) v. Canada (Attorney General)（1937）; Canada (Attorney General) v. Ontario (Attorney General)（1937） | [1937] A.C. 405 |
| 7 | 是 | Minister of National Revenue v. Wrights' Canadian Ropes, Ltd | 1946/1947 | Wrights' Canadian Ropes Limited v. Canada (National Revenue)（1946） | [1947] A.C. 109 |
| 7 | 是 | Sambasivam v. Public Prosecutor, Federation of Malaya | 1950 | Malaya (Public Prosecutor) v. Sambasivam（1950） | [1950] A.C. 458 |
| 6 | 是 | City of Halifax v. Nova Scotia Car Works, Ltd | 1914 | City of Halifax v. Nova Scotia Car Works（1914） | [1914] A.C. 992 |
| 6 | 是 | Sisters of Charity of Rockingham v. The King | 1922 | R. v. Sisters of Charity of Rockingham（1922） | [1922] 2 A.C. 315 |
| 6 | 是 | McColl v. Canadian Pacific Railway Co | 1923 | McColl v. Canadian Pacific Railway Company（1922） | [1923] A.C. 126 |
| 6 | 是 | and Brooks-Bidlake and Whittall, Ltd. v. Attorney-General for British Columbia | 1923 | Brooks-Bidlake v. British Columbia (Attorney General)（1923） | [1923] A.C. 450 |
| 6 | 是 | Roman Catholic Separate School Trustees for Tiny v. The King | 1928 | R. v. Tiny Township Separate School Trustees（1928） | [1928] A.C. 363 |
| 6 | 是 | Pope Appliance Corporation v. Spanish River Pulp and Paper Mills | 1929 | Pope Appliance Corp. v. Spanish River Pulp & Paper Mills, Ltd.（1928） | [1929] A.C. 269 |
| 6 | 是 | R. v. Williams | 1942 | R. v. Williams（1942） | [1942] A.C. 541 |
| 6 | 是 | McKee v. McKee | 1950/1951 | McKee v. McKee（1951） | [1951] A.C. 352 |
| 5 | 是 | Forbes v. Git | 1922 | Forbes v. Git（1921） | [1922] 1 A.C. 256; [1922] 1 A.C. 256 |
| 5 | 是 | Minister of Justice v. City of Levis | 1919 | Minister of Justice for Canada v. City of Levis（1918） | [1919] A.C. 505 |
| 5 | 是 | Craig v. Lamoureux | 1920 | Lamoureux v. Craig（1919） | [1920] A.C. 349 |
| 5 | 是 | Esquimalt and Nanaimo Rly. Co. v. Wilson, [ | 1920 | Esquimalt v. Wilson（1919） | [1920] A.C. 358 |
| 5 | 是 | Toronto Railway Co. v. Corporation of the City of Toronto | 1920 | Toronto R. Co. v. City of Toronto（1919）; Toronto (City) v. Toronto Railway Company（1920） | [1920] A.C. 426 |
| 5 | 是 | Attorney General for Canada v. Attorney General for Quebec | 1921 | Attorney-General for Canada v. Attorney-General for Quebec. Re Quebec Fisheries（1920）; Attorney-General for Quebec v. Attorney-General for Canada. Re Indian Lands（1920） | [1921] 1 A.C. 413 |
| 5 | 是 | Canadian Pacific Wine Co. v. Tuley | 1921 | Canadian Pacific Wine Co. Ltd. v. Tuley（1921） | [1921] 2 A.C. 417 |
| 5 | 是 | Walpole v. Canadian Northern Railway Co | 1923 | Walpole v. Canadian Northern R. Co.（1922） | [1923] A.C. 113 |
| 5 | 是 | Carling Export Brewing & Malting Co. Ltd. v. The King | 1931 | R. v. Carling Export Brewing and Malting Company（1931） | [1931] A.C. 435 |
| 5 | 是 | Pronek v. Winnipeg, Selkirk and Lake Winnipeg Railway Co | 1933 | Pronek v. Winnipeg, Selkirk & Lake Winnipeg Railway Company（1932） | [1933] A.C. 61 |
| 5 | 是 | Canada Rice Mills, Ld. v. Union Marine & General Insurance Co | 1941 | Canada Rice Mills Limited v. Union Marine and General Insurance Company (No. 1)（1940） | [1941] A.C. 55 |
| 5 | 是 | Trower and Sons, Ld. v. Ripstein | 1944 | Trower & Sons Ltd. v. Ripstein（1944） | [1944] A.C. 254 |
| 5 | 是 | Attorney-General for Ontario v. Attorney-General for Canada | 1947 | Ontario (Attorney General) v. Canada Temperance Federation（1946）; Ontario (Attorney General) v. Canada (Attorney General)（1947） | [1947] A.C. 127 |
| 5 | 是 | Co‑operative Committee on Japanese Canadians v. Attorney‑General of Canada | 1947 | Co-Operative Committee On Japanese Canadians et al. v. Attorney-General of Canada et al.（1946） | [1947] A.C. 87 |
| 4 |  | Berthiaume v. Dastous | 1930 | Berthiaume v. Dastous（1929） | [1930] A.C. 79 |
| 4 |  | That the effect of the agreement was to create an interest in land. (McPherson v. Temiskaming Lumber Co | 1913 | McPherson et al. v. Temiskaming Lumber Co., Limited.（1912） | [1913] A.C. 145 |
| 4 |  | Held, also, applying the principle of Cameron v. Cuddy ( | 1914 | Cuddy v. Cameron（1913） | [1914] A.C. 651 |
| 4 |  | Montreal Street Railway Co. v. Normandin | 1917 | Montreal Street R. Co. v. Normandin（1917） | [1917] A.C. 170 |
| 4 |  | Toronto General Trusts v. The King | 1919 | R. v. Toronto General Trusts Corporation（1919） | [1919] A.C. 679 |
| 4 |  | Attorney-General for the Dominion of Canada v. Ritchie Contracting and Supply Company | 1919 | Atty-Gen'L for Canada v. Ritchie Contracting and Supply Co.（1919） | [1919] A.C. 999 |
| 4 |  | Bain v. Central Vermont Ry. Co | 1921 | Bain v. Central Vermont Railway Company（1921） | [1921] 2 A.C. 412 |
| 4 |  | Wilson v. Esquimalt and Nanaimo Railway Company | 1922 | Esquimalt & Nanaimo Railway Company v. Wilson（1921） | [1922] A.C. 202 |
| 4 |  | Goh Choon Seng v. Lee Kim Soo | 1925 | Lee Kim Soo v. Goh Choon Seng（1925） | [1925] A.C. 550 |
| 4 |  | Stevenson v. Florant | 1927 | Stevenson v. Florant（1926） | [1927] A.C. 211 |
| 4 |  | Dominion Press Limited v. Minister of Customs and Excise | 1928 | Dominion Press, Ltd. v. Minister of Customs and Excise（1928） | [1928] A.C. 340 |
| 4 |  | Robinson v. State of South Australia (No. 2) | 1931 | Robinson v. South Australia (State)（1929）; Robinson v. South Australia (State) (No. 2)（1931） | [1931] A.C. 704 |
| 4 |  | Reilly v. The King | 1934 | R. v. Reilly（1933） | [1934] A.C. 176 |
| 4 |  | O’Connor v. Waldron | 1935 | O'Connor v. Waldron（1934） | [1935] A.C. 76 |
| 4 |  | Windsor Education Board v. Ford Motor Co. of Canada Ltd | 1941 | Board of Education of Windsor v. Ford Motor Co. et al.（1941） | [1941] A.C. 453 |
| 4 |  | Abitibi Power & Paper Co. v. Montreal Trust Co | 1943 | Montreal Trust Company v. Abitibi Power & Paper Company（1943） | [1943] A.C. 536 |
| 4 |  | Vigneux v. Canadian Performing Right Society, Ltd | 1945 | Vigneux et al. v. Canadian Performing Right Society Ltd.（1945） | [1945] A.C. 108 |
| 4 |  | Bennett & White (Calgary) Ltd. v. Municipal District of Sugar City No. 5 | 1950/1951 | Bennett & White (Calgary) Limited v. Sugar City (Municipal District)（1951） | [1951] A.C. 786 |
| 4 |  | White v. Kuzych | 1951 | Kuzych v. White (No. 3)（1951） | [1951] A.C. 585 |
| 3 |  | Royal Trust Co. v. Attorney General for Alberta | 1930 | Alberta (Attorney General) v. Royal Trust Company（1929） | [1930] A.C. 144; [1930] A.C. 144 |
| 3 |  | Browne v. Moody | 1936 | Browne v. Moody et al.（1936） | [1936] A.C. 635 |
| 3 |  | Attorney-General for Canada v. Attorney General for Ontario and Others | 1937 | Ontario (Attorney General) v. Canada (Attorney General)（1937）; Canada (Attorney General) v. Ontario (Attorney General)（1937） | [1937] A.C. 326 |
| 3 |  | Dominion of Canada v. Province of Ontario | 1910 | Dominion of Canada v. Province of Ontario（1910） | [1910] A.C. 637 |
| 3 |  | Commercial Cable Co. v. Government of Newfoundland | 1916 | Commercial Cable Co. v. Government of Newfoundland（1916） | [1916] 2 A.C. 610 |
| 3 |  | Ottawa Separate Schools Trustees v. Ottawa Corporation | 1917 | Ottawa Separate School Trustees v. City of Ottawa; Ottawa Separate School Trustees v. Quebec Bank（1916） | [1917] A.C. 76 |
| 3 |  | Electrical Development Co. of Ontario v. Attorney General of Ontario | 1919 | Electrical Development Co. of Ont. v. Att'Y-Gen'L of Ontario（1919） | [1919] A.C. 687 |
| 3 |  | Attorney-General for Manitoba v. Kelly | 1922 | Manitoba (Attorney General) v. Kelly（1922） | [1922] 1 A.C. 268 |
| 3 |  | The King v. Canadian Northern Ry. Co | 1923 | R. v. Canadian Northern Railway Company（1923） | [1923] A.C. 714 |
| 3 |  | Firm of R.M.K. R.M. v. Firm of M.R.M. V.L | 1926 | Firm of M. R. M. V. L. v. Firm of R. M. K. R. M.（1926） | [1926] A.C. 761 |
| 3 |  | Doughty v. Commissioner of Taxes | 1927 | Commissioner of Taxes v. Doughty（1927） | [1927] A.C. 327 |
| 3 |  | Att.-Gen. for Alberta v. Att.-Gen. for Canada | 1928 | Canada (Attorney General) v. Alberta (Attorney General)（1928） | [1928] A.C. 475 |
| 3 |  | Chung Chuck v. The King ( | 1930 | R. v. Chung Chuck（1929） | [1930] A.C. 244 |
| 3 |  | Corporation of the City of Toronto v. The King | 1932 | R. v. Toronto (City)（1931） | [1932] A.C. 98 |
| 3 |  | Attorney-General for Ontario v. Perry | 1934 | Ontario (Attorney General) v. Perry（1934） | [1934] A.C. 477 |
| 3 |  | Seneviratne v. R | 1936 | R. v. Seneviratne（1936） | [1936] 3 All E.R. 36 |
| 3 |  | Knight Sugar Co. v. Alberta Railway Co | 1938 | Knight Sugar Company v. Alberta Railway and Irrigation Company（1937） | [1938] 1 All E.R. 266 |
| 3 |  | Vita Food Products, Inc. v. Unus Shipping Co | 1939 | Vita Food Products Inc. v. Unus Shipping Company（1939） | [1939] A.C. 277 |
| 3 |  | International Railway Co. v. Niagara Parks Commission | 1941 | International Railway Company v. Niagara Parks Commission (No. 2)（1941） | [1941] 2 All E.R. 456 |
| 3 |  | Gooderham and Worts, Ltd. v. Canadian Broadcasting Corp | 1947 | Gooderham & Worts Limited v. Canadian Broadcasting Corporation（1946） | [1947] A.C. 66 |
| 3 |  | International Harvester Co. v. Provincial Tax Commission | 1949 | International Harvester Company of Canada v. Income Tax Commission（1948） | [1949] A.C. 36 |
| 2 |  | St. Catherine’s Milling [St. Catherine’s Milling and Lumber Co. v. The Queen | 1888 | St. Catherine's Milling and Lumber Company v. The Queen（1888） | (1888), 14 A.C. 46 |
| 2 |  | Waimiha Sawmilling Co. v. Waione Timber Co | 1926 | Waimiha Sawmilling Company v. Waione Timber Company（1925） | [1926] A.C. 101 |
| 2 |  | Williams v. The King | 1942 | R. v. Williams（1942） | [1942] A.C. 541 |
| 2 |  | Parsons v. Sovereign Bank of Canada | 1913 | Parsons et al. (Defendants, Appellants) v. Sovereign Bank of Canada (Plaintiff, Respondent)（1912） | [1913] A.C. 160 |
| 2 |  | Canadian Northern Pacific Railway v. New Westminster Corporation | 1917 | Canadian Northern Pacific R. Co. v. City of New Westminster（1917） | [1917] A.C. 602 |
| 2 |  | Matamajaw Salmon Club v. Duchaine | 1921 | Matamajaw Salmon Club v. Duchaine（1921） | [1921] 2 A.C. 426 |
| 2 |  | Victoria City v. Bishop of Vancouver Island | 1921 | Bishop of Vancouver Island v. Victoria (City)（1921） | [1921] A.C. 384 |
| 2 |  | McMillan v. Canadian Northern Railway Co | 1923 | McMillan v. Canadian Northern R. Co.（1922） | [1923] A.C. 120 |
| 2 |  | Ward & Co. Ltd. v. Commissioner of Taxes | 1923 | Ward and Company v. Canada (Commissioner of Taxes)（1922） | [1923] A.C. 145 |
| 2 |  | British Columbia Electric Railway Co. Ltd. v. Pribble | 1926 | Pribble v. British Columbia Electric Railway Company（1926） | [1926] A.C. 466 |
| 2 |  | Kinch v. Walcott | 1929 | Kinch v. Walcott（1929） | [1929] A.C. 482 |
| 2 |  | Hill v. Permanent Trustee Co. of New South Wales Ltd | 1930 | Hill v. Permanent Trustee Company of New South Wales, Limited（1930） | [1930] A.C. 720 |
| 2 |  | Shell Co. of Australia v. Federal Commissioner of Taxation | 1931 | Shell Company of Australia v. Canada (Federal Commissioner of Taxation)（1930） | [1931] A.C. 275 |
| 2 |  | Vancouver Malt v. Vancouver Breweries | 1933/1934 | Vancouver Breweries Limited v. Vancouver Malt & Sake Brewing Company（1934） | [1934] A.C. 181 |
| 2 |  | McPherson v. McPherson | 1936 | McPherson v. McPherson（1935） | [1936] A.C. 177 |
| 2 |  | Ambard v. Attorney-General for Trinidad and Tobago | 1936 | Trinidad and Tobago (Attorney General) v. Ambard（1936） | [1936] A.C. 322 |
| 2 |  | Commissioner for Stamp Duties of New South Wales v. Perpetual Trustee Co | 1943 | New South Wales (Stamp Duties Commissioner) v. Perpetual Trustee Company（1943） | [1943] A.C. 425 |
| 2 |  | Sherwin-Williams Co. of Canada Ltd. v. Boiler Inspection & Insurance Co. of Canada | 1950/1951 | Boiler Inspection & Insurance Co. of Canada v. Sherwin-Williams Co. of Canada Ltd.（1951） | [1951] A.C. 319 |
| 1 |  | Attorney-General for the Dominion of Canada v. Attorney-General for Ontario | 1897 | Attorney-General for the Dominion of Canada v. Attorney-General for Ontario; Attorney-General for Quebec v. Attorney-General for Ontario（1896） | [1897] A.C. 199 |
| 1 |  | Treaty 3 was again considered by the Privy Council in Dominion of Canada v. Province of Ontario | 1910 | Dominion of Canada v. Province of Ontario（1910） | [1910] A.C. 637 |
| 1 |  | McPherson et al. v. Temiskaming Lumber Co., Ltd., 9 D.L.R. 726 at pp. 731-2 | 1913 | McPherson et al. v. Temiskaming Lumber Co., Limited.（1912） | [1913] A.C. 145 |
| 1 |  | LexisNexis Canada, 2008).] Sir Arthur Channell in Montreal Street Railway Co. v. Normandin | 1917 | Montreal Street R. Co. v. Normandin（1917） | [1917] A.C. 170 |
| 1 |  | Toronto General Trusts Corporation v. The King [ | 1919 | R. v. Toronto General Trusts Corporation（1919） | [1919] A.C. 679 |
| 1 |  | United States v. Motor Trucks, Ltd | 1924 | United States of America v. Motor Trucks Ltd.（1923） | [1924] A.C. 196 |
| 1 |  | and Toronto City Corporation v. Toronto Railway Corporation | 1925 | City of Toronto v. Board of Trustees of R.C. Separate Schools for City of Toronto（1925） | [1925] A.C. 177 |
| 1 |  | Inche Noriah v. Shaik Allie Bin Omar | 1929 | Inche Noriah binte Mohamed Tahir v. Shaik Allie bin Omar Abdullah Bahashuan（1928） | [1929] A.C. 127 |
| 1 |  | As well, in Jardine v. Attorney General for Newfoundland | 1932 | Newfoundland (Attorney General) v. Jardine（1932） | [1932] A.C. 275 |
| 1 |  | A.G. Canada v. A.G. Ontario | 1937 | Ontario (Attorney General) v. Canada (Attorney General)（1937）; Canada (Attorney General) v. Ontario (Attorney General)（1937） | [1937] A.C. 355 |
| 1 |  | and Chung Chi Cheung v. The King | 1939 | R. v. Chung Chi Cheung（1938） | [1939] A.C. 160 |
| 1 |  | this was the outcome in Dillon v. Public Trustee of New Zealand | 1941 | Dillon v. New Zealand (Public Trustee)（1941） | [1941] A.C. 294 |
| 1 |  | Canadian Pacific Railway Company v. Lockhart | 1942 | Lockhart v. Canadian Pacific Railway Company（1942） | [1942] A.C. 591 |
| 1 |  | Abitibi Power and Paper Co. v. Montreal Trust Co | 1943 | Montreal Trust Company v. Abitibi Power & Paper Company（1943） | [1943] A.C. 536 |
| 1 |  | a subsequent case, Attorney-General for Ontario v. Canada Temperance Federation | 1946 | Ontario (Attorney General) v. Canada Temperance Federation（1946） | [1946] A.C. 193 |
| 1 |  | Nance v. British Columbia Electric Railway | 1951 | Nance v. British Columbia Electric Railway Company（1951） | [1951] 2 All E.R. 448 |
| 1 |  | Attorney‑General for Canada v. Attorney‑General for Ontario | 1898 | Attorney-General for the Dominion of Canada v. Attorney-General for Ontario; Attorney-General for Quebec v. Attorney-General for Ontario（1896） | [1898] A.C. 247 |
| 1 |  | A.G. for Ont. v. Hamilton Street Ry. Co | 1903 | Attorney-General (Ont.) v. Hamilton Street Railway（1903） | [1903] A.C. 425 |
| 1 |  | Dominion Cotton Mills Co. v. Amyot | 1912 | Dominion Cotton Mills Co., Limited v. Amyot and Others (Respondents) and Brunet (Intervenant)（1912） | [1912] A.C. 546 |
| 1 |  | Toronto R. Co. v. The King | 1917 | Toronto Railway Company v. The King（1917） | [1917] A.C. 630 |
| 1 |  | Taylor v. Davies | 1920 | Taylor v. Davies（1919） | [1920] A.C. 636 |
| 1 |  | Royal Trust Co. v. Minister of Finance of British Columbia | 1922 | Royal Trust Company v. British Columbia (Minister of Finance)（1921） | [1922] 1 A.C. 87 |
| 1 |  | Loch v. John Blackwood Ltd | 1924 | Loch v. Blackwood Limited（1924） | [1924] A.C. 783 |
| 1 |  | Lew v. Lee | 1924/1925 | Lew v. Wing Lee（1925） | [1925] A.C. 819 |
| 1 |  | Waimiha Sawmilling Company Limited, v. Waione Timber Company Limited | 1926 | Waimiha Sawmilling Company v. Waione Timber Company（1925） | [1926] A.C. 101 |
| 1 |  | Fournier v. Canadian National Railway Co | 1927 | Fournier v. Canadian National Railway Company（1926） | [1927] A.C. 167 |
| 1 |  | Attorney-General for Ontario v. McLean Gold Mines | 1927 | McLean Gold Mines, Limited v. Ontario (Attorney General)（1926） | [1927] A.C. 185 |
| 1 |  | Hong Kong and Shanghai Banking Corporation v. Lo Lee Shi | 1928 | Lo Lee Shi v. Hong Kong & Shanghai Banking Corporation（1928） | [1928] A.C. 181 |
| 1 |  | Gray v. Perpetual Trustee Co | 1928 | Gray v. Perpetual Trustee Company（1928） | [1928] A.C. 391 |
| 1 |  | R. v. Caledonian Collieries | 1928 | R. v. Caledonian Collieries, Limited（1928） | [1928] A.C. 538 |
| 1 |  | James v. Cowan | 1932 | James v. Cowan（1932） | [1932] A.C. 542 |
| 1 |  | Maritime Electric Co. Ltd. v. General Dairies Ltd | 1937 | Maritime Electric Company v. General Dairies, Limited（1937） | [1937] A.C. 610 |
| 1 |  | Toronto v. Attorney-General for Canada | 1946 | Toronto v. Attorney-General of Canada（1945） | [1946] A.C. 32 |
| 1 |  | Kwaku Mensah v. The King | 1946 | R. v. Kwaku Mensah（1945） | [1946] A.C. 83 |
| 1 |  | Spun Rock Wools Ltd. v. Fiberglas Canada Ltd | 1947 | Fiberglas Canada Ltd. et al. v. Spun Rock Wools Ltd. et al.（1947） | [1947] A.C. 313 |
| 1 |  | Basma v. Weekes et al | 1950 | Abdul Karim Basma v. Weekes（1950） | [1950] A.C. 441 |

## 疑似漏网：案名含加拿大地名却没对上的（按 dd 降序，前 60）

多为非加拿大来源的同名案、CanLII 标题写法差得太远、或年份超窗。按约束四不猜，留 UNDETERMINED。

- dd 59 `Citizens Insurance Co. of Canada v. Parsons` [1881] — (1881), 7 App. Cas. 96
- dd 49 `Union Colliery Co. of British Columbia v. Bryden` [1899] — [1899] A.C. 580
- dd 43 `Canadian Pacific Railway Co. v. Corporation of the Parish of Notre Dame de Bonsecours` [1899] — [1899] A.C. 367
- dd 39 `Bank of Toronto v. Lambe` [1887] — (1887), 12 App. Cas. 575
- dd 37 `Attorney‑General for Ontario v. Hamilton Street Railway Co` [1903] — [1903] A.C. 524
- dd 35 `Attorney-General of Ontario v. Attorney-General for the Dominion of Canada` [1894] — [1894] A.C. 189
- dd 34 `Liquidators of the Maritime Bank of Canada v. Receiver-General of New Brunswick` [1892] — [1892] A.C. 437
- dd 32 `Toronto Corporation v. Bell Telephone Co. of Canada` [1905] — [1905] A.C. 52
- dd 32 `Grand Trunk Railway Company of Canada v. Attorney-General of Canada` [1907] — [1907] A.C. 65
- dd 30 `Toronto Electric Commissioners v. Snider` [1922] — [1922] 1 A.C. 191
- dd 30 `Tennant v. Union Bank of Canada` [1894] — [1894] A.C. 31
- dd 29 `Attorney‑General of Manitoba v. Manitoba Licence Holders' Association` [1902] — [1902] A.C. 73
- dd 29 `Attorney-General for Ontario v. Reciprocal Insurers` [1924] — [1924] A.C. 328
- dd 27 `Attorney-General for Ontario v. Winner` [1954] — [1954] A.C. 541
- dd 24 `Toronto Railway Co. v. Toronto Corporation` [1904] — [1904] A.C. 809
- dd 24 `Robinson v. Canadian Pacific Railway Co` [1892] — [1892] A.C. 481
- dd 22 `Canadian Pacific Railway Co. v. Roy` [1902] — [1902] A.C. 220
- dd 21 `Canadian Pacific Railway Co. v. Attorney‑General for British Columbia` [1950] — [1950] A.C. 122
- dd 20 `Brewers and Maltsters' Association of Ontario v. Attorney-General for Ontario` [1897] — [1897] A.C. 231
- dd 20 `Attorney‑General for British Columbia v. Canadian Pacific Railway` [1906] — [1906] A.C. 204
- dd 18 `Workmen’s Compensation Board v. Canadian Pacific Railway Co` [1920] — [1920] A.C. 184
- dd 18 `Toronto Railway Co. v. King` [1908] — [1908] A.C. 260
- dd 16 `British Columbia Electric Ry Co. Ltd. v. Loach` [1916, 1917] — [1916] 1 A.C. 719
- dd 14 `therefore, as decided by McArthur v. Dominion Cartridge Co. (` [1905] — [1905] A.C. 72
- dd 14 `and, applying to the verdict the principle laid down in Dominion Natural Gas Co. Ltd. v. Collins` [1909] — [1909] A.C. 640
- dd 14 `Corporation of the City of Toronto v. Canadian Pacific Railway Co` [1908] — [1908] A.C. 54
- dd 14 `Attorney-General of Ontario v. Mercer` [1883] — (1883) 8 App. Cas. 767
- dd 12 `Royal Bank of Canada v. Larue` [1928] — [1928] A.C. 187
- dd 12 `Miller v. Grand Trunk Railway Co. of Canada` [1906] — [1906] A.C. 187
- dd 12 `Brophy v. Attorney‑General of Manitoba` [1895] — [1895] A.C. 202
- dd 11 `—Attorney-General for Ontario v. Reciprocal Insurers` [1932] — [1932] A.C. 41
- dd 10 `Toronto v. Virgo` [1896] — [1896] A.C. 88
- dd 10 `Toronto Railway Co. v. Corporation of the City of Toronto` [1906] — [1906] A.C. 117
- dd 10 `Attorney-General of British Columbia v. Attorney-General of Canada` [1889] — (1889), 14 App. Cas. 295
- dd 10 `Attorney-General for British Columbia v. Attorney-General for Canada` [1914] — [1914] A.C. 153
- dd 9 `Dechène v. City of Montreal` [1894] — [1894] A.C. 640
- dd 8 `United Shoe Machinery Company of Canada v. Brunet` [1909] — [1909] A.C. 330
- dd 8 `Holditch v. Canadian Northern Railway Co. (50 Can. S.C.R. 265` [1916] — [1916] 1 A.C. 536
- dd 8 `City of Winnipeg v. Barrett` [1892] — [1892] A.C. 445
- dd 8 `Canadian Northern Railway Co. v. Robinson` [1910, 1911] — [1911] A.C. 739
- dd 8 `Attorney-General for Quebec v. Reed` [1884] — (1884) 10 A.C. 141
- dd 8 `A.G. for Manitoba v. A.G. for Canada` [1904] — [1904] A.C. 405
- dd 8 `3 Q.L.R. 173), Trust & Loan Co. of Canada v. Gauthier (` [1904] — [1904] A.C. 94
- dd 7 `Hirsch v. Protestant Board of School Commissioners of Montreal` [1928] — [1928] A.C. 200
- dd 7 `Attorney General for Canada v. Cain` [1906] — [1906] A.C. 542
- dd 6 `Canadian Pacific Railway Co. v. Toronto Corporation` [1910, 1911] — [1911] A.C. 461
- dd 5 `the principle set down in Anglo-Newfoundland Development Co. v. Pacific Steam Navigation Co. (` [1924] — [1924] A.C. 406
- dd 5 `Treasurer of Ontario v. Aberdein` [1947] — [1947] A.C. 24
- dd 5 `Sun Life Assurance Co. of Canada v. Jervis` [1944] — [1944] A.C. 111
- dd 5 `Montreal Light, Heat and Power Consolidated v. City of Outremont` [1932] — [1932] A.C. 423
- dd 5 `Ewing v. Dominion Bank` [1904] — [1904] A.C. 806
- dd 5 `Dumphy v. Montreal Light, Heat & Power Co` [1907] — [1907] A.C. 454
- dd 5 `Attorney-General for Saskatchewan v. Canadian Pacific Railway Company et al` [1953] — [1953] A.C. 594
- dd 4 `Union St. Jacques de Montreal v. Bélisle` [1874] — (1874), L.R. 6 P.C. 31
- dd 4 `The principle, approved by the House of Lords in Gosse Millerd Ltd. v. Canadian Government Merchant Marine` [1929] — [1929] A.C. 223
- dd 4 `R. v. Attorney General of British Columbia` [1924] — [1924] A.C. 213
- dd 4 `Inglewood Pulp and Paper Co. v. New Brunswick Electric Power Commission` [1928] — [1928] A.C. 492
- dd 4 `Grand Trunk Railway Co. of Canada v. Jennings` [1888] — (1888) 13 App. Cas. 800
- dd 4 `Bell Telephone Company of Canada v. City of Saint-Laurent` [1936] — [1936] A.C. 73
- dd 3 `and Ottawa Roman Catholic Separate Schools Trustees v. Quebec Bank` [1920] — [1920] A.C. 230
