"""Spec 2026-11-05 (flash lanes): the engine-side closers of glm-writing-plans.
No network. call_model is stubbed for the split cases."""
import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_TOOL = os.path.join(HERE, "..", "..", "glm-writing-plans", "scripts", "plan_tool.py")


def _load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_flash_under_test", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan_tool = _load_plan_tool()

SPEC = "\n".join([
    "# Settings loader",
    "",
    "## Background",
    'Context for the loader and "telemetry".',
    "",
    "## Behavior",
    'The loader "must ship" a dict and "must log" every key.',
    "Return value is plain and lock-free.",
    "",
])

PLAN = "\n".join([
    "# Plan",
    "",
    "**Out of scope:** the `telemetry` sender",
    "",
    "## Contracts",
    "",
    "#### T01: settings",
    "- Files: `src/a.py`, `src/b.py`, `src/c.py`, `src/d.py`, `src/e.py`, `tests/test_a.py`",
    "- Produces: `load_settings()`",
    "- Spec: L7-L8",
    "- Tier: light",
    "",
    "<!-- TASKS -->",
    "",
])

SPLIT_REPLY = "\n".join([
    "#### T01: settings part one",
    "- Files: `src/a.py`, `src/b.py`, `src/c.py`, `tests/test_a.py`",
    "- Produces: `load_settings()`",
    "- Spec: L7-L7",
    "- Tier: light",
    "",
    "#### T02: settings part two",
    "- Files: `src/d.py`, `src/e.py`",
    "- Produces: `validate_settings()`",
    "- Spec: L8-L8",
    "- Tier: light",
    "",
])


def _spec_and_cs(tmp, plan_text=PLAN, spec_text=SPEC):
    spec_path = os.path.join(tmp, "spec.md")
    plan_path = os.path.join(tmp, "plan.md")
    with open(spec_path, "w", encoding="utf-8") as fh:
        fh.write(spec_text)
    with open(plan_path, "w", encoding="utf-8") as fh:
        fh.write(plan_text)
    cs, errs = plan_tool.parse_contracts(plan_text)
    assert cs and not errs, errs
    return spec_path, plan_path, cs


FENCE = "`" * 3
AGENT_FILES = ["src/a.py", "src/b.py", "src/c.py", "src/d.py", "src/e.py", "tests/test_a.py"]


def agent_body(asserts):
    """A task body that lints clean against PLAN's T01, with N asserts."""
    code = ["value = %d" % asserts] + ["assert value >= %d" % i for i in range(asserts)]
    rows = (["**Files:**"] + ["- Create: `%s`" % f for f in AGENT_FILES]
            + ["", "- [ ] **Step 1: Write the code**", "", FENCE + "python"]
            + code + [FENCE, "",
                      "**Run:** python3 -m unittest tests.test_a", "",
                      "**Expected:** `load_settings()` returns the dict", "",
                      "- [ ] **Step 2: Commit**", "",
                      FENCE + "bash",
                      "git add " + " ".join(AGENT_FILES),
                      'git commit -m "feat: settings"', FENCE, ""])
    return "\n".join(rows)


class HeadingErrTests(unittest.TestCase):
    def test_uncovered_behavior_is_err_and_background_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = os.path.join(tmp, "spec.md")
            with open(spec_path, "w", encoding="utf-8") as fh:
                fh.write(SPEC)
            covered, errs = plan_tool.parse_contracts(PLAN)
            self.assertFalse(errs, errs)
            errs, _ = plan_tool.analyze(covered, spec_path, None)
            self.assertFalse([e for e in errs if "uncovered" in e], errs)   # Behavior covered, Background ignored
            narrow = PLAN.replace("- Spec: L7-L8", "- Spec: L4-L4")
            cs2, _ = plan_tool.parse_contracts(narrow)
            errs2, _ = plan_tool.analyze(cs2, spec_path, None)
            self.assertTrue(any("uncovered" in e and "Behavior" in e for e in errs2), errs2)
            self.assertFalse(any("Background" in e for e in errs2), errs2)


class AtomHomeTests(unittest.TestCase):
    def test_two_spec_ranges_fail_and_out_of_scope_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path, plan_path, cs = _spec_and_cs(tmp)
            fails = plan_tool.atom_errs(cs, spec_path, plan_tool.load(plan_path))
            self.assertEqual(fails, [], fails)   # one home each: L7-L8 + the out-of-scope line
            twice = PLAN.replace("- Spec: L7-L8", "- Spec: L7-L7").replace(
                "<!-- TASKS -->",
                "#### T02: second\n- Files: `src/z.py`\n- Spec: L7-L7\n\n<!-- TASKS -->")
            cs2, perrs = plan_tool.parse_contracts(twice)
            self.assertEqual(len(cs2), 2, perrs)
            fails2 = plan_tool.atom_errs(cs2, spec_path, twice)
            self.assertTrue(any("2 homes" in f and "must ship" in f for f in fails2), fails2)


class ExistingSymbolTests(unittest.TestCase):
    def test_missing_read_or_missing_name_is_err(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "src"))
            with open(os.path.join(tmp, "src", "a.py"), "w", encoding="utf-8") as fh:
                fh.write("def other():\n    return 1\n")
            base = {"id": "T01"}
            errs = plan_tool.external_symbol_errs(
                [dict(base, external=["load_config"], reads=[])], tmp)
            self.assertEqual(errs, ["T01: existing symbol load_config is not in a Read file"], errs)
            errs2 = plan_tool.external_symbol_errs(
                [dict(base, external=["load_config"], reads=["src/a.py"])], tmp)
            self.assertEqual(errs2, ["T01: existing symbol load_config is not in a Read file"], errs2)
            errs3 = plan_tool.external_symbol_errs(
                [dict(base, external=["other"], reads=["src/a.py"])], tmp)
            self.assertEqual(errs3, [], errs3)


