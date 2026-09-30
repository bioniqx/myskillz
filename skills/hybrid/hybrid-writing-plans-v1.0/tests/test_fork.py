import importlib.util
import unittest
from pathlib import Path

HP = Path(__file__).resolve().parents[1]
SRC = Path(__file__).resolve().parents[3] / "claude-skills" / "writing-plans-6.2"
COPIED = ["task-writer-prompt.md", "plan-reviewer-prompt.md", "agents/plan-task-writer.md"]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def contract(i, spec, files, produces):
    return {"id": "T%02d" % i, "spec": spec, "files": files, "produces": produces}


SAMPLE = [
    contract(1, [(1, 10)], ["a.py"], ["def a():"]),
    contract(2, [(1, 90), (100, 130)], ["b.py", "c.py", "d.py"], ["def b():", "def c():"]),
    contract(3, [], [], []),
    contract(4, [(5, 5)], ["e.py", "f.py"], []),
    contract(5, [(10, 70)], ["g.py"], ["def g():", "def h():", "def i():"]),
    contract(6, [(1, 300)], ["h.py"], ["def j():"]),
    contract(7, [(20, 29)], ["i.py", "j.py"], ["def k():"]),
]


class ForkCopyTest(unittest.TestCase):
    @unittest.skipUnless(SRC.is_dir(), "writing-plans-6.2 not present")
    def test_prompts_and_agent_copied_unchanged(self):
        for rel in COPIED:
            self.assertEqual((HP / rel).read_bytes(), (SRC / rel).read_bytes(), rel)

    def test_plan_tool_compiles_and_has_commands(self):
        text = (HP / "scripts" / "plan_tool.py").read_text(encoding="utf-8")
        compile(text, "plan_tool.py", "exec")
        for name in ("def cmd_contracts", "def partition", "def writer_brief", "def dispatch_lines"):
            self.assertIn(name, text)


class WeightTest(unittest.TestCase):
    def setUp(self):
        self.pt = load(HP / "scripts" / "plan_tool.py", "hp_fork_plan_tool")

    def test_weight_formula(self):
        c = contract(9, [(1, 30), (41, 70)], ["x.py", "y.py"], ["def f():"])
        self.assertAlmostEqual(self.pt.weight(c), 2.0 + 60 / 30.0 + 0.5 * 2 + 0.5 * 1)

    def test_weight_empty_contract(self):
        self.assertAlmostEqual(self.pt.weight(contract(3, [], [], [])), 2.0)

    def test_one_slot_is_one_group_on_every_python(self):
        # Python >= 3.12 sums floats with compensation: sum(w) can undershoot the running total of groups().
        cs = [contract(1, [(1, 96)], ["a", "b"], ["x", "y", "z"]), contract(2, [(1, 65)], ["a", "b", "c"], ["x"]),
              contract(3, [(1, 39)], ["a", "b"], ["x", "y", "z"])]
        self.assertEqual([[c["id"] for c in g] for g in self.pt.partition(cs, 1)], [["T01", "T02", "T03"]])

    @unittest.skipUnless(SRC.is_dir(), "writing-plans-6.2 not present")
    def test_partition_matches_6_2(self):
        old = load(SRC / "scripts" / "plan_tool.py", "wp62_plan_tool")
        for k in (1, 2, 3, 4, 7, 10):
            got = [[c["id"] for c in g] for g in self.pt.partition(SAMPLE, k)]
            want = [[c["id"] for c in g] for g in old.partition(SAMPLE, k)]
            self.assertEqual(got, want, "k=%d" % k)


if __name__ == "__main__":
    unittest.main()
