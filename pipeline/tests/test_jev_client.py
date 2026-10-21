"""Jev client: cache keys, the three modes, failure handling and adoption gates. No network."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jev_client as jc

CFG = jc.load_config()


def choice_answer(**probs):
    top = max(probs, key=probs.get)
    return {"type": "choice", "choice": top, "probabilities": probs, "confidence": 0.0}


class FakeTransport:
    def __init__(self, answer=None, fail=False):
        self.bodies = []
        self.answer = answer
        self.fail = fail

    def __call__(self, body):
        self.bodies.append(body)
        if self.fail:
            raise RuntimeError("HTTP 503 from Jev")
        return {"model": "jev-1.13.0", "usage": {"input_tokens": 10},
                "answers": {"q": self.answer or choice_answer(a=0.95, b=0.05)}}


QUESTIONS = {"q": jc.choice_question("Pick", {"a": "first", "b": "second"})}


class JevClientTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)  # runs last: cleanups are LIFO
        self.tmp = tmp.name

    def client(self, mode, transport=None, tmp=None):
        # Windows cannot delete an open SQLite file, so close before the directory goes.
        c = jc.JevClient(mode, config=CFG, cache_path=Path(self.tmp) / "c.sqlite", transport=transport)
        self.addCleanup(c.close)
        return c

    def test_off_never_calls(self):
        fake = FakeTransport()
        out = self.client("off", fake).ask_many("N2_case_name", [("s", QUESTIONS)])
        self.assertEqual(out[0][1], None)
        self.assertEqual(fake.bodies, [])

    def test_live_caches_and_cache_only_replays(self):
        fake = FakeTransport()
        live = self.client("live", fake)
        first = live.ask_many("N2_case_name", [("s", QUESTIONS), ("s", QUESTIONS)])
        live.close()
        self.assertEqual(len(fake.bodies), 1)  # identical items are sent once
        self.assertEqual(fake.bodies[0]["model"], "jev-1.13.0")
        replay = self.client("cache-only", FakeTransport(fail=True))
        second = replay.ask_many("N2_case_name", [("s", QUESTIONS)])
        self.assertEqual(second[0][1], first[0][1])
        self.assertEqual(replay.stats["N2_case_name:cache_hits"], 1)

    def test_cache_only_miss_is_no_answer(self):
        out = self.client("cache-only", FakeTransport()).ask_many(
            "N2_case_name", [("new", QUESTIONS)])
        self.assertIsNone(out[0][1])

    def test_failure_is_recorded_not_raised(self):
        c = self.client("live", FakeTransport(fail=True))
        out = c.ask_many("N2_case_name", [("s", QUESTIONS)])
        self.assertIsNone(out[0][1])
        self.assertEqual(c.stats["N2_case_name:failures"], 1)

    def test_key_changes_with_model_spec_state_and_questions(self):
        base = jc.cache_key("jev-1.13.0", "N2", "1", "s", QUESTIONS)
        self.assertNotEqual(base, jc.cache_key("jev-1.14.0", "N2", "1", "s", QUESTIONS))
        self.assertNotEqual(base, jc.cache_key("jev-1.13.0", "N2", "2", "s", QUESTIONS))
        self.assertNotEqual(base, jc.cache_key("jev-1.13.0", "N2", "1", "t", QUESTIONS))
        self.assertEqual(base, jc.cache_key("jev-1.13.0", "N2", "1", "s", dict(QUESTIONS)))

    def test_gates(self):
        strong = choice_answer(a=0.95, b=0.03, none=0.02)
        self.assertEqual(jc.gate(CFG, "T1", strong)[0], "adopt")
        self.assertEqual(jc.gate(CFG, "T2", strong), ("review", "missing_agreement_check"))
        self.assertEqual(jc.gate(CFG, "T2", strong, noul=0.5), ("review", "agreement_check_failed"))
        self.assertEqual(jc.gate(CFG, "T2", strong, noul=0.95)[0], "adopt")
        close = choice_answer(a=0.82, b=0.18)          # ratio 4.6: T1 yes, T2 no
        self.assertEqual(jc.gate(CFG, "T1", close)[0], "adopt")
        self.assertEqual(jc.gate(CFG, "T2", close, noul=0.99), ("review", "below_T2"))
        self.assertEqual(jc.gate(CFG, "T1", choice_answer(a=0.65, b=0.35)), ("review", "below_T1"))
        self.assertEqual(jc.gate(CFG, "T1", choice_answer(a=0.5, b=0.5)), ("reject", "low_probability"))
        self.assertEqual(jc.gate(CFG, "T1", choice_answer(none=0.99, a=0.01), abstain={"none"}),
                     ("reject", "abstained"))
        self.assertEqual(jc.gate(CFG, "T1", None), ("reject", "no_answer"))

    def test_cap_is_deterministic(self):
        items = list(range(100))
        a, dropped = jc.cap(items, 10, "seed")
        self.assertEqual((a, dropped), (jc.cap(items, 10, "seed")[0], 90))
        self.assertEqual(jc.cap(items, None, "x"), (items, 0))


if __name__ == "__main__":
    unittest.main()
