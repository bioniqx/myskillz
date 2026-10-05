import os
import subprocess
import tempfile
import unittest

GLM_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCRIPT = os.path.join(GLM_ROOT, "install-zcode.sh")
SKILLS = ["brainstorming", "dev-team", "doc-generator", "requirements-code-audit",
          "systematic-debugging", "writing-plans"]
AGENTS = ["code-reviewer", "debug-worker", "doc-reviewer", "doc-writer", "investigator", "plan-task-writer",
          "programmer", "rca-investigator", "rca-verifier", "spot-reviewer", "team-leader"]


def frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().split("\n---\n")[0]


class InstallZcodeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def install(self, *args):
        return subprocess.run(["sh", SCRIPT, "--home", self.home] + list(args),
                              capture_output=True, text=True, timeout=120)

    def skill(self, name, *parts):
        return os.path.join(self.home, ".zcode", "skills", name, *parts)

    def agent(self, name):
        return os.path.join(self.home, ".zcode", "agents", name + ".md")

    def test_skills_install_without_glm_suffix_and_without_opencode_sources(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in SKILLS:
            self.assertTrue(os.path.isfile(self.skill(name, "SKILL.md")), name)
            self.assertFalse(os.path.exists(self.skill(name, "opencode")), name)
            self.assertFalse(os.path.exists(self.skill(name + "-glm")), name)
        self.assertTrue(os.path.isfile(self.skill("dev-team", "scripts", "devteam.py")))

    def test_agents_use_zcode_frontmatter(self):
        self.assertEqual(self.install("--flash", "acct/Flash", "--main", "acct/Main").returncode, 0)
        for name in AGENTS:
            fm = frontmatter(self.agent(name))
            for key in ("effort:", "hooks:", "isolation:", "memory:", "mode:", "temperature:", "haiku", "opus"):
                self.assertNotIn("\n" + key if key.endswith(":") else key, "\n" + fm, (name, key))
            self.assertIn("\nmodel: acct/", "\n" + fm, name)
        self.assertIn("model: acct/Flash", frontmatter(self.agent("programmer")))
        self.assertIn("thoughtLevel: high", frontmatter(self.agent("programmer")))
        self.assertIn("model: acct/Main", frontmatter(self.agent("team-leader")))
        self.assertIn("thoughtLevel: max", frontmatter(self.agent("team-leader")))
        self.assertIn("thoughtLevel: low", frontmatter(self.agent("plan-task-writer")))

    def test_rerun_is_idempotent_and_keeps_changed_agents(self):
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual([f for f in os.listdir(os.path.dirname(self.agent("x"))) if f.endswith(".bak")], [])
        with open(self.agent("programmer"), "a", encoding="utf-8") as fh:
            fh.write("my edit\n")
        self.assertEqual(self.install().returncode, 0)
        self.assertTrue(os.path.isfile(self.agent("programmer") + ".bak"))

    def test_stale_glm_folder_is_warned_about_not_deleted(self):
        stale = self.skill("brainstorming-glm")
        os.makedirs(stale)
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("WARN: stale: " + stale, r.stdout)
        self.assertTrue(os.path.isdir(stale))

    def test_dry_run_writes_nothing(self):
        r = self.install("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode", "skills", "brainstorming")))
        self.assertFalse(os.path.exists(self.agent("programmer")))


if __name__ == "__main__":
    unittest.main()
