import os
import shutil
import subprocess
import tempfile
import unittest

GLM_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCRIPT = os.path.join(GLM_ROOT, "install-dsh.sh")


def discover_skills(root):
    names = []
    for name in sorted(os.listdir(root)):
        if name.startswith("glm-") and os.path.isfile(os.path.join(root, name, "SKILL.md")):
            names.append(name)
    return names


SKILLS = discover_skills(GLM_ROOT)


class InstallDshTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def run_install(self, *args, root=None, dsh_home=None, with_home=True):
        env = dict(os.environ)
        env.pop("DSH_HOME", None)
        if dsh_home is not None:
            env["DSH_HOME"] = dsh_home
        if with_home:
            env["HOME"] = self.home
        else:
            env.pop("HOME", None)
        return subprocess.run(["sh", os.path.join(root or GLM_ROOT, "install-dsh.sh")] + list(args),
                              capture_output=True, text=True, timeout=120, env=env)

    def target(self, *parts):
        return os.path.join(self.home, ".dsh", "skills", *parts)

    def copied_tree(self):
        copy_root = os.path.join(self.home, "tree")
        shutil.copytree(GLM_ROOT, copy_root,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        return copy_root

    def test_dry_run_writes_nothing(self):
        r = self.run_install("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.listdir(self.home), [])
        self.assertIn("Nothing written.", r.stdout)
        self.assertIn("files in %d skill folders" % len(SKILLS), r.stdout)

    def test_installs_every_skill_as_is_and_prunes_junk(self):
        copy_root = self.copied_tree()
        junk = os.path.join(copy_root, "glm-brainstorming", "__pycache__")
        os.makedirs(junk)
        with open(os.path.join(junk, "ask.pyc"), "wb") as fh:
            fh.write(b"\x00junk")
        with open(os.path.join(copy_root, "glm-brainstorming", ".DS_Store"), "wb") as fh:
            fh.write(b"\x00junk")
        r = self.run_install(root=copy_root)
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in SKILLS:
            self.assertTrue(os.path.isfile(self.target(name, "SKILL.md")), name)
        for dirpath, dirnames, filenames in os.walk(os.path.dirname(self.target())):
            self.assertNotIn("__pycache__", dirnames, dirpath)
            self.assertNotIn(".DS_Store", filenames, dirpath)
            self.assertFalse([f for f in filenames if f.endswith(".pyc")], dirpath)
        with open(self.target("glm-brainstorming", "agents", "glm-explorer.md"), encoding="utf-8") as fh:
            with open(os.path.join(GLM_ROOT, "glm-brainstorming", "agents", "glm-explorer.md"),
                      encoding="utf-8") as src:
                self.assertEqual(fh.read(), src.read())

    def test_home_flag_and_dsh_home_env_pick_the_root(self):
        by_flag = os.path.join(self.home, "flagroot")
        r = self.run_install("--home", by_flag)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(by_flag, "skills", "glm-brainstorming", "SKILL.md")))
        self.assertFalse(os.path.exists(self.target()))
        by_env = os.path.join(self.home, "envroot")
        r = self.run_install(dsh_home=by_env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(by_env, "skills", "glm-brainstorming", "SKILL.md")))
        flag_and_env = os.path.join(self.home, "bothroot")
        r = self.run_install("--home", flag_and_env, dsh_home=os.path.join(self.home, "ignored"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(flag_and_env, "skills", "glm-brainstorming", "SKILL.md")))
        self.assertFalse(os.path.exists(os.path.join(self.home, "ignored")))

    def test_oversize_description_is_rejected_before_any_copy(self):
        copy_root = self.copied_tree()
        skill_md = os.path.join(copy_root, "glm-git-diff-summary", "SKILL.md")
        with open(skill_md, encoding="utf-8") as fh:
            text = fh.read()
        with open(skill_md, "w", encoding="utf-8") as fh:
            fh.write(text.replace("description: ", "description: " + "x" * 1100, 1))
        r = self.run_install(root=copy_root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("1024", r.stderr)
        self.assertEqual(os.listdir(self.home), ["tree"])

    def test_non_kebab_case_name_is_rejected_before_any_copy(self):
        copy_root = self.copied_tree()
        skill_md = os.path.join(copy_root, "glm-idea-to-spec", "SKILL.md")
        with open(skill_md, encoding="utf-8") as fh:
            text = fh.read()
        with open(skill_md, "w", encoding="utf-8") as fh:
            fh.write(text.replace("name: glm-idea-to-spec\n", "name: Not Kebab!\n", 1))
        r = self.run_install(root=copy_root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("kebab-case", r.stderr)
        self.assertEqual(os.listdir(self.home), ["tree"])

    def test_tree_without_installable_skills_fails_loudly(self):
        copy_root = self.copied_tree()
        for name in SKILLS:
            os.remove(os.path.join(copy_root, name, "SKILL.md"))
        r = self.run_install(root=copy_root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no glm-*/SKILL.md", r.stderr)

    def test_foreign_and_stale_folders_are_warned_not_touched(self):
        foreign = self.target("my-own-skill", "nested")
        os.makedirs(foreign)
        with open(os.path.join(foreign, "keep.md"), "w", encoding="utf-8") as fh:
            fh.write("keep\n")
        stale = self.target("brainstorming")
        os.makedirs(stale)
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isdir(foreign))
        with open(os.path.join(foreign, "keep.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "keep\n")
        self.assertIn("WARN: stale: " + stale, r.stdout)
        self.assertTrue(os.path.isdir(stale))
        self.assertTrue(os.path.isfile(self.target("glm-brainstorming", "SKILL.md")))

    def test_rerun_is_idempotent_and_replaces_changed_files(self):
        self.assertEqual(self.run_install().returncode, 0)
        installed = self.target("glm-brainstorming", "SKILL.md")
        with open(installed, "a", encoding="utf-8") as fh:
            fh.write("my edit\n")
        self.assertEqual(self.run_install().returncode, 0)
        with open(installed, encoding="utf-8") as fh:
            self.assertNotIn("my edit", fh.read())
        for dirpath, dirnames, filenames in os.walk(os.path.dirname(self.target())):
            self.assertEqual([f for f in filenames if f.endswith(".bak")], [], dirpath)

    def test_inventory_prints_dest_and_counts(self):
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        self.assertIn("dest: " + self.target() + "/", out)
        self.assertIn("    SKILL.md\n", out)
        self.assertIn("  " + self.target("glm-brainstorming") + "/", out)
        self.assertIn("files in %d skill folders" % len(SKILLS), out)
        self.assertEqual(len(SKILLS), 11)

    def test_missing_home_is_rejected(self):
        r = self.run_install(with_home=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("HOME", r.stderr)
        self.assertEqual(os.listdir(self.home), [])


if __name__ == "__main__":
    unittest.main()
