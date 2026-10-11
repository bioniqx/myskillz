# glm-skills Speed and Parallelism Implementation Plan

> **Execution note:** This plan is self-contained and tool-agnostic. Any AI
> agent or human engineer can execute it with only a shell, a code editor, and
> git. Follow the Execution Protocol below.

**Goal:** Remove the seven verified serial bottlenecks in the glm-skills engines so each workflow's wall-clock drops, with every existing quality gate intact.

**Architecture:** Six surgical edits inside existing concurrency machinery (audit.py wave pipelining, two plan_tool.py phase overlaps, context.sh and gather.sh shell concurrency, devteam.py pre-check overlap) plus one guidance edit (glm-idea-to-spec/SKILL.md). No CLI shape, on-disk format, or public behavior contract changes; all fan-out stays inside the existing pools with the same 8-call cap.

**Tech Stack:** stdlib Python 3 (concurrent.futures.ThreadPoolExecutor), POSIX sh, unittest.

## Execution Protocol (for any AI agent or human engineer)

1. A task may start only when every task in its **Depends** and **Runs after**
   lists is complete. Single worker: run tasks in ID order.
2. Parallel workers: follow **Execution Waves**. Tasks in the same wave touch
   disjoint files and MAY run concurrently (marked `[P]`). Never run two tasks
   that modify the same file at once.
3. Within a task, execute steps top to bottom and mark each checkbox `- [x]`
   when done. To resume, continue from the first unchecked step.
4. Run every command exactly as written and compare with **Expected**. On
   mismatch, stop and fix before continuing.
5. Code blocks are the implementation - copy them verbatim. Signatures under
   **Interfaces** are contracts with other tasks: never rename, reorder
   parameters, or change types.
6. Commit exactly where the plan says, with the given message, staging only the
   listed paths. Never batch commits across tasks.
7. **Global Constraints** apply to every task.
8. If anything is ambiguous, missing, or contradicts the codebase, STOP and ask
   the requester. Do not invent behavior.

## Global Constraints

- stdlib-only Python 3 + POSIX sh; no new dependencies, no package managers.
- Touch ONLY paths under glm-skills/; never ../claude-skills/, ../hybrid-skills/, ../opencode-skills/.
- Work on main; never create branches.
- Concurrency cap stays 8 in every engine (MAX_PARALLEL=8, MAX_WORKERS=8); never more than 8 in-flight API calls.
- audit.py keeps both prefix warm-ups: judge prefix before the first judge job, verify prefix before the first verify submission; shared prompt blocks stay byte-identical.
- plan_tool.py Budget abort-gate semantics unchanged: a tripped budget stops new write AND review submissions; exit codes unchanged.
- devteam.py: every state mutation stays inside save_state/state_lock; merge order, conflict reporting and the next wake-up chain unchanged.
- Shell scripts stay read-only and ALWAYS exit 0: guard every backgrounded git with `|| true`; `wait` must not propagate a non-zero status into the script exit.
- debug_tool.py, bisect-parallel.sh, stress.sh, find-polluter.sh are out of scope: their serialization is load-bearing.
- Audit citation checker, deterministic retrieval and writes-only-under-.audit/ are untouched.
- Byte-identical outputs where the spec demands them: plan_tool.py brief output, context.sh stdout block, gather.sh output on this repo.
- Full test suite, run from glm-skills/: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests
- Engine self-test: bash glm-dev-team/scripts/selftest.sh — pass criterion is the recorded baseline set (323 pass, 6 pre-existing Claude-lane failures, same six).
- Files in English; plain ASCII (no emoji, arrows or decorative glyphs) outside .md files; .md files exempt.
- Bookkeeping per spec L122-128: version bumps and CHANGELOG entries only where the folder keeps one (writing-plans CHANGELOG, brainstorming CHANGELOG for context.sh); idea-to-spec and git-diff-summary keep no changelog.

## References

- `glm-skills/_shared/tests/test_adopt_plan.py` - the suite's test idiom: load a script with importlib.util.spec_from_file_location, drive it against temp dirs and http.server fake endpoints; every new test file follows this style.

## File Structure

- `glm-skills/glm-requirements-code-audit/scripts/` — audit.py (T01)
- `glm-skills/_shared/tests/` — test_audit_pipeline.py (T01), test_plan_brief_parallel.py (T02), test_plan_review_overlap.py (T03), test_idea_to_spec_guidance.py (T04), test_context_sh.py (T05), test_gather_micro.py (T06), test_devteam_precheck.py (T07)
- `glm-skills/glm-writing-plans/scripts/` — plan_tool.py (T02, T03)
- `glm-skills/glm-writing-plans/` — CHANGELOG.md (T02, T03)
- `glm-skills/glm-idea-to-spec/` — SKILL.md (T04)
- `glm-skills/glm-brainstorming/scripts/` — context.sh (T05)
- `glm-skills/glm-brainstorming/` — CHANGELOG.md (T05)
- `glm-skills/glm-git-diff-summary/scripts/` — gather.sh (T06)
- `glm-skills/glm-dev-team/scripts/` — devteam.py (T07)

## Contracts

#### T01: audit.py — pipeline verify behind judge
- Files: `glm-skills/glm-requirements-code-audit/scripts/audit.py`, `glm-skills/_shared/tests/test_audit_pipeline.py`
- Produces: `Fan.submit(fn, *args)`; `def run_judge_verify_pipeline(items, judge_fn, verify_fn, should_verify, fan, warm_judge=None, warm_verify=None) -> (list, list)`; reworked `cmd_run` wave submission: one completion-aware pool, verify jobs enqueued the moment their item's judge result lands
- Consumes: `Fan` (existing), `judge_one` (existing), `verify_one` (existing), `needs_verify(it, f)` (existing), `verify_targets` (existing, unchanged), `warm_call` (existing)
- Read: `glm-skills/glm-requirements-code-audit/scripts/audit.py`
- Spec: L21-41, L47-60
- Tier: deep

#### T02: plan_tool.py — parallelize cmd_brief recon
- Files: `glm-skills/glm-writing-plans/scripts/plan_tool.py`, `glm-skills/glm-writing-plans/CHANGELOG.md`, `glm-skills/_shared/tests/test_plan_brief_parallel.py`
- Produces: `def run_recon(steps) -> dict` (step name to result; steps executed via `pmap`, merged in the original deterministic order); reworked `cmd_brief` body using it, output byte-identical
- Consumes: `pmap` (existing), `workers_cap()` (existing)
- Read: `glm-skills/glm-writing-plans/scripts/plan_tool.py`
- Spec: L21-41, L61-66
- Tier: std

#### T03: plan_tool.py — overlap review with writes in cmd_build
- Depends: T02
- Files: `glm-skills/glm-writing-plans/scripts/plan_tool.py`, `glm-skills/glm-writing-plans/CHANGELOG.md`, `glm-skills/_shared/tests/test_plan_review_overlap.py`
- Produces: reworked `cmd_build`: `review_one` submitted as each writer finishes (`.ok` mark), through the same wave; `Budget.blown()` additionally gates review submission; failed writes keep today's failure path and skip their review
- Consumes: `review_one` (existing), `Budget` (existing), `call_model` (existing), `lint_one` (existing)
- Read: `glm-skills/glm-writing-plans/scripts/plan_tool.py`
- Spec: L21-41, L67-72
- Tier: deep

#### T04: idea-to-spec guidance — collapse interview when the brief is detailed
- Files: `glm-skills/glm-idea-to-spec/SKILL.md`, `glm-skills/_shared/tests/test_idea_to_spec_guidance.py`
- Produces: SKILL.md rule blocks: (a) when the initial brief already answers the Phase 0-2 questions (target users, goal, success criteria), remaining questions collapse into ONE batched question round; (b) research query variants are batched in one message even without a Task tool. Verdict-before-spec order and Fast mode unchanged; frontmatter `name` unchanged and `description` stays under 1024 characters.
- Read: `glm-skills/glm-idea-to-spec/SKILL.md`
- Spec: L21-41, L73-79
- Tier: std

#### T05: context.sh — dedupe ls-files and background the hot-dir log
- Files: `glm-skills/glm-brainstorming/scripts/context.sh`, `glm-skills/glm-brainstorming/CHANGELOG.md`, `glm-skills/_shared/tests/test_context_sh.py`
- Produces: reworked git block: `git ls-files` output captured once and reused for the count, `files:` line and `tree:` aggregation; hot-dir `git log` runs backgrounded into a temp file (`|| true`) while the rest of the git block executes, joined before emit; stdout block identical in content and order; script ALWAYS exits 0
- Read: `glm-skills/glm-brainstorming/scripts/context.sh`
- Spec: L21-41, L80-86
- Tier: std

#### T06: gather.sh — batch base probing and single-pass chunking
- Files: `glm-skills/glm-git-diff-summary/scripts/gather.sh`, `glm-skills/_shared/tests/test_gather_micro.py`
- Produces: base-branch resolution via one batched refs query (`git for-each-ref` / `rev-parse --verify` over candidates) replacing the serial probe loop; chunk boundaries computed once per pass instead of re-running awk per iteration; output byte-identical on this repo
- Read: `glm-skills/glm-git-diff-summary/scripts/gather.sh`
- Spec: L21-41, L87-92
- Tier: std

