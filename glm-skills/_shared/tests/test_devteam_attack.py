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

    def test_split_off_keeps_one_lane(self):
        os.environ["DEVTEAM_SPLIT"] = "off"
        try:
            self.assertEqual(devteam.code_mode({"fast": 0}, self._slice()), "slice")
        finally:
            os.environ.pop("DEVTEAM_SPLIT", None)
