import unittest
import os
import hashlib
import subprocess


class TestVendored(unittest.TestCase):
    def test_sync_copies_and_verifies_identity(self):
        """Test that sync.sh copies files and they are byte-identical to sources."""
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
        shared_dir = os.path.join(repo_root, 'skills/glm/_shared')

        zai_client_src = os.path.join(shared_dir, 'zai_client.py')
        oc_harness_src = os.path.join(shared_dir, 'oc_harness.py')

        skills = {
            'zai_client.py': ['systematic-debugging-glm', 'writing-plans-glm', 'requirements-code-audit-glm'],
            'oc_harness.py': ['systematic-debugging-glm', 'writing-plans-glm', 'requirements-code-audit-glm', 'brainstorming-glm', 'doc-generator-glm', 'dev-team-glm']
        }

        sync_script = os.path.join(shared_dir, 'sync.sh')
        result = subprocess.run(['sh', sync_script], cwd=repo_root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"sync.sh failed: {result.stderr}")

        for filename, skill_list in skills.items():
            if filename == 'zai_client.py':
                src = zai_client_src
            else:
                src = oc_harness_src

            with open(src, 'rb') as f:
                src_bytes = f.read()
            src_hash = hashlib.sha256(src_bytes).hexdigest()

            for skill in skill_list:
                dest = os.path.join(repo_root, f'skills/glm/{skill}/scripts/{filename}')
                with open(dest, 'rb') as f:
                    dest_bytes = f.read()
                dest_hash = hashlib.sha256(dest_bytes).hexdigest()

                self.assertEqual(src_hash, dest_hash, f"{filename} in {skill} differs from canonical")

        lines = result.stdout.strip().split('\n')
        expected_count = len(skills['zai_client.py']) + len(skills['oc_harness.py'])
        self.assertEqual(len([l for l in lines if l.startswith('synced ')]), expected_count)


if __name__ == '__main__':
    unittest.main()
