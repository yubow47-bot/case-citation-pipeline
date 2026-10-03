import json, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from canlii_client import get, calls_made

probes = [
    "caseBrowse/en/csc-scc/2002scc33/",
    "caseBrowse/en/onca/2023onca812/",
    "caseBrowse/en/bcca/2007bcca306/",
    "caseBrowse/en/csc-scc/?offset=0&resultCount=5&publishedBefore=1990-01-01",
    "caseBrowse/en/onca/?offset=0&resultCount=5&publishedBefore=2003-01-01",
    "caseCitator/en/csc-scc/2002scc33/citedCases",
    "caseCitator/en/csc-scc/2002scc33/citingCases",
]
for p in probes:
    d = get(p)
    s = json.dumps(d, ensure_ascii=False)
    print("==", p, "| len", len(s))
    if "citingCases" in d:
        print("  citingCases n=", len(d["citingCases"]), d["citingCases"][:2])
    elif "citedCases" in d:
        print("  citedCases n=", len(d["citedCases"]), d["citedCases"][:3])
    else:
        print(" ", s[:600])
print("calls:", calls_made())
