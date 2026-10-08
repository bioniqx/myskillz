import os
import shutil
import subprocess
import tempfile
import unittest

GLM_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCRIPT = os.path.join(GLM_ROOT, "install-zcode.sh")
SKILLS = ["glm-brainstorming", "glm-dev-team", "glm-doc-generator", "glm-git-diff-summary", "glm-idea-to-spec", "glm-requirements-code-audit",
          "glm-systematic-debugging", "glm-writing-plans"]
AGENTS = ["glm-code-reviewer", "glm-debug-worker", "glm-doc-reviewer", "glm-doc-writer", "glm-explorer", "glm-investigator",
          "glm-plan-reviewer", "glm-plan-task-writer", "glm-plan-task-writer-deep", "glm-programmer", "glm-programmer-lite",
          "glm-programmer-strong", "glm-rca-investigator", "glm-rca-verifier", "glm-researcher", "glm-spot-reviewer", "glm-team-leader"]
ALLOWED_KEYS = {"name", "description", "model", "thoughtLevel", "color", "tools", "disallowedTools",
                "maxTurns", "background", "injectAgentsMd", "mcpServers"}


def frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().split("\n---\n")[0]


def fm_keys(fm):
    keys = set()
    for line in fm.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or line[:1] in (" ", "\t"):
            continue
        if ":" in line:
            keys.add(line.split(":", 1)[0].strip())
    return keys


class InstallZcodeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def install(self, *args, root=None):
        return subprocess.run(["sh", os.path.join(root or GLM_ROOT, "install-zcode.sh"),
                               "--home", self.home] + list(args),
                              capture_output=True, text=True, timeout=120)

    def skill(self, name, *parts):
        return os.path.join(self.home, ".zcode", "skills", name, *parts)

    def agents_dir(self):
        return os.path.join(self.home, ".zcode", "agents")

    def agent(self, name):
        return self.agent_in(self.agents_dir(), name)

    @staticmethod
    def agent_in(agents_dir, name):
        return os.path.join(agents_dir, name + ".md")

    def source_agent(self, name):
        for skill in SKILLS:
            path = os.path.join(GLM_ROOT, skill, "agents", name + ".md")
            if os.path.isfile(path):
                return path
        raise AssertionError(name)

    def copied_tree(self):
        copy_root = os.path.join(self.home, "tree")
        shutil.copytree(GLM_ROOT, copy_root,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        return copy_root

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

    def test_every_source_agent_is_installed_and_nothing_else(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        source_names = []
        for skill in SKILLS:
            agents = os.path.join(GLM_ROOT, skill, "agents")
            if os.path.isdir(agents):
                source_names += [f[:-3] for f in os.listdir(agents) if f.endswith(".md")]
        source_names.sort()
        self.assertEqual(sorted(AGENTS), source_names, "the AGENTS list must match the repo tree")
        self.assertEqual(sorted(os.listdir(self.agents_dir())), sorted(n + ".md" for n in source_names))
        for name in source_names:
            with open(self.source_agent(name), encoding="utf-8") as fh:
                self.assertEqual(open(self.agent(name), encoding="utf-8").read(), fh.read(), name)

    def test_agent_files_carry_final_zcode_frontmatter(self):
        for name in AGENTS:
            fm = frontmatter(self.source_agent(name))
            self.assertTrue(fm_keys(fm) <= ALLOWED_KEYS, (name, sorted(fm_keys(fm) - ALLOWED_KEYS)))
            for bad in ("effort:", "steps:", "omitClaudeMd:", "permissionMode:", "access:", "bash:", "web:", "hooks:"):
                self.assertNotIn("\n" + bad, "\n" + fm, (name, bad))
            for alias in ("haiku", "sonnet", "opus"):
                self.assertNotIn("\nmodel: " + alias, "\n" + fm, (name, alias))
            self.assertRegex(fm, r'(?m)^model: "?account:zai-', name)

    def test_rerun_is_idempotent_and_replaces_changed_agents(self):
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual([f for f in os.listdir(self.agents_dir()) if f.endswith(".bak")], [])
        with open(self.agent("glm-programmer"), "a", encoding="utf-8") as fh:
            fh.write("my edit\n")
        self.assertEqual(self.install().returncode, 0)
        with open(self.agent("glm-programmer"), encoding="utf-8") as fh:
            self.assertNotIn("my edit", fh.read())
        self.assertEqual([f for f in os.listdir(self.agents_dir()) if f.endswith(".bak")], [])

    def test_installer_only_copies_no_hooks_no_config(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode", "cli", "config.json")))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude")))

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
        self.assertFalse(os.path.exists(self.agents_dir()))

    def test_oversize_description_is_rejected_before_any_copy(self):
        copy_root = self.copied_tree()
        skill_md = os.path.join(copy_root, "glm-git-diff-summary", "SKILL.md")
        with open(skill_md, encoding="utf-8") as fh:
            text = fh.read()
        with open(skill_md, "w", encoding="utf-8") as fh:
            fh.write(text.replace("description: ", "description: " + "x" * 1100, 1))
        r = self.install(root=copy_root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("1024", r.stderr)
        self.assertFalse(os.path.exists(self.skill("glm-git-diff-summary")))

    def test_a_tree_without_agent_sources_fails_loudly(self):
        copy_root = self.copied_tree()
        for skill in SKILLS:
            shutil.rmtree(os.path.join(copy_root, skill, "agents"), ignore_errors=True)
        r = self.install(root=copy_root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no agents", r.stderr)

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
