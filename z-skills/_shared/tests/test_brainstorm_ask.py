"""A silent brainstorming ask picks the scored option and opens the chain."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.realpath(os.path.join(HERE, "..", "..", "z-brainstorming", "scripts"))
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
        self.assertEqual(chain["next"], ["spec", "z-writing-plans", "z-dev-team"])

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

    def test_a_slow_wait_stops_at_its_limit_and_picks_nothing(self):
        before = ask.resolve_once(
            self.ledger, self.options, self.reply, self.cancel, self.chain,
            now=1, deadline=2, allow_pick=False)
        self.assertIsNone(before)
        at_limit = ask.resolve_once(
            self.ledger, self.options, self.reply, self.cancel, self.chain,
            now=2, deadline=2, allow_pick=False)
        self.assertEqual(at_limit, ("TIMEOUT", ""))
        self.assertFalse(os.path.exists(self.chain))

    def test_the_wait_loop_hands_the_no_pick_flag_to_the_deadline(self):
        ticks = iter([0, 0, 5])
        kind, text = ask.wait_loop(
            self.ledger, self.options, self.reply, self.cancel, self.chain, 1,
            allow_pick=False, sleep=lambda _seconds: None, clock=lambda: next(ticks))
        self.assertEqual((kind, text), ("TIMEOUT", ""))
        self.assertFalse(os.path.exists(self.chain))

    def test_cmd_wait_picks_only_outside_a_slow_stamp(self):
        for mode in ("slow", "fast", ""):
            with self.subTest(mode=mode):
                seen = {}

                def fake_loop(*args, **kwargs):
                    seen.update(kwargs)
                    if kwargs.get("allow_pick"):
                        return "AUTO", "DECISION pick=A auto=1"
                    return "TIMEOUT", ""

                ns = type("N", (), {"ledger": self.ledger, "options": self.options,
                                    "reply": self.reply, "cancel": self.cancel,
                                    "chain": self.chain, "timeout": 0})()
                buf = io.StringIO()
                old = sys.stdout
                sys.stdout = buf
                try:
                    with mock.patch.object(ask, "brainstorm_mode", return_value=mode):
                        with mock.patch.object(ask, "wait_loop", fake_loop):
                            rc = ask.cmd_wait(ns)
                finally:
                    sys.stdout = old
                out = buf.getvalue()
                self.assertEqual(rc, 0, out)
                self.assertEqual(out.splitlines()[0],
                                 "TIMEOUT" if mode == "slow" else "AUTO", out)
                self.assertIs(seen.get("allow_pick"), mode != "slow")
                if mode == "slow":
                    self.assertIn("Nothing is approved", out)
                    self.assertNotIn("AUTO", out)
                    self.assertFalse(os.path.exists(self.chain))
                else:
                    self.assertIn("APPROVE: approved", out)


class ApproveAutoTests(unittest.TestCase):
    def test_the_auto_block_approves(self):
        ns = type("N", (), {"asked": "design"})()
        old = sys.stdin
        sys.stdin = _In("AUTO\nDECISION pick=A auto=1\n")
        try:
            with mock.patch.object(check, "brainstorm_mode", return_value=""):
                self.assertEqual(check.check_approve(ns), 0)
        finally:
            sys.stdin = old

    def test_the_auto_block_is_approved_under_a_slow_stamp(self):
        # 2026-11-27: SLOW decides, so the engine's pick is the approval and
        # the stamp no longer refuses an AUTO block.
        ns = type("N", (), {"asked": "design"})()
        old = sys.stdin
        sys.stdin = _In("AUTO\nDECISION pick=A auto=1\n")
        try:
            with mock.patch.object(check, "brainstorm_mode", return_value="slow"):
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
        buf = io.StringIO()
        old_out = sys.stdout
        with mock.patch.object(ask, "read_mode_stamp", return_value=""):
            sys.stdout = buf
            try:
                rc = ask.cmd_mode(ns)
            finally:
                sys.stdin = old
                sys.stdout = old_out
        self.assertEqual(rc, 0)
        self.assertEqual(json.load(open(dest))["mode"], "fast")
        printed = buf.getvalue()
        self.assertIn("MODE fast", printed)
        self.assertIn("NEXT: follow the PACE fast NEXT", printed)
        self.assertNotIn("fast.md", printed)


class FastPickTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="fast-")
        self.ledger = os.path.join(self.dir, "ledger.json")
        self.options = os.path.join(self.dir, "options.json")
        self.chain = os.path.join(self.dir, "chain.json")
        self.mode = os.path.join(self.dir, "mode.json")
        json.dump({"facts": [{"id": "F-1", "status": "OK", "text": "pool"}],
                   "atoms": ["must ship"]}, open(self.ledger, "w"))

    def _run(self, options, breaks, request=""):
        json.dump(options, open(self.options, "w"))
        json.dump({"breaks": breaks}, open(os.path.join(self.dir, "breaks.json"), "w"))
        ns = type("N", (), {"ledger": self.ledger, "options": self.options,
                            "chain": self.chain, "mode": self.mode,
                            "request": request})()
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            rc = ask.cmd_fast(ns)
        finally:
            sys.stdout = old
        return rc, buf.getvalue()

    def test_a_narrow_margin_writes_fast_chain(self):
        rc, out = self._run([
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
        self.assertIn("RESULT approve yes", out)
        self.assertIn("check.py send", out)
        self.assertNotIn("check.py approve", out)

    def test_an_unattacked_leader_is_still_picked(self):
        rc, _out = self._run([
            {"id": "A", "atoms_hit": ["must ship"], "fact_ids": ["F-1"], "assumptions": []},
        ], [])
        self.assertEqual(rc, 0)
        self.assertEqual(json.load(open(self.chain))["pick"], "A")

    def test_an_all_broken_set_picks_the_least_bad(self):
        broken = {"kind": "COUNTEREXAMPLE", "reproduced": True}
        rc, _out = self._run([
            {"id": "A", "atoms_hit": ["must ship"], "fact_ids": ["F-1"], "assumptions": []},
            {"id": "B", "atoms_hit": [], "fact_ids": [], "assumptions": []},
        ], [dict(broken, option="A"), dict(broken, option="B")])
        self.assertEqual(rc, 0)
        self.assertEqual(json.load(open(self.chain))["pick"], "A")

    def test_no_option_does_not_write_a_chain(self):
        rc, out = self._run([], [])
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(self.chain))
        self.assertNotIn("RESULT approve yes", out)

    def test_a_request_argument_writes_the_single_option(self):
        rc, _out = self._run([], [], request="add an export flag to the api")
        self.assertEqual(rc, 0)
        options = json.load(open(self.options))
        self.assertEqual([o["id"] for o in options], ["A"])
        self.assertEqual(options[0]["text"], "add an export flag to the api")
        self.assertEqual(json.load(open(self.chain))["pick"], "A")

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

    def test_a_slow_stamp_writes_a_slow_chain(self):
        home = tempfile.mkdtemp(prefix="chain-slow-")
        cases = ((json.dumps({"mode": "slow"}), None), (None, "slow 1\n"))
        for mode_file, stamp in cases:
            with self.subTest(stamp=stamp):
                mode = os.path.join(home, "mode.json")
                if mode_file is not None:
                    with open(mode, "w", encoding="utf-8") as fh:
                        fh.write(mode_file + "\n")
                repo = tempfile.mkdtemp(prefix="chain-repo-")
                subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
                if stamp is not None:
                    os.makedirs(os.path.join(repo, ".claude", "dev-team"))
                    with open(os.path.join(repo, ".claude", "dev-team", "mode"), "w",
                              encoding="utf-8") as fh:
                        fh.write(stamp)
                dest = os.path.join(home, "chain.json")
                rc = subprocess.call(
                    [sys.executable, os.path.join(SCRIPTS, "ask.py"), "chain",
                     "--pick", "A", "--chain", dest, "--mode", mode],
                    stdout=subprocess.DEVNULL, cwd=repo)
                self.assertEqual(rc, 0)
                self.assertEqual(json.load(open(dest))["mode"], "slow")


class EngineChainTests(unittest.TestCase):
    """chain without --pick: the engine names the pick, which is all SLOW needs."""

    CLEAR = ({"id": "A", "atoms_hit": ["must ship"], "fact_ids": ["F-1"], "assumptions": []},
             {"id": "B", "atoms_hit": [], "fact_ids": [], "assumptions": []})

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="chain-engine-")
        self.ledger = os.path.join(self.dir, "ledger.json")
        self.options = os.path.join(self.dir, "options.json")
        self.chain = os.path.join(self.dir, "chain.json")
        json.dump({"facts": [{"id": "F-1", "status": "OK", "text": "pool"}],
                   "atoms": ["must ship"]}, open(self.ledger, "w"))

    def _chain(self, options, breaks, stamp=""):
        json.dump(options, open(self.options, "w"))
        json.dump({"breaks": breaks}, open(os.path.join(self.dir, "breaks.json"), "w"))
        ns = type("N", (), {"pick": "", "ledger": self.ledger, "options": self.options,
                            "chain": self.chain,
                            "mode": os.path.join(self.dir, "mode.json")})()
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            with mock.patch.object(ask, "read_mode_stamp", return_value=stamp):
                rc = ask.cmd_chain(ns)
        finally:
            sys.stdout = old
        return rc, buf.getvalue()

    def test_a_clear_leader_is_chained_and_approved(self):
        rc, out = self._chain(list(self.CLEAR), [attacked("A"), attacked("B")])
        self.assertEqual(rc, 0, out)
        self.assertIn("DECISION pick=A auto=1", out)
        self.assertIn("RESULT approve yes", out)
        # The design-only stop comes before the order to chain (review, 2026-11-27).
        self.assertLess(out.index("A Spike or a design-only request stops"),
                        out.index("handoff.py next"))
        self.assertIn("Only when the request asks to build", out)
        chain = json.load(open(self.chain))
        self.assertEqual((chain["pick"], chain["source"]), ("A", "auto"))
        self.assertTrue(chain["continue"])
        self.assertNotIn("mode", chain)

    def test_a_narrow_margin_chains_its_leader_and_the_slow_stamp(self):
        options = [
            {"id": "A", "atoms_hit": ["must ship"], "fact_ids": ["F-1"], "assumptions": []},
            {"id": "B", "atoms_hit": ["must ship"], "fact_ids": [], "assumptions": []},
        ]
        rc, out = self._chain(options, [attacked("A"), attacked("B")], stamp="slow")
        self.assertEqual(rc, 0, out)
        chain = json.load(open(self.chain))
        self.assertEqual((chain["pick"], chain["mode"], chain["source"]),
                         ("A", "slow", "auto"))
        self.assertIn("RESULT approve yes", out)

    def test_an_unattacked_leader_is_refused_with_its_repair(self):
        rc, out = self._chain(list(self.CLEAR), [attacked("B")])
        self.assertEqual(rc, 2, out)
        self.assertIn("DECISION ask=unattacked", out)
        self.assertIn("the score leader A has no reproduced break", out)
        self.assertIn("run one breaker on it", out)
        self.assertIn("Do not ask the user.", out)
        self.assertNotIn("RESULT approve yes", out)
        self.assertFalse(os.path.exists(self.chain))

    def test_a_stop_is_refused_with_its_repair(self):
        broken = {"kind": "COUNTEREXAMPLE", "reproduced": True}
        rc, out = self._chain(list(self.CLEAR),
                              [dict(broken, option="A"), dict(broken, option="B")])
        self.assertEqual(rc, 2, out)
        self.assertIn("DECISION stop", out)
        self.assertIn("rewrite the options once", out)
        self.assertIn("Do not ask the user.", out)
        self.assertFalse(os.path.exists(self.chain))


if __name__ == "__main__":
    unittest.main()
