"""CanLII API 最小客户端：缓存落盘、≤1 次/秒、key 只从文件读且不落任何文件。

用法：from canlii_client import get
      get("caseBrowse/en/onca/2023onca812/")  -> dict
缓存：data/canlii_cache/crosscheck/<path 转义>.json；命中则 0 次请求。
遇 429/403/5xx/非 JSON：抛 StopError，调用方应立即停。
"""
import json, os, re, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, "data", "canlii_cache", "crosscheck")
KEY_FILE = r"C:\api key\canlii.txt"
BUDGET = int(os.environ.get("CANLII_BUDGET", "2000"))
_state = {"last": 0.0, "calls": 0, "key": None}
LOG = os.path.join(CACHE, "_calls.log")


class StopError(RuntimeError):
    pass


def _key():
    if _state["key"] is None:
        _state["key"] = open(KEY_FILE, encoding="utf-8").read().split()[0]
    return _state["key"]


def _redact(s):
    return re.sub(r"api_key=[^&\s]+", "api_key=REDACTED", str(s))


def _cache_path(path):
    return os.path.join(CACHE, re.sub(r"[^A-Za-z0-9._-]+", "_", path.strip("/")) + ".json")


def calls_made():
    return _state["calls"]


def get(path):
    cp = _cache_path(path)
    if os.path.exists(cp):
        with open(cp, encoding="utf-8") as f:
            return json.load(f)
    if _state["calls"] >= BUDGET:
        raise StopError("调用预算用尽 %d" % BUDGET)
    wait = float(os.environ.get("CANLII_GAP", "3.0")) - (time.time() - _state["last"])
    if wait > 0:
        time.sleep(wait)
    sep = "&" if "?" in path else "?"
    url = "https://api.canlii.org/v1/" + path + sep + "api_key=" + _key()
    _state["last"] = time.time()
    _state["calls"] += 1
    os.makedirs(CACHE, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            body = r.read().decode("utf-8")
        status = 200
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8", "replace")
    except Exception as e:  # 网络错误：不带 URL 抛出
        raise StopError("网络错误: %s" % _redact(e)) from None
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s\t%d\t%s\n" % (time.strftime("%H:%M:%S"), status, path))
    if status == 404:
        data = {"_http": 404}
    elif status != 200:
        raise StopError("HTTP %d on %s: %s" % (status, path, _redact(body[:200])))
    else:
        try:
            data = json.loads(body)
        except ValueError:
            raise StopError("非 JSON 响应 on %s: %s" % (path, _redact(body[:200])))
    with open(cp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data
