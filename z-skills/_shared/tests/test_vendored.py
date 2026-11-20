import unittest
import os
import hashlib
import subprocess


class TestVendored(unittest.TestCase):
    def test_sync_copies_and_verifies_identity(self):
        """Test that sync.sh copies files and they are byte-identical to sources."""
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
        shared_dir = os.path.join(repo_root, 'z-skills/_shared')

        skills = {
            'zai_client.py': ['z-systematic-debugging', 'z-writing-plans', 'z-requirements-code-audit'],
            'flash_pin.py': [
                'z-dev-team', 'z-systematic-debugging', 'z-writing-plans',
                'z-requirements-code-audit',
            ],
            'handoff.py': [
                'z-brainstorming', 'z-dev-team', 'z-doc-generator', 'z-git-diff-summary',
                'z-idea-to-spec', 'z-requirements-code-audit', 'z-systematic-debugging',
                'z-writing-plans',
            ],
            'decide.py': [
                'z-brainstorming', 'z-writing-plans', 'z-dev-team',
                'z-requirements-code-audit', 'z-systematic-debugging',
                'z-doc-generator', 'z-git-diff-summary',
            ],
        }

        sync_script = os.path.join(shared_dir, 'sync.sh')
        result = subprocess.run(['sh', sync_script, os.path.join(repo_root, 'z-skills')], cwd=repo_root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"sync.sh failed: {result.stderr}")

        for filename, skill_list in skills.items():
            src = os.path.join(shared_dir, filename)
            with open(src, 'rb') as f:
                src_bytes = f.read()
            src_hash = hashlib.sha256(src_bytes).hexdigest()

            for skill in skill_list:
                dest = os.path.join(repo_root, f'z-skills/{skill}/scripts/{filename}')
                with open(dest, 'rb') as f:
                    dest_bytes = f.read()
                dest_hash = hashlib.sha256(dest_bytes).hexdigest()

                self.assertEqual(src_hash, dest_hash, f"{filename} in {skill} differs from canonical")

        lines = result.stdout.strip().split('\n')
        expected_count = sum(len(names) for names in skills.values())
        self.assertEqual(len([l for l in lines if l.startswith('synced ')]), expected_count)


if __name__ == '__main__':
    unittest.main()
