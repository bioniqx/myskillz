"""A silent brainstorming ask picks the scored option and opens the chain."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.realpath(os.path.join(HERE, "..", "..", "glm-brainstorming", "scripts"))
sys.path.insert(0, SCRIPTS)
import ask  # noqa: E402
import check  # noqa: E402


def attacked(option_id):
    return {"option": option_id, "kind": "NO-BREAK", "reproduced": True}


class AutoDecisionTests(unittest.TestCase):
    def test_a_narrow_margin_becomes_the_leading_pick(self):
        options = [
            {"id": "A", "atoms_hit": ["must ship"], "fact_ids": ["F-1"], "assumptions": []},
            {"id": "B", "atoms_hit": ["must ship"], "fact_ids": [], "assumptions": []},
        ]
        ledger = {"facts": [{"id": "F-1", "status": "OK", "text": "pool"}], "atoms": ["must ship"]}
        reports = [attacked("A"), attacked("B")]
        self.assertEqual(ask.auto_decision(options, ["must ship"], ledger, [], reports),
                         "DECISION pick=A auto=1")

    def test_an_unattacked_leader_is_not_a_pick(self):
        options = [{"id": "A", "atoms_hit": ["must ship"], "fact_ids": ["F-1"], "assumptions": []}]
        ledger = {"facts": [{"id": "F-1", "status": "OK", "text": "pool"}], "atoms": ["must ship"]}
        self.assertEqual(ask.auto_decision(options, ["must ship"], ledger, [], []),
                         "DECISION ask=unattacked")


class WaitTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ask-")
        self.ledger = os.path.join(self.dir, "ledger.json")
        self.options = os.path.join(self.dir, "options.json")
        self.reply = os.path.join(self.dir, "reply.txt")
        self.cancel = os.path.join(self.dir, "ask.cancel")
        self.chain = os.path.join(self.dir, "chain.json")
        json.dump({"facts": [{"id": "F-1", "status": "OK", "text": "pool"}],
                   "atoms": ["must ship"]}, open(self.ledger, "w"))
        json.dump([
            {"id": "A", "atoms_hit": ["must ship"], "fact_ids": ["F-1"], "assumptions": []},
            {"id": "B", "atoms_hit": ["must ship"], "fact_ids": [], "assumptions": []},
        ], open(self.options, "w"))
        json.dump({"breaks": [attacked("A"), attacked("B")]},
                  open(os.path.join(self.dir, "breaks.json"), "w"))

    def test_timeout_writes_the_chain_and_names_the_pick(self):
        kind, text = ask.resolve_once(
            self.ledger, self.options, self.reply, self.cancel, self.chain, now=2, deadline=1)
        self.assertEqual(kind, "AUTO")
        self.assertIn("pick=A", text)
        chain = json.load(open(self.chain))
        self.assertTrue(chain["continue"])
        self.assertEqual(chain["next"], ["spec", "glm-writing-plans", "glm-dev-team"])

    def test_a_reply_file_wins_over_the_deadline(self):
        open(self.reply, "w").write("revise the api\n")
        kind, text = ask.resolve_once(
            self.ledger, self.options, self.reply, self.cancel, self.chain, now=5, deadline=1)
        self.assertEqual(kind, "REPLY")
        self.assertIn("revise", text)
        self.assertFalse(os.path.exists(self.chain))

    def test_cancel_wins(self):
        open(self.cancel, "w").write("cancel\n")
        kind, _text = ask.resolve_once(
            self.ledger, self.options, self.reply, self.cancel, self.chain, now=5, deadline=1)
        self.assertEqual(kind, "CANCEL")


class ApproveAutoTests(unittest.TestCase):
    def test_the_auto_block_approves(self):
        ns = type("N", (), {"asked": "design"})()
        old = sys.stdin
        sys.stdin = _In("AUTO\nDECISION pick=A auto=1\n")
        try:
            self.assertEqual(check.check_approve(ns), 0)
        finally:
            sys.stdin = old

    def test_revise_does_not_approve(self):
        ns = type("N", (), {"asked": "design"})()
        old = sys.stdin
        sys.stdin = _In("revise\n")
        try:
            self.assertEqual(check.check_approve(ns), 1)
        finally:
            sys.stdin = old


class _In(object):
    def __init__(self, text):
        self.text = text

    def read(self):
        return self.text


class ModeTests(unittest.TestCase):
    def test_a_fast_phrase_is_fast_and_a_plain_request_is_fast(self):
        from handoff import mode_of
        self.assertEqual(mode_of("dung che do FAST", ""), "fast")
        self.assertEqual(mode_of("use FAST mode for this feature", ""), "fast")
        self.assertEqual(mode_of("D\u00f9ng ch\u1ebf \u0111\u1ed9 fast", ""), "fast")
        self.assertEqual(mode_of("FAST", ""), "fast")
        self.assertEqual(mode_of("make the search fast", ""), "fast")
        self.assertEqual(mode_of("build an interactive dashboard", ""), "fast")

    def test_a_slow_phrase_is_slow(self):
        from handoff import mode_of
        self.assertEqual(mode_of("SLOW", ""), "slow")
        self.assertEqual(mode_of("che do chat luong", ""), "slow")
        self.assertEqual(mode_of("uu tien chat luong", ""), "slow")

    def test_a_refusal_does_not_select_the_other_mode(self):
        from handoff import mode_of
        self.assertEqual(mode_of("khong dung fast", ""), "fast")
        self.assertEqual(mode_of("khong dung slow", ""), "fast")
        self.assertEqual(mode_of("do not use FAST mode", ""), "fast")

    def test_cmd_mode_never_asks(self):
        dest = os.path.join(tempfile.mkdtemp(prefix="mode-"), "mode.json")
        ns = type("N", (), {"file": dest})()
        old = sys.stdin
        sys.stdin = _In("build an interactive dashboard")
        try:
            rc = ask.cmd_mode(ns)
        finally:
            sys.stdin = old
        self.assertEqual(rc, 0)
        self.assertEqual(json.load(open(dest))["mode"], "fast")


class FastPickTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="fast-")
        self.ledger = os.path.join(self.dir, "ledger.json")
        self.options = os.path.join(self.dir, "options.json")
        self.chain = os.path.join(self.dir, "chain.json")
        self.mode = os.path.join(self.dir, "mode.json")
        json.dump({"facts": [{"id": "F-1", "status": "OK", "text": "pool"}],
                   "atoms": ["must ship"]}, open(self.ledger, "w"))

    def _run(self, options, breaks):
        json.dump(options, open(self.options, "w"))
        json.dump({"breaks": breaks}, open(os.path.join(self.dir, "breaks.json"), "w"))
        ns = type("N", (), {"ledger": self.ledger, "options": self.options,
                            "chain": self.chain, "mode": self.mode})()
        return ask.cmd_fast(ns)

    def test_a_narrow_margin_writes_fast_chain(self):
        rc = self._run([
            {"id": "A", "atoms_hit": ["must ship"], "fact_ids": ["F-1"], "assumptions": []},
            {"id": "B", "atoms_hit": ["must ship"], "fact_ids": [], "assumptions": []},
        ], [attacked("A"), attacked("B")])
        self.assertEqual(rc, 0)
        chain = json.load(open(self.chain))
        self.assertEqual(chain["mode"], "fast")
        self.assertEqual(chain["source"], "fast")
        self.assertEqual(chain["pick"], "A")
        self.assertTrue(chain["continue"])
        self.assertEqual(json.load(open(self.mode))["mode"], "fast")

    def test_an_unattacked_leader_is_still_picked(self):
        rc = self._run([
            {"id": "A", "atoms_hit": ["must ship"], "fact_ids": ["F-1"], "assumptions": []},
        ], [])
        self.assertEqual(rc, 0)
        self.assertEqual(json.load(open(self.chain))["pick"], "A")

    def test_an_all_broken_set_picks_the_least_bad(self):
        broken = {"kind": "COUNTEREXAMPLE", "reproduced": True}
        rc = self._run([
            {"id": "A", "atoms_hit": ["must ship"], "fact_ids": ["F-1"], "assumptions": []},
            {"id": "B", "atoms_hit": [], "fact_ids": [], "assumptions": []},
        ], [dict(broken, option="A"), dict(broken, option="B")])
        self.assertEqual(rc, 0)
        self.assertEqual(json.load(open(self.chain))["pick"], "A")

    def test_no_option_does_not_write_a_chain(self):
        rc = self._run([], [])
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(self.chain))

    def test_the_silence_path_still_refuses_an_unattacked_leader(self):
        json.dump([
            {"id": "A", "atoms_hit": ["must ship"], "fact_ids": ["F-1"], "assumptions": []},
        ], open(self.options, "w"))
        kind, text = ask.resolve_once(
            self.ledger, self.options, os.path.join(self.dir, "reply.txt"),
            os.path.join(self.dir, "cancel"), self.chain, now=2, deadline=1)
        self.assertEqual(kind, "AUTO")
        self.assertIn("unattacked", text)
        self.assertFalse(os.path.exists(self.chain))


class ChainCommandTests(unittest.TestCase):
    def test_user_approval_writes_the_same_chain(self):
        dest = os.path.join(tempfile.mkdtemp(prefix="chain-"), "chain.json")
        rc = subprocess.call(
            [sys.executable, os.path.join(SCRIPTS, "ask.py"), "chain",
             "--pick", "A", "--chain", dest],
            stdout=subprocess.DEVNULL)
        self.assertEqual(rc, 0)
        self.assertTrue(json.load(open(dest))["continue"])


if __name__ == "__main__":
    unittest.main()
