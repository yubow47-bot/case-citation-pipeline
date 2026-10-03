"""Turn a Chinese search question into English legal search terms (query side only).

The index is English judgments; a Chinese question embeds near other Chinese text, not near the
passages that answer it. One cheap model call (gpt-4o-mini via OpenRouter, ~$0.00002) rewrites the
question into the doctrine / test / term names Canadian courts use. The rewrite only steers retrieval:
every result shown still comes from our own data, and the rewrite is shown to the user.
Rewrites are cached in data/foundation/rewrite_cache.db, so the same question never costs twice.
"""
import json
import re
import sqlite3
import urllib.request
from common import ROOT
from embed import _key, SECRET

MODEL = 'openai/gpt-4o-mini'
CACHE = ROOT/'data'/'foundation'/'rewrite_cache.db'
CJK = re.compile(r'[㐀-鿿]')
SYSTEM = ("Rewrite the user's search query about Canadian law as English search terms that Canadian judgments "
          "actually use: the doctrine or test name, key legal terms, and leading case names only if you are sure of them. "
          "One line, no commentary.")


def has_cjk(q):
    return bool(CJK.search(q))


def to_english(q):
    """Return an English rewrite of q, or '' when q has no Chinese or the call fails."""
    if not has_cjk(q):
        return ''
    db = sqlite3.connect(CACHE)
    db.execute('CREATE TABLE IF NOT EXISTS rw(q TEXT, model TEXT, en TEXT, PRIMARY KEY(q,model))')
    row = db.execute('SELECT en FROM rw WHERE q=? AND model=?', (q, MODEL)).fetchone()
    if row:
        db.close()
        return row[0]
    body = json.dumps({'model': MODEL, 'temperature': 0, 'max_tokens': 120,
                       'messages': [{'role': 'system', 'content': SYSTEM},
                                    {'role': 'user', 'content': SECRET.sub('[redacted]', q)[:500]}]}).encode()
    try:
        req = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions', data=body,
                                     headers={'Authorization': 'Bearer ' + _key(), 'Content-Type': 'application/json'})
        en = json.load(urllib.request.urlopen(req, timeout=30))['choices'][0]['message']['content'].strip().split('\n')[0]
    except Exception:
        db.close()
        return ''
    if en:
        db.execute('INSERT OR REPLACE INTO rw VALUES(?,?,?)', (q, MODEL, en))
        db.commit()
    db.close()
    return en
