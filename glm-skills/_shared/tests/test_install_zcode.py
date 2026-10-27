import os
import shutil
import subprocess
import tempfile
import unittest

GLM_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCRIPT = os.path.join(GLM_ROOT, "install-zcode.sh")


def discover_skills(root):
    names = []
    for name in sorted(os.listdir(root)):
        if name.startswith("glm-") and os.path.isfile(os.path.join(root, name, "SKILL.md")):
            names.append(name)
    return names


def discover_agents(root, skills):
    names = []
    for skill in skills:
        agents = os.path.join(root, skill, "agents")
        if os.path.isdir(agents):
            names += [f[:-3] for f in os.listdir(agents) if f.endswith(".md")]
    return sorted(names)


def discover_commands(root, skills):
    names = []
    for skill in skills:
        commands = os.path.join(root, skill, "commands")
        if os.path.isdir(commands):
            names += [f for f in os.listdir(commands) if f.endswith(".md")]
    return sorted(names)


SKILLS = discover_skills(GLM_ROOT)
AGENTS = discover_agents(GLM_ROOT, SKILLS)
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
        with open(self.agent("glm-team-leader"), "a", encoding="utf-8") as fh:
            fh.write("my edit\n")
        self.assertEqual(self.install().returncode, 0)
        with open(self.agent("glm-team-leader"), encoding="utf-8") as fh:
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
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode", "commands")))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode", "glm-skills-manifest.txt")))
        self.assertIn("Nothing written.", r.stdout)
        self.assertNotIn("\nDone.", r.stdout)

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

    def test_install_prints_full_inventory(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        self.assertIn("dest: " + os.path.join(self.home, ".zcode", "skills") + "/", out)
        self.assertIn(self.skill("glm-brainstorming") + "/", out)
        self.assertIn("invoke $glm-brainstorming", out)
        self.assertIn("    SKILL.md\n", out)
        self.assertIn("    scripts/context.sh\n", out)
        self.assertIn("    scripts/devteam.py\n", out)
        self.assertIn("    scripts/debug_tool.py\n", out)
        self.assertIn("glm-brainstorming/agents/glm-drafter.md  ->  " + self.agent("glm-drafter"), out)
        self.assertIn("glm-dev-team/agents/glm-team-leader.md  ->  " + self.agent("glm-team-leader"), out)
        self.assertIn("glm-systematic-debugging/agents/glm-debug-worker.md  ->  " + self.agent("glm-debug-worker"), out)
        cmd = os.path.join(self.home, ".zcode", "commands", "glm-brainstorm.md")
        self.assertIn("glm-brainstorming/commands/glm-brainstorm.md  ->  " + cmd, out)
        self.assertIn("/glm-brainstorm", out)
        self.assertIn("/glm-devteam", out)
        self.assertIn("/glm-plan", out)
        self.assertIn("cli/config.json", out)
        self.assertRegex(out, r"\d+ files in %d skill folders" % len(SKILLS))
        self.assertRegex(out, r"%d agent files -> " % len(AGENTS))
        self.assertRegex(out, r"%d command files -> " % len(discover_commands(GLM_ROOT, SKILLS)))
        self.assertIn("glm-viral-video-studio/", out)
        self.assertIn("no SKILL.md at root", out)

    def test_closing_message_claims(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("ZCode does not have", r.stdout)
        self.assertNotIn("Restart ZCode", r.stdout)
        self.assertIn("NEW ZCode session", r.stdout)
        self.assertIn("devteam.py doctor --harness zcode", r.stdout)
        self.assertIn("~/.zcode/cli/config.json", r.stdout)
        self.assertIn("truncated when loaded", r.stdout)
        self.assertIn("/glm-brainstorm", r.stdout)

    def test_commands_are_installed_with_the_skill_path_filled_in(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        skill_dir = self.skill("glm-brainstorming")
        live = os.path.join(self.home, ".zcode", "commands", "glm-brainstorm.md")
        inside = self.skill("glm-brainstorming", "commands", "glm-brainstorm.md")
        with open(live, encoding="utf-8") as fh:
            text = fh.read()
        with open(inside, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), text)
        self.assertNotIn("{{SKILL_DIR}}", text)
        self.assertNotIn("!`", text)
        self.assertIn("sh " + skill_dir + "/scripts/context.sh", text)
        for name, folder in (("glm-devteam.md", "glm-dev-team"), ("glm-plan.md", "glm-writing-plans")):
            path = os.path.join(self.home, ".zcode", "commands", name)
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            self.assertNotIn("{{SKILL_DIR}}", body)
            self.assertIn(self.skill(folder), body)
        manifest = os.path.join(self.home, ".zcode", "glm-skills-manifest.txt")
        with open(manifest, encoding="utf-8") as fh:
            listed = fh.read().split()
        self.assertIn("commands/glm-brainstorm.md", listed)
        self.assertIn("agents/glm-debug-worker.md", listed)
        self.assertEqual(self.install().returncode, 0)

    def test_rerun_drops_manifested_files_and_keeps_foreign_ones(self):
        self.assertEqual(self.install().returncode, 0)
        retired = self.agent("glm-retired")
        foreign = self.agent("my-custom")
        old_cmd = os.path.join(self.home, ".zcode", "commands", "glm-old.md")
        keep_cmd = os.path.join(self.home, ".zcode", "commands", "my-alias.md")
        for path, text in ((retired, "old\n"), (foreign, "keep\n"), (old_cmd, "old\n"), (keep_cmd, "keep\n")):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        manifest = os.path.join(self.home, ".zcode", "glm-skills-manifest.txt")
        with open(manifest, "a", encoding="utf-8") as fh:
            fh.write("agents/glm-retired.md\ncommands/glm-old.md\n")
        self.assertEqual(self.install().returncode, 0)
        self.assertFalse(os.path.exists(retired))
        self.assertFalse(os.path.exists(old_cmd))
        self.assertTrue(os.path.isfile(foreign))
        self.assertTrue(os.path.isfile(keep_cmd))
        self.assertTrue(os.path.isfile(self.agent("glm-team-leader")))
        with open(manifest, encoding="utf-8") as fh:
            listed = fh.read()
        self.assertNotIn("glm-retired", listed)
        self.assertNotIn("glm-old", listed)

    def test_discovers_new_glm_folder_with_skill_md(self):
        copy_root = self.copied_tree()
        new = os.path.join(copy_root, "glm-newskill")
        os.makedirs(new)
        with open(os.path.join(new, "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nname: glm-newskill\n"
                     "description: Use when testing installer discovery of a new glm folder.\n"
                     "---\n\nBody.\n")
        r = self.install(root=copy_root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(self.skill("glm-newskill", "SKILL.md")))
        self.assertIn("invoke $glm-newskill", r.stdout)

    def test_skips_glm_folder_without_skill_md(self):
        copy_root = self.copied_tree()
        os.makedirs(os.path.join(copy_root, "glm-not-a-skill", "scripts"))
        r = self.install(root=copy_root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(self.skill("glm-not-a-skill")))
        self.assertIn("glm-not-a-skill/", r.stdout)
        self.assertIn("no SKILL.md at root", r.stdout)
        self.assertFalse(os.path.exists(self.skill("glm-viral-video-studio")))

    def test_missing_home_is_rejected(self):
        env = dict(os.environ)
        env.pop("HOME", None)
        r = subprocess.run(["sh", SCRIPT], capture_output=True, text=True, env=env, timeout=30)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("HOME", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode")))

    def test_skill_name_is_not_checked(self):
        copy_root = self.copied_tree()
        skill_md = os.path.join(copy_root, "glm-idea-to-spec", "SKILL.md")
        with open(skill_md, encoding="utf-8") as fh:
            text = fh.read()
        with open(skill_md, "w", encoding="utf-8") as fh:
            fh.write(text.replace("name: glm-idea-to-spec\n", "name: some-other-name\n", 1))
        r = self.install(root=copy_root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(self.skill("glm-idea-to-spec", "SKILL.md")))
        with open(self.skill("glm-idea-to-spec", "SKILL.md"), encoding="utf-8") as fh:
            self.assertIn("name: some-other-name\n", fh.read())

    def test_agent_without_model_is_rejected_before_any_copy(self):
        copy_root = self.copied_tree()
        agent = os.path.join(copy_root, "glm-systematic-debugging", "agents", "glm-debug-worker.md")
        with open(agent, encoding="utf-8") as fh:
            text = fh.read()
        with open(agent, "w", encoding="utf-8") as fh:
            fh.write(text.replace('model: "account:zai-individual-coding-plan/GLM-5.3-Flash"\n', "", 1))
        r = self.install(root=copy_root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("model", r.stderr)
        self.assertFalse(os.path.exists(self.agent("glm-debug-worker")))


if __name__ == "__main__":
    unittest.main()
