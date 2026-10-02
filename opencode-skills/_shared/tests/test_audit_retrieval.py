"""oc_audit.py retrieval and citation paths: is_doc, cited-path normalisation,
ripgrep globs (spec RA1-RA3)."""
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import threading
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(
    HERE, "..", "..", "oc-requirements-code-audit", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
_spec = importlib.util.spec_from_file_location(
    "audit_retrieval_under_test", os.path.join(SCRIPTS, "oc_audit.py"))
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def _write(root, rel, text):
    full = os.path.join(root, rel)
    d = os.path.dirname(full)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(full, "w", encoding="utf-8") as fh:
        fh.write(text)
    return full


class IsDocTest(unittest.TestCase):
    CODE = [
        "app/security.py", "src/to" "do.ts", "models/history.py", "pkg/support.go",
        "requirements.txt", "requirements-dev.txt", "blog/views.py",
        "site/app.js", "design/tokens.py", "book/models.rb", "security.py",
        "CMakeLists.txt",
    ]
    PROSE = [
        "README.md", "docs/guide.html", "notes.txt", "LICENSE", "CHANGELOG",
        "documentation/api.html", "wiki/Home.py", "adr/0001-choice.adoc",
        "src/README.rst", "handbook/onboarding.js",
    ]

    def test_code_files_with_doc_like_names_are_not_prose(self):
        for rel in self.CODE:
            self.assertFalse(audit.is_doc(rel), rel)

    def test_prose_by_extension_and_doc_dirs_is_still_prose(self):
        for rel in self.PROSE:
            self.assertTrue(audit.is_doc(rel), rel)

    def test_runtime_data_under_doc_dir_is_not_prose(self):
        self.assertFalse(audit.is_doc("docs/openapi.yaml"))
        self.assertFalse(audit.is_doc(".github/workflows/ci.yml"))

    def test_walk_repo_keeps_security_and_requirements(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        _write(root, "app/security.py", "def check():\n    return True\n")
        _write(root, "requirements.txt", "flask==3.0\n")
        _write(root, "README.md", "readme text\n")
        rels = [r[0] for r in audit.walk_repo(root)]
        self.assertIn("app/security.py", rels)
        self.assertIn("requirements.txt", rels)
        self.assertNotIn("README.md", rels)


class CitePathTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        _write(self.root, ".eslintrc.json", '{\n  "rules": {}\n}\n')
        _write(self.root, "src/app.py", "a = 1\nb = 2\nc = 3\n")

    def _lint(self, path):
        row = {"status": "MATCHED", "confidence": "high", "notes": "n",
               "evidence": [{"path": path, "lines": "1-2", "note": "x"}]}
        return audit.lint_finding(row, {"id": "R1"}, self.root,
                                  {".eslintrc.json", "src/app.py"})

    def test_dotfile_keeps_its_leading_dot(self):
        out, errs, _ = self._lint(".eslintrc.json")
        self.assertEqual(errs, [])
        self.assertEqual(out["evidence"][0]["path"], ".eslintrc.json")

    def test_dot_slash_prefix_is_stripped(self):
        out, errs, _ = self._lint("./src/app.py")
        self.assertEqual(errs, [])
        self.assertEqual(out["evidence"][0]["path"], "src/app.py")

    def test_absolute_path_inside_root_becomes_relative(self):
        out, errs, _ = self._lint(os.path.join(self.root, "src", "app.py"))
        self.assertEqual(errs, [])
        self.assertEqual(out["evidence"][0]["path"], "src/app.py")

    def test_absolute_path_outside_root_is_rejected(self):
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other, True)
        outside = _write(other, "leak.py", "x = 1\ny = 2\n")
        out, errs, _ = self._lint(outside)
        self.assertEqual(out["evidence"], [])
        self.assertTrue(any("outside the codebase" in e for e in errs), errs)

    def test_norm_cite_path_helper(self):
        self.assertEqual(audit.norm_cite_path("././.env.example", self.root),
                         (".env.example", False))
        self.assertEqual(audit.norm_cite_path("", self.root), ("", False))
        self.assertEqual(audit.norm_cite_path(None, self.root), ("", False))

    def test_relative_dotdot_path_outside_root_is_rejected(self):
        outer = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outer, True)
        root = os.path.join(outer, "repo")
        _write(root, "src/app.py", "a = 1\nb = 2\n")
        _write(outer, "leak.py", "x = 1\ny = 2\n")
        row = {"status": "MATCHED", "confidence": "high", "notes": "n",
               "evidence": [{"path": "../leak.py", "lines": "1-2", "note": "x"}]}
        out, errs, _ = audit.lint_finding(row, {"id": "R1"}, root, {"src/app.py"})
        self.assertEqual(out["evidence"], [])
        self.assertTrue(any("outside the codebase" in e for e in errs), errs)

    def test_norm_cite_path_collapses_dotdot(self):
        self.assertEqual(audit.norm_cite_path("a/../b.py", self.root), ("b.py", False))
        self.assertTrue(audit.norm_cite_path("../x.py", self.root)[1])
        self.assertTrue(audit.norm_cite_path("src/../../x.py", self.root)[1])


