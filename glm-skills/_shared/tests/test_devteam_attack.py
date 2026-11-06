import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "glm-dev-team", "scripts"))
import devteam  # noqa: E402


class ClassifyTests(unittest.TestCase):
    def test_table(self):
        self.assertEqual(devteam.classify_attack(1, 0, False, True), "PIN")
        self.assertEqual(devteam.classify_attack(0, 1, False, True), "BLOCKER")
        self.assertEqual(devteam.classify_attack(1, 1, True, True), "BLOCKER")
        self.assertEqual(devteam.classify_attack(1, 1, False, True), "DISCARD")
        self.assertEqual(devteam.classify_attack(0, 0, True, True), "DISCARD")
        self.assertEqual(devteam.classify_attack(None, None, False, False, body_empty=True), "DISCARD")
        self.assertEqual(devteam.classify_attack(None, None, False, False, body_empty=False), "BLOCKER")


class ModeTests(unittest.TestCase):
    def _slice(self, status="pending", risk="low", size="small"):
        return {"id": "S1", "kind": "code", "status": status, "risk": risk, "size": size,
                "from_review": False, "attempt": 1}

    def test_balanced_pending_is_red_and_red_done_is_green(self):
        os.environ.pop("DEVTEAM_SPLIT", None)
        st = {"fast": 0}
        self.assertEqual(devteam.code_mode(st, self._slice("pending")), "red")
        self.assertEqual(devteam.code_mode(st, self._slice("red-done")), "green")

    def test_turbo_stays_slice(self):
        os.environ.pop("DEVTEAM_SPLIT", None)
        self.assertEqual(devteam.code_mode({"fast": 2}, self._slice()), "slice")

    def test_first_green_stays_lite_and_a_retry_goes_strong(self):
        # Mirrors do_dispatch: RED leaves attempt at 1, the GREEN dispatch
        # increments, then routes. A retry increments once more.
        s = self._slice("red-done")
        s["title"] = "easy"
        s["attempt"] = s["attempt"] + 1
        mode = devteam.code_mode({"fast": 0}, s)
        self.assertEqual(mode, "green")
        self.assertIn("glm-programmer-lite", devteam.dispatch_route({}, s, mode))
        s["attempt"] += 1
        self.assertIn("glm-programmer-strong", devteam.dispatch_route({}, s, mode))
        red = self._slice("pending")
        red["title"] = "easy"
        self.assertIn("glm-programmer-strong", devteam.dispatch_route({}, red, "red"))

    def test_attack_is_due_once_per_report_and_tip(self):
        s = {"status": "green-proved", "attack_report_sha": "abc", "attack_at": "tip1"}
        self.assertFalse(devteam.attack_judgment_due(s, "abc", "tip1"))
        self.assertTrue(devteam.attack_judgment_due(s, "abc", "tip2"))
        self.assertTrue(devteam.attack_judgment_due(s, "def", "tip1"))
        s["attack_closed"] = True
        self.assertFalse(devteam.attack_judgment_due(s, "def", "tip2"))

    def test_prose_attack_report_blocks_instead_of_merging(self):
        import tempfile
        from pathlib import Path
        root = Path(tempfile.mkdtemp())
        reviews = root / ".claude" / "dev-team" / "reviews"
        reviews.mkdir(parents=True)
        (reviews / "attack-S1.md").write_text("APPROVED\nThe slice looks done.\n", encoding="utf-8")
        s = {"status": "inflight", "attack_n": 0}
        st = {"slices": {"S1": s}}
        line = devteam.hold_for_attack(root, st, s, "S1", "tip1")
        self.assertIn("ATTACK BLOCKER S1", line)
        self.assertNotIn("MERGED", line)
        self.assertEqual(s["status"], "green-proved")
        self.assertEqual(s["attack_at"], "tip1")
        self.assertFalse(devteam.attack_judgment_due(
            s, s["attack_report_sha"], "tip1"))

    def test_split_off_keeps_one_lane(self):
        os.environ["DEVTEAM_SPLIT"] = "off"
        try:
            self.assertEqual(devteam.code_mode({"fast": 0}, self._slice()), "slice")
        finally:
            os.environ.pop("DEVTEAM_SPLIT", None)
