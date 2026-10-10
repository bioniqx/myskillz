import glob
import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GATHER = os.path.join(HERE, "..", "..", "glm-git-diff-summary", "scripts", "gather.sh")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _write_file(path, lines):
    stem = os.path.basename(path).rsplit(".", 1)[0]
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(1, lines + 1):
            fh.write("%s line %03d\n" % (stem, i))


class GatherMicroTestCase(unittest.TestCase):
    """Drive gather.sh in throwaway repos; PATH shims count tool invocations."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gather-micro-")
        self.bin = os.path.join(self.tmp, "bin")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def shim(self, real, log_var, log_path):
        os.makedirs(self.bin, exist_ok=True)
        name = os.path.basename(real)
        path = os.path.join(self.bin, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\n"
                     "printf '%%s\\n' \"$*\" >> \"$%s\"\n"
                     "exec '%s' \"$@\"\n" % (log_var, real))
        os.chmod(path, 0o755)
        return log_path

    def make_repo(self, name, default_branch="main", change_base=True):
        root = os.path.join(self.tmp, name)
        os.makedirs(root)
        _git(root, "init", "-q", "-b", default_branch)
        _git(root, "config", "user.email", "test@example.com")
        _git(root, "config", "user.name", "Test")
        _write_file(os.path.join(root, "base.txt"), 3)
        _git(root, "add", ".")
        _git(root, "commit", "-qm", "base")
        _git(root, "checkout", "-qb", "feature")
        if change_base:
            _write_file(os.path.join(root, "base.txt"), 4)
            _git(root, "commit", "-qam", "change")
        return root

    def add_files(self, root, count, lines=200):
        for n in range(1, count + 1):
            _write_file(os.path.join(root, "f%03d.txt" % n), lines)
        _git(root, "add", ".")
        _git(root, "commit", "-qm", "bulk")

    def gather(self, repo, log_var=None, log_path=None, extra=None):
        env = dict(os.environ)
        env["GLM_GDS_NO_FETCH"] = "1"
        env["TMPDIR"] = self.tmp
        env["PATH"] = self.bin + os.pathsep + env["PATH"]
        if log_var:
            env[log_var] = log_path
        env.update(extra or {})
        proc = subprocess.run(["bash", GATHER], cwd=repo, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        out = proc.stdout.decode("utf-8", "replace")
        self.assertEqual(proc.returncode, 0, out + proc.stderr.decode("utf-8", "replace"))
        return out


class BatchedBaseProbeTests(GatherMicroTestCase):
    def test_script_probes_base_with_one_batched_refs_query(self):
        with open(GATHER, encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("for c in main master develop trunk", text,
                         "candidate probing must not be a serial rev-parse loop")
        self.assertEqual(text.count("for-each-ref"), 1,
                         "candidate probing must be one batched for-each-ref query")

    def test_probe_issues_no_serial_rev_parse_calls(self):
        repo = self.make_repo("probe", default_branch="trunk")
        log = self.shim(shutil.which("git"), "GLM_GDS_GITLOG",
                        os.path.join(self.tmp, "git.log"))
        out = self.gather(repo, "GLM_GDS_GITLOG", log)
        self.assertIn(" REF=trunk MB=", out)
        with open(log, encoding="utf-8") as fh:
            probes = [line for line in fh.read().splitlines()
                      if "rev-parse" in line and "--verify" in line]
        self.assertEqual(len(probes), 1,
                         "pick_ref keeps exactly one verify; the candidate probe must add none")

    def test_candidate_and_remote_preference_order_unchanged(self):
        main_master = self.make_repo("mm")
        _git(main_master, "branch", "master")
        self.assertIn(" REF=main MB=", self.gather(main_master))

        dev_trunk = self.make_repo("dt", default_branch="develop")
        _git(dev_trunk, "branch", "trunk")
        self.assertIn(" REF=develop MB=", self.gather(dev_trunk))

        origin = os.path.join(self.tmp, "origin.git")
        _git(self.tmp, "init", "-q", "--bare", origin)
        _git(dev_trunk, "remote", "add", "origin", origin)
        _git(dev_trunk, "push", "-q", "origin", "develop:refs/heads/trunk")
        _git(dev_trunk, "fetch", "-q", "origin")
        self.assertIn(" REF=develop MB=", self.gather(dev_trunk))

        remote_main = self.make_repo("rmrepo")
        origin2 = os.path.join(self.tmp, "origin2.git")
        _git(self.tmp, "init", "-q", "--bare", origin2)
        _git(remote_main, "remote", "add", "origin", origin2)
        _git(remote_main, "push", "-q", "origin", "main")
        _git(remote_main, "fetch", "-q", "origin")
        self.assertIn(" REF=origin/main MB=", self.gather(remote_main))


class SinglePassChunkingTests(GatherMicroTestCase):
    def fan_repo(self, name, count):
        root = self.make_repo(name, change_base=False)
        self.add_files(root, count)
        return root

    @staticmethod
    def chunker_awk_runs(log):
        with open(log, encoding="utf-8") as fh:
            return sum(1 for line in fh.read().splitlines() if "-v tgt=" in line)

    def test_below_cap_rechunk_path_is_untouched(self):
        repo = self.fan_repo("fan60", 60)
        log = self.shim(shutil.which("awk"), "GLM_GDS_AWKLOG",
                        os.path.join(self.tmp, "awk60.log"))
        out = self.gather(repo, "GLM_GDS_AWKLOG", log, {"GLM_GDS_FAN_CHUNK": "1000"})
        self.assertIn("MODE=FAN_OUT chunks=60 ", out)
        self.assertNotIn("NOTE:", out)
        self.assertEqual(self.chunker_awk_runs(log), 1)
        chunk_dir = re.search(r"dir=(\S+)", out).group(1)
        self.assertEqual(len(glob.glob(os.path.join(chunk_dir, "[0-9][0-9][0-9].patch"))), 60)

    def test_over_cap_rechunk_runs_awk_once_and_stays_consistent(self):
        repo = self.fan_repo("fan100", 100)
        log = self.shim(shutil.which("awk"), "GLM_GDS_AWKLOG",
                        os.path.join(self.tmp, "awk100.log"))
        out = self.gather(repo, "GLM_GDS_AWKLOG", log, {"GLM_GDS_FAN_CHUNK": "1000"})
        self.assertIn("MODE=FAN_OUT chunks=50 ", out)
        self.assertIn("NOTE:", out)
        self.assertEqual(self.chunker_awk_runs(log), 1)
        chunk_dir = re.search(r"dir=(\S+)", out).group(1)
        self.assertEqual(len(glob.glob(os.path.join(chunk_dir, "[0-9][0-9][0-9].patch"))), 50)
        with open(os.path.join(chunk_dir, "count"), encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "50")
        with open(os.path.join(chunk_dir, "index"), encoding="utf-8") as fh:
            rows = fh.read().splitlines()
        self.assertEqual(len(rows), 50)
        self.assertEqual(rows[0], "1\t2\tf001.txt .. f002.txt")
        self.assertEqual(rows[-1], "50\t2\tf099.txt .. f100.txt")


if __name__ == "__main__":
    unittest.main()