class _FakePopen(object):
    calls = []

    def __init__(self, args, **kw):
        _FakePopen.calls.append(list(args))

    def communicate(self, timeout=None):
        return b"", b""


def _bare_retriever(root, rg):
    r = audit.Retriever.__new__(audit.Retriever)
    r.root = root
    r.rg = rg
    r.files = []
    return r


class RgGlobArgsTest(unittest.TestCase):
    def _globs(self, **kw):
        _FakePopen.calls = []
        r = _bare_retriever(tempfile.gettempdir(), "rg")
        with mock.patch.object(audit.subprocess, "Popen", _FakePopen):
            r._rg(["retention"], **kw)
        args = _FakePopen.calls[-1]
        return [args[i + 1] for i, a in enumerate(args) if a == "--glob"]

    def test_data_only_globs(self):
        g = self._globs(data_only=True)
        self.assertIn("*.{yml,yaml}", g)
        self.assertNotIn("*.ya?ml", g)
        self.assertIn("**/migrations/**", g)
        self.assertNotIn("migrations/**", g)

    def test_tests_only_globs(self):
        g = self._globs(tests_only=True)
        self.assertIn("**/tests/**", g)
        self.assertIn("**/__tests__/**", g)
        self.assertNotIn("tests/**", g)


@unittest.skipUnless(shutil.which("rg"), "ripgrep not installed")
class RgGlobRealTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        _write(self.root, "config/app.yaml", "retention_days: 30\n")
        _write(self.root, "config/alt.yml", "retention_days: 7\n")
        _write(self.root, "pkg/db/migrations/0001_init.py", "retention_days = 30\n")
        _write(self.root, "pkg/tests/helpers.py", "retention_days = 1\n")
        _write(self.root, "src/core.py", "retention_days = 30\n")
        self.r = _bare_retriever(self.root, shutil.which("rg"))

    def test_data_only_finds_yaml_and_nested_migrations(self):
        paths = sorted(set(h[0] for h in self.r._rg(["retention_days"], data_only=True)))
        self.assertEqual(paths, ["config/alt.yml", "config/app.yaml",
                                 "pkg/db/migrations/0001_init.py"])

    def test_tests_only_finds_nested_tests_dir(self):
        paths = sorted(set(h[0] for h in self.r._rg(["retention_days"], tests_only=True)))
        self.assertEqual(paths, ["pkg/tests/helpers.py"])


class GatherSizingTest(unittest.TestCase):
    def test_gather_takes_no_tier_and_stays_inside_the_char_cap(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        _write(root, "src/login.py", "def login():\n    return lock_account()\n")
        r = _bare_retriever(root, None)
        r.files = ["src/login.py"]
        r.symbols, r.routes, r.lines = {}, {}, {"src/login.py": 2}
        r._cache, r._lock = {}, threading.Lock()
        out = r.gather({"id": "R1", "text": "login locks the account",
                        "search_hints": ["lock_account", "login"]})
        self.assertEqual(out["considered"], ["src/login.py"])
        self.assertTrue(out["snippets"])
        self.assertLessEqual(out["chars"], audit.RETRIEVAL["chars"])


if __name__ == "__main__":
    unittest.main()
