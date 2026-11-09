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
