"""Tier wording sweep over SKILL bodies, the team-leader agent and the playbooks.

Pins the five-model vocabulary of the 2026-11-19 spec: lane tables and
denylist sentences switch to session-model wording (no flash-only claim, no
promotion wording that names GLM-5.3 or deepseek-v4-pro as forbidden
switches), the two metadata `models:` lines list all five ids on one flat
line, and the brainstorming description keeps its trigger clause inside the
1024-char ceiling even when the rewritten text sits near that ceiling.
"""

import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GLM_ROOT = os.path.dirname(os.path.dirname(HERE))

FIVE_ID_LINE = ("glm-5.3-flash | deepseek-flash | glm-5.3 | deepseek-v4-pro"
                " | claude-sonnet-5.5")

SWEPT_FOLDERS = [
    "glm-brainstorming",
    "glm-dev-team",
    "glm-writing-plans",
    "glm-systematic-debugging",
    "glm-requirements-code-audit",
]


def read(rel):
    with open(os.path.join(GLM_ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def flat(text):
    """Collapse wrapped markdown lines so line breaks cannot hide a phrase."""
    return re.sub(r"\s+", " ", text)


def frontmatter_description(rel):
    """Read the 'description' value: quoted, plain, or a block scalar."""
    m = re.search(r"^---\n(.*?)\n---", read(rel), re.DOTALL)
    if not m:
        return None
    lines = m.group(1).split("\n")
    for i, line in enumerate(lines):
        mm = re.match(r"^description:\s*(.*)$", line)
        if not mm:
            continue
        rest = mm.group(1).strip()
        if rest in (">-", ">", "|-", "|"):
            block = []
            for cont in lines[i + 1:]:
                if cont.strip() == "":
                    continue
                if cont.startswith(" ") or cont.startswith("\t"):
                    block.append(cont.strip())
                else:
                    break
            return " ".join(block)
        if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in ('"', "'"):
            return rest[1:-1]
        return rest
    return None


class TestTierWordingSweep(unittest.TestCase):
    def test_devteam_skill_uses_session_model_wording(self):
        content = read("glm-dev-team/SKILL.md")
        header = [l for l in content.splitlines() if l.startswith("| Agent")]
        self.assertTrue(header, "no workers table header row")
        self.assertIn("session model", header[0].lower(),
                      "lane table header must say 'session model', not a flash pin")
        self.assertNotIn("Flash pin", content, "stale 'Flash pin' column survived")
        self.assertNotIn("| GLM-5.3-Flash |", content,
                         "agent rows still pin GLM-5.3-Flash")
        self.assertNotIn("The pinned Flash model", content,
                         "stale flash-only claim in the conductor discipline")
        self.assertNotIn("runs on GLM-5.3-Flash", content,
                         "retry sentence still names GLM-5.3-Flash")

    def test_team_leader_agent_pins_no_model(self):
        content = read("glm-dev-team/agents/glm-team-leader.md")
        self.assertNotIn("GLM-5.3-Flash", content,
                         "agent body still pins GLM-5.3-Flash lanes")
        self.assertIn("session model", content,
                      "agent body must say lanes follow the session model")
        self.assertIn("high effort", content, "lite-lane effort wording lost")
        self.assertIn("max effort", content, "strong-lane effort wording lost")

    def test_writing_plans_r6_addresses_session_models(self):
        content = read("glm-writing-plans/SKILL.md")
        self.assertNotIn("Never GLM-5.3, never deepseek-v4-pro", content,
                         "denylist sentence must become no-promotion wording")
        self.assertNotIn("GLM-5.3-Flash, or deepseek-flash", flat(content),
                         "R6 still names only the two flash models")
        self.assertIn("session model", content,
                      "R6 must address the session model")

    def test_debugging_skill_and_readme_address_session_models(self):
        skill = read("glm-systematic-debugging/SKILL.md")
        self.assertNotIn("Every tier is GLM-5.3-Flash", skill,
                         "tier sentence still flash-only")
        self.assertNotIn("Do not name GLM-5.3 or deepseek-v4-pro", skill,
                         "denylist sentence must become no-promotion wording")
        self.assertIn("session model", skill,
                      "SKILL.md must address the session model")
        self.assertIn("`light` and `std` are effort high", skill,
                      "effort ladder changed")
        self.assertIn("`deep` is effort max", skill, "effort ladder changed")
        readme = read("glm-systematic-debugging/README.md")
        self.assertNotIn("GLM-5.3 / GLM-5.3-Flash", readme,
                         "README intro still names only GLM models")
        self.assertIn("Claude", readme, "README must address the Claude tier")
        self.assertIn("DeepSeek", readme,
                      "README must address the DeepSeek models")

    def test_requirements_audit_r1_names_session_model(self):
        content = read("glm-requirements-code-audit/SKILL.md")
        self.assertNotIn("GLM-5.3-Flash, or deepseek-flash when", content,
                         "R1 pass 4 still names only the two flash models")
        self.assertIn("session model", content,
                      "R1 must address the session model")
        self.assertIn("Never skip the second pass", content,
                      "second-pass rule changed")

    def test_metadata_models_lines_list_five_ids_flat(self):
        for rel in ("glm-systematic-debugging/SKILL.md",
                    "glm-requirements-code-audit/SKILL.md"):
            content = read(rel)
            m = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
            self.assertIsNotNone(m, "%s has no frontmatter" % rel)
            lines = [l for l in m.group(1).splitlines()
                     if re.match(r"^\s*models:", l)]
            self.assertEqual(len(lines), 1,
                             "%s must keep exactly one models: line" % rel)
            self.assertIn(FIVE_ID_LINE, lines[0],
                          "%s models: line must list all five ids on one"
                          " flat line" % rel)
            self.assertRegex(lines[0], r"claude-sonnet-5\.5[\"']?\s*$",
                             "%s models: line must end at the fifth id"
                             " (stay flat)" % rel)

    def test_brainstorming_description_ceiling_and_when_clause(self):
        desc = frontmatter_description("glm-brainstorming/SKILL.md")
        self.assertIsNotNone(desc, "brainstorming SKILL.md has no description")
        self.assertLessEqual(len(desc), 1024,
                             "description is %d chars, max 1024" % len(desc))
        self.assertIn("before ANY creative work", desc[:250],
                      "trigger clause left the first 250 chars")
        self.assertIn("FAST or SLOW", desc[:250],
                      "trigger clause left the first 250 chars")
        self.assertNotIn("Tuned for GLM-5.3-Flash", desc,
                         "flash-only tuning claim survived the sweep")

    def test_brainstorming_companions_use_session_model_wording(self):
        visual = read("glm-brainstorming/visual-companion.md")
        self.assertNotIn("GLM-5.3-Flash is natively multimodal", visual,
                         "multimodal claim still assumes a flash session")
        self.assertIn("session model", visual,
                      "visual companion must address the session model")
        for rel, stale in (
            ("glm-brainstorming/fanout-playbook.md",
             "All counts assume Flash lanes"),
            ("glm-brainstorming/research-playbook.md",
             "Do not promote a lane to GLM-5.3"),
        ):
            content = read(rel)
            self.assertNotIn(stale, content,
                             "%s still carries a flash-only lane claim" % rel)
            self.assertIn("session model", content,
                          "%s must address the session model" % rel)

    def test_changelog_records_sweep_skipping_folders_without_one(self):
        recorded = []
        for folder in SWEPT_FOLDERS:
            path = os.path.join(GLM_ROOT, folder, "CHANGELOG.md")
            if not os.path.isfile(path):
                continue  # folders without a CHANGELOG are skipped silently
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
            dated = [l for l in content.splitlines() if "2026-11-19" in l]
            self.assertTrue(dated, "%s has no 2026-11-19 entry" % path)
            self.assertTrue(
                any(("session model" in l) or ("five" in l.lower())
                    or ("tier" in l.lower()) for l in dated),
                "%s 2026-11-19 entry does not describe the model sweep" % path)
            recorded.append(folder)
        self.assertEqual(recorded, ["glm-brainstorming", "glm-writing-plans"],
                         "exactly the two swept folders with a CHANGELOG"
                         " should record the sweep")


if __name__ == "__main__":
    unittest.main()
