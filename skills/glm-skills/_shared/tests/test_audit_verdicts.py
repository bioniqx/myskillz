import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from argparse import Namespace

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "requirements-code-audit-glm", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import audit  # noqa: E402


def _repo():
    d = tempfile.mkdtemp(prefix="audit-verdicts-")
    os.makedirs(os.path.join(d, "src"))
    with io.open(os.path.join(d, "src", "app.py"), "w", encoding="utf-8") as fh:
        fh.write(u"".join(u"line_%d = %d\n" % (i, i) for i in range(1, 11)))
    return d


class FakeRetr(object):
    def __init__(self, root):
        self.root = root

    def gather(self, it, tier, round2=False, extra_queries=None, tried=None):
        return {"snippets": [{"path": "src/app.py", "start": 1, "end": 5, "text": "line_1 = 1"}],
                "queries": ["round2_q" if round2 else "round1_q"],
                "considered": ["src/app.py"], "near_misses": [],
                "layers": ["symbol"], "chars": 10, "engine": "python"}

    def expand_region(self, rel, start, end):
        return None


class FakeCl(object):
    """Replies with the queued objects in order, then repeats the last one."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.log = []

    def call(self, model, effort, prefix, task, max_tokens, temperature=None, **kw):
        self.calls += 1
        self.log.append({"model": model, "effort": effort, "prefix": prefix,
                         "max_tokens": max_tokens, "kw": kw})
        r = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return json.dumps(r)


ITEM = {"id": "REQ-001", "text": "Users can log in", "strength": "MUST",
        "stakes": "normal", "search_hints": ["login", "session"]}
BAD_MATCH = {"status": "MATCHED", "confidence": "low", "evidence": [], "notes": "no cite"}
GOOD_MATCH = {"status": "MATCHED", "confidence": "high",
              "evidence": [{"path": "src/app.py", "lines": "1-3", "note": "login"}],
              "notes": "found"}


class JudgeOneTest(unittest.TestCase):
    def setUp(self):
        self.repo = _repo()
        self.addCleanup(shutil.rmtree, self.repo, True)

    def test_clean_second_pass_clears_first_pass_errors(self):
        cl = FakeCl([BAD_MATCH, BAD_MATCH, BAD_MATCH, GOOD_MATCH])
        fix = audit.judge_one(None, cl, FakeRetr(self.repo), "PFX", dict(ITEM), "std", 1200)
        self.assertEqual(fix["status"], "MATCHED")
        self.assertNotIn("lint_error", fix)
        self.assertEqual(fix["passes"], 2)
        self.assertEqual(cl.calls, 4)

    def test_rejected_second_pass_keeps_errors_and_unsettles(self):
        cl = FakeCl([BAD_MATCH])
        fix = audit.judge_one(None, cl, FakeRetr(self.repo), "PFX", dict(ITEM), "std", 1200)
        self.assertEqual(fix["status"], "UNSEARCHED")
        self.assertTrue(fix["lint_error"])


def _audit_dir(repo, verdict):
    out = tempfile.mkdtemp(prefix="audit-out-")
    with io.open(os.path.join(out, "config.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"repo_root": repo, "lane": "api", "tier": "std"}))
    finding = dict(GOOD_MATCH, id="REQ-001", confidence="medium")
    for name, row in (("checklist.jsonl", ITEM), ("findings.jsonl", finding),
                      ("verdicts.jsonl", verdict)):
        with io.open(os.path.join(out, name), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + u"\n")
    return out


REJECTED = {"id": "REQ-001", "verified_status": "MISSING", "confidence": "high",
            "evidence": [], "reason": "nothing", "lint_error": ["evidence path x does not exist"]}


class VerifyOneTest(unittest.TestCase):
    def setUp(self):
        self.repo = _repo()
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.prelim = dict(GOOD_MATCH, id="REQ-001", confidence="medium", searched=["round1_q"])

    def test_rejected_verdict_is_no_verdict(self):
        cl = FakeCl([{"verified_status": "MATCHED", "confidence": "high", "evidence": [],
                      "reason": "trust me", "agree": True}])
        v = audit.verify_one(None, cl, FakeRetr(self.repo), "VPFX", dict(ITEM),
                             self.prelim, "std", 1200)
        self.assertEqual(v["verified_status"], "UNSEARCHED")
        self.assertEqual(v["rejected_status"], "MATCHED")
        self.assertEqual(v["evidence"], [])
        self.assertTrue(v["lint_error"])
        self.assertEqual(cl.calls, 3)

    def test_accepted_verdict_is_kept(self):
        cl = FakeCl([{"verified_status": "MATCHED", "confidence": "high",
                      "evidence": [{"path": "src/app.py", "lines": "2-4"}],
                      "reason": "login at app.py", "agree": True}])
        v = audit.verify_one(None, cl, FakeRetr(self.repo), "VPFX", dict(ITEM),
                             self.prelim, "std", 1200)
        self.assertEqual(v["verified_status"], "MATCHED")
        self.assertNotIn("lint_error", v)


class MergedRejectedTest(unittest.TestCase):
    def test_rejected_verdict_row_falls_back_to_the_finding(self):
        repo = _repo()
        self.addCleanup(shutil.rmtree, repo, True)
        out = _audit_dir(repo, REJECTED)
        self.addCleanup(shutil.rmtree, out, True)
        m = audit.Merged(audit.Ctx(out))
        self.assertEqual(m.final("REQ-001"), ("MATCHED", "investigator"))
        self.assertNotIn("REQ-001", m.ver)
        self.assertIn("REQ-001", m.ver_rejected)
        self.assertEqual(m.evidence("REQ-001")[0]["path"], "src/app.py")


class CheckGateRejectedTest(unittest.TestCase):
    def test_gate_fails_on_an_unadjudicated_rejected_verdict(self):
        repo = _repo()
        self.addCleanup(shutil.rmtree, repo, True)
        out = _audit_dir(repo, REJECTED)
        self.addCleanup(shutil.rmtree, out, True)
        buf = io.StringIO()
        code = None
        with contextlib.redirect_stdout(buf):
            try:
                audit.cmd_check(Namespace(out=out))
            except SystemExit as e:
                code = e.code
        text = buf.getvalue()
        self.assertIn("rejected the verifier's answer", text)
        self.assertIn("GATE: FAIL", text)
        self.assertEqual(code, 2)


def _openai_reply(text, finish):
    return {"choices": [{"message": {"content": text}, "finish_reason": finish}], "usage": {}}


class LengthRetryTest(unittest.TestCase):
    def _client(self, replies, base="http://127.0.0.1:9", route="openai"):
        cl = audit.Client(base, "k" * 32, route)
        sent = []
        queue = list(replies)

        def fake_post(payload):
            sent.append(payload["max_tokens"])
            return queue.pop(0)

        cl._post = fake_post
        return cl, sent

    def test_length_stop_doubles_the_cap_until_the_reply_completes(self):
        cl, sent = self._client([_openai_reply("cut", "length"), _openai_reply("cut", "length"),
                                 _openai_reply("full", "stop")])
        text = cl.call(audit.FLASH, "high", "sys", "task", 1200)
        self.assertEqual(text, "full")
        self.assertEqual(sent, [1200, 2400, 4096])
        self.assertEqual(cl.truncated, 2)

    def test_no_retry_at_or_above_the_retry_cap(self):
        cl, sent = self._client([_openai_reply("cut", "length")])
        self.assertEqual(cl.call(audit.FLASH, "high", "sys", "task", audit.LENGTH_RETRY_CAP), "cut")
        self.assertEqual(sent, [audit.LENGTH_RETRY_CAP])

    def test_grow_false_never_retries(self):
        cl, sent = self._client([_openai_reply("cut", "length")])
        self.assertEqual(cl.call(audit.FLASH, "high", "sys", "task", 64, grow=False), "cut")
        self.assertEqual(sent, [64])


class FanWarmTest(unittest.TestCase):
    def _jobs(self, ran, n):
        return [("k%d" % i, (lambda i=i: ran.append(i) or i)) for i in range(n)]

    def test_callable_warm_makes_one_call_and_every_job_runs_once(self):
        warmed, ran = [], []
        res = audit.Fan(None, 4, quiet=True).run(self._jobs(ran, 6), "t",
                                                 warm=lambda: warmed.append(1))
        self.assertEqual(warmed, [1])
        self.assertEqual(sorted(ran), list(range(6)))
        self.assertEqual(res["k0"], (0, None))

    def test_failed_warm_call_does_not_stop_the_wave(self):
        ran = []

        def boom():
            raise RuntimeError("warm failed")

        fan = audit.Fan(None, 4, quiet=True)
        res = fan.run(self._jobs(ran, 6), "t", warm=boom)
        self.assertEqual(sorted(ran), list(range(6)))
        self.assertEqual(len(res), 6)
        self.assertEqual(fan.errors, [])

    def test_small_wave_skips_the_warm_call(self):
        warmed, ran = [], []
        audit.Fan(None, 4, quiet=True).run(self._jobs(ran, 3), "t",
                                           warm=lambda: warmed.append(1))
        self.assertEqual(warmed, [])
        self.assertEqual(sorted(ran), [0, 1, 2])


class WarmCallTest(unittest.TestCase):
    def test_warm_call_is_one_small_request_on_the_shared_prefix(self):
        cl = FakeCl([{}])
        audit.warm_call(cl, (audit.FLASH, "high"), "JUDGE-PREFIX")()
        self.assertEqual(cl.calls, 1)
        entry = cl.log[0]
        self.assertEqual((entry["model"], entry["effort"], entry["prefix"]),
                         (audit.FLASH, "high", "JUDGE-PREFIX"))
        self.assertEqual(entry["max_tokens"], 64)
        self.assertIs(entry["kw"].get("grow"), False)


class VerifyTargetsTest(unittest.TestCase):
    ORDER = ["REQ-001", "REQ-002", "REQ-003", "REQ-004"]

    def _fixture(self):
        by_id = dict((rid, dict(ITEM, id=rid)) for rid in self.ORDER)
        findings = dict((rid, {"id": rid, "status": "MISSING", "confidence": "medium"})
                        for rid in self.ORDER)
        return by_id, findings

    def test_resume_keeps_settled_verdicts_and_verifies_the_rest(self):
        by_id, findings = self._fixture()
        done = dict((rid, findings[rid]) for rid in ("REQ-001", "REQ-002", "REQ-004"))
        prev_ver = {
            "REQ-001": {"id": "REQ-001", "verified_status": "MISSING"},
            "REQ-003": {"id": "REQ-003", "verified_status": "MATCHED"},
            "REQ-004": {"id": "REQ-004", "verified_status": "UNSEARCHED", "lint_error": ["x"]},
        }
        vset, kept = audit.verify_targets(self.ORDER, by_id, findings, done, prev_ver)
        self.assertEqual(vset, ["REQ-002", "REQ-003", "REQ-004"])
        self.assertEqual(kept, {"REQ-001": prev_ver["REQ-001"]})

    def test_fresh_run_verifies_what_needs_it(self):
        by_id, findings = self._fixture()
        findings["REQ-002"] = {"id": "REQ-002", "status": "MATCHED", "confidence": "high",
                               "passes": 2}
        vset, kept = audit.verify_targets(self.ORDER, by_id, findings, {}, {})
        self.assertEqual(vset, ["REQ-001", "REQ-003", "REQ-004"])
        self.assertEqual(kept, {})


if __name__ == "__main__":
    unittest.main()
