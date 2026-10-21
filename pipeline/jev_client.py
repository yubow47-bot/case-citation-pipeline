"""jev_client.py — cached TypeSafe Jev calls for bounded per-case judgments.

method card 09. The layer that owns a judgment builds the question: code generates
every option from the source text or registry, and Jev only chooses. Answers are
cached by (pinned model, node, spec version, state, questions), so `cache-only`
replays a live run exactly. `off` never calls anything and is the rule pipeline.

The wire format follows POST /v1/systemone (typesafe-sdk 0.7.5 schema); the
standard library is used so production environments need no extra dependency.
The API key is read only from TYPESAFE_API_KEY and is never written anywhere.
"""
import concurrent.futures
import datetime
import hashlib
import json
import os
import random
import sqlite3
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "jev_config.yaml"
DEFAULT_CACHE = ROOT / "data" / "jev_cache.sqlite"
MODES = ("off", "cache-only", "live")
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}

LEDGER_FIELDS = ["node", "item_key", "level", "question", "options_json", "choice", "p_max",
                 "ratio", "noul", "probabilities_json", "model", "cache_key", "adopted",
                 "reason_not_adopted", "state_excerpt"]


def load_config(path=None):
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def config_sha256(path=None):
    with open(path or DEFAULT_CONFIG, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def cache_key(model, node, spec_version, state, questions):
    return hashlib.sha256(canonical(
        {"model": model, "node": node, "spec_version": spec_version,
         "state": state, "questions": questions}).encode("utf-8")).hexdigest()


def choice_question(instructions, criteria):
    return {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}


def noul_question(instructions):
    return {"type": "noul", "instructions": instructions}


def choice_metrics(answer):
    """(choice, p_max, ratio) from a choice answer; ratio = top / runner-up probability.

    Jev's own `confidence` depends on the option count, so gates use these two
    measures instead (docs.typesafe.ai/confidence).
    """
    probs = sorted((answer or {}).get("probabilities", {}).values(), reverse=True)
    if not probs:
        return "", 0.0, 0.0
    second = probs[1] if len(probs) > 1 else 0.0
    ratio = probs[0] / second if second > 0 else float("inf")
    return answer.get("choice", ""), probs[0], ratio


def gate(cfg, tier, answer, noul=None, abstain=()):
    """Return (decision, reason): decision is adopt, review or reject.

    T1: p_max and ratio. T2 adds an independently phrased Noul that must agree.
    An abstaining option (none / cannot_tell) is never adopted and is not
    evidence against anything.
    """
    gates = cfg["gates"]
    choice, p_max, ratio = choice_metrics(answer)
    if not choice:
        return "reject", "no_answer"
    if choice in abstain:
        return "reject", "abstained"
    need = gates[tier]
    if p_max >= need["p_max"] and ratio >= need["ratio"]:
        if tier == "T2":
            if noul is None:
                return "review", "missing_agreement_check"
            if noul < need["noul"]:
                return "review", "agreement_check_failed"
        return "adopt", ""
    if p_max >= gates["review_floor"]:
        return "review", "below_" + tier
    return "reject", "low_probability"


def level_allowed(cfg, level):
    return bool(cfg.get("levels", {}).get("allow_" + level, False))


def cap(items, limit, seed):
    """Fixed-seed sample when a node exceeds its per-run question limit."""
    if limit is None or len(items) <= limit:
        return list(items), 0
    rng = random.Random(seed)
    keep = sorted(rng.sample(range(len(items)), limit))
    return [items[i] for i in keep], len(items) - limit


def _http_transport(cfg):
    url = cfg.get("api_url", "https://api.typesafe.ai/v1/systemone")
    timeout = float(cfg.get("timeout_seconds", 30))
    retries = int(cfg.get("max_retries", 4))

    def send(body):
        key = os.environ.get("TYPESAFE_API_KEY", "")
        if not key:
            raise RuntimeError("TYPESAFE_API_KEY is not set")
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        delay = 0.5
        for attempt in range(retries + 1):
            req = urllib.request.Request(url, data=data, method="POST", headers={
                "Authorization": "Bearer " + key, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code not in RETRY_STATUSES or attempt == retries:
                    raise RuntimeError("HTTP %d from Jev" % exc.code) from None
                wait = exc.headers.get("retry-after") if exc.headers else None
                time.sleep(float(wait) if wait and wait.replace(".", "", 1).isdigit() else delay)
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == retries:
                    raise RuntimeError("Jev connection failed: %s" % type(exc).__name__) from None
                time.sleep(delay)
            delay = min(delay * 2, 8.0)
        raise RuntimeError("unreachable")
    return send


class JevClient:
    """One client per layer process; `ask_many` checks the cache, then calls in parallel."""

    def __init__(self, mode="off", config=None, config_path=None, cache_path=None,
                 transport=None):
        if mode not in MODES:
            raise ValueError("jev mode must be one of %s" % (MODES,))
        self.mode = mode
        self.config_path = config_path or DEFAULT_CONFIG
        self.cfg = config if config is not None else (
            load_config(self.config_path) if mode != "off" else {})
        self.cache_path = Path(cache_path or DEFAULT_CACHE)
        self._send = transport
        self.stats = Counter()
        self.timings = []
        self._db = None

    # -- configuration -------------------------------------------------
    def node_cfg(self, node):
        return (self.cfg.get("nodes") or {}).get(node) or {}

    def enabled(self, node):
        return self.mode != "off" and bool(self.node_cfg(node).get("enabled"))

    @property
    def model(self):
        return self.cfg.get("model", "")

    # -- cache -------------------------------------------------------------
    def _conn(self):
        if self._db is None:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self.cache_path))
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS answers(key TEXT PRIMARY KEY, node TEXT, "
                "spec_version TEXT, model_requested TEXT, model_answered TEXT, "
                "response_json TEXT, input_tokens INTEGER, created_at TEXT)")
        return self._db

    def close(self):
        if self._db is not None:
            self._db.commit()
            self._db.close()
            self._db = None

    # -- asking ------------------------------------------------------------
    def ask_many(self, node, items):
        """items: list of (state, questions). Returns [(cache_key, response | None)].

        A response is {"model": versioned id, "answers": {...}}. None means no
        answer (cache miss in cache-only, or a failed call); callers treat it as
        "not adopted", never as a default value.
        """
        spec = str(self.node_cfg(node).get("spec_version", 1))
        keys = [cache_key(self.model, node, spec, s, q) for s, q in items]
        self.stats[node + ":asked"] += len(items)
        if self.mode == "off" or not items:
            return [(k, None) for k in keys]
        db = self._conn()
        found = {}
        for i in range(0, len(keys), 500):
            chunk = keys[i:i + 500]
            for key, payload in db.execute(
                    "SELECT key, response_json FROM answers WHERE key IN (%s)"
                    % ",".join("?" * len(chunk)), chunk):
                found[key] = json.loads(payload)
        self.stats[node + ":cache_hits"] += sum(k in found for k in keys)
        missing = [(k, it) for k, it in zip(keys, items) if k not in found]
        if missing and self.mode == "live":
            send = self._send or _http_transport(self.cfg)
            workers = max(1, int(self.cfg.get("concurrency", 8)))

            def call(pair):
                key, (state, questions) = pair
                start = time.monotonic()
                try:
                    body = {"model": self.model, "state": state, "questions": questions}
                    return key, send(body), time.monotonic() - start, ""
                except Exception as exc:  # recorded per item; never fails the layer
                    return key, None, time.monotonic() - start, str(exc)[:200]
            seen = set()
            unique = [p for p in missing if not (p[0] in seen or seen.add(p[0]))]
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                for key, resp, elapsed, err in pool.map(call, unique):
                    self.stats[node + ":calls"] += 1
                    self.timings.append((node, elapsed))
                    if resp is None or "answers" not in resp:
                        self.stats[node + ":failures"] += 1
                        if err:
                            self.stats[node + ":failure:" + err.split(" from")[0][:60]] += 1
                        continue
                    tokens = int((resp.get("usage") or {}).get("input_tokens") or 0)
                    self.stats[node + ":input_tokens"] += tokens
                    found[key] = {"model": resp.get("model", ""), "answers": resp["answers"]}
                    db.execute("INSERT OR REPLACE INTO answers VALUES (?,?,?,?,?,?,?,?)", (
                        key, node, spec, self.model, resp.get("model", ""),
                        canonical(found[key]), tokens,
                        datetime.datetime.now().isoformat(timespec="seconds")))
            db.commit()
        elif missing:
            self.stats[node + ":cache_misses"] += len(missing)
        return [(k, found.get(k)) for k in keys]

    # -- reporting ---------------------------------------------------------
    def summary(self):
        timing = {}
        by_node = {}
        for node, t in self.timings:
            by_node.setdefault(node, []).append(t)
        for node, values in by_node.items():
            values.sort()
            timing[node] = {"p50": round(values[len(values) // 2], 3),
                            "p95": round(values[min(len(values) - 1, int(len(values) * 0.95))], 3),
                            "n": len(values)}
        return {"mode": self.mode, "model": self.model,
                "config_sha256": config_sha256(self.config_path) if self.mode != "off" else "",
                "stats": dict(sorted(self.stats.items())), "timing_seconds": timing}


def write_ledger(path, rows):
    import csv
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def ledger_row(node, item_key, level, question_id, questions, response, decision, reason,
               ckey, noul_id=None, state=None):
    answer = ((response or {}).get("answers") or {}).get(question_id) or {}
    choice, p_max, ratio = choice_metrics(answer)
    noul = (((response or {}).get("answers") or {}).get(noul_id) or {}).get("noul") if noul_id else None
    return {"node": node, "item_key": item_key, "level": level, "question": question_id,
            "options_json": canonical(questions[question_id].get("criteria", {})),
            "choice": choice, "p_max": round(p_max, 4),
            "ratio": round(ratio, 3) if ratio != float("inf") else "inf",
            "noul": "" if noul is None else round(noul, 4),
            "probabilities_json": canonical(answer.get("probabilities", {})),
            "model": (response or {}).get("model", ""), "cache_key": ckey,
            "adopted": str(decision == "adopt").lower(),
            "reason_not_adopted": "" if decision == "adopt" else reason,
            "state_excerpt": (state if isinstance(state, str) else canonical(state))[:600]
            if state is not None else ""}


def add_cli(ap):
    ap.add_argument("--jev-mode", choices=MODES, default="off",
                    help="Jev judgments: off (rule pipeline), cache-only, live")
    ap.add_argument("--jev-config", default=None)
    ap.add_argument("--jev-cache", default=None)


def from_args(args):
    return JevClient(args.jev_mode, config_path=args.jev_config, cache_path=args.jev_cache)
