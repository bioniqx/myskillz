"""The fork's linter must accept and reject exactly what writing-plans-6.2's linter does."""
import importlib.util
import unittest
import warnings
from pathlib import Path

HP = Path(__file__).resolve().parents[1]
SRC = Path(__file__).resolve().parents[3] / "claude-skills" / "claude-writing-plans-6.2"
FENCE = "`" * 3

PLAN = "\n".join([
    "# Demo Implementation Plan", "", "**Goal:** parity.", "", "## Contracts", "",
    "#### T01: Build", "- Files: `src/a.py`, `tests/test_a.py`", "- Produces: `def a() -> int`", "- Spec: L1-2", "",
    "#### T02: Makefile", "- Files: `Makefile`, `Dockerfile`", "- Spec: L1-2", "",
    "#### T03: Annotated", "- Files: `src/c.py` (new module; see `Symbol`)", "- Spec: L1-2", "",
])


warnings.filterwarnings("ignore", category=DeprecationWarning)  # 6.2 passes maxsplit positionally


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def body(files, code, add, run=True, extra=""):
    return "\n".join([
        "**Files:**"] + files + [
        "", "- [ ] **Step 1: Write**", "", FENCE + "python", code, FENCE, "",
        "- [ ] **Step 2: Check**", ""] + (["Run: `python3 -m py_compile src/a.py`", "Expected: no output", ""] if run else []) + [
        "- [ ] **Step 3: Commit**", "", FENCE + "bash", add, FENCE, extra]) + "\n"


A = ["- Create: `src/a.py`", "- Create: `tests/test_a.py`"]
COMMIT = 'git commit -m "feat: a"'
BODIES = {
    "T01": [
        body(A, "def a() -> int:\n    return 1", "git add src/a.py tests/test_a.py\n" + COMMIT),
        body(A, "# a comment at column 0\ndef a() -> int:\n    return 1", "git add src/a.py tests/test_a.py\n" + COMMIT),
        body(A, "def a() -> int:\n    return 1  # TODO later", "git add src/a.py tests/test_a.py\n" + COMMIT),
        body(A, "def a() -> int:\n    return 1  # todo lower case", "git add src/a.py tests/test_a.py\n" + COMMIT),
        body(A, "def a() -> int:\n    return 1", "git add src/a.py tests/test_a.py && git commit -m x\n" + COMMIT),
        body(A, "def a() -> int:\n    return 1", "git add src/a.py tests/test_a.py; git commit -m x\n" + COMMIT),
        body(A, "def a() -> int:\n    return 1", "git add -A\n" + COMMIT),
        body(A, "def a() -> int:\n    return 1", "git add src/other.py\n" + COMMIT),
        body(A, "def a() -> int:\n    return 1", "git add src/a.py tests/test_a.py\n" + COMMIT,
             extra="\nUse `TODO` markers sparingly; see https://claude.ai/docs and the `Claude` note.\n"),
        body(A, "def a() -> int:\n    return 1", "git add src/a.py tests/test_a.py\n" + COMMIT,
             extra="\nThe Claude subagent will do it. TODO: later. Same as T02.\n"),
        body(A, "def a() -> int:\n    return 1", "git add src/a.py tests/test_a.py\n" + COMMIT,
             extra="\n# Heading at column 0\n" + FENCE + "text\n# not a heading\n### T09: fake task\n" + FENCE + "\n"),
        body(A, "def a() -> int:\n    return 1", "git add src/a.py tests/test_a.py\n" + COMMIT, run=False),
        body(A, "def a( -> int:\n    return 1", "git add src/a.py tests/test_a.py\n" + COMMIT),
        body(A, "def b() -> int:\n    return 1", "git add src/a.py tests/test_a.py\n" + COMMIT),
        body(A, "def a() -> int:\n    return 1", "git add src/a.py tests/test_a.py\ngit commit -am x"),
        body(A, "def a() -> int:\n    return 1", "git commit -m x"),
    ],
    "T02": [
        body(["- Create: `Makefile`", "- Create: `Dockerfile`"], "x = 1", "git add Makefile Dockerfile\n" + COMMIT),
        body(["- Create: `Makefile`"], "x = 1", "git add Makefile LICENSE\n" + COMMIT),
    ],
    "T03": [
        body(["- Create: `src/c.py`"], "x = 1", "git add src/c.py\n" + COMMIT),
    ],
}


@unittest.skipUnless(SRC.is_dir(), "writing-plans-6.2 not present")
class LintParityTest(unittest.TestCase):
    def test_lint_body_matches_6_2(self):
        old = load(SRC / "scripts" / "plan_tool.py", "wp62_parity")
        new = load(HP / "scripts" / "plan_tool.py", "hp_parity")
        results = {}
        for name, mod in (("old", old), ("new", new)):
            cs, errs = mod.parse_contracts(PLAN)
            self.assertFalse(errs, errs)
            mod.analyze(cs, None, None)
            cmap = {c["id"]: c for c in cs}
            results[name] = [(tid, i, mod.lint_body(cmap[tid], b, [], tid, None, ()))
                             for tid, bodies in BODIES.items() for i, b in enumerate(bodies)]
        for o, n in zip(results["old"], results["new"]):
            self.assertEqual(n, o, "%s body %d" % (o[0], o[1]))
        accepted = [r for r in results["new"] if not r[2][0]]
        self.assertTrue(accepted and len(accepted) < len(results["new"]))  # the set exercises both outcomes

    def test_allow_stem_matches_6_2(self):
        old = load(SRC / "scripts" / "plan_tool.py", "wp62_parity_allow")
        new = load(HP / "scripts" / "plan_tool.py", "hp_parity_allow")
        text = "The Claude subagent writes a todo list.\n"
        for allow in ([], ["subagent"], ["re:Claude"], ["claude", "subagent"]):
            self.assertEqual(new.scan(text, allow, "t"), old.scan(text, allow, "t"), allow)

    def test_bare_filenames_can_lint(self):
        new = load(HP / "scripts" / "plan_tool.py", "hp_parity_bare")
        cs, _ = new.parse_contracts(PLAN)
        new.analyze(cs, None, None)
        c = next(x for x in cs if x["id"] == "T02")
        errs, _ = new.lint_body(c, BODIES["T02"][0], [], "T02", None, ())
        self.assertEqual(errs, [])


if __name__ == "__main__":
    unittest.main()
