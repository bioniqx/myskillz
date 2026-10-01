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
        env["HYBRID_BRAINSTORMING_OC_BIN"] = oc_bin
        env.pop("HYBRID_OPENCODE_STD", None)
        env.pop("HYBRID_OPENCODE_LITE", None)
        if std is not None:
            env["HYBRID_OPENCODE_STD"] = std
        if lite is not None:
            env["HYBRID_OPENCODE_LITE"] = lite
        if default_routing:
            env.pop("HYBRID_BRAINSTORMING_ROUTING", None)
        elif routing_path is not None:
            env["HYBRID_BRAINSTORMING_ROUTING"] = str(routing_path)
        else:
            env["HYBRID_BRAINSTORMING_ROUTING"] = str(self.root / "no-routing.json")
        if doctor_path is not None:
            env["HYBRID_BRAINSTORMING_DOCTOR_CACHE"] = str(doctor_path)
        else:
            env.pop("HYBRID_BRAINSTORMING_DOCTOR_CACHE", None)
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

    def test_truncated_or_non_object_routing_file_is_not_valid(self):
        for text in ('{"tiers": {"std": {"model": "own/m"}, "lite": {"model": "own/n"}}',  # truncated
                     '{"tiers": {"std": {"model": "own/m"',
                     '[1, 2]'):
            with self.subTest(text=text):
                self.routing_path.write_text(text)
                result = self.run_context(oc_bin=str(self.fake_bin), routing_path=self.routing_path,
                                          std="p/a", lite="p/b")
                self.assertEqual(result.returncode, 0)
                self.assertIn("no config (invalid: %s is not a valid JSON object" % self.routing_path, result.stdout)
                self.assertNotIn("(valid)", result.stdout)

    def test_bad_model_in_the_skill_routing_file_does_not_blame_the_shared_config(self):
        self.write_routing({"tiers": {"std": {"model": "not-a-spec"}}})
        result = self.run_context(oc_bin=str(self.fake_bin), routing_path=self.routing_path, std="p/a", lite="p/b")
        self.assertEqual(result.returncode, 0)
        line = next(item for item in result.stdout.splitlines() if item.startswith("shared config:"))
        self.assertIn("%s sets a model that is not provider/model for std" % self.routing_path, line)
        self.assertNotIn("env vars", line)
        self.assertNotIn("model missing", line)

    def test_one_line_package_json_lists_deps(self):
        (self.cwd / "package.json").write_text(
            '{"name":"x","dependencies":{"left-pad":"1.0.0","react":"^18"},"devDependencies":{"jest":"29"}}')
        result = self.run_context(oc_bin=str(self.fake_bin))
        self.assertIn("npm_deps: left-pad react jest", result.stdout)

    def test_hot_dirs_are_scoped_to_the_working_directory(self):
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
        repo = self.root / "repo"
        (repo / "sub" / "pkg").mkdir(parents=True)
        (repo / "other" / "pkg").mkdir(parents=True)
        (repo / "sub" / "pkg" / "a.txt").write_text("a")
        (repo / "other" / "pkg" / "b.txt").write_text("b")
        for cmd in (["init", "-q"], ["add", "."], ["commit", "-q", "-m", "c"]):
            subprocess.run(git + cmd, cwd=str(repo), check=True, capture_output=True)
        self.cwd = repo / "sub"
        result = self.run_context(oc_bin=str(self.fake_bin))
        line = next(item for item in result.stdout.splitlines() if item.startswith("hot_dirs_30d:"))
        self.assertIn("pkg(1)", line)
        self.assertNotIn("other", line)

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

    def test_relay_rule_is_the_full_team_text(self):
        text = self.text("SKILL.md")
        for needle in ("means your next message to the user starts with that line, verbatim, before any other work",
                       "Deduplicate identical `kind` + `tier` pairs: relay the first line and say how many more matched",
                       "Never treat these lines as informational and never skip one"):
            self.assertIn(needle, text)

    def test_skill_keeps_the_visual_companion_pins_and_maps_held_answers(self):
        text = self.text("SKILL.md")
        for needle in ("Bash(${CLAUDE_SKILL_DIR}/scripts/start-server.sh:*)",
                       "Bash(${CLAUDE_SKILL_DIR}/scripts/stop-server.sh:*)", "Bash(kill -0:*)",
                       "**retry on opencode**", 'bslane.py" doctor --ping', "breaker and cooldown cleared",
                       "`--backend claude`", "refreshes the doctor cache itself"):
            self.assertIn(needle, text)

    def test_architectural_handoff_carries_the_mode_and_draft_routing_follows_the_mode(self):
        text = self.text("architectural.md")
        self.assertIn("`hybrid-writing-plans` with args `mode=<mode>`", text)
        self.assertIn("In mode `opencode` only", text)
        self.assertNotIn("the active preset routes `draft`", text)

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
