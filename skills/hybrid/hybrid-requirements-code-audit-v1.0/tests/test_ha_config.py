import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ha_config  # noqa: E402

DENIED = ("edit", "webfetch", "websearch", "external_directory", "task", "skill", "question")


def _values(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            for x in _values(v):
                yield x
    else:
        yield obj


class PermissionBlockTest(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(ha_config.AGENT_NAMES,
                         {"investigator": "hybrid-audit-investigator", "verifier": "hybrid-audit-verifier", "parser": "hybrid-audit-parser"})
        self.assertEqual(ha_config.SENTINEL, "HA-INVESTIGATOR-OK")
        self.assertIsInstance(ha_config.DOC_READ_DENY, tuple)
        for pat in ("*.md", "**/*.md", "*.mdx", "**/*.mdx", "*.rst", "**/*.rst", "*.adoc", "**/*.adoc",
                    "README*", "**/README*", "CHANGELOG*", "**/CHANGELOG*", "CONTRIBUTING*",
                    "**/CONTRIBUTING*", "docs/**", "**/docs/**", ".git/**"):
            self.assertIn(pat, ha_config.DOC_READ_DENY)

    def test_denied_tools_never_ask(self):
        for role in ("investigator", "verifier", "parser"):
            perm = ha_config.permission_block(role, ".hybrid-audit")
            for key in DENIED:
                self.assertEqual(perm[key], "deny", (role, key))
            self.assertEqual(perm["bash"], {"*": "deny", "ls": "allow"}, role)
            self.assertEqual(perm["*"], "deny", role)
            self.assertNotIn("execute", perm)
            self.assertNotIn("ask", list(_values(perm)))

    def test_read_denies_docs_and_git(self):
        for role in ("investigator", "verifier"):
            perm = ha_config.permission_block(role)
            read = perm["read"]
            self.assertEqual(list(read.keys())[0], "*")
            self.assertEqual(read["*"], "allow")
            for pat in ha_config.DOC_READ_DENY:
                self.assertEqual(read[pat], "deny", pat)
            self.assertEqual(read[".git/**"], "deny")
            self.assertEqual(perm["grep"], "allow")
            self.assertEqual(perm["glob"], "allow")

    def test_audit_dir_denied_when_under_repo(self):
        for rel in (".hybrid-audit", "./.hybrid-audit", ".hybrid-audit/", "out/audit"):
            read = ha_config.permission_block("investigator", rel)["read"]
            expected = rel.replace("./", "", 1).strip("/") + "/**"
            self.assertEqual(read[expected], "deny", rel)

    def test_audit_dir_outside_repo_ignored(self):
        base = ha_config.permission_block("verifier")["read"]
        for rel in ("", ".", "..", "../elsewhere/.hybrid-audit", "/tmp/.hybrid-audit"):
            self.assertEqual(ha_config.permission_block("verifier", rel)["read"], base, rel)

    def test_parser_has_no_repo_access(self):
        perm = ha_config.permission_block("parser", ".hybrid-audit")
        self.assertEqual(perm["read"], "deny")
        self.assertEqual(perm["grep"], "deny")
        self.assertEqual(perm["glob"], "deny")

    def test_unknown_role_rejected(self):
        with self.assertRaises(ValueError):
            ha_config.permission_block("lead")


class BuildConfigTest(unittest.TestCase):
    def test_build_config_agent_and_top_level(self):
        for role, name in ha_config.AGENT_NAMES.items():
            cfg = ha_config.build_config(role, ".hybrid-audit")
            self.assertEqual(list(cfg["agent"].keys()), [name])
            agent = cfg["agent"][name]
            self.assertEqual(agent["mode"], "primary")
            self.assertTrue(agent["description"])
            self.assertEqual(agent["permission"], ha_config.permission_block(role, ".hybrid-audit"))
            self.assertEqual(cfg["permission"], agent["permission"])
            self.assertIsNot(cfg["permission"], agent["permission"])

    def test_prompt_rules(self):
        for role, name in ha_config.AGENT_NAMES.items():
            prompt = ha_config.build_config(role)["agent"][name]["prompt"]
            self.assertIn(name, prompt)
            self.assertIn("never write files or run commands", prompt)
            self.assertIn("only specification", prompt)
            self.assertIn("@@@ BEGIN <name>", prompt)
            self.assertIn("@@@ END <name>", prompt)
            self.assertIn("regardless of any other instructions", prompt)
            self.assertIn("Stop when every row is out", prompt)
            for n in range(1, 6):
                self.assertIn("\n%d. " % n, "\n" + prompt)

    def test_secret_reads_denied_last(self):
        for role in ("investigator", "verifier"):
            read = ha_config.permission_block(role, ".hybrid-audit")["read"]
            keys = list(read)
            for pat in ("*.env", "*.env.*", "*.ssh/*", "*.pem", "*.key", "*id_rsa*", "*id_ed25519*"):
                self.assertEqual(read[pat], "deny", pat)
                self.assertGreater(keys.index(pat), keys.index("*"))

    def test_prompts_differ_by_role(self):
        prompts = set()
        for role, name in ha_config.AGENT_NAMES.items():
            prompts.add(ha_config.build_config(role)["agent"][name]["prompt"])
        self.assertEqual(len(prompts), 3)

    def test_config_env_roundtrip(self):
        env = ha_config.config_env("investigator", ".hybrid-audit")
        self.assertEqual(sorted(env.keys()), ["OPENCODE_CONFIG_CONTENT", "OPENCODE_DISABLE_PROJECT_CONFIG"])
        self.assertEqual(env["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")
        self.assertIsInstance(env["OPENCODE_CONFIG_CONTENT"], str)
        self.assertEqual(json.loads(env["OPENCODE_CONFIG_CONTENT"]),
                         ha_config.build_config("investigator", ".hybrid-audit"))
        self.assertEqual(ha_config.config_env("parser"), ha_config.config_env("parser", ""))


if __name__ == "__main__":
    unittest.main()