#### T07: devteam.py — overlap read-only pre-checks ahead of the serial merge loop
- Files: `glm-skills/glm-dev-team/scripts/devteam.py`, `glm-skills/_shared/tests/test_devteam_precheck.py`
- Produces: `def precheck_one(c, sl) -> dict` (read-only per-slice checks: dirty status, log scans, footprint diffs); `def precheck_all(c, slices) -> list`; `integrate_one` gains a trailing `pc` parameter; reworked `do_integrate`: prechecks run through a small ThreadPoolExecutor (never more than 8 threads) BEFORE the serial integration loop; merge order and all state mutations unchanged
- Consumes: `state_lock` (existing), `save_state` (existing), `merge_slice` (existing), `do_integrate` (existing), `integrate_one` (existing)
- Read: `glm-skills/glm-dev-team/scripts/devteam.py`
- Spec: L21-41, L93-98
- Tier: deep

<!-- WAVES -->
## Execution Waves

Every task in a wave has all its Depends/Runs-after tasks in earlier waves. Tasks in the
same wave touch disjoint files, so a wave's `[P]` tasks may all run at once.

- **Wave 1:** T01 [P], T02 [P], T04 [P], T05 [P], T06 [P], T07 [P]
- **Wave 2:** T03
<!-- /WAVES -->

<!-- TASKS -->

### T01: audit.py — pipeline verify behind judge [P]

**Depends:** —

**Interfaces:**
- Uses existing: `Fan`; `judge_one`; `verify_one`; `needs_verify(it, f)`; `verify_targets`; `warm_call`
- Produces: `Fan.submit(fn, *args)`; `def run_judge_verify_pipeline(items, judge_fn, verify_fn, should_verify, fan, warm_judge=None, warm_verify=None) -> (list, list)`; `cmd_run`

**Files:**
- Modify: `glm-skills/glm-requirements-code-audit/scripts/audit.py`
- Test: `glm-skills/_shared/tests/test_audit_pipeline.py`

- [ ] **Step 1: Write the failing pipeline tests**

audit.py currently runs two hard-ordered waves inside cmd_run: every judge job is submitted and joined before the first verify job goes out, although each verify job needs only its own item's finding. The per-item decision already exists as the two-argument `needs_verify(it, f)` (audit.py:1597), which `verify_targets` delegates to - this task reuses it as-is and adds nothing around it. This task replaces the two-wave block with one completion-aware pool that submits a verify job the moment its item's judge result lands. All shell commands in the steps below run from the `glm-skills/` directory.

Create `glm-skills/_shared/tests/test_audit_pipeline.py`:

```python
import concurrent.futures
import importlib.util
import os
import threading
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(HERE, "..", "..", "glm-requirements-code-audit", "scripts", "audit.py")


def _load_audit():
    spec = importlib.util.spec_from_file_location("audit_under_test", AUDIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


audit = _load_audit()


class RecordingFan:
    """Fan stand-in for tests: real worker threads plus an ordered submit log."""

    def __init__(self, workers=8):
        self.log = []
        self.lock = threading.Lock()
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=workers)

    def submit(self, fn, *args):
        with self.lock:
            self.log.append((fn.__name__,) + args)
        return self.pool.submit(fn, *args)

    def shutdown(self):
        self.pool.shutdown(wait=True)


class PipelineTests(unittest.TestCase):
    @staticmethod
    def _pipeline(items, fan, should_verify, judge_fn=None, verify_fn=None,
                  warm_judge=None, warm_verify=None):
        return audit.run_judge_verify_pipeline(
            items, judge_fn or (lambda it: ({"id": it}, None)),
            verify_fn or (lambda it, row: ({"verdict_for": it}, None)),
            should_verify, fan, warm_judge=warm_judge, warm_verify=warm_verify)

    def test_verify_is_submitted_while_the_judge_tail_is_still_running(self):
        judge_a_may_finish = threading.Event()
        observed = {"verify_ran_while_a_blocked": False, "a_judge_timed_out": False}

        def judge_fn(item):
            if item != "a":
                return ({"id": item}, None)
            if not judge_a_may_finish.wait(timeout=5):
                observed["a_judge_timed_out"] = True
            return ({"id": item}, None)

        def verify_fn(item, row):
            if item == "b":
                observed["verify_ran_while_a_blocked"] = not judge_a_may_finish.is_set()
                judge_a_may_finish.set()
            return ({"verdict_for": item}, None)

        fan = RecordingFan()
        findings, verdicts = self._pipeline(
            ["a", "b", "c"], fan, lambda it, row: True,
            judge_fn=judge_fn, verify_fn=verify_fn)
        fan.shutdown()

        self.assertFalse(observed["a_judge_timed_out"])
        self.assertTrue(observed["verify_ran_while_a_blocked"])
        self.assertEqual([entry[0] for entry in fan.log[:3]],
                         ["judge_fn", "judge_fn", "judge_fn"])
        self.assertEqual([f[0]["id"] for f in findings], ["a", "b", "c"])
        self.assertEqual([v[0]["verdict_for"] for v in verdicts],
                         ["a", "b", "c"])

    def test_items_where_should_verify_is_false_produce_no_verify_jobs(self):
        def verify_fn(item, row):
            raise AssertionError("no verify job may run when should_verify is False")

        fan = RecordingFan()
        findings, verdicts = self._pipeline(["a", "b"], fan, lambda it, row: False,
                                            verify_fn=verify_fn)
        fan.shutdown()

        self.assertEqual([f[0]["id"] for f in findings], ["a", "b"])
        self.assertEqual(verdicts, [None, None])
        self.assertTrue(all(entry[0] == "judge_fn" for entry in fan.log))

    def test_warm_ups_fire_once_before_their_first_submission(self):
        order = []

        def judge_fn(item):
            order.append(("judge", item))
            return ({"id": item}, None)

        def verify_fn(item, row):
            order.append(("verify", item))
            return ({"verdict_for": item}, None)

        fan = RecordingFan()
        self._pipeline(["a", "b"], fan, lambda it, row: True,
                       judge_fn=judge_fn, verify_fn=verify_fn,
                       warm_judge=lambda: order.append("warm_judge"),
                       warm_verify=lambda: order.append("warm_verify"))
        fan.shutdown()

        self.assertEqual(order[0], "warm_judge")
        verify_positions = [i for i, entry in enumerate(order)
                            if isinstance(entry, tuple) and entry[0] == "verify"]
        self.assertTrue(verify_positions)
        self.assertLess(order.index("warm_verify"), min(verify_positions))
        self.assertEqual(order.count("warm_judge"), 1)
        self.assertEqual(order.count("warm_verify"), 1)

    def test_shared_pool_never_exceeds_eight_in_flight_jobs(self):
        live = [0]
        peak = [0]
        lock = threading.Lock()

        def judge_fn(item):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.005)
            with lock:
                live[0] -= 1
            return ({"id": item}, None)

        def verify_fn(item, row):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.005)
            with lock:
                live[0] -= 1
            return ({"verdict_for": item}, None)

        fan = RecordingFan(workers=8)
        self._pipeline(list(range(40)), fan, lambda it, row: True,
                       judge_fn=judge_fn, verify_fn=verify_fn)
        fan.shutdown()

        self.assertLessEqual(peak[0], 8)

    def test_api_errors_travel_as_error_rows_not_exceptions(self):
        def judge_fn(item):
            if item == "b":
                return (None, "api error: 429")
            return ({"id": item}, None)

        def verify_fn(item, row):
            raise AssertionError("an error row must not be verified")

        fan = RecordingFan()
        findings, verdicts = self._pipeline(
            ["a", "b"], fan, lambda it, row: True,
            judge_fn=judge_fn, verify_fn=verify_fn)
        fan.shutdown()

        self.assertEqual(findings[0], ({"id": "a"}, None))
        self.assertEqual(findings[1], (None, "api error: 429"))
        self.assertEqual([v[0]["verdict_for"] for v in verdicts[:1]], ["a"])
        self.assertIsNone(verdicts[1])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_audit_pipeline.py -v`
Expected: FAILED (errors=5): all five PipelineTests error with "AttributeError: module 'audit_under_test' has no attribute 'run_judge_verify_pipeline'".

- [ ] **Step 3: Add Fan.submit and run_judge_verify_pipeline**

In `glm-skills/glm-requirements-code-audit/scripts/audit.py`:

1. Extend the concurrent.futures import so the module also receives FIRST_COMPLETED and wait, keeping every name it already imports. If audit.py imports the module instead of names, call them as concurrent.futures.wait and concurrent.futures.FIRST_COMPLETED in the function below.
2. Add a `submit` method to the existing `Fan` class, next to `run()`:

```python fragment
    def submit(self, fn, *args):
        """Submit fn(*args) on Fan's executor: Fan.submit(fn, *args) -> future."""
```

It submits fn(*args) on the executor Fan already holds, updates the same peak/progress bookkeeping its run() path uses, and returns the future. `run()` itself does not change; Fan's constructor, its MAX_PARALLEL=8 width clamping and its error collection stay exactly as they are.
3. Directly above cmd_run, add:

