import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "..", "_shared"))
import decide  # noqa: E402


def attacked(option_id, kind="NO-BREAK"):
    return [{"option": option_id, "kind": kind, "reproduced": True, "via": "check"}]


class AtomTests(unittest.TestCase):
    def test_model_atom_that_is_not_a_substring_is_dropped(self):
        frozen, dropped = decide.check_model_atoms("must retry", "ATOM: invented span\n")
        self.assertEqual(dropped, ["ATOM: invented span"])
        self.assertIn("must retry", frozen)
        self.assertNotIn("invented span", frozen)

    def test_year_inside_a_date_is_not_an_atom_and_a_criterion_number_is(self):
        self.assertEqual(decide.extract_atoms("shipped on 2026-10-26"), [])
        self.assertEqual(decide.extract_atoms("criterion 42"), ["42"])
        self.assertNotIn("12", decide.extract_atoms("version 1.2.3 stays out"))


class ScoreTests(unittest.TestCase):
    def test_each_term_including_a_reproduced_break(self):
        facts = {"F-1": {"id": "F-1", "status": "OK", "text": "pool"}}
        base = {"id": "A1", "atoms_hit": ["must ship"], "out_of_scope": "",
                "fact_ids": ["F-1"], "new_deps": [], "assumptions": []}
        self.assertEqual(decide.score_option(base, ["must ship"], facts, [], []), 5)
        broken = dict(base)
        reports = attacked("A1", "COUNTEREXAMPLE")
        self.assertEqual(decide.score_option(broken, ["must ship"], facts, [], reports), 0)
        missing_dep = dict(base, new_deps=["left-pad"], fact_ids=[])
        self.assertEqual(decide.score_option(missing_dep, ["must ship"], facts, [], []), 1)
        bare = dict(base, fact_ids=[], assumptions=[{"text": "guess", "fact": ""}])
        self.assertEqual(decide.score_option(bare, ["must ship"], facts, [], []), 2)

    def _pair(self, a_score_facts, b_atoms=True):
        facts = {"F-1": {"id": "F-1", "status": "OK", "text": "pool-get"}}
        ledger = {"facts": list(facts.values())}
        a = {"id": "A1", "atoms_hit": ["must ship"], "out_of_scope": "",
             "fact_ids": ["F-1"] if a_score_facts else [], "new_deps": [], "assumptions": []}
        b = {"id": "A2", "atoms_hit": ["must ship"] if b_atoms else [],
             "out_of_scope": "", "fact_ids": [], "new_deps": [],
             "assumptions": [{"text": "x", "fact": ""}]}
        reports = attacked("A1") + attacked("A2")
        return decide.decide([a, b], ["must ship"], ledger, [], reports)

    def test_margin_below_3_asks_and_a_wider_margin_picks(self):
        # A = +3+2 = 5, B = +3-1 = 2, margin 3, leave-one-out drops the only fact
        # and the margin falls, so this asks. A lone option with no rival scores
        # against 0.
        self.assertTrue(self._pair(True).startswith("DECISION ask="))
        facts = {"F-1": {"id": "F-1", "status": "OK", "text": "pool"}}
        only = {"id": "A1", "atoms_hit": ["must ship"], "fact_ids": ["F-1"],
                "out_of_scope": "", "new_deps": [], "assumptions": []}
        line = decide.decide([only], ["must ship"], {"facts": list(facts.values())}, [], attacked("A1"))
        self.assertEqual(line, "DECISION pick=A1 margin=5")

    def test_unattacked_option_does_not_win(self):
        option = {"id": "A1", "atoms_hit": ["must ship"], "fact_ids": [],
                  "out_of_scope": "", "new_deps": [], "assumptions": []}
        line = decide.decide([option], ["must ship"], {"facts": []}, [], [])
        self.assertEqual(line, "DECISION ask=unattacked")

    def test_leave_one_out_flips_a_margin_3_winner_when_its_only_ok_fact_is_removed(self):
        line = self._pair(True)
        self.assertEqual(line, "DECISION ask=A1")


class ProveTests(unittest.TestCase):
    def test_offline_does_not_call_urlopen(self):
        ledger = {"facts": [{"id": "F-1", "kind": "web", "loc": "https://example.com",
                             "text": "hello", "status": "OK"}]}
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("socket")) as opened:
            decide.prove_ledger(ledger, offline=True)
        opened.assert_not_called()
        self.assertEqual(ledger["facts"][0]["status"], "UNPROVEN")
        self.assertEqual(ledger["facts"][0]["reason"], "offline")


class BindTests(unittest.TestCase):
    def test_dated_https_without_a_fact_fails_and_an_ok_fact_passes(self):
        line = "retries (https://docs.example.org/client) (2026-08-01).\n"
        self.assertTrue(decide.bind_text(line, {"facts": []}))
        ledger = {"facts": [{"id": "F-1", "status": "OK", "kind": "web",
                             "loc": "https://docs.example.org/client", "text": "retries"}]}
        bound = "retries (https://docs.example.org/client) (2026-08-01) F-1.\n"
        self.assertEqual(decide.bind_text(bound, ledger), [])

    def test_pick_must_be_named(self):
        fails = decide.bind_text("APPROACH 1: stay\n", {"facts": []}, pick="A2")
        self.assertTrue(any("A2" in item for item in fails))


class CliTests(unittest.TestCase):
    def test_atoms_check_prints_drop_and_frozen(self):
        fd, path = tempfile.mkstemp()
        os.write(fd, b"must retry\n")
        os.close(fd)
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch("sys.stdin", io.StringIO("ATOM: not in source\n")):
            code = decide.main(["atoms-check", "--source", path])
        os.remove(path)
        out = buf.getvalue()
        self.assertEqual(code, 0, out)
        self.assertIn("ATOM: must retry", out)
        self.assertIn("DROP: ATOM: not in source", out)
        self.assertIn("FROZEN n=1", out)
