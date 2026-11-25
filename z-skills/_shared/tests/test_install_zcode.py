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
        if name.startswith("z-") and os.path.isfile(os.path.join(root, name, "SKILL.md")):
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

    def test_skills_install_with_z_prefix_and_without_opencode_sources(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in SKILLS:
            self.assertTrue(os.path.isfile(self.skill(name, "SKILL.md")), name)
            self.assertFalse(os.path.exists(self.skill(name, "opencode")), name)
            self.assertTrue(name.startswith("z-"), name)
        for old in ("brainstorming", "brainstorming-glm"):
            self.assertFalse(os.path.exists(self.skill(old)), old)
        self.assertTrue(os.path.isfile(self.skill("z-dev-team", "scripts", "devteam.py")))

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
            self.assertNotRegex(fm, r"(?m)^model:", name)
            self.assertRegex(fm, r"(?m)^thoughtLevel:[ \t]*(low|high|max)[ \t]*$", name)

    def test_rerun_is_idempotent_and_replaces_changed_agents(self):
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual([f for f in os.listdir(self.agents_dir()) if f.endswith(".bak")], [])
        with open(self.agent("z-team-leader"), "a", encoding="utf-8") as fh:
            fh.write("my edit\n")
        self.assertEqual(self.install().returncode, 0)
        with open(self.agent("z-team-leader"), encoding="utf-8") as fh:
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
        # The new z- install still lands next to them.
        self.assertTrue(os.path.isfile(self.skill("z-brainstorming", "SKILL.md")))

    def test_flash_deepseek_stamps_installed_agents_only(self):
        r = self.install("--flash", "deepseek")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        pin = os.path.join(self.home, ".zcode", "z-flash")
        with open(pin, encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "deepseek")
        installed = open(self.agent("z-explorer"), encoding="utf-8").read()
        source = open(self.source_agent("z-explorer"), encoding="utf-8").read()
        self.assertNotIn("\nmodel:", "\n" + installed)
        self.assertNotIn("\nmodel:", "\n" + source)
        self.assertIn("thoughtLevel: high", installed)
        skill_agent = self.skill("z-brainstorming", "agents", "z-explorer.md")
        with open(skill_agent, encoding="utf-8") as fh:
            self.assertNotIn("\nmodel:", "\n" + fh.read())
        self.assertIn("stamped", r.stdout)

    def test_reinstall_keeps_deepseek_pin_and_glm_flag_reverts_it(self):
        self.assertEqual(self.install("--flash", "deepseek").returncode, 0)
        foreign = os.path.join(self.home, ".zcode", "notes", "keep.md")
        os.makedirs(os.path.dirname(foreign))
        marker = 'model: "account:zai-individual-coding-plan/GLM-5.3-Flash"\n'
        with open(foreign, "w", encoding="utf-8") as fh:
            fh.write(marker)
        again = self.install()
        self.assertEqual(again.returncode, 0, again.stderr + again.stdout)
        with open(os.path.join(self.home, ".zcode", "z-flash"), encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "deepseek")
        with open(self.agent("z-explorer"), encoding="utf-8") as fh:
            self.assertNotIn("\nmodel:", "\n" + fh.read())
        with open(foreign, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), marker)
        back = self.install("--flash", "glm")
        self.assertEqual(back.returncode, 0, back.stderr + back.stdout)
        with open(self.agent("z-explorer"), encoding="utf-8") as fh:
            self.assertNotIn("\nmodel:", "\n" + fh.read())
        with open(foreign, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), marker)

    def _saved_pin(self, word):
        pin = os.path.join(self.home, ".zcode", "z-flash")
        os.makedirs(os.path.dirname(pin))
        with open(pin, "w", encoding="utf-8") as fh:
            fh.write(word)
        return pin

    @staticmethod
    def _pin_word(pin):
        with open(pin, encoding="utf-8") as fh:
            return fh.read().strip()

    def test_saved_pro_pin_word_keeps_the_deepseek_provider_and_the_word(self):
        pin = self._saved_pin("deepseek-v4-pro\n")
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("pin: deepseek", r.stdout)
        self.assertEqual(self._pin_word(pin), "deepseek-v4-pro")
        again = self.install()
        self.assertEqual(again.returncode, 0, again.stderr + again.stdout)
        self.assertIn("pin: deepseek", again.stdout)
        self.assertEqual(self._pin_word(pin), "deepseek-v4-pro")

    def test_saved_glm_5_4_pin_word_keeps_the_glm_provider_and_the_word(self):
        pin = self._saved_pin("glm-5.4\n")
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("pin: glm", r.stdout)
        self.assertEqual(self._pin_word(pin), "glm-5.4")

    def test_explicit_flash_flag_replaces_a_saved_pro_word(self):
        pin = self._saved_pin("glm-5.3\n")
        r = self.install("--flash", "deepseek")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual(self._pin_word(pin), "deepseek")

    def test_unknown_saved_pin_word_falls_back_to_glm(self):
        pin = self._saved_pin("nonsense\n")
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual(self._pin_word(pin), "glm")

    def test_flash_deepseek_dry_run_writes_nothing(self):
        r = self.install("--dry-run", "--flash", "deepseek")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode")))
        self.assertIn("pin: deepseek", r.stdout)
        self.assertIn("Nothing written.", r.stdout)

    def test_flash_rejects_an_unknown_name(self):
        r = self.install("--flash", "opus")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("glm or deepseek", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode")))

    def test_dry_run_writes_nothing(self):
        r = self.install("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode", "skills", "z-brainstorming")))
        self.assertFalse(os.path.exists(self.agents_dir()))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode", "commands")))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode", "z-skills-manifest.txt")))
        self.assertIn("Nothing written.", r.stdout)
        self.assertNotIn("\nDone.", r.stdout)

    def test_oversize_description_is_rejected_before_any_copy(self):
        copy_root = self.copied_tree()
        skill_md = os.path.join(copy_root, "z-git-diff-summary", "SKILL.md")
        with open(skill_md, encoding="utf-8") as fh:
            text = fh.read()
        with open(skill_md, "w", encoding="utf-8") as fh:
            fh.write(text.replace("description: ", "description: " + "x" * 1100, 1))
        r = self.install(root=copy_root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("1024", r.stderr)
        self.assertFalse(os.path.exists(self.skill("z-git-diff-summary")))

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
        self.assertIn(self.skill("z-brainstorming") + "/", out)
        self.assertIn("invoke $z-brainstorming", out)
        self.assertIn("    SKILL.md\n", out)
        self.assertIn("    scripts/context.sh\n", out)
        self.assertIn("    scripts/devteam.py\n", out)
        self.assertIn("    scripts/debug_tool.py\n", out)
        self.assertIn("z-brainstorming/agents/z-drafter.md  ->  " + self.agent("z-drafter"), out)
        self.assertIn("z-dev-team/agents/z-team-leader.md  ->  " + self.agent("z-team-leader"), out)
        self.assertIn("z-systematic-debugging/agents/z-debug-worker.md  ->  " + self.agent("z-debug-worker"), out)
        cmd = os.path.join(self.home, ".zcode", "commands", "z-brainstorm.md")
        self.assertIn("z-brainstorming/commands/z-brainstorm.md  ->  " + cmd, out)
        self.assertIn("/z-brainstorm", out)
        self.assertIn("/z-devteam", out)
        self.assertIn("/z-plan", out)
        self.assertIn("cli/config.json", out)
        self.assertRegex(out, r"\d+ files in %d skill folders" % len(SKILLS))
        self.assertRegex(out, r"%d agent files -> " % len(AGENTS))
        self.assertRegex(out, r"%d command files -> " % len(discover_commands(GLM_ROOT, SKILLS)))
        self.assertIn("z-viral-video-studio/", out)

    def test_closing_message_claims(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("ZCode does not have", r.stdout)
        self.assertNotIn("Restart ZCode", r.stdout)
        self.assertIn("NEW ZCode session", r.stdout)
        self.assertIn("devteam.py doctor --harness zcode", r.stdout)
        self.assertIn("~/.zcode/cli/config.json", r.stdout)
        self.assertIn("truncated when loaded", r.stdout)
        self.assertIn("/z-brainstorm", r.stdout)

    def test_commands_are_installed_with_the_skill_path_filled_in(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        skill_dir = self.skill("z-brainstorming")
        live = os.path.join(self.home, ".zcode", "commands", "z-brainstorm.md")
        inside = self.skill("z-brainstorming", "commands", "z-brainstorm.md")
        with open(live, encoding="utf-8") as fh:
            text = fh.read()
        with open(inside, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), text)
        self.assertNotIn("{{SKILL_DIR}}", text)
        self.assertNotIn("!`", text)
        self.assertIn("sh " + skill_dir + "/scripts/context.sh", text)
        for name, folder in (("z-devteam.md", "z-dev-team"), ("z-plan.md", "z-writing-plans")):
            path = os.path.join(self.home, ".zcode", "commands", name)
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            self.assertNotIn("{{SKILL_DIR}}", body)
            self.assertIn(self.skill(folder), body)
        manifest = os.path.join(self.home, ".zcode", "z-skills-manifest.txt")
        with open(manifest, encoding="utf-8") as fh:
            listed = fh.read().split()
        self.assertIn("commands/z-brainstorm.md", listed)
        self.assertIn("agents/z-debug-worker.md", listed)
        self.assertEqual(self.install().returncode, 0)

    def test_rerun_drops_manifested_files_and_keeps_foreign_ones(self):
        self.assertEqual(self.install().returncode, 0)
        retired = self.agent("z-retired")
        foreign = self.agent("my-custom")
        old_cmd = os.path.join(self.home, ".zcode", "commands", "z-old.md")
        keep_cmd = os.path.join(self.home, ".zcode", "commands", "my-alias.md")
        for path, text in ((retired, "old\n"), (foreign, "keep\n"), (old_cmd, "old\n"), (keep_cmd, "keep\n")):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        manifest = os.path.join(self.home, ".zcode", "z-skills-manifest.txt")
        with open(manifest, "a", encoding="utf-8") as fh:
            fh.write("agents/z-retired.md\ncommands/z-old.md\n")
        self.assertEqual(self.install().returncode, 0)
        self.assertFalse(os.path.exists(retired))
        self.assertFalse(os.path.exists(old_cmd))
        self.assertTrue(os.path.isfile(foreign))
        self.assertTrue(os.path.isfile(keep_cmd))
        self.assertTrue(os.path.isfile(self.agent("z-team-leader")))
        with open(manifest, encoding="utf-8") as fh:
            listed = fh.read()
        self.assertNotIn("z-retired", listed)
        self.assertNotIn("z-old", listed)

    def test_discovers_new_z_folder_with_skill_md(self):
        copy_root = self.copied_tree()
        new = os.path.join(copy_root, "z-newskill")
        os.makedirs(new)
        with open(os.path.join(new, "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nname: z-newskill\n"
                     "description: Use when testing installer discovery of a new glm folder.\n"
                     "---\n\nBody.\n")
        r = self.install(root=copy_root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(self.skill("z-newskill", "SKILL.md")))
        self.assertIn("invoke $z-newskill", r.stdout)

    def test_skips_z_folder_without_skill_md(self):
        copy_root = self.copied_tree()
        os.makedirs(os.path.join(copy_root, "z-not-a-skill", "scripts"))
        r = self.install(root=copy_root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(self.skill("z-not-a-skill")))
        self.assertIn("z-not-a-skill/", r.stdout)
        self.assertIn("no SKILL.md at root", r.stdout)
        # z-viral-video-studio is a real skill now: test_skills_install and the
        # inventory test above both require it to install.
        self.assertTrue(os.path.exists(self.skill("z-viral-video-studio")))

    def test_missing_home_is_rejected(self):
        env = dict(os.environ)
        env.pop("HOME", None)
        r = subprocess.run(["sh", SCRIPT], capture_output=True, text=True, env=env, timeout=30)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("HOME", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode")))

    def test_skill_name_is_not_checked(self):
        copy_root = self.copied_tree()
        skill_md = os.path.join(copy_root, "z-idea-to-spec", "SKILL.md")
        with open(skill_md, encoding="utf-8") as fh:
            text = fh.read()
        with open(skill_md, "w", encoding="utf-8") as fh:
            fh.write(text.replace("name: z-idea-to-spec\n", "name: some-other-name\n", 1))
        r = self.install(root=copy_root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(self.skill("z-idea-to-spec", "SKILL.md")))
        with open(self.skill("z-idea-to-spec", "SKILL.md"), encoding="utf-8") as fh:
            self.assertIn("name: some-other-name\n", fh.read())

    def test_agent_with_hardcoded_model_is_rejected_before_any_copy(self):
        copy_root = self.copied_tree()
        agent = os.path.join(copy_root, "z-systematic-debugging", "agents", "z-debug-worker.md")
        with open(agent, encoding="utf-8") as fh:
            text = fh.read()
        with open(agent, "w", encoding="utf-8") as fh:
            fh.write(text.replace("thoughtLevel:", 'model: "deepseek/deepseek-flash"\nthoughtLevel:', 1))
        r = self.install(root=copy_root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("hardcodes a model", r.stderr)
        self.assertFalse(os.path.exists(self.agent("z-debug-worker")))


if __name__ == "__main__":
    unittest.main()
