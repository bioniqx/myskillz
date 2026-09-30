import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

CONTEXT_SH = Path(__file__).resolve().parents[1] / "scripts" / "context.sh"
SKILL_DIR = CONTEXT_SH.parents[1]

UNAVAILABLE = "opencode: unavailable → preset claude (run bslane.py doctor)"
SHARED_SOURCE = "$HYBRID_OPENCODE_STD/$HYBRID_OPENCODE_LITE"


class TestContextSh(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cwd = self.root / "work"
        self.cwd.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()
        self.marker = self.root / "opencode-ran.marker"
        self.fake_bin = self.root / "opencode"
        self.fake_bin.write_text(
            "#!/bin/sh\ntouch '%s'\necho fake-opencode\n" % self.marker
        )
        self.fake_bin.chmod(self.fake_bin.stat().st_mode | stat.S_IEXEC)
        self.routing_path = self.root / "routing.json"
        self.doctor_path = self.root / "doctor.json"

    def run_context(self, oc_bin, routing_path=None, doctor_path=None, std=None, lite=None,
                    script=CONTEXT_SH, default_routing=False):
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        env["HB_OC_BIN"] = oc_bin
        env.pop("HYBRID_OPENCODE_STD", None)
        env.pop("HYBRID_OPENCODE_LITE", None)
        if std is not None:
            env["HYBRID_OPENCODE_STD"] = std
        if lite is not None:
            env["HYBRID_OPENCODE_LITE"] = lite
        if default_routing:
            env.pop("HB_ROUTING", None)
        elif routing_path is not None:
            env["HB_ROUTING"] = str(routing_path)
        else:
            env["HB_ROUTING"] = str(self.root / "no-routing.json")
        if doctor_path is not None:
            env["HB_DOCTOR_CACHE"] = str(doctor_path)
        else:
            env.pop("HB_DOCTOR_CACHE", None)
        result = subprocess.run(
            ["sh", str(script)],
            cwd=str(self.cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result

    def write_routing(self, payload, pretty=False):
        text = json.dumps(payload, indent=2) if pretty else json.dumps(payload)
        self.routing_path.write_text(text)

    def write_doctor(self, payload):
        self.doctor_path.write_text(json.dumps(payload))

    def shared_line(self, tail):
        return "shared config: %s %s" % (SHARED_SOURCE, tail)

    def test_status_line_printed_verbatim_with_spaces_preserved(self):
        status_line = "opencode:  v2.0.18   preset=hybrid  locate=oc:lite websearch=off"
        self.write_doctor(
            {"t": "2026-09-28T12:00:00Z", "version": "2.0.18", "status_line": status_line}
        )
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            routing_path=self.routing_path,
            doctor_path=self.doctor_path,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(status_line, result.stdout)
        self.assertFalse(self.marker.exists())

    def test_missing_opencode_binary_prints_unavailable(self):
        self.write_doctor(
            {"t": "2026-09-28T12:00:00Z", "version": "2.0.18", "status_line": "opencode: v2.0.18 preset=claude"}
        )
        result = self.run_context(
            oc_bin=str(self.root / "no-such-opencode-binary"),
            routing_path=self.routing_path,
            doctor_path=self.doctor_path,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(UNAVAILABLE, result.stdout)
        self.assertFalse(self.marker.exists())

    def test_missing_doctor_cache_prints_unavailable(self):
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            routing_path=self.routing_path,
            doctor_path=self.root / "no-such-doctor.json",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(UNAVAILABLE, result.stdout)
        self.assertFalse(self.marker.exists())

    def test_empty_status_line_prints_unavailable(self):
        self.write_doctor({"t": "2026-09-28T12:00:00Z", "version": "2.0.18", "status_line": ""})
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            routing_path=self.routing_path,
            doctor_path=self.doctor_path,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(UNAVAILABLE, result.stdout)
        self.assertFalse(self.marker.exists())

    def test_absent_status_line_key_prints_unavailable(self):
        self.write_doctor({"t": "2026-09-28T12:00:00Z", "version": "2.0.18"})
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            routing_path=self.routing_path,
            doctor_path=self.doctor_path,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(UNAVAILABLE, result.stdout)
        self.assertFalse(self.marker.exists())

    def test_status_line_ignores_routing_file_oc_tiers(self):
        self.write_routing(
            {
                "preset": "hybrid",
                "roles": {
                    "locate": "lite",
                    "explore": "std",
                    "fact": "lite",
                    "research": "claude",
                    "draft": "claude",
                },
            },
            pretty=True,
        )
        all_claude_line = (
            "opencode: v2.0.18 preset=claude locate=claude explore=claude "
            "fact=claude research=claude draft=claude websearch=off (doctor 2026-09-28)"
        )
        self.write_doctor(
            {"t": "2026-09-28T12:00:00Z", "version": "2.0.18", "status_line": all_claude_line}
        )
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            routing_path=self.routing_path,
            doctor_path=self.doctor_path,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(all_claude_line, result.stdout)
        self.assertNotIn("locate=oc:lite", result.stdout)
        self.assertFalse(self.marker.exists())

    def test_shell_syntax_is_valid(self):
        result = subprocess.run(
            ["sh", "-n", str(CONTEXT_SH)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_shared_env_missing_prints_no_config(self):
        result = self.run_context(oc_bin=str(self.fake_bin))
        self.assertEqual(result.returncode, 0)
        self.assertIn(self.shared_line("no config (missing)"), result.stdout)
        self.assertFalse(self.marker.exists())

    def test_lite_alone_does_not_make_the_shared_models_valid(self):
        result = self.run_context(oc_bin=str(self.fake_bin), lite="p/b")
        self.assertEqual(result.returncode, 0)
        self.assertIn(self.shared_line("no config (missing)"), result.stdout)

    def test_blank_std_counts_as_missing(self):
        result = self.run_context(oc_bin=str(self.fake_bin), std="   ")
        self.assertEqual(result.returncode, 0)
        self.assertIn(self.shared_line("no config (missing)"), result.stdout)

    def test_default_routing_file_is_read_from_the_skill_folder(self):
        skill = self.root / "skill"
        (skill / "scripts").mkdir(parents=True)
        script = skill / "scripts" / "context.sh"
        script.write_text(CONTEXT_SH.read_text())
        (skill / "routing.json").write_text(json.dumps({"tiers": {"std": {"model": "own/m"}}}))
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            std="p/a",
            lite="p/b",
            script=script,
            default_routing=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            self.shared_line("std=own/m (skill) lite=p/b (shared) (valid)"), result.stdout
        )

    def test_shared_env_valid_prints_specs_with_and_without_variant(self):
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            std="zai-coding-plan/glm-5.3#high",
            lite="zai-coding-plan/glm-5.3-flash",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            self.shared_line(
                "std=zai-coding-plan/glm-5.3#high (shared) "
                "lite=zai-coding-plan/glm-5.3-flash (shared) (valid)"
            ),
            result.stdout,
        )
        self.assertFalse(self.marker.exists())

    def test_lite_defaults_to_std(self):
        result = self.run_context(
            oc_bin=str(self.fake_bin), std="opencode/muse-spark-1.3-contributor-free#xhigh"
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            self.shared_line(
                "std=opencode/muse-spark-1.3-contributor-free#xhigh (shared) "
                "lite=opencode/muse-spark-1.3-contributor-free#xhigh (shared) (valid)"
            ),
            result.stdout,
        )

    def test_surrounding_whitespace_is_trimmed(self):
        result = self.run_context(oc_bin=str(self.fake_bin), std="  p/a  ", lite=" p/b#low ")
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            self.shared_line("std=p/a (shared) lite=p/b#low (shared) (valid)"), result.stdout
        )

    def test_shared_env_model_without_provider_is_invalid(self):
        result = self.run_context(oc_bin=str(self.fake_bin), std="p/a", lite="glm-flash")
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            self.shared_line(
                "no config (invalid: model missing or not provider/model for lite)"
            ),
            result.stdout,
        )

    def test_shared_env_garbage_is_invalid_and_still_exits_zero(self):
        for bad in ("this is not a spec", "p/a#x#y", "/a"):
            with self.subTest(std=bad):
                result = self.run_context(oc_bin=str(self.fake_bin), std=bad)
                self.assertEqual(result.returncode, 0)
                self.assertIn(
                    self.shared_line(
                        "no config (invalid: model missing or not provider/model for std lite)"
                    ),
                    result.stdout,
                )

    def test_per_skill_model_wins_over_shared_and_never_takes_shared_variant(self):
        self.write_routing(
            {"tiers": {"std": {"model": "own/m", "stall_s": 90}, "lite": {"stall_s": 60}}}
        )
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            routing_path=self.routing_path,
            std="p/a#high",
            lite="p/b",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            self.shared_line("std=own/m (skill) lite=p/b (shared) (valid)"), result.stdout
        )

    def test_per_skill_model_shows_its_own_variant(self):
        self.write_routing({"tiers": {"lite": {"model": "own/n", "variant": "low"}}})
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            routing_path=self.routing_path,
            std="p/a#high",
            lite="p/b",
        )
        self.assertIn(
            self.shared_line("std=p/a#high (shared) lite=own/n#low (skill) (valid)"),
            result.stdout,
        )

    def test_per_skill_models_for_both_tiers_do_not_need_the_shared_env(self):
        self.write_routing(
            {"tiers": {"std": {"model": "own/m"}, "lite": {"model": "own/n", "variant": "low"}}}
        )
        result = self.run_context(oc_bin=str(self.fake_bin), routing_path=self.routing_path)
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            self.shared_line("std=own/m (skill) lite=own/n#low (skill) (valid)"), result.stdout
        )

    def test_tier_without_any_model_reports_the_missing_shared_env(self):
        self.write_routing({"tiers": {"std": {"model": "own/m"}}})
        result = self.run_context(oc_bin=str(self.fake_bin), routing_path=self.routing_path)
        self.assertEqual(result.returncode, 0)
        self.assertIn(self.shared_line("no config (missing)"), result.stdout)

    def test_leaked_shared_env_from_the_parent_process_is_ignored(self):
        with mock.patch.dict(os.environ, {"HYBRID_OPENCODE_STD": "zz/leak#x"}):
            result = self.run_context(oc_bin=str(self.fake_bin))
        self.assertIn(self.shared_line("no config (missing)"), result.stdout)
        self.assertNotIn("zz/leak", result.stdout)

    def test_old_doctor_cache_prints_stale_line(self):
        self.write_doctor(
            {"t": "2026-09-28T12:00:00Z", "version": "2.0.18", "status_line": "opencode: v2.0.18 preset=hybrid"}
        )
        old = self.doctor_path.stat().st_mtime - 3600
        os.utime(str(self.doctor_path), (old, old))
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            routing_path=self.routing_path,
            doctor_path=self.doctor_path,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            "opencode: doctor cache older than 10 min → stale (run bslane.py doctor)",
            result.stdout,
        )
        self.assertNotIn("preset=hybrid", result.stdout)


