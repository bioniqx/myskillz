import pathlib
import unittest


class TestHybridSharedSync(unittest.TestCase):
    def test_hybrid_shared_byte_identical(self):
        hybrid_root = pathlib.Path(__file__).resolve().parents[2]
        paths = {
            'brainstorming': hybrid_root / 'hybrid-brainstorming-v1.0/scripts/hybrid_shared.py',
            'writing-plans': hybrid_root / 'hybrid-writing-plans-v1.0/scripts/hybrid_shared.py',
            'audit': hybrid_root / 'hybrid-requirements-code-audit-v1.0/scripts/hybrid_shared.py',
            'team': hybrid_root / 'hybrid-team-v1.0/scripts/hybrid_shared.py',
        }
        missing = sorted(name for name, path in paths.items() if not path.exists())
        self.assertEqual(missing, [], 'hybrid_shared.py copies not found')
        canonical_content = paths['brainstorming'].read_bytes()
        for name, path in paths.items():
            if name != 'brainstorming':
                with self.subTest(skill=name):
                    self.assertEqual(canonical_content, path.read_bytes())