```python
def run_judge_verify_pipeline(items, judge_fn, verify_fn, should_verify, fan, warm_judge=None, warm_verify=None) -> (list, list):
    """One completion-aware pool pass over items.

    Submits every judge job to the shared pool, then submits each item's
    verify job the moment its judge result lands, so verify work fills
    judge-tail slots. judge_fn and verify_fn return (value, err) tuples,
    the convention the two waves use today; an error row is never verified.
    Returns (findings, verdicts): two lists aligned with items; verdicts
    holds None where no verify job ran. In-flight work is bounded by the
    pool's own width; nothing here touches the disk or the client stats.
    """
    pending = {}
    findings = {}
    verdicts = {}
    if items and warm_judge is not None:
        warm_judge()
    for i, it in enumerate(items):
        pending[fan.submit(judge_fn, it)] = (i, "judge")
    verify_warmed = warm_verify is None
    while pending:
        done, _ = wait(set(pending), return_when=FIRST_COMPLETED)
        for fut in done:
            i, phase = pending.pop(fut)
            value, err = fut.result()
            if phase == "judge":
                findings[i] = (value, err)
                if err is not None or not should_verify(items[i], value):
                    continue
                if not verify_warmed:
                    verify_warmed = True
                    warm_verify()
                pending[fan.submit(verify_fn, items[i], value)] = (i, "verify")
            else:
                verdicts[i] = (value, err)
    return ([findings.get(i) for i in range(len(items))],
            [verdicts.get(i) for i in range(len(items))])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_audit_pipeline.py -v`
Expected: OK — Ran 5 tests with OK

- [ ] **Step 5: Rewire cmd_run onto the pipeline**

Inside cmd_run in `glm-skills/glm-requirements-code-audit/scripts/audit.py`, find the two-wave submission block (it sits near lines 2145-2244: it submits every judge job through one Fan, joins them all, then submits every verify job through a second Fan). Delete both wave submissions and the second Fan, and replace them with a single call:

```python fragment
    findings, verdicts = run_judge_verify_pipeline(
        live, judge_fn, verify_fn, should_verify, fan,
        warm_judge=warm_judge, warm_verify=warm_verify)
```

Wire the names like this:

- items: the same ordered `live` list the judge wave iterates today, with settled-item resume skipping exactly as today, so an interrupted run still resumes without redoing settled items.
- judge_fn and verify_fn: closures defined in cmd_run that forward to the existing judge_one and verify_one with exactly the arguments the two waves pass today; read those arguments from the block before deleting it. Do not modify judge_one, verify_one, needs_verify, verify_targets, or any shared prompt text.
- should_verify: `lambda it, row: (not a.no_verify) and it["id"] not in prev_ver and needs_verify(it, row)` where prev_ver is the settled-verdict mapping cmd_run already reads on resume. This preserves the resume semantics: settled verdicts are never re-verified (today verify_targets returns them as `kept`); verify_targets itself stays in the file unchanged, still covered by its own tests.
- fan: ONE Fan at the existing width (MAX_PARALLEL, 8). The verify wave's separate Fan is deleted; verify jobs now fill judge-tail slots in the same pool, so total in-flight work never exceeds 8.
- warm_judge and warm_verify: closures around the two existing warm_call prefix blocks, byte-identical prompt text. Pass warm_judge only when the judge wave meets the same total-jobs >= 6 threshold Fan.run applies today, and warm_verify only when len(live) >= 6 - the no-warm-up-on-tiny-runs intent is preserved, evaluated on the live count because the verify count is no longer known upfront.
- After the call, findings arrive as (row, err) pairs: apply today's error conversion verbatim (an err row becomes the UNSEARCHED row exactly as the wave-A result loop does now), then write findings.jsonl in requirement order as today. Verdicts: start from the kept verdicts exactly as today's `verdicts = dict(kept)` line does, overlay every non-None pipeline verdict, and write verdicts.jsonl as today. Keep the --no-verify skip notice.
- The WAVE A / WAVE B progress banners become ONE banner printed before the call (live count, thread count, judge and verify model config). The RUN DONE line and state["run"] keep today's field names and meanings (wave_a = len(live), wave_b = number of verdicts written, peak_threads from the single fan).
- Do not touch the citation checker, the deterministic retrieval, or the write paths under the .audit directory.

- [ ] **Step 6: Re-run the pipeline tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_audit_pipeline.py -v`
Expected: OK — Ran 5 tests with OK

- [ ] **Step 7: Run the full suite and the engine self-test**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: OK — zero failures and zero errors across the whole suite.

Run: `bash glm-dev-team/scripts/selftest.sh`
Expected: the recorded baseline set: 323 pass and the same 6 pre-existing lane failures as before this task; no new failures and none missing.

- [ ] **Step 8: Commit**

From the repository root, on main:

```bash
git add glm-skills/glm-requirements-code-audit/scripts/audit.py glm-skills/_shared/tests/test_audit_pipeline.py
git commit -m "perf: pipeline audit verify jobs behind judge results"
```

---

### T02: plan_tool.py — parallelize cmd_brief recon [P]

**Depends:** —

**Interfaces:**
- Uses existing: `pmap`; `workers_cap()`
- Produces: `def run_recon(steps) -> dict`; `pmap`; `cmd_brief`

**Files:**
- Modify: `glm-skills/glm-writing-plans/scripts/plan_tool.py`
- Modify: `glm-skills/glm-writing-plans/CHANGELOG.md`
- Test: `glm-skills/_shared/tests/test_plan_brief_parallel.py`

- [ ] **Step 1: Write the failing tests for run_recon**

Create `glm-skills/_shared/tests/test_plan_brief_parallel.py` following the suite's loader idiom:

```python
import importlib.util
import inspect
import os
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_TOOL = os.path.join(HERE, "..", "..", "glm-writing-plans", "scripts", "plan_tool.py")


def _load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_brief_under_test", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan_tool = _load_plan_tool()


class RunReconContractTests(unittest.TestCase):
    def test_run_recon_maps_step_names_to_results_in_original_order(self):
        steps = [
            ("git", lambda: "log-output"),
            ("status", lambda: "status-output"),
            ("spec", lambda: "spec-body"),
        ]
        result = plan_tool.run_recon(steps)
        self.assertIsInstance(result, dict)
        self.assertEqual(result, {"git": "log-output", "status": "status-output", "spec": "spec-body"})
        self.assertEqual(list(result), ["git", "status", "spec"])

    def test_run_recon_signature_is_exact(self):
        with open(PLAN_TOOL, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("def run_recon(steps) -> dict:", text)


class RunReconConcurrencyTests(unittest.TestCase):
    def test_run_recon_runs_steps_concurrently(self):
        barrier = threading.Barrier(3, timeout=10)

        def waiter(value):
            barrier.wait()
            return value

        steps = [
            ("one", lambda: waiter(1)),
            ("two", lambda: waiter(2)),
            ("three", lambda: waiter(3)),
        ]
        result = plan_tool.run_recon(steps)
        self.assertEqual(result, {"one": 1, "two": 2, "three": 3})

    def test_run_recon_never_exceeds_eight_in_flight(self):
        live, peak, lock = [0], [0], threading.Lock()

        def probe():
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.02)
            with lock:
                live[0] -= 1
            return True

        steps = [("step%02d" % i, probe) for i in range(24)]
        result = plan_tool.run_recon(steps)
        self.assertEqual(len(result), 24)
        self.assertLessEqual(peak[0], 8)


