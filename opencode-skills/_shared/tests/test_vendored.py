import hashlib
import os
import subprocess
import unittest

SKILLS = [
    "brainstorming",
    "dev-team",
    "doc-generator",
    "requirements-code-audit",
    "systematic-debugging",
    "writing-plans",
]


class TestVendored(unittest.TestCase):
    def test_sync_copies_and_verifies_identity(self):
        """sync.sh copies oc_harness.py into every skill and the copies are byte-identical."""
        shared_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        repo_root = os.path.dirname(shared_dir)
        src = os.path.join(shared_dir, "oc_harness.py")
        with open(src, "rb") as fh:
            src_hash = hashlib.sha256(fh.read()).hexdigest()

        result = subprocess.run(["sh", os.path.join(shared_dir, "sync.sh"), repo_root],
                                cwd=repo_root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, "sync.sh failed: %s" % result.stderr)

        for skill in SKILLS:
            dest = os.path.join(repo_root, "oc-" + skill, "scripts", "oc_harness.py")
            with open(dest, "rb") as fh:
                dest_hash = hashlib.sha256(fh.read()).hexdigest()
            self.assertEqual(src_hash, dest_hash, "oc_harness.py in %s differs from canonical" % skill)

        synced = [line for line in result.stdout.splitlines() if line.startswith("synced ")]
        self.assertEqual(len(synced), len(SKILLS))


if __name__ == "__main__":
    unittest.main()
