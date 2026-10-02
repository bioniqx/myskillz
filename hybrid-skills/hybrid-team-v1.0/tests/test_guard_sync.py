"""hybrid-team: devteam.py and guard.py must keep TEST_DIR_NAMES, TEST_FILE_PATTERNS, STATE_DIRNAME,
is_test_path and path_matches identical (AST comparison, docstrings ignored); and every script of this
skill must parse under Python 3.8 grammar (ast.parse(..., feature_version=(3, 8))).
"""
import ast
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
DEVTEAM_PY = SKILL / "scripts" / "devteam.py"
GUARD_PY = SKILL / "scripts" / "guard.py"


def _strip_docstring(body):
    """Drop a leading bare string-literal Expr (a docstring) from a body list."""
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def _dump(node):
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def _module(path):
    return ast.parse(path.read_text(), filename=str(path))


def _top_level_value(module, name):
    """ast.literal_eval() of the value assigned to a module-level `name = ...`."""
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("no top-level assignment named %r" % name)


def _function_body_dump(module, name):
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return _dump(ast.Module(body=_strip_docstring(node.body), type_ignores=[]))
    raise AssertionError("no top-level function named %r" % name)


class TestDuplicatedDefinitionsStayIdentical(unittest.TestCase):
    """C2 + spec W2: devteam.py and guard.py duplicate these on purpose; they must match."""

    @classmethod
    def setUpClass(cls):
        cls.dt = _module(DEVTEAM_PY)
        cls.gd = _module(GUARD_PY)

    def test_test_dir_names_identical(self):
        self.assertEqual(
            _top_level_value(self.dt, "TEST_DIR_NAMES"),
            _top_level_value(self.gd, "TEST_DIR_NAMES"),
        )

    def test_test_file_patterns_identical(self):
        self.assertEqual(
            _top_level_value(self.dt, "TEST_FILE_PATTERNS"),
            _top_level_value(self.gd, "TEST_FILE_PATTERNS"),
        )

    def test_state_dirname_identical(self):
        self.assertEqual(
            _top_level_value(self.dt, "STATE_DIRNAME"),
            _top_level_value(self.gd, "STATE_DIRNAME"),
        )

    def test_is_test_path_identical(self):
        self.assertEqual(
            _function_body_dump(self.dt, "is_test_path"),
            _function_body_dump(self.gd, "is_test_path"),
        )

    def test_path_matches_identical(self):
        # C2: only "./" prefixes are stripped in a loop; never lstrip("./").
        self.assertEqual(
            _function_body_dump(self.dt, "path_matches"),
            _function_body_dump(self.gd, "path_matches"),
        )


class TestPython38Grammar(unittest.TestCase):
    """Every script of this skill must stay parseable as Python 3.8."""

    def _scripts(self):
        paths = sorted((SKILL / "scripts").glob("*.py"))
        self.assertTrue(paths, "expected to find at least one script to check")
        return paths

    def test_all_scripts_parse_as_python38(self):
        failures = []
        for path in self._scripts():
            src = path.read_text()
            try:
                ast.parse(src, filename=str(path), feature_version=(3, 8))
            except SyntaxError as exc:
                failures.append("%s: %s" % (path, exc))
        self.assertEqual(failures, [], "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
