"""Flash closes nothing in the audit: atoms, reproduced quotes, Flash-only tiers."""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.realpath(
    os.path.join(HERE, "..", "..", "glm-requirements-code-audit", "scripts"))
sys.path.insert(0, SCRIPTS)
import audit  # noqa: E402


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class AtomHomeTests(unittest.TestCase):
    def test_a_missing_quoted_atom_fails(self):
        fails = audit.atom_home_fails(['"retry-limit"'], [{"id": "REQ-001", "text": "other"}], "")
        self.assertTrue(any("no home" in f for f in fails))

    def test_one_home_passes(self):
        fails = audit.atom_home_fails(
            ['"retry-limit"'], [{"id": "REQ-001", "text": 'keep "retry-limit"'}], "")
        self.assertEqual(fails, [])

    def test_two_homes_fail_for_a_quote_and_not_for_an_integer(self):
        items = [
            {"id": "REQ-001", "text": 'limit "retry-limit" 30'},
            {"id": "REQ-002", "text": 'also "retry-limit" 30'},
        ]
        fails = audit.atom_home_fails(['"retry-limit"', "30"], items, "")
        self.assertTrue(any("retry-limit" in f and "homes" in f for f in fails))
        self.assertFalse(any(f.endswith(": 30") for f in fails))

    def test_out_of_scope_is_a_home(self):
        fails = audit.atom_home_fails(['"legacy"'], [{"id": "REQ-001", "text": "x"}], '"legacy"')
        self.assertEqual(fails, [])

    def test_model_span_that_is_not_in_the_spec_is_dropped(self):
        frozen, dropped = audit.merge_atom_passes(
            'must retry', "ATOM: must retry\nATOM: invented span", "")
        self.assertIn("must retry", frozen)
        self.assertTrue(any("invented" in d for d in dropped))


class AttackResultTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="audit-flash-")
        self.addCleanup(shutil.rmtree, self.root, True)
        _write(os.path.join(self.root, "src", "a.py"), "line 1\nline 2\n")

    def test_no_break_quote_in_the_file_is_ok(self):
        row = {"attack": {"kind": "NO-BREAK", "path": "src/a.py", "lines": "1-2",
                          "quote": "line 1"}}
        self.assertEqual(audit.attack_result(self.root, row), "ok")

    def test_invented_quote_is_absent(self):
        row = {"attack": {"kind": "NO-BREAK", "path": "src/a.py", "lines": "1-2",
                          "quote": "not in the file"}}
        self.assertEqual(audit.attack_result(self.root, row), "absent")

    def test_counterexample_quote_is_counter(self):
        row = {"attack": {"kind": "COUNTEREXAMPLE", "path": "src/a.py", "lines": "1-1",
                          "quote": "line 1"}}
        self.assertEqual(audit.attack_result(self.root, row), "counter")

    def test_missing_attack_is_missing(self):
        self.assertEqual(audit.attack_result(self.root, {}), "missing")


class TierPinTests(unittest.TestCase):
    def test_every_tier_is_flash_and_light_is_not_low(self):
        for name, cfg in audit.TIERS.items():
            self.assertEqual(cfg["judge"][0], audit.FLASH, name)
            self.assertEqual(cfg["verify"][0], audit.FLASH, name)
            self.assertEqual(cfg["parse"][0], audit.FLASH, name)
            self.assertNotEqual(cfg["judge"][1], "low", name)
        self.assertEqual(audit.TIERS["deep"]["judge"][1], "max")
        self.assertEqual(audit.TIERS["light"]["judge"][1], "high")

    def test_agents_pin_flash_at_max(self):
        agents = os.path.join(SCRIPTS, "..", "agents")
        for name in ("glm-rca-investigator.md", "glm-rca-verifier.md"):
            with open(os.path.join(agents, name), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("GLM-5.3-Flash", text)
            self.assertIn("thoughtLevel: max", text)
            self.assertNotIn("GLM-5.3\"", text.split("GLM-5.3-Flash")[0] + "TAIL")


class AtomCallTests(unittest.TestCase):
    def _client(self, replies, finishes):
        cl = type("C", (), {})()
        cl._tl = type("T", (), {"finish": ""})()
        cl.n = 0
        cl.replies = list(replies)
        cl.finishes = list(finishes)

        def call(*_a, **_k):
            cl._tl.finish = cl.finishes[cl.n]
            text = cl.replies[cl.n]
            cl.n += 1
            return text

        cl.call = call
        return cl

    def test_a_finished_reply_is_one_call(self):
        cl = self._client(["ATOM: must retry"], ["stop"])
        atoms, _dropped, ncalls = audit.freeze_with_client(cl, "must retry")
        self.assertEqual(ncalls, 1)
        self.assertEqual(cl.n, 1)
        self.assertIn("must retry", atoms)

    def test_a_truncated_reply_gets_one_follow_up(self):
        cl = self._client(["ATOM: must retry", "ATOM: \"cap\""], ["length", "stop"])
        atoms, _dropped, ncalls = audit.freeze_with_client(cl, "must retry \"cap\"")
        self.assertEqual(ncalls, 2)
        self.assertEqual(cl.n, 2)
        self.assertIn("cap", atoms)


class PrefetchTests(unittest.TestCase):
    def test_prefetch_uses_gather_and_keeps_the_id(self):
        class Retr(object):
            def gather(self, item, tier):
                return {"id": item["id"], "tier": tier}

        got = audit.prefetch_gathers(Retr(), [{"id": "REQ-001"}], "std", 2)
        self.assertEqual(got["REQ-001"]["tier"], "std")


class NeedsVerifyTests(unittest.TestCase):
    def test_a_high_confidence_match_is_still_attacked(self):
        it = {"id": "REQ-001", "stakes": "normal", "strength": "MUST", "tags": []}
        finding = {"status": "MATCHED", "confidence": "high", "passes": 1}
        self.assertTrue(audit.needs_verify(it, finding))

    def test_a_static_limit_tag_is_not_attacked(self):
        it = {"id": "REQ-001", "tags": ["static-limit"]}
        self.assertFalse(audit.needs_verify(it, {"status": "MATCHED", "confidence": "high"}))


if __name__ == "__main__":
    unittest.main()
