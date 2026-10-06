import os
import subprocess
import tempfile
import unittest

GLM_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCRIPT = os.path.join(GLM_ROOT, "install-zcode.sh")
SKILLS = ["glm-brainstorming", "glm-dev-team", "glm-doc-generator", "glm-git-diff-summary", "glm-idea-to-spec", "glm-requirements-code-audit",
          "glm-systematic-debugging", "glm-writing-plans"]
AGENTS = ["glm-code-reviewer", "glm-debug-worker", "glm-doc-reviewer", "glm-doc-writer", "glm-investigator", "glm-plan-task-writer",
          "glm-programmer", "glm-rca-investigator", "glm-rca-verifier", "glm-spot-reviewer", "glm-team-leader"]


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

    def test_skills_install_with_glm_prefix_and_without_opencode_sources(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in SKILLS:
            self.assertTrue(os.path.isfile(self.skill(name, "SKILL.md")), name)
            self.assertFalse(os.path.exists(self.skill(name, "opencode")), name)
            self.assertTrue(name.startswith("glm-"), name)
        for old in ("brainstorming", "brainstorming-glm"):
            self.assertFalse(os.path.exists(self.skill(old)), old)
        self.assertTrue(os.path.isfile(self.skill("glm-dev-team", "scripts", "devteam.py")))

    def test_agents_use_zcode_frontmatter(self):
        self.assertEqual(self.install("--flash", "acct/Flash", "--main", "acct/Main").returncode, 0)
        for name in AGENTS:
            fm = frontmatter(self.agent(name))
            for key in ("effort:", "hooks:", "isolation:", "memory:", "mode:", "temperature:", "haiku", "opus"):
                self.assertNotIn("\n" + key if key.endswith(":") else key, "\n" + fm, (name, key))
            self.assertIn("\nmodel: acct/", "\n" + fm, name)
        self.assertIn("model: acct/Flash", frontmatter(self.agent("glm-programmer")))
        self.assertIn("thoughtLevel: high", frontmatter(self.agent("glm-programmer")))
        self.assertIn("model: acct/Main", frontmatter(self.agent("glm-team-leader")))
        self.assertIn("thoughtLevel: max", frontmatter(self.agent("glm-team-leader")))
        self.assertIn("thoughtLevel: low", frontmatter(self.agent("glm-plan-task-writer")))

    def test_rerun_is_idempotent_and_keeps_changed_agents(self):
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual([f for f in os.listdir(os.path.dirname(self.agent("x"))) if f.endswith(".bak")], [])
        with open(self.agent("glm-programmer"), "a", encoding="utf-8") as fh:
            fh.write("my edit\n")
        self.assertEqual(self.install().returncode, 0)
        self.assertTrue(os.path.isfile(self.agent("glm-programmer") + ".bak"))

    def test_stale_old_names_are_warned_about_not_deleted(self):
        for old in ("brainstorming", "brainstorming-glm"):
            stale = self.skill(old)
            os.makedirs(stale)
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        for old in ("brainstorming", "brainstorming-glm"):
            stale = self.skill(old)
            self.assertIn("WARN: stale: " + stale, r.stdout)
            self.assertTrue(os.path.isdir(stale))
        # The new glm- install still lands next to them.
        self.assertTrue(os.path.isfile(self.skill("glm-brainstorming", "SKILL.md")))

    def test_dry_run_writes_nothing(self):
        r = self.install("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode", "skills", "glm-brainstorming")))
        self.assertFalse(os.path.exists(self.agent("glm-programmer")))


if __name__ == "__main__":
    unittest.main()
