"""FAST chain self-detection in init: with no pace file, a fast chain.json
marks fast_lane; a slow mode stamp still wins and stays strict. No model calls."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DT_PATH = str(Path(__file__).resolve().parents[2] / "glm-dev-team" / "scripts" / "devteam.py")
FENCE = "`" * 3


def clean_env(tmp):
    env = dict(os.environ)
    for k in list(env):
        if k.startswith(("DEVTEAM_", "OPENCODE", "HYBRID_")):
            del env[k]
    (tmp / "home").mkdir(exist_ok=True)
    (tmp / "tx").mkdir(exist_ok=True)
    env.update(HOME=str(tmp / "home"), XDG_DATA_HOME=str(tmp / "home"), DEVTEAM_PROVIDER="anthropic",
               DEVTEAM_HARNESS="other", DEVTEAM_TRANSCRIPTS_DIR=str(tmp / "tx"))
    return env


class ChainFastTests(unittest.TestCase):
    def new_repo(self):
        tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="devteam-chainfast-")))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        self.env = clean_env(tmp)
        repo = tmp / "repo"
        repo.mkdir()
        for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"],
                     ["config", "user.name", "t"], ["config", "commit.gpgsign", "false"]):
            subprocess.run(["git"] + args, cwd=repo, check=True)
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        (repo / "src" / ".keep").write_text("")
        (repo / "tests" / ".keep").write_text("")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
        plan = {"request": "chain fast", "profile": "balanced",
                "commands": {"test": "none", "test_file": "none"},
                "slices": [{"id": "S1", "title": "S1", "files": ["src/a.py", "tests/a.test.js"],
                            "risk": "low", "criteria": ["works"]}]}
        (repo / "plan.md").write_text("# plan\n" + FENCE + "json\n" + json.dumps(plan) + "\n" + FENCE + "\n")
        return repo

    def run_init(self, repo):
        return subprocess.run([sys.executable, DT_PATH, "init", "plan.md"], cwd=str(repo),
                              capture_output=True, text=True, timeout=90, env=self.env)

    def state(self, repo):
        return json.loads((repo / ".claude" / "dev-team" / "state.json").read_text())

    def write_chain(self, repo, mode, cont):
        d = repo / ".brainstorm" / "drafts"
        d.mkdir(parents=True)
        (d / "chain.json").write_text(json.dumps({"mode": mode, "continue": cont}))

    def test_fast_chain_no_pace_file_marks_fast_lane(self):
        repo = self.new_repo()
        self.write_chain(repo, "fast", True)
        self.assertFalse((repo / ".claude" / "dev-team" / "pace").exists())
        r = self.run_init(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.state(repo)
        self.assertEqual(st["pace"], "fast")
        self.assertIs(st["slices"]["S1"]["fast_lane"], True)

    def test_slow_mode_stamp_beats_the_fast_chain(self):
        repo = self.new_repo()
        self.write_chain(repo, "fast", True)
        sd = repo / ".claude" / "dev-team"
        sd.mkdir(parents=True)
        (sd / "mode").write_text("slow 1770000000\n")
        r = self.run_init(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.state(repo)
        self.assertEqual(st["profile"], "strict")
        self.assertEqual(st["pace"], "")
        self.assertNotIn("fast_lane", st["slices"]["S1"])

    def test_no_chain_and_no_pace_stays_full_lane(self):
        repo = self.new_repo()
        r = self.run_init(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.state(repo)
        self.assertEqual(st["pace"], "")
        self.assertNotIn("fast_lane", st["slices"]["S1"])


if __name__ == "__main__":
    unittest.main()
