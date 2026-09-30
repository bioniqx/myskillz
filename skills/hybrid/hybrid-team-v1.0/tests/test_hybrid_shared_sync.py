import pathlib
import unittest


class TestHybridSharedSync(unittest.TestCase):
    def test_hybrid_shared_byte_identical(self):
        skillz_root = pathlib.Path(__file__).resolve().parent.parent.parent.parent
        paths = {
            'brainstorming': skillz_root / 'hybrid/hybrid-brainstorming-v1.0/scripts/hybrid_shared.py',
            'writing-plans': skillz_root / 'hybrid/hybrid-writing-plans-v1.0/scripts/hybrid_shared.py',
            'audit': skillz_root / 'hybrid/hybrid-requirements-code-audit-v1.0/scripts/hybrid_shared.py',
            'team': skillz_root / 'hybrid/hybrid-team-v1.0/scripts/hybrid_shared.py',
        }
        existing = {name: path for name, path in paths.items() if path.exists()}
        if len(existing) < 2:
            self.skipTest('Not all skill copies present')
        canonical_content = existing['brainstorming'].read_bytes()
        for name, path in existing.items():
            if name != 'brainstorming':
                with self.subTest(skill=name):
                    self.assertEqual(canonical_content, path.read_bytes())