class CmdBriefWiringTests(unittest.TestCase):
    def test_cmd_brief_calls_run_recon(self):
        source = inspect.getsource(plan_tool.cmd_brief)
        self.assertIn("run_recon(", source)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new test file to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_plan_brief_parallel.py -v` (from `glm-skills/`)

Expected: FAIL with `AttributeError: module 'plan_tool_brief_under_test' has no attribute 'run_recon'` on the four RunRecon tests; CmdBriefWiringTests also fails because `run_recon(` does not appear in the `cmd_brief` source yet.

- [ ] **Step 3: Add run_recon to plan_tool.py**

In `glm-skills/glm-writing-plans/scripts/plan_tool.py`, locate the existing `workers_cap` definition (`pmap` lives in the same concurrency section) and insert directly after it:

```python
def run_recon(steps) -> dict:
    """Run read-only recon steps concurrently; return name -> result in input order."""
    if not steps:
        return {}
    done = pmap(lambda pair: (pair[0], pair[1]()), list(enumerate(steps)), workers_cap())
    return {steps[i][0]: value for i, value in sorted(done)}
```

Each step's index travels with it, so the merge is deterministic regardless of completion order; `workers_cap()` keeps the fan-out inside the shared 8-call cap.

- [ ] **Step 4: Run the test file to verify the run_recon tests pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_plan_brief_parallel.py -v` (from `glm-skills/`)

Expected: the four RunRecon tests PASS; CmdBriefWiringTests still FAILS with an `AssertionError` because `cmd_brief` is not reworked until Step 5.

- [ ] **Step 5: Rework cmd_brief to route recon through run_recon**

In `glm-skills/glm-writing-plans/scripts/plan_tool.py`:

1. Locate `def cmd_brief(`. Its recon section is the serial read-only run around lines 1617-1712 today: the git log / ls-files / status probes, the conventions reads, the inline pattern-file reads, the spec read, and the `pick_patterns` result.
2. Turn each independent read into a zero-argument function with its exact existing body - same commands, same parsing, same local variables.
3. Collect them as a `[(name, function), ...]` list and replace the serial calls with one call: `recon = run_recon(steps)`.
4. At each later use site read the value back as `recon["<name>"]`. Keep every consumer reading in the same order as before and keep every rendered string, sort and join unchanged, so the printed brief stays byte-identical.
5. In `pick_patterns` (the per-candidate file-read loop around lines 1589-1595), replace the serial candidate reads with one `pmap` fan-out capped at `workers_cap()`, preserving the candidate order and the ranking output exactly.
6. Recon steps are read-only: no disk writes, no shared-state mutation, no model calls. Do not touch the Budget gate or the output rendering.

- [ ] **Step 6: Run the new test file to verify all tests pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_plan_brief_parallel.py -v` (from `glm-skills/`)

Expected: PASS - `Ran 5 tests` and `OK`.

- [ ] **Step 7: Run the full suite to verify the brief output is unchanged**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests` (from `glm-skills/`)

Expected: OK - the full suite passes, including the existing tests that pin the `brief` output on their fixtures.

- [ ] **Step 8: Record the change in the CHANGELOG**

In `glm-skills/glm-writing-plans/CHANGELOG.md`, insert directly after the paragraph beginning `**thoughtLevel (2026-10-08):**` and before the `Target:` line:

```text fragment
**Parallel recon (2026-10-10):** `brief` runs its read-only recon steps (git log / ls-files / status, conventions reads, inline pattern-file reads, spec read, `pick_patterns` candidate reads) through the shared `pmap` pool via a new `run_recon` helper; the cap stays 8 and the printed output is byte-identical.
```

- [ ] **Step 9: Commit**

```bash
git add glm-skills/glm-writing-plans/scripts/plan_tool.py glm-skills/glm-writing-plans/CHANGELOG.md glm-skills/_shared/tests/test_plan_brief_parallel.py
git commit -m "perf: parallelize plan_tool brief recon through run_recon"
```

---

### T03: plan_tool.py — overlap review with writes in cmd_build

**Depends:** T02

**Interfaces:**
- Uses existing: `review_one`; `Budget`; `call_model`; `lint_one`
- Produces: `cmd_build`; `review_one`; `.ok`; `Budget.blown()`

**Files:**
- Modify: `glm-skills/glm-writing-plans/scripts/plan_tool.py`
- Modify: `glm-skills/glm-writing-plans/CHANGELOG.md:13-15`
- Test: `glm-skills/_shared/tests/test_plan_review_overlap.py`

- [ ] **Step 1: Write the failing tests for the overlapped review**

Create `glm-skills/_shared/tests/test_plan_review_overlap.py`:

```python
import importlib.util
import inspect
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_TOOL = os.path.join(HERE, "..", "..", "glm-writing-plans", "scripts", "plan_tool.py")


def _load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_review_overlap", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan_tool = _load_plan_tool()


def _cmd_build_source():
    return inspect.getsource(plan_tool.cmd_build)


class ReviewBudgetGateTests(unittest.TestCase):
    """The shared Budget and the no-review flag gate every overlapped submission."""

    def test_every_review_submission_sits_behind_the_budget_gate(self):
        src = _cmd_build_source()
        sites = list(re.finditer(r"review_one\(", src))
        self.assertTrue(sites, "cmd_build submits no review at all")
        for m in sites:
            window = src[max(0, m.start() - 300):m.start()]
            self.assertIn(
                "budget.blown()",
                window,
                "review_one call at offset %d is not gated by Budget.blown()" % m.start(),
            )

    def test_every_review_submission_honors_no_review(self):
        src = _cmd_build_source()
        sites = list(re.finditer(r"review_one\(", src))
        self.assertTrue(sites, "cmd_build submits no review at all")
        for m in sites:
            window = src[max(0, m.start() - 300):m.start()]
            self.assertIn(
                "no_review",
                window,
                "review_one call at offset %d ignores the no-review flag" % m.start(),
            )

    def test_review_results_are_collected_in_a_mapping(self):
        src = _cmd_build_source()
        self.assertIn("review_results = {}", src)
        self.assertIn("review_results[", src)


class ReviewOverlapTests(unittest.TestCase):
    """Review submission moved from after the writer wave into it."""

    def test_submission_at_write_completion_and_consumption_after_the_wave(self):
        src = _cmd_build_source()
        submit = src.index("review_results[")
        consume = src.index("review_results.get(")
        self.assertLess(
            submit,
            consume,
            "review submission must be written before the post-wave consumption reads it",
        )

    def test_submission_follows_both_marks(self):
        src = _cmd_build_source()
        ok = src.index(".ok")
        warn = src.index(".warn")
        submit = src.index("review_results[")
        self.assertLess(
            ok,
            submit,
            "review must be submitted only after the .ok mark is written",
        )
        self.assertLess(
            warn,
            submit,
            "review must be submitted only after the .warn signal it reads is written",
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_plan_review_overlap.py -v`
Expected: FAIL ending in `FAILED (failures=3, errors=2)`. The three failures: the budget-gate window test (today's post-wave `review_one` site has no `budget.blown()` nearby), the no-review window test (same window lacks `no_review`), and the mapping test (`'review_results = {}' not found in`). The two errors are `ValueError: substring not found` from the ordering tests (`review_results[` does not exist in cmd_build yet).

- [ ] **Step 3: Rework cmd_build to submit reviews from the writer wave**

In `cmd_build` of `glm-skills/glm-writing-plans/scripts/plan_tool.py` (the write/review section sits at roughly lines 1080-1124 of the pre-edit file; the earlier task on this file may have shifted those lines, so locate the code by the anchors below, not by line number). The current shape: the writer wave `pmap` runs the write tasks (each calls `call_model`, repairs through `lint_one`, writes the body file, then writes its `.ok` mark); after the wave a failure check aborts with the usual report; only then does the risky-task pick run and a second `pmap` submit `review_one` for the picked tasks.

1. Before the writer wave `pmap`, add at `cmd_build` body indentation:

```python
review_results = {}
```

2. Inside the writer wave task function, at the END of its success path - after BOTH mark writes (the `.ok` touch and, when lint warnings exist, the `.warn` write that follows it; the pick reads that warn signal) and after the failure branch that returns on a write error, so a failed write never reaches the submission - add:

```python fragment
        if not a.no_review and not budget.blown() and _picked(<SIGNALS>):
            review_results[task_id] = review_one(<ITEM>)
```

Binding rules for that block: `_picked` is the removed review wave's pick condition for ONE task, copied verbatim into a small helper defined once in cmd_build before the wave, parameterized by exactly the values the condition reads at this site - the task record's tier, the finished body's length, the task's consumer count, and the lint-warning flag; include the review-everything/`a.thorough` signal only if the original pick honors it, and nothing else. `<ITEM>` is the exact single tuple argument the removed review wave built for a picked task (the context record plus the pick-reason string): `review_one` takes that one tuple argument and keeps its own save/`.ok`-rewrite side effects - do not reimplement them. The wave threads write distinct `task_id` keys, so the plain dict needs no lock. Keep the submission and the wave task function inside `cmd_build` so the test's source scan sees them.

3. Delete the post-wave review `pmap`. Where its results were consumed (rewrite acceptance, review reporting), read `review_results.get(task_id)` instead; a missing entry means the review was skipped (not picked, budget already tripped, or failed write) and is handled exactly as the old code handled a task it did not pick.

4. Keep untouched: the post-wave failure check with its report and exit codes, the writer-side `budget.blown()` gate, the shared prompt blocks, and the 8-wide pool - reviews now run on the writer wave threads, so there is no new executor and the in-flight cap stays at 8.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_plan_review_overlap.py -v`
Expected: PASS with "Ran 5 tests" and "OK"

- [ ] **Step 5: Run the full test suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: PASS with "OK"

- [ ] **Step 6: Record the change in the changelog**

In `glm-skills/glm-writing-plans/CHANGELOG.md`, insert a new entry between the thoughtLevel entry (line 13) and the "Target:" line (line 15):

```markdown
**Review overlap (2026-10-10):** `build` submits each picked task's review as soon as its writer finishes (right after the `.ok` mark) instead of after every writer completes; a tripped shared budget now also stops new review submissions; failed writes still skip review and the failure report and exit codes are unchanged.
```

- [ ] **Step 7: Commit**

```bash
git add glm-skills/glm-writing-plans/scripts/plan_tool.py glm-skills/glm-writing-plans/CHANGELOG.md glm-skills/_shared/tests/test_plan_review_overlap.py
git commit -m "perf: overlap plan review with writer fan-out in build"
```

---

### T04: idea-to-spec guidance — collapse interview when the brief is detailed [P]

**Depends:** —

**Interfaces:**
- Produces: `name`; `description`

**Files:**
- Modify: `glm-skills/glm-idea-to-spec/SKILL.md:48-80`
- Test: `glm-skills/_shared/tests/test_idea_to_spec_guidance.py`

- [ ] **Step 1: Write the failing test**

Create `glm-skills/_shared/tests/test_idea_to_spec_guidance.py` with exactly this content. It follows the existing suite idiom: plain unittest, read the target file, assert on its text.

```python
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..", "..", "glm-idea-to-spec", "SKILL.md")


def _skill_text():
    with open(SKILL, encoding="utf-8") as fh:
        return fh.read()


class DetailedBriefCollapseTests(unittest.TestCase):
    """Rule (a): a detailed opening brief collapses the interview into one round."""

    def test_opening_brief_answers_phase_0_2_collapses_to_one_round(self):
        text = _skill_text()
        self.assertIn("already answers the Phase 0-2 questions", text)
        self.assertIn("target users, goal, success criteria", text)
        self.assertIn("collapse the remaining questions into ONE batched question round", text)
        self.assertIn("one numbered chat list", text)
        self.assertIn("then move to Phase 3", text)


class ResearchBatchingTests(unittest.TestCase):
    """Rule (b): query variants are batched in one message without a subagent tool."""

    def test_query_variants_batched_in_one_message_without_a_task_tool(self):
        text = _skill_text()
        self.assertIn("With no subagent tool", text)
        self.assertIn("query variants", text)
        self.assertIn("one message of web search and fetch calls", text)
        self.assertIn("never one query per turn", text)


class UnchangedGuidanceTests(unittest.TestCase):
    """Guards: verdict-before-spec order, fast mode and frontmatter stay unchanged."""

    def test_verdict_still_precedes_the_spec(self):
        text = _skill_text()
        self.assertIn("BEFORE writing the spec", text)
        self.assertLess(text.index("Verdict & path to money"), text.index("Write the spec"))

    def test_fast_mode_still_defined(self):
        text = _skill_text()
        self.assertIn("**Fast mode**", text)
        self.assertIn("one research sweep + one round", text)

    def test_frontmatter_name_and_description_limit(self):
        text = _skill_text()
        head = text.split("---\n")[1]
        fields = {}
        for line in head.splitlines():
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
        self.assertEqual(fields["name"], "glm-idea-to-spec")
        self.assertLessEqual(len(fields["description"]), 1024)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_idea_to_spec_guidance.py -v`
Expected: FAIL with `AssertionError: 'already answers the Phase 0-2 questions' not found in` (DetailedBriefCollapseTests) and `AssertionError: 'With no subagent tool' not found in` (ResearchBatchingTests), ending in `FAILED (failures=2)`; the three UnchangedGuidanceTests guards already pass because they assert existing text.

- [ ] **Step 3: Add the detailed-brief collapse rule at the end of Phase 2**

In `glm-skills/glm-idea-to-spec/SKILL.md`, find this exact line (it is the last line of the Phase 2 section; match the existing dash and quote characters exactly):

```markdown
Usually 2–4 rounds. If the user says "go fast", fill the rest with labeled assumptions.
```

Replace that single line with:

```markdown
Usually 2–4 rounds. If the user says "go fast", fill the rest with labeled assumptions. If the opening brief already answers the Phase 0-2 questions (target users, goal, success criteria), collapse the remaining questions into ONE batched question round: ask everything still open in a single question-tool call or one numbered chat list, then move to Phase 3.
```

- [ ] **Step 4: Add the research-batching rule to Phase 1**

In the same file, find this exact line in the Phase 1 section:

```markdown
If a subagent tool (Task/Agent) exists, run branches in parallel (competitors & pricing / pain & demand / market & trend / tech & cost / legal) and have each return findings + sources.
```

Insert this new paragraph immediately after that line, as its own paragraph with a blank line before and after it:

```markdown
With no subagent tool, batch the query variants of every branch into one message of web search and fetch calls (several searches in parallel, then the fetches of the most promising sources), never one query per turn.
```

- [ ] **Step 5: Run the new test to verify it passes**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_idea_to_spec_guidance.py -v`
Expected: `Ran 5 tests` followed by `OK` (no failures, no errors)

- [ ] **Step 6: Run the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: `OK` on the final line; no failures or errors.

- [ ] **Step 7: Commit**

```bash
git add glm-skills/glm-idea-to-spec/SKILL.md glm-skills/_shared/tests/test_idea_to_spec_guidance.py
git commit -m "perf: collapse idea-to-spec interview when the brief is detailed"
```

---

### T05: context.sh — dedupe ls-files and background the hot-dir log [P]

**Depends:** —

**Interfaces:**
- Produces: `git ls-files`; `files:`; `tree:`; `git log`; `|| true`

**Files:**
- Modify: `glm-skills/glm-brainstorming/scripts/context.sh:50-67`
- Modify: `glm-skills/glm-brainstorming/CHANGELOG.md`
- Test: `glm-skills/_shared/tests/test_context_sh.py`

- [ ] **Step 1: Write the failing test**

Create `glm-skills/_shared/tests/test_context_sh.py` with exactly this content. The two script-shape tests fail against the current script and drive the change; the eight output-contract tests pin the current stdout contract (content, order, determinism, always-exit-0) so the rework cannot change it.

```python
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CONTEXT_SH = os.path.join(HERE, "..", "..", "glm-brainstorming", "scripts", "context.sh")


def run_context(cwd):
    return subprocess.run(["sh", CONTEXT_SH], cwd=cwd, capture_output=True,
                          text=True, timeout=60)


def git(repo, *args):
    subprocess.run(["git", "-C", repo] + list(args), check=True,
                   capture_output=True, text=True)


def make_repo(extra_top_level=0):
    repo = tempfile.mkdtemp(prefix="ctx_sh_")
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "test")
    for rel in ("alpha.txt", "docs/readme.md", "src/main.py"):
        path = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("x\n")
    for i in range(extra_top_level):
        with open(os.path.join(repo, "fill_%02d.txt" % i), "w", encoding="utf-8") as fh:
            fh.write("x\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "initial commit")
    return repo


class TestScriptShape(unittest.TestCase):
    def script_text(self):
        with open(CONTEXT_SH, encoding="utf-8") as fh:
            return fh.read()

    def test_git_ls_files_runs_exactly_once(self):
        self.assertEqual(self.script_text().count("git ls-files"), 1)

    def test_hot_dir_log_is_backgrounded_guarded_and_joined(self):
        text = self.script_text()
        self.assertIn("|| true &", text)
        self.assertRegex(text, r"(?m)^\s*wait\b")
        self.assertTrue(text.rstrip().endswith("exit 0"))


class TestOutputContract(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_exits_zero_and_keeps_line_order(self):
        proc = run_context(self.repo)
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.splitlines()
        git_line = next(i for i, l in enumerate(lines) if l.startswith("git: "))
        commits = next(i for i, l in enumerate(lines) if l == "recent_commits:")
        hot = next(i for i, l in enumerate(lines) if l.startswith("hot_dirs_30d:"))
        files = next(i for i, l in enumerate(lines) if l.startswith("files:"))
        self.assertLess(git_line, commits)
        self.assertLess(commits, hot)
        self.assertLess(hot, files)

    def test_small_repo_counts_and_names_tracked_files(self):
        proc = run_context(self.repo)
        self.assertIn("tracked=3", proc.stdout)
        self.assertIn("modified=0", proc.stdout)
        files_line = next(l for l in proc.stdout.splitlines() if l.startswith("files:"))
        self.assertEqual(files_line, "files: alpha.txt docs/readme.md src/main.py ")

    def test_hot_dirs_line_groups_top_level_dirs(self):
        proc = run_context(self.repo)
        hot = next(l for l in proc.stdout.splitlines() if l.startswith("hot_dirs_30d:"))
        self.assertIn("docs(1)", hot)
        self.assertIn("src(1)", hot)
        self.assertIn(".(1)", hot)

    def test_recent_commits_lists_the_last_commit(self):
        proc = run_context(self.repo)
        self.assertIn("initial commit", proc.stdout)

    def test_two_runs_are_byte_identical(self):
        first = run_context(self.repo).stdout
        second = run_context(self.repo).stdout
        self.assertEqual(first, second)

    def test_empty_repo_keeps_the_files_line_shape(self):
        empty = tempfile.mkdtemp(prefix="ctx_sh_empty_")
        git(empty, "init", "-q")
        try:
            proc = run_context(empty)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("tracked=0", proc.stdout)
            files_line = next(l for l in proc.stdout.splitlines() if l.startswith("files:"))
            self.assertEqual(files_line, "files: ")
        finally:
            shutil.rmtree(empty, ignore_errors=True)


class TestTreeBranch(unittest.TestCase):
    def test_many_files_repo_prints_tree_not_files(self):
        repo = make_repo(extra_top_level=60)
        try:
            proc = run_context(repo)
            self.assertEqual(proc.returncode, 0)
            lines = proc.stdout.splitlines()
            self.assertFalse(any(l.startswith("files:") for l in lines))
            tree = next(l for l in lines if l.startswith("tree:"))
            self.assertIn(".(60)", tree)
            self.assertIn("docs/(1)", tree)
            self.assertIn("src/(1)", tree)
        finally:
            shutil.rmtree(repo, ignore_errors=True)


class TestOutsideRepo(unittest.TestCase):
    def test_exits_zero_outside_a_git_repo(self):
        plain = tempfile.mkdtemp(prefix="ctx_sh_plain_")
        try:
            proc = run_context(plain)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("git: none", proc.stdout)
        finally:
            shutil.rmtree(plain, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_context_sh.py -v`
Expected: "Ran 10 tests" ending in "FAILED (failures=2)". The two failures are:
- `test_git_ls_files_runs_exactly_once` fails with "AssertionError: 3 != 1" (the current script runs `git ls-files` three times: once for the tracked count, once for the `files:` line, once for the `tree:` aggregation).
- `test_hot_dir_log_is_backgrounded_guarded_and_joined` fails with "AssertionError: '|| true &' not found in" followed by the script text (the hot-dir `git log` still runs in the foreground).

The eight output-contract tests pass against the current script; they guard the rework.

- [ ] **Step 3: Rework the git block in context.sh**

In `glm-skills/glm-brainstorming/scripts/context.sh`, replace the whole first branch of the outer repo `if` — from the line `if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then` through its closing `fi`, the `fi` immediately before `elif [ "$in_home" = no ]` (currently lines 50-67) — with exactly:

```sh fragment
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ls_out=$(git ls-files 2>/dev/null)
  files=$(printf '%s' "$ls_out" | awk 'END{print NR}')
  hot_tmp=$(mktemp "${TMPDIR:-/tmp}/ctx_hot.XXXXXX")
  ( git log --since=30.days -n 300 --name-only --pretty=format: --relative -- . 2>/dev/null \
      | head -n 20000 \
      | awk -F/ 'NF>2{print $1"/"$2} NF==2{print $1} NF==1&&$1!=""{print "."}' \
      | sort | uniq -c | sort -rn | cap 6 \
      | awk '{printf "%s(%s) ", $2, $1}' ) >"$hot_tmp" 2>/dev/null || true &
  dirty=$(git status --porcelain --untracked-files=no 2>/dev/null | wc -l | tr -d ' ')
  echo "git: root=$(git rev-parse --show-toplevel 2>/dev/null) branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) tracked=$files modified=$dirty"
  echo "recent_commits:"
  git log --oneline -n 6 2>/dev/null | cut -c1-100 | sed 's/^/  /'
  wait 2>/dev/null || true
  echo "hot_dirs_30d: $(cat "$hot_tmp" 2>/dev/null)"
  rm -f "$hot_tmp" 2>/dev/null
  if [ "$files" -le 50 ] 2>/dev/null; then
    echo "files: $([ -n "$ls_out" ] && printf '%s\n' "$ls_out" | tr '\n' ' ')"
  else
    echo "tree: $(printf '%s\n' "$ls_out" | awk -F/ 'NF>1{print $1"/"} NF==1{print "."}' | sort | uniq -c | sort -rn | cap 14 \
      | awk '{printf "%s(%s) ", $2, $1}')"
  fi
```

Leave every other line of the script untouched, including the final `exit 0`. What changed and why:
- `ls_out` captures the `git ls-files` stream once; the tracked count (`awk 'END{print NR}'`, equal to the old `wc -l` for any real list and 0 for an empty one), the `files:` line and the `tree:` aggregation all reuse it. The `[ -n "$ls_out" ]` guard keeps the `files:` line byte-identical for a repo with zero tracked files.
- The hot-dir pipeline is unchanged byte for byte; it now writes to a mktemp file as one background job guarded with `|| true &`, while the quick calls (`git status`, the two `rev-parse`, `git log -n 6`) execute. `wait` joins the job and the line is emitted at its original position, so stdout content and order are unchanged.
- `wait 2>/dev/null || true` plus the final `exit 0` keep the always-exit-0 contract; every git call stays read-only (`GIT_OPTIONAL_LOCKS=0` is already exported at the top of the script).

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_context_sh.py -v`
Expected: "Ran 10 tests" ending in "OK".

- [ ] **Step 5: Add the changelog entry**

In `glm-skills/glm-brainstorming/CHANGELOG.md`, insert above the current first line `# 9.5 (from 9.4) — ZCode only` a new first section with the heading `# 9.6 (from 9.5) — context.sh git block concurrency` followed by this body:

```text
context.sh: `git ls-files` output is captured once and reused for the tracked
count, the `files:` line and the `tree:` aggregation (it ran two to three times
before); the hot-dir `git log` runs in the background behind a mktemp file
while the quick git calls execute and is joined with `wait` before emit, so the
stdout block keeps its content and order. Still read-only, still bounded, still
always exits 0: the backgrounded job is guarded with `|| true` and `wait`
cannot propagate a failure into the script exit.
```

- [ ] **Step 6: Run the full test suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: final line "OK" with no "FAILED" anywhere in the output.

- [ ] **Step 7: Commit**

From the repository root:

```bash
git add glm-skills/glm-brainstorming/scripts/context.sh glm-skills/glm-brainstorming/CHANGELOG.md glm-skills/_shared/tests/test_context_sh.py
git commit -m "perf: dedupe git ls-files and background the hot-dir log in context.sh"
```

---

### T06: gather.sh — batch base probing and single-pass chunking [P]

**Depends:** —

**Interfaces:**
- Produces: `git for-each-ref`; `rev-parse --verify`

**Files:**
- Modify: `glm-skills/glm-git-diff-summary/scripts/gather.sh`
- Test: `glm-skills/_shared/tests/test_gather_micro.py`

- [ ] **Step 1: Capture the byte-identity baseline**

Run from the repo root, on a tree whose only uncommitted changes are this task's files. The exclusion var hides this task's own files from the diff so the runs at steps 1 and 8 see identical tree content. Do not commit anything before step 10.

Run:

```bash
GLM_GDS_NO_FETCH=1 GLM_GDS_EXCLUDE='glm-git-diff-summary/** _shared/tests/test_gather_micro.py docs/plans/**' bash glm-skills/glm-git-diff-summary/scripts/gather.sh > "${TMPDIR:-/tmp}/gather-before.txt"; echo "exit=$?"
```

Expected: `exit=0`, and the file contains one `BRANCH=` header line and exactly one `MODE=` line.

- [ ] **Step 2: Write the failing tests**

Create the test file. It drives gather.sh against throwaway repos and counts tool invocations through PATH shims, following the suite's temp-dir style.

```python
import glob
import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GATHER = os.path.join(HERE, "..", "..", "glm-git-diff-summary", "scripts", "gather.sh")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _write_file(path, lines):
    stem = os.path.basename(path).rsplit(".", 1)[0]
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(1, lines + 1):
            fh.write("%s line %03d\n" % (stem, i))


class GatherMicroTestCase(unittest.TestCase):
    """Drive gather.sh in throwaway repos; PATH shims count tool invocations."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gather-micro-")
        self.bin = os.path.join(self.tmp, "bin")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def shim(self, real, log_var, log_path):
        os.makedirs(self.bin, exist_ok=True)
        name = os.path.basename(real)
        path = os.path.join(self.bin, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\n"
                     "printf '%%s\\n' \"$*\" >> \"$%s\"\n"
                     "exec '%s' \"$@\"\n" % (log_var, real))
        os.chmod(path, 0o755)
        return log_path

    def make_repo(self, name, default_branch="main", change_base=True):
        root = os.path.join(self.tmp, name)
        os.makedirs(root)
        _git(root, "init", "-q", "-b", default_branch)
        _git(root, "config", "user.email", "test@example.com")
        _git(root, "config", "user.name", "Test")
        _write_file(os.path.join(root, "base.txt"), 3)
        _git(root, "add", ".")
        _git(root, "commit", "-qm", "base")
        _git(root, "checkout", "-qb", "feature")
        if change_base:
            _write_file(os.path.join(root, "base.txt"), 4)
            _git(root, "commit", "-qam", "change")
        return root

    def add_files(self, root, count, lines=200):
        for n in range(1, count + 1):
            _write_file(os.path.join(root, "f%03d.txt" % n), lines)
        _git(root, "add", ".")
        _git(root, "commit", "-qm", "bulk")

    def gather(self, repo, log_var=None, log_path=None, extra=None):
        env = dict(os.environ)
        env["GLM_GDS_NO_FETCH"] = "1"
        env["TMPDIR"] = self.tmp
        env["PATH"] = self.bin + os.pathsep + env["PATH"]
        if log_var:
            env[log_var] = log_path
        env.update(extra or {})
        proc = subprocess.run(["bash", GATHER], cwd=repo, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        out = proc.stdout.decode("utf-8", "replace")
        self.assertEqual(proc.returncode, 0, out + proc.stderr.decode("utf-8", "replace"))
        return out


class BatchedBaseProbeTests(GatherMicroTestCase):
    def test_script_probes_base_with_one_batched_refs_query(self):
        with open(GATHER, encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("for c in main master develop trunk", text,
                         "candidate probing must not be a serial rev-parse loop")
        self.assertEqual(text.count("for-each-ref"), 1,
                         "candidate probing must be one batched for-each-ref query")

    def test_probe_issues_no_serial_rev_parse_calls(self):
        repo = self.make_repo("probe", default_branch="trunk")
        log = self.shim(shutil.which("git"), "GLM_GDS_GITLOG",
                        os.path.join(self.tmp, "git.log"))
        out = self.gather(repo, "GLM_GDS_GITLOG", log)
        self.assertIn(" REF=trunk MB=", out)
        with open(log, encoding="utf-8") as fh:
            probes = [line for line in fh.read().splitlines()
                      if "rev-parse" in line and "--verify" in line]
        self.assertEqual(len(probes), 1,
                         "pick_ref keeps exactly one verify; the candidate probe must add none")

    def test_candidate_and_remote_preference_order_unchanged(self):
        main_master = self.make_repo("mm")
        _git(main_master, "branch", "master")
        self.assertIn(" REF=main MB=", self.gather(main_master))

        dev_trunk = self.make_repo("dt", default_branch="develop")
        _git(dev_trunk, "branch", "trunk")
        self.assertIn(" REF=develop MB=", self.gather(dev_trunk))

        origin = os.path.join(self.tmp, "origin.git")
        _git(self.tmp, "init", "-q", "--bare", origin)
        _git(dev_trunk, "remote", "add", "origin", origin)
        _git(dev_trunk, "push", "-q", "origin", "develop:refs/heads/trunk")
        _git(dev_trunk, "fetch", "-q", "origin")
        self.assertIn(" REF=develop MB=", self.gather(dev_trunk))

        remote_main = self.make_repo("rmrepo")
        origin2 = os.path.join(self.tmp, "origin2.git")
        _git(self.tmp, "init", "-q", "--bare", origin2)
        _git(remote_main, "remote", "add", "origin", origin2)
        _git(remote_main, "push", "-q", "origin", "main")
        _git(remote_main, "fetch", "-q", "origin")
        self.assertIn(" REF=origin/main MB=", self.gather(remote_main))


class SinglePassChunkingTests(GatherMicroTestCase):
    def fan_repo(self, name, count):
        root = self.make_repo(name, change_base=False)
        self.add_files(root, count)
        return root

    @staticmethod
    def chunker_awk_runs(log):
        with open(log, encoding="utf-8") as fh:
            return sum(1 for line in fh.read().splitlines() if "-v tgt=" in line)

    def test_below_cap_rechunk_path_is_untouched(self):
        repo = self.fan_repo("fan60", 60)
        log = self.shim(shutil.which("awk"), "GLM_GDS_AWKLOG",
                        os.path.join(self.tmp, "awk60.log"))
        out = self.gather(repo, "GLM_GDS_AWKLOG", log, {"GLM_GDS_FAN_CHUNK": "1000"})
        self.assertIn("MODE=FAN_OUT chunks=60 ", out)
        self.assertNotIn("NOTE:", out)
        self.assertEqual(self.chunker_awk_runs(log), 1)
        chunk_dir = re.search(r"dir=(\S+)", out).group(1)
        self.assertEqual(len(glob.glob(os.path.join(chunk_dir, "[0-9][0-9][0-9].patch"))), 60)

    def test_over_cap_rechunk_runs_awk_once_and_stays_consistent(self):
        repo = self.fan_repo("fan100", 100)
        log = self.shim(shutil.which("awk"), "GLM_GDS_AWKLOG",
                        os.path.join(self.tmp, "awk100.log"))
        out = self.gather(repo, "GLM_GDS_AWKLOG", log, {"GLM_GDS_FAN_CHUNK": "1000"})
        self.assertIn("MODE=FAN_OUT chunks=50 ", out)
        self.assertIn("NOTE:", out)
        self.assertEqual(self.chunker_awk_runs(log), 1)
        chunk_dir = re.search(r"dir=(\S+)", out).group(1)
        self.assertEqual(len(glob.glob(os.path.join(chunk_dir, "[0-9][0-9][0-9].patch"))), 50)
        with open(os.path.join(chunk_dir, "count"), encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "50")
        with open(os.path.join(chunk_dir, "index"), encoding="utf-8") as fh:
            rows = fh.read().splitlines()
        self.assertEqual(len(rows), 50)
        self.assertEqual(rows[0], "1\t2\tf001.txt .. f002.txt")
        self.assertEqual(rows[-1], "50\t2\tf099.txt .. f100.txt")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the tests, verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_gather_micro.py -v`

Expected: `FAILED (failures=4)` - `test_script_probes_base_with_one_batched_refs_query` (the candidate loop text is still present), `test_probe_issues_no_serial_rev_parse_calls` (the old loop issues candidate probes plus pick_ref's verify), `test_over_cap_rechunk_runs_awk_once_and_stays_consistent` (the geometric rechunk loop runs the chunker awk more than once AND lands on a different chunk count than 50 on this fixture), and the chunks=50 pin inside it. The preference test and the below-cap guard pass.

- [ ] **Step 4: Replace the serial base probe with one batched refs query**

In gather.sh, in the `else` arm of the `ARG_OK` check (the block from `B=""` through `B=${B:-main}`), replace the candidate loop:

```bash fragment
    for c in main master develop trunk; do
      { [ -n "$REMOTE" ] && has "$REMOTE/$c"; } || has "refs/heads/$c" && { B=$c; break; }
    done
```

with the batched query below: one `git for-each-ref` call over all eight candidate refs replaces the eight serial `rev-parse --verify` probe calls. Keep the `B=""` plus symbolic-ref line above it and the `B=${B:-main}` fallback below it unchanged. The awk pass re-applies the original preference: candidate-major (main, master, develop, trunk), remote before local within a candidate.

```bash fragment
    B=$($G for-each-ref --format='%(refname)' \
      ${REMOTE:+"refs/remotes/$REMOTE/main"} ${REMOTE:+"refs/remotes/$REMOTE/master"} \
      ${REMOTE:+"refs/remotes/$REMOTE/develop"} ${REMOTE:+"refs/remotes/$REMOTE/trunk"} \
      refs/heads/main refs/heads/master refs/heads/develop refs/heads/trunk 2>/dev/null | awk '
      { remote = (index($0, "refs/remotes/") == 1)
        base = $0
        if (remote) { sub(/^refs\/remotes\/[^\/]+\//, "", base) }
        else { sub(/^refs\/heads\//, "", base) }
        c = 0
        if (base == "main") c = 1; else if (base == "master") c = 2
        else if (base == "develop") c = 3; else if (base == "trunk") c = 4
        if (!c) next
        pri = c * 10 + (remote ? 0 : 5)
        if (best == "" || pri < best + 0) { best = pri; B = base } }
      END { print B }')
```

The remote-name strip is load-bearing: without it a `refs/remotes/origin/main` row would read `origin/main`, never match the candidate `main`, and the remote-first preference would silently die. `B` comes out as the bare candidate name (exactly what the old loop assigned), so the downstream REF/merge-base resolution is untouched and still emits `REF=origin/main` when only the remote candidate exists.

- [ ] **Step 5: Run the tests, verify only the chunk test still fails**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_gather_micro.py -v`

Expected: `FAILED (failures=2)` - inside `test_over_cap_rechunk_runs_awk_once_and_stays_consistent`: the awk-runs count (the serial loop still re-runs the chunker) and the chunks=50 pin (the geometric loop produces a different chunk count on this fixture). The NOTE assertion passes on both sides of the change (this fixture's initial ml already exceeds 1900, and the NOTE gate stays where it is).

- [ ] **Step 6: Make the over-cap rechunk single-pass**

In the fan-out `else` branch (the one containing the `TL=`, `tgt=` and `ml=` assignments), replace exactly this line:

```bash fragment
  N=$(chunk $tgt $ml); while [ "$N" -gt $MAXN ]; do tgt=$((tgt*3/2)); ml=$((ml*3/2)); N=$(chunk $tgt $ml); done
```

with the block below. It computes the rechunk boundaries once from the measured chunk index (groups of ceil(N/MAXN) adjacent chunks), concatenates the chunk files with cat, and rewrites count and index, so awk never re-runs on the patch. The NOTE echo, the MODE=FAN_OUT echo and everything after stay unchanged: the NOTE gate keeps evaluating ml where it stands, now the initial ml (the scaling loop is gone) - only diffs whose initial ml already exceeds 1900 print it, and on this repo the rechunk path never triggers at all, so output stays byte-identical.

```bash fragment
  N=$(chunk $tgt $ml)
  if [ "$N" -gt "$MAXN" ]; then
    # one pass: group the measured chunk index arithmetically; awk never re-runs on the patch
    per=$(( (N + MAXN - 1) / MAXN ))
    awk -F'\t' -v per="$per" -v dir="$T/c" '
      { g = int((FNR - 1) / per) + 1; nf[g] += $2
        n = split($3, rr, / \.\. /)
        if (!(g in gf)) gf[g] = rr[1]
        gl[g] = rr[n]; ng = g }
      END { for (i = 1; i <= ng; i++)
              print i "\t" nf[i] "\t" gf[i] (gf[i] == gl[i] ? "" : " .. " gl[i]) > (dir "/index.new") }' "$T/c/index"
    m=0; i=1
    while [ "$i" -le "$N" ]; do
      m=$((m+1)); j=$((i + per - 1)); [ "$j" -gt "$N" ] && j=$N
      k=$i; : > "$T/c/.m"
      while [ "$k" -le "$j" ]; do cat "$T/c/$(printf '%03d' "$k").patch" >> "$T/c/.m"; k=$((k+1)); done
      mv "$T/c/.m" "$T/c/.new-$(printf '%03d' "$m")"
      i=$((j + 1))
    done
    k=1; while [ "$k" -le "$m" ]; do mv "$T/c/.new-$(printf '%03d' "$k")" "$T/c/$(printf '%03d' "$k").patch"; k=$((k+1)); done
    while [ "$k" -le "$N" ]; do rm -f "$T/c/$(printf '%03d' "$k").patch"; k=$((k+1)); done
    mv "$T/c/index.new" "$T/c/index"; echo "$m" > "$T/c/count"; N=$m
  fi
```

- [ ] **Step 7: Run the tests, verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_gather_micro.py -v`

Expected: `OK` (5 tests).

- [ ] **Step 8: Verify byte-identical output on this repo**

Run:

```bash
GLM_GDS_NO_FETCH=1 GLM_GDS_EXCLUDE='glm-git-diff-summary/** _shared/tests/test_gather_micro.py docs/plans/**' bash glm-skills/glm-git-diff-summary/scripts/gather.sh > "${TMPDIR:-/tmp}/gather-after.txt"; echo "exit=$?"
```

Expected: `exit=0`.

Run: `diff "${TMPDIR:-/tmp}/gather-before.txt" "${TMPDIR:-/tmp}/gather-after.txt"`

Expected: no output and exit status 0 (the two runs are byte-identical).

- [ ] **Step 9: Run the full test suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`

Expected: `OK`.

- [ ] **Step 10: Commit**

```bash
git add glm-skills/glm-git-diff-summary/scripts/gather.sh glm-skills/_shared/tests/test_gather_micro.py
git commit -m "perf: batch gather.sh base probe and make rechunk single-pass"
```

---

### T07: devteam.py — overlap read-only pre-checks ahead of the serial merge loop [P]

**Depends:** —

**Interfaces:**
- Uses existing: `state_lock`; `save_state`; `merge_slice`; `do_integrate`; `integrate_one`
- Produces: `def precheck_one(c, sl) -> dict`; `def precheck_all(c, slices) -> list`; `integrate_one`; `pc`; `do_integrate`

**Files:**
- Modify: `glm-skills/glm-dev-team/scripts/devteam.py`
- Test: `glm-skills/_shared/tests/test_devteam_precheck.py`

- [ ] **Step 1: Write the failing tests**

Create `glm-skills/_shared/tests/test_devteam_precheck.py` with exactly this content. It follows the suite idiom of loading the script by path with importlib, driving the new helpers against fakes, and asserting structure on the real source. Note where the work lives: the per-slice integration (including the read-only probes this task moves) is inside `integrate_one` (around lines 1981-2103); `do_integrate`'s loop calls `integrate_one` - the structure tests below target those two functions, never the merge internals.

```python
import importlib.util
import inspect
import os
import threading
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
DEVTEAM = os.path.join(HERE, "..", "..", "glm-dev-team", "scripts", "devteam.py")


def _load_devteam():
    spec = importlib.util.spec_from_file_location("devteam_under_test", DEVTEAM)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


devteam = _load_devteam()


def _devteam_text():
    with open(DEVTEAM, encoding="utf-8") as fh:
        return fh.read()


def _function_source(text, name):
    start = text.index("def %s(" % name)
    end = text.find("\ndef ", start + 1)
    if end == -1:
        end = len(text)
    return text[start:end]


class TestPrecheckOneContract(unittest.TestCase):
    def test_precheck_one_exists_with_exact_signature(self):
        self.assertTrue(callable(devteam.precheck_one))
        self.assertEqual(
            list(inspect.signature(devteam.precheck_one).parameters), ["c", "sl"]
        )

    def test_precheck_one_body_is_read_only(self):
        body = _function_source(_devteam_text(), "precheck_one")
        for banned in ("save_state", "state_lock", "merge_slice", "reject("):
            self.assertNotIn(banned, body)


class TestPrecheckConcurrency(unittest.TestCase):
    def test_precheck_all_runs_slices_concurrently_capped_at_eight(self):
        live = [0]
        peak = [0]
        lock = threading.Lock()

        def fake_precheck(c, sl):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.01)
            with lock:
                live[0] -= 1
            return {"slice": sl}

        with mock.patch.object(devteam, "precheck_one", fake_precheck):
            devteam.precheck_all({}, list(range(40)))
        self.assertLessEqual(peak[0], 8)
        self.assertGreater(peak[0], 1)

    def test_precheck_all_preserves_slice_order(self):
        def fake_precheck(c, sl):
            return {"slice": sl}

        with mock.patch.object(devteam, "precheck_one", fake_precheck):
            out = devteam.precheck_all({}, list(range(12)))
        self.assertEqual(out, [{"slice": n} for n in range(12)])


class TestIntegrateStructure(unittest.TestCase):
    def test_do_integrate_prechecks_before_the_integration_loop(self):
        body = _function_source(_devteam_text(), "do_integrate")
        self.assertIn("precheck_all(", body,
                      "do_integrate must run precheck_all before the integration loop")
        self.assertIn("integrate_one(", body,
                      "do_integrate must still call integrate_one for every slice")
        self.assertLess(body.index("precheck_all("), body.index("integrate_one("),
                        "prechecks must complete before the first integrate_one call")

    def test_integrate_one_gains_a_trailing_pc_parameter(self):
        params = list(inspect.signature(devteam.integrate_one).parameters)
        self.assertEqual(params[-1], "pc",
                         "integrate_one must receive its precheck result as a trailing pc param")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_precheck.py -v`
Expected: FAIL ending in `FAILED (failures=2, errors=4)`. The four errors: `AttributeError: module 'devteam_under_test' has no attribute 'precheck_one'` (the signature test), the same AttributeError from both concurrency tests (via `precheck_all`), and `ValueError: substring not found` from the read-only scan (no `precheck_one` in the file yet). The two failures: the do_integrate structure test (`'precheck_all(' ... not found`) and the trailing-pc test (integrate_one's last parameter is not `pc`).

- [ ] **Step 3: Add the import, precheck_one and precheck_all above do_integrate**

First, in the import block at the top of `glm-skills/glm-dev-team/scripts/devteam.py`, add this line (skip it if an equivalent import already exists):

```python
from concurrent.futures import ThreadPoolExecutor
```

Next, insert both functions immediately ABOVE the `def do_integrate(` line. `precheck_all` is complete as written:

```python
def precheck_all(c, slices) -> list:
    """Run the read-only per-slice pre-checks concurrently, capped at 8 threads.

    Returns the results in slice order. Nothing here mutates state.
    """
    if not slices:
        return []
    workers = min(8, len(slices))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda sl: precheck_one(c, sl), slices))
```

`precheck_one` is a move of the read-only probes ONLY. In `integrate_one` (around lines 1981-2103), locate the head-of-function probes that run before any state decision: the working-tree dirty-status probe, the slice log scan and the footprint diff. Move only those pure read-only computations into `precheck_one`:

```python fragment
def precheck_one(c, sl) -> dict:
    """Read-only pre-checks for one slice: dirty status, log scan, footprint diff."""
    result = {}
    # The read-only probes moved from integrate_one's head go here, unchanged
    # except that the enclosing function's locals become locals of this
    # function, and every value integrate_one later reads is stored into
    # result under the variable's own name.
    return result
```

Move rules:

- `c` is the same context/config object do_integrate's loop already passes to `integrate_one` as its first argument - precheck_one receives that same object; `sl` is the slice record.
- Every `reject()` call, every history/verdict decision and every state mutation STAYS in `integrate_one`, serial. precheck_one returns raw probe outputs only, and integrate_one keeps making exactly the same decisions from them. Where a probe and a `reject()` interleave today, split them: the probe's computation moves, the `reject()` call stays.
- Include no `save_state`, `state_lock`, `merge_slice` or `reject(` statement in this function. Reads of already-loaded state need no lock here because nothing mutates state until the serial integration loop starts.

- [ ] **Step 4: Run the tests again; only the two structure tests may still fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_precheck.py -v`
Expected: FAIL ending in `FAILED (failures=2)` with exactly the two structure failures (`precheck_all(` not in do_integrate yet; integrate_one has no trailing `pc`); the four helper tests pass.

- [ ] **Step 5: Rework do_integrate and integrate_one to consume the prechecks**

In `do_integrate`, let SLICES denote the list of slices the integration loop iterates today and CTX the first argument it passes to `integrate_one` (use their real local names). Make exactly these edits:

1. Immediately before the loop, insert `prechecks = precheck_all(CTX, SLICES)`. SLICES is exactly the list the loop iterates today - keep whatever filtering it already applies (status checks, research slices); add none, relax none.
2. Keep the loop head as it is when it is index-based and read `pc = prechecks[i]` as the loop's first statement; otherwise switch to `for sl, pc in zip(SLICES, prechecks):`. Pass pc at the call site: `integrate_one(CTX, sl, pc)`.
3. Append a trailing `pc=None` parameter to `integrate_one`'s signature (rename nothing). Inside it, delete the moved probes and replace each of their former locals with the matching read from `pc` (same key names as the dict). Everything else - every `reject()` call, every `merge_slice` call, every `save_state`/`state_lock` mutation, conflict reporting, and the `next` wake-up chain - stays byte-for-byte where it is, still serial.

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_precheck.py -v`
Expected: PASS, `OK` (6 tests).

- [ ] **Step 7: Run the full shared suite and the engine self-test**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: `OK` (full suite passes, no new failures).

Run: `cd glm-skills && bash glm-dev-team/scripts/selftest.sh`
Expected: the recorded baseline set holds: 323 pass with the 6 pre-existing Claude-lane failures, the same six as before this change, and no new failures.

- [ ] **Step 8: Commit**

```bash
git add glm-skills/glm-dev-team/scripts/devteam.py glm-skills/_shared/tests/test_devteam_precheck.py
git commit -m "perf: overlap devteam read-only pre-checks ahead of the serial merge loop"
```
