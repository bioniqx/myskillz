"""install-all.sh end-to-end tests (temp HOME only; the real four-target install is S5).
The preflight cases pin review r1-3: every --only set must abort non-zero before the first
copy when the shared preflight rejects the tree, and the existing six test_install_all.py
cases must stay green."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

GLM_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCRIPT = os.path.join(GLM_ROOT, "install-all.sh")

# The eleven skills install-all.sh must install into every selected target.
SKILLS = (
    "glm-brainstorming",
    "glm-dev-team",
    "glm-doc-generator",
    "glm-find-skills",
    "glm-git-diff-summary",
    "glm-idea-to-spec",
    "glm-requirements-code-audit",
    "glm-systematic-debugging",
    "glm-video-shotcraft",
    "glm-viral-video-studio",
    "glm-writing-plans",
)


class InstallAllTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = self._tmp.name
        self.addCleanup(self._tmp.cleanup)
        self.xdg = os.path.join(self.home, ".config")

    def install_all(self, *args, root=None):
        root = root or GLM_ROOT
        env = dict(os.environ)
        env["HOME"] = self.home
        env["XDG_CONFIG_HOME"] = self.xdg
        return subprocess.run(
            ["sh", os.path.join(root, "install-all.sh"), "--home", self.home] + list(args),
            cwd=root, env=env, capture_output=True, text=True, timeout=300)

    def target(self, harness, *parts):
        roots = {
            "zcode": os.path.join(self.home, ".zcode"),
            "agents": os.path.join(self.home, ".agents"),
            "claude": os.path.join(self.home, ".claude"),
            "opencode": os.path.join(self.xdg, "opencode"),
        }
        return os.path.join(roots[harness], "skills", *parts)

    def source(self, *parts):
        return os.path.join(GLM_ROOT, *parts)

    def copied_tree(self):
        copy_root = os.path.join(self.home, "tree")
        shutil.copytree(GLM_ROOT, copy_root,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        return copy_root

    def test_dry_run_writes_nothing(self):
        r = self.install_all("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.listdir(self.home), [])

    def test_agents_and_claude_install_every_skill_as_is(self):
        copy_root = self.copied_tree()
        junk = os.path.join(copy_root, "glm-brainstorming", "__pycache__")
        os.makedirs(junk)
        with open(os.path.join(junk, "ask.pyc"), "wb") as fh:
            fh.write(b"\x00junk")
        with open(os.path.join(copy_root, "glm-brainstorming", ".DS_Store"), "wb") as fh:
            fh.write(b"\x00junk")
        r = self.install_all("--only", "agents,claude", root=copy_root)
        self.assertEqual(r.returncode, 0, r.stderr)
        for harness in ("agents", "claude"):
            for name in SKILLS:
                self.assertTrue(os.path.isfile(self.target(harness, name, "SKILL.md")), (harness, name))
            # as-is: the repo agents/ dir stays at the installed skill root, verbatim
            explorer = self.target(harness, "glm-brainstorming", "agents", "glm-explorer.md")
            self.assertTrue(os.path.isfile(explorer), harness)
            with open(explorer, encoding="utf-8") as fh:
                with open(self.source("glm-brainstorming", "agents", "glm-explorer.md"),
                          encoding="utf-8") as src:
                    self.assertEqual(fh.read(), src.read(), harness)
            for dirpath, dirnames, filenames in os.walk(os.path.dirname(self.target(harness, "x"))):
                self.assertNotIn("__pycache__", dirnames, dirpath)
                self.assertNotIn(".DS_Store", filenames, dirpath)
                self.assertFalse([f for f in filenames if f.endswith(".pyc")], dirpath)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode")))
        self.assertFalse(os.path.exists(os.path.join(self.xdg, "opencode")))

    def test_opencode_moves_agents_bumps_major_and_preserves_command_bodies(self):
        skill = self.target("opencode", "glm-brainstorming")
        os.makedirs(os.path.join(skill, "opencode", "commands"))
        with open(os.path.join(skill, ".oc-major"), "w", encoding="utf-8") as fh:
            fh.write("2\n")
        body = "# local opencode command body\nmust survive the reinstall byte-identically\n"
        with open(os.path.join(skill, "opencode", "commands", "glm-brainstorm.md"),
                  "w", encoding="utf-8") as fh:
            fh.write(body)
        r = self.install_all("--only", "opencode")
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in SKILLS:
            self.assertTrue(os.path.isfile(self.target("opencode", name, "SKILL.md")), name)
        # repo agents/ moved under opencode/agents/, verbatim; top-level agents/ gone
        moved = self.target("opencode", "glm-brainstorming", "opencode", "agents", "glm-explorer.md")
        self.assertTrue(os.path.isfile(moved))
        with open(moved, encoding="utf-8") as fh:
            with open(self.source("glm-brainstorming", "agents", "glm-explorer.md"),
                      encoding="utf-8") as src:
                self.assertEqual(fh.read(), src.read())
        self.assertFalse(os.path.exists(self.target("opencode", "glm-brainstorming", "agents")))
        self.assertTrue(os.path.isfile(
            self.target("opencode", "glm-dev-team", "opencode", "agents", "glm-team-leader.md")))
        self.assertFalse(os.path.exists(self.target("opencode", "glm-dev-team", "agents")))
        # .oc-major bumped from the pre-seeded 2
        with open(self.target("opencode", "glm-brainstorming", ".oc-major"), encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "3")
        # pre-existing opencode command body preserved byte-identically
        with open(os.path.join(skill, "opencode", "commands", "glm-brainstorm.md"),
                  encoding="utf-8") as fh:
            self.assertEqual(fh.read(), body)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".zcode")))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".agents")))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude")))

    def test_opencode_fresh_install_writes_oc_major_one(self):
        r = self.install_all("--only", "opencode")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(SKILLS), 11)
        for name in SKILLS:
            path = self.target("opencode", name, ".oc-major")
            self.assertTrue(os.path.isfile(path), name)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read().strip(), "1", name)

    def test_non_glm_folders_are_untouched(self):
        keep = "marker body\n"
        folders = [
            self.target("opencode", "oc-brainstorming"),
            self.target("agents", "foreign-agent"),
            self.target("claude", "foreign-skill"),
        ]
        for folder in folders:
            os.makedirs(os.path.join(folder, "nested"))
            with open(os.path.join(folder, "nested", "keep.md"), "w", encoding="utf-8") as fh:
                fh.write(keep)
        r = self.install_all("--only", "agents,claude,opencode")
        self.assertEqual(r.returncode, 0, r.stderr)
        for folder in folders:
            self.assertTrue(os.path.isdir(folder), folder)
            with open(os.path.join(folder, "nested", "keep.md"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), keep, folder)
        self.assertTrue(os.path.isfile(self.target("opencode", "glm-brainstorming", "SKILL.md")))
        self.assertTrue(os.path.isfile(self.target("agents", "glm-brainstorming", "SKILL.md")))
        self.assertTrue(os.path.isfile(self.target("claude", "glm-brainstorming", "SKILL.md")))

    def test_only_zcode_delegates_to_install_zcode(self):
        r = self.install_all("--only", "zcode")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(
            os.path.join(self.home, ".zcode", "skills", "glm-brainstorming", "SKILL.md")))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".agents")))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude")))
        self.assertFalse(os.path.exists(os.path.join(self.xdg, "opencode")))

    def test_over_1024_description_aborts_only_agents_with_nothing_installed(self):
        """Criterion: in a copied repo tree where one skill's frontmatter description exceeds 1024 characters,
        sh install-all.sh --home TMP --only agents exits non-zero and TMP contains no installed skill
        (preflight aborts before the first copy for target sets without zcode)."""
        copy_root = self.copied_tree()
        skill_md = os.path.join(copy_root, "glm-brainstorming", "SKILL.md")
        with open(skill_md, encoding="utf-8") as fh:
            text = fh.read()
        over, n = re.subn(r"(?m)^description:.*$", "description: " + "x" * (1024 + 1), text, count=1)
        self.assertEqual(n, 1)
        with open(skill_md, "w", encoding="utf-8") as fh:
            fh.write(over)
        r = self.install_all("--only", "agents", root=copy_root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("glm-brainstorming", r.stdout + r.stderr)
        self.assertEqual(os.listdir(self.home), ["tree"])

    def test_agent_model_line_aborts_only_opencode_with_nothing_written(self):
        """An agent file carrying a model: line aborts --only opencode non-zero before
        anything is written: the preflight must run for target sets without zcode."""
        copy_root = self.copied_tree()
        agent_md = os.path.join(copy_root, "glm-brainstorming", "agents", "glm-explorer.md")
        with open(agent_md, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        self.assertEqual(lines[0], "---")
        lines.insert(1, "model: glm-5.3")
        with open(agent_md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        r = self.install_all("--only", "opencode", root=copy_root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("glm-brainstorming", r.stdout + r.stderr)
        self.assertEqual(os.listdir(self.home), ["tree"])

    def test_opencode_dir_pruned_from_every_target_like_zcode(self):
        """A skill's opencode/ dir is install junk (install-zcode.sh parity): pruned from
        the agents and claude as-is copies, and from the opencode leg before the agents
        move and the saved-commands restore."""
        copy_root = self.copied_tree()
        leak = os.path.join(copy_root, "glm-brainstorming", "opencode")
        os.makedirs(leak)
        with open(os.path.join(leak, "local.md"), "w", encoding="utf-8") as fh:
            fh.write("# opencode-only content that must not leak to other targets\n")
        r = self.install_all("--only", "agents,claude,opencode", root=copy_root)
        self.assertEqual(r.returncode, 0, r.stderr)
        for harness in ("agents", "claude"):
            self.assertFalse(os.path.exists(self.target(harness, "glm-brainstorming", "opencode")), harness)
            self.assertTrue(os.path.isfile(self.target(harness, "glm-brainstorming", "SKILL.md")), harness)
        oc = self.target("opencode", "glm-brainstorming")
        self.assertFalse(os.path.exists(os.path.join(oc, "opencode", "local.md")))
        self.assertTrue(os.path.isfile(os.path.join(oc, "opencode", "agents", "glm-explorer.md")))


if __name__ == "__main__":
    unittest.main()
