"""Step 8 wrappers: claims.py shells to the vendored decide.py claim CLI."""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
WRAPPERS = [
    os.path.join(REPO, "z-doc-generator", "scripts", "claims.py"),
    os.path.join(REPO, "z-git-diff-summary", "scripts", "claims.py"),
]


def run(wrapper, stdin, cwd):
    return subprocess.run(
        [sys.executable, wrapper, "--root", "."],
        input=stdin, capture_output=True, text=True, cwd=cwd, timeout=60)


class ChunkClaimTests(unittest.TestCase):
    def test_chunk_claim_through_both_wrappers(self):
        for wrapper in WRAPPERS:
            with tempfile.TemporaryDirectory() as tmp:
                chunk_dir = os.path.join(tmp, "z-gds.test01", "c")
                os.makedirs(chunk_dir)
                chunk = os.path.join(chunk_dir, "001.patch")
                with open(chunk, "w", encoding="utf-8") as fh:
                    fh.write("@@ -1,2 +1,3 @@\n context\n+return 1\n")
                stdin = ("CLAIM return 1 :: %s\n"
                         "CLAIM handles errors :: %s\n" % (chunk, chunk))
                proc = run(wrapper, stdin, tmp)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("KEEP CLAIM return 1", proc.stdout)
                self.assertIn("DROP CLAIM handles errors", proc.stdout)
                tail = proc.stdout.strip().splitlines()[-1]
                self.assertTrue(tail.startswith("RESULT claim keep="), tail)
                self.assertIn("keep=1", tail)
                self.assertIn("drop=1", tail)


class DocClaimTests(unittest.TestCase):
    def test_doc_quote_missing_from_source_drops(self):
        for wrapper in WRAPPERS:
            with tempfile.TemporaryDirectory() as tmp:
                src = os.path.join(tmp, "mod.py")
                with open(src, "w", encoding="utf-8") as fh:
                    fh.write("def add(a, b):\n    return a + b\n")
                stdin = ("CLAIM returns the sum :: mod.py\n"
                         "CLAIM return a + b :: mod.py\n")
                proc = run(wrapper, stdin, tmp)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("DROP CLAIM returns the sum", proc.stdout)
                self.assertIn("KEEP CLAIM return a + b", proc.stdout)
                tail = proc.stdout.strip().splitlines()[-1]
                self.assertTrue(tail.startswith("RESULT claim keep="), tail)
                self.assertIn("keep=1", tail)
                self.assertIn("drop=1", tail)


if __name__ == "__main__":
    unittest.main()