class TierRaiseTests(unittest.TestCase):
    def test_lock_raises_light_and_deep_stays_deep(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path, _, _ = _spec_and_cs(tmp)
            light = {"id": "T01", "spec": [(8, 8)], "tier": "light"}
            notes = plan_tool.raise_tiers([light], spec_path)
            self.assertEqual(light["tier"], "deep")
            self.assertEqual(notes, ["TIER T01 light -> deep (lock)"], notes)
            deep = {"id": "T02", "spec": [(8, 8)], "tier": "deep"}
            notes2 = plan_tool.raise_tiers([deep], spec_path)
            self.assertEqual(deep["tier"], "deep")
            self.assertEqual(notes2, [], notes2)


class RewriteKeptTests(unittest.TestCase):
    BODY = 'assert parse("must ship") == 1\nassert ready()'

    def test_rewrite_dropping_an_assert_or_an_atom_is_discarded(self):
        self.assertFalse(plan_tool.rewrite_ok(self.BODY, "assert parse('must ship') == 1"))
        self.assertFalse(plan_tool.rewrite_ok(self.BODY, "assert parse('other') == 1\nassert ready()"))
        self.assertTrue(plan_tool.rewrite_ok(self.BODY,
                                             'assert parse("must ship") == 1\nassert ready()\nassert more()'))


class AgentLaneAssertsTests(unittest.TestCase):
    """Spec step 6 (agent lane): the first clean lint arms tasks/<id>.md.asserts,
    and a later lower count is an ERR from lint_body, like a missing Expected."""

    def test_the_agent_lane_guards_an_assertion_drop(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, plan_path, _ = _spec_and_cs(tmp)
            task = os.path.join(tmp, "T01.md")
            with open(task, "w", encoding="utf-8") as fh:
                fh.write(agent_body(3))
            e, w, _ = plan_tool.lint_file(plan_path, task)
            self.assertEqual(e, [], e)
            plan_tool.apply_marks(task, "ok", e, w)
            with open(task + ".asserts", encoding="utf-8") as fh:
                self.assertEqual(fh.read().strip(), "3")
            with open(task, "w", encoding="utf-8") as fh:
                fh.write(agent_body(1))
            e2, _, _ = plan_tool.lint_file(plan_path, task)
            self.assertTrue(any("assertion count dropped from 3" in x for x in e2), e2)

    def test_an_equal_or_higher_count_is_not_an_err(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, plan_path, _ = _spec_and_cs(tmp)
            task = os.path.join(tmp, "T01.md")
            for n in (3, 3, 5):
                with open(task, "w", encoding="utf-8") as fh:
                    fh.write(agent_body(n))
                if not os.path.exists(task + ".asserts"):
                    e, w, _ = plan_tool.lint_file(plan_path, task)
                    self.assertEqual(e, [], e)
                    plan_tool.apply_marks(task, "ok", e, w)
                e, _, _ = plan_tool.lint_file(plan_path, task)
                self.assertFalse([x for x in e if "dropped" in x], (n, e))


class SplitWideTests(unittest.TestCase):
    def _run(self, reply):
        with tempfile.TemporaryDirectory() as tmp:
            spec_path, plan_path, cs = _spec_and_cs(tmp)
            plan_text = plan_tool.load(plan_path)
            calls = []

            def fake_call_model(cfg, blocks, user, tier, budget, **kw):
                calls.append(tier)
                return reply, ""

            orig = plan_tool.call_model
            plan_tool.call_model = fake_call_model
            try:
                new_cs, new_plan, notes = plan_tool.split_wide({}, plan_text, cs, spec_path, None)
            finally:
                plan_tool.call_model = orig
            return new_cs, new_plan, notes, calls, plan_text

    def test_overlapping_files_are_rejected(self):
        overlap = SPLIT_REPLY.replace("- Files: `src/d.py`, `src/e.py`",
                                      "- Files: `src/c.py`, `src/e.py`")
        new_cs, new_plan, notes, calls, plan_text = self._run(overlap)
        self.assertEqual(notes, ["SPLIT T01 rejected"], notes)
        self.assertEqual(new_plan, plan_text)
        self.assertEqual(len(new_cs), 1)

    def test_partition_replaces_the_contract(self):
        new_cs, new_plan, notes, calls, plan_text = self._run(SPLIT_REPLY)
        self.assertEqual(notes, ["SPLIT T01 -> T01 T02"], notes)
        self.assertEqual([c["id"] for c in new_cs], ["T01", "T02"])
        self.assertEqual(calls, ["std"])
        reparsed, errs = plan_tool.parse_contracts(new_plan)
        self.assertEqual([c["id"] for c in reparsed], ["T01", "T02"])
        self.assertEqual(sorted(f for c in reparsed for f in c["files"]),
                         sorted(["src/a.py", "src/b.py", "src/c.py", "src/d.py", "src/e.py",
                                 "tests/test_a.py"]))
        self.assertNotEqual(new_plan, plan_text)


class PinsTests(unittest.TestCase):
    def test_deep_tier_is_flash(self):
        self.assertEqual(plan_tool.GLM["deep"][0], "glm-5.3-flash")
        self.assertEqual(plan_tool.GLM["deep"][1], "max")
        self.assertEqual(plan_tool.GLM["light"][1], "high")


if __name__ == "__main__":
    unittest.main()