class TestSkillDocs(unittest.TestCase):
    def text(self, name):
        return " ".join((SKILL_DIR / name).read_text().split())

    def test_description_within_limit_and_names_run_mode(self):
        lines = (SKILL_DIR / "SKILL.md").read_text().splitlines()
        line = next(item for item in lines if item.startswith("description:"))
        value = line[len("description:"):].strip().strip('"')
        self.assertLessEqual(len(value), 1024)
        self.assertIn("run mode", value)

    def test_skill_has_mode_step(self):
        text = self.text("SKILL.md")
        for needle in (
            "Step 0: Run mode",
            "mode=hybrid|claude|opencode",
            "Run this skill in which mode?",
            "AskUserQuestion",
            "does not count against the turn budget",
            "(skill)",
            "(shared)",
            "HYBRID_OPENCODE_STD",
            "HYBRID_OPENCODE_LITE",
            "~/.claude/settings.json",
        ):
            self.assertIn(needle, text)

    def test_skill_has_relay_rule(self):
        text = self.text("SKILL.md")
        self.assertIn("Any `OC-ERROR` or `OC-WARN` line in tool output", text)
        self.assertIn("your next message to the user starts with that line", text)

    def test_skill_uses_opencode_preset_not_max(self):
        text = self.text("SKILL.md")
        self.assertIn("--preset claude|hybrid|opencode", text)
        self.assertNotIn("hybrid|max", text)
        self.assertNotIn("preset max", text)

    def test_skill_documents_exit_codes_and_stats(self):
        text = self.text("SKILL.md")
        self.assertIn("Exit code 3 means the lane failed on opencode", text)
        self.assertIn('bslane.py" stats', text)

    def test_skill_hands_off_mode(self):
        text = self.text("SKILL.md")
        self.assertIn("hybrid-writing-plans with args `mode=<mode>`", text)

    def test_skill_has_no_contradicting_wording(self):
        text = self.text("SKILL.md").lower()
        self.assertNotIn("informational", text)
        self.assertNotIn("transparent to you", text)

    def test_readme_documents_shared_config_and_modes(self):
        text = self.text("README.md")
        for needle in (
            "HYBRID_OPENCODE_STD",
            "HYBRID_OPENCODE_LITE",
            "~/.claude/settings.json",
            "<skill dir>/routing.json",
            "(skill)",
            "(shared)",
            "`disabled`",
            "OC-ERROR",
        ):
            self.assertIn(needle, text)
        self.assertNotIn("legacy", text)
        self.assertNotIn("one NOTE", text)
        self.assertNotIn("| `max` |", text)

    def test_changelog_has_v1_1_0_entry(self):
        text = self.text("CHANGELOG.md")
        self.assertIn("## v1.1.0 (2026-09-29)", text)
        self.assertIn("hybrid_shared.py", text)


if __name__ == "__main__":
    unittest.main()
