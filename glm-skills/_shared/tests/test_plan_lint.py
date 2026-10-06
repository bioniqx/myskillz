import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_TOOL = os.path.join(HERE, "..", "..", "glm-writing-plans", "scripts", "plan_tool.py")


def _load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_lint_under_test", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan_tool = _load_plan_tool()
FENCE = "`" * 3


def contract(*files):
    return {"files": list(files), "produces": []}


def make_body(file_lines, code_lines, commit_line, extra=()):
    rows = ["**Files:**"] + list(file_lines) + [""] + list(extra) + [
        "- [ ] **Step 1: Write the code**", "",
        FENCE + "python"] + list(code_lines) + [FENCE, "",
        "- [ ] **Step 2: Commit**", "",
        FENCE + "bash", commit_line, FENCE, ""]
    return "\n".join(rows)


def lint(c, body):
    return plan_tool.lint_body(c, body, [], "T99")


HEADING_ERR = "heading inside a task body"


class HeadingFenceTest(unittest.TestCase):
    def test_hash_comment_inside_fence_is_not_a_heading(self):
        body = make_body(["- Create: `src/app.py`"],
                         ["# build the value", "x = 1"],
                         "git add src/app.py")
        errs, _ = lint(contract("src/app.py"), body + "\ngit commit -m x\n")
        self.assertFalse([e for e in errs if HEADING_ERR in e], errs)

    def test_hash_comment_inside_tilde_fence_is_not_a_heading(self):
        body = "\n".join(["**Files:**", "- Create: `src/app.py`", "",
                          "- [ ] **Step 1: Write the code**", "",
                          "~~~python", "## section comment", "x = 1", "~~~", "",
                          "- [ ] **Step 2: Commit**", "",
                          FENCE + "bash", "git add src/app.py", "git commit -m x", FENCE, ""])
        errs, _ = lint(contract("src/app.py"), body)
        self.assertFalse([e for e in errs if HEADING_ERR in e], errs)

    def test_heading_outside_fence_still_fails(self):
        body = make_body(["- Create: `src/app.py`"], ["x = 1"],
                         "git add src/app.py", extra=["## Notes", ""])
        errs, _ = lint(contract("src/app.py"), body + "\ngit commit -m x\n")
        self.assertTrue([e for e in errs if HEADING_ERR in e], errs)

    def test_heading_after_closed_fence_still_fails(self):
        body = make_body(["- Create: `src/app.py`"], ["x = 1"],
                         "git add src/app.py")
        errs, _ = lint(contract("src/app.py"), body + "\n### Late heading\ngit commit -m x\n")
        self.assertTrue([e for e in errs if HEADING_ERR in e], errs)


class FilesBlockBareNameTest(unittest.TestCase):
    def test_bare_known_filenames_are_kept(self):
        body = "\n".join(["**Files:**",
                          "- Modify: `Makefile`",
                          "- Modify: `Dockerfile:3-9`",
                          "- Create: `Gemfile`",
                          "- Test: `tests/test_x.py`", ""])
        self.assertEqual(plan_tool.files_block(body),
                         ["Makefile", "Dockerfile", "Gemfile", "tests/test_x.py"])

    def test_symbol_mentions_are_still_skipped(self):
        body = "**Files:**\n- Modify: `src/a.py` (adds `run_all`)\n"
        self.assertEqual(plan_tool.files_block(body), ["src/a.py"])

    def test_lint_accepts_bare_filename_contract(self):
        body = make_body(["- Modify: `Makefile`", "- Create: `src/app.py`"], ["x = 1"],
                         "git add Makefile src/app.py")
        errs, _ = lint(contract("Makefile", "src/app.py"), body + "\ngit commit -m x\n")
        self.assertFalse([e for e in errs if "missing from the **Files:** list" in e], errs)


class GitAddChainTest(unittest.TestCase):
    def _errs(self, commit_line, files=("src/app.py",)):
        body = make_body(["- Create: `%s`" % f for f in files], ["x = 1"], commit_line)
        errs, _ = lint(contract(*files), body)
        return errs

    def test_split_helper_returns_only_add_arguments(self):
        src = 'cd repo && git add a.py b.py && git commit -m "feat: x"\ngit add c.py; git status || true'
        self.assertEqual(plan_tool.git_add_args(src), ["a.py b.py", "c.py"])

    def test_and_chain_with_commit_is_clean(self):
        self.assertEqual(self._errs('git add src/app.py && git commit -m "feat: add app"'), [])

    def test_semicolon_and_or_chains_are_clean(self):
        self.assertEqual(self._errs("git add src/app.py; git commit -m x || true"), [])

    def test_foreign_path_in_chain_still_flagged(self):
        errs = self._errs("cd repo && git add other.py && git commit -m x")
        self.assertTrue([e for e in errs if "`git add` path `other.py` is not in the contract Files" in e], errs)
        self.assertFalse([e for e in errs if "`commit`" in e or "`&&`" in e], errs)

    def test_add_all_in_chain_still_flagged(self):
        errs = self._errs("git add -A && git commit -m x")
        self.assertTrue([e for e in errs if "stage explicit paths from Files only" in e], errs)


if __name__ == "__main__":
    unittest.main()
