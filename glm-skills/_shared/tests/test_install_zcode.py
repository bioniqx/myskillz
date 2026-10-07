import os
import shutil
import subprocess
import tempfile
import unittest

GLM_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCRIPT = os.path.join(GLM_ROOT, "install-zcode.sh")
SKILLS = ["glm-brainstorming", "glm-dev-team", "glm-doc-generator", "glm-git-diff-summary", "glm-idea-to-spec", "glm-requirements-code-audit",
          "glm-systematic-debugging", "glm-writing-plans"]
AGENTS = ["glm-code-reviewer", "glm-debug-worker", "glm-doc-reviewer", "glm-doc-writer", "glm-investigator", "glm-plan-task-writer",
          "glm-programmer", "glm-programmer-lite", "glm-programmer-strong", "glm-rca-investigator", "glm-rca-verifier",
          "glm-spot-reviewer", "glm-team-leader"]


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

    def test_rerun_is_idempotent_and_replaces_changed_agents(self):
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual([f for f in os.listdir(os.path.dirname(self.agent("x"))) if f.endswith(".bak")], [])
        with open(self.agent("glm-programmer"), "a", encoding="utf-8") as fh:
            fh.write("my edit\n")
        self.assertEqual(self.install().returncode, 0)
        with open(self.agent("glm-programmer"), encoding="utf-8") as fh:
            self.assertNotIn("my edit", fh.read())
        self.assertEqual([f for f in os.listdir(os.path.dirname(self.agent("x"))) if f.endswith(".bak")], [])

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

    def test_convert_maps_steps_and_omitclaudemd_end_to_end(self):
        copy_root = os.path.join(self.home, "tree")
        shutil.copytree(GLM_ROOT, copy_root,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        agents_src = os.path.join(copy_root, "glm-doc-generator", "agents", "zcode")
        os.makedirs(agents_src, exist_ok=True)
        with open(os.path.join(agents_src, "glm-fixture-agent.md"), "w", encoding="utf-8") as fh:
            fh.write(
                "---\n"
                "name: glm-fixture-agent\n"
                "description: Fixture agent for the frontmatter mapping.\n"
                "model: glm-5.3-flash\n"
                "effort: high\n"
                "steps: 12\n"
                "omitClaudeMd: true\n"
                "permissionMode: acceptEdits\n"
                "background: true\n"
                "---\n"
                "Fixture body.\n"
            )
        r = subprocess.run(["sh", os.path.join(copy_root, "install-zcode.sh"), "--home", self.home],
                           capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, 0, r.stderr)
        fm = frontmatter(self.agent("glm-fixture-agent"))
        self.assertIn("maxTurns: 12", fm)
        self.assertIn("injectAgentsMd: false", fm)
        self.assertIn("background: true", fm)
        self.assertIn("thoughtLevel: high", fm)
        self.assertNotIn("steps:", fm)
        self.assertNotIn("omitClaudeMd:", fm)
        self.assertNotIn("permissionMode:", fm)
        self.assertNotIn("effort:", fm)

    def test_debug_worker_gains_thoughtlevel_low(self):
        self.assertEqual(self.install().returncode, 0)
        self.assertIn("thoughtLevel: low", frontmatter(self.agent("glm-debug-worker")))

    def test_devteam_doctor_installs_programmer_lite_and_strong(self):
        r = self.install("--flash", "acct/Flash", "--main", "acct/Main")
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in ("glm-programmer-lite", "glm-programmer-strong"):
            fm = frontmatter(self.agent(name))
            for key in ("effort:", "hooks:", "isolation:", "memory:", "mode:", "temperature:"):
                self.assertNotIn("\n" + key, "\n" + fm, (name, key))
            self.assertIn("\nmodel: ", "\n" + fm, name)
            self.assertIn("\nthoughtLevel: ", "\n" + fm, name)

    def test_closing_message_claims(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("ZCode does not have", r.stdout)
        self.assertNotIn("Restart ZCode", r.stdout)
        self.assertIn("NEW ZCode session", r.stdout)
        self.assertIn("devteam.py doctor --harness zcode", r.stdout)
        self.assertIn("~/.zcode/cli/config.json", r.stdout)
        self.assertIn("truncated when loaded", r.stdout)


if __name__ == "__main__":
    unittest.main()
