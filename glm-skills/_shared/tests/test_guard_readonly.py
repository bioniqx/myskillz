"""guard.py read-only allow-list: write/exec forms (DG4), rewriting formatters (DG5), devteam status/probe (DG14)."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[2] / "glm-dev-team" / "scripts" / "guard.py"


def load_guard():
    spec = importlib.util.spec_from_file_location("devteam_guard_readonly", str(GUARD))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = load_guard()


def run_guard(mode, payload):
    r = subprocess.run([sys.executable, str(GUARD), mode], input=json.dumps(payload),
                       text=True, capture_output=True, timeout=30)
    return r.stdout


def decision(out):
    """'allow' / 'deny', or None for a silent exit (the normal permission flow)."""
    if not out.strip():
        return None
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"]


class GuardCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = self._tmp.name

    def bash_ro(self, cmd):
        return decision(run_guard("bash-ro", {"cwd": self.cwd, "agent_type": "reviewer",
                                              "tool_input": {"command": cmd}}))

    def preapproved(self, cmd, readonly=False):
        return guard.bash_allow_reason(cmd, None, footprint=[], pinned=[], readonly=readonly)


WRITE_EXEC_FORMS = [
    "git diff --output=/tmp/x.patch",
    "git diff --output /tmp/x.patch HEAD",
    "git log -p --output=log.txt",
    "git show --output=show.txt HEAD",
    "git grep --open-files-in-pager=vim foo",
    "git grep -Ovim foo",
    "rg --pre ./decompress.sh foo",
    "rg --pre=cat foo src",
    "uniq in.txt out.txt",
    "sed -n 's/a/b/w out.txt' in.txt",
    "sed 'w out.txt' in.txt",
    "sed '1e date' in.txt",
    "sed -e 's/a/b/e' in.txt",
    "sed -f prog.sed in.txt",
    "sort --compress-program=sh in.txt",
    "sort --compress-program sh in.txt",
    "cat in.txt | sed 'w out.txt'",
]

READ_ONLY_FORMS = [
    "git diff HEAD~1 -- src",
    "git log --oneline -5",
    "git show HEAD --stat",
    "git grep -n foo",
    "rg -n foo src",
    "sort -u in.txt",
    "uniq -c in.txt",
    "uniq -f 1 in.txt",
    "uniq --skip-fields 1 in.txt",
    "sed -n '1,5p' in.txt",
    "sed 's/we/us/g' in.txt",
    "cat in.txt | sort | uniq -c",
]


class ReadOnlyWriteExecFormsTest(GuardCase):
    def test_bash_ro_denies_write_and_exec_forms(self):
        bad = [c for c in WRITE_EXEC_FORMS if self.bash_ro(c) != "deny"]
        self.assertEqual(bad, [])

    def test_programmer_allow_list_does_not_preapprove_them(self):
        bad = [c for c in WRITE_EXEC_FORMS if self.preapproved(c) is not None]
        self.assertEqual(bad, [])

    def test_read_only_mode_denies_write_forms(self):
        cmds = ["git diff --output=x.patch", "uniq in.txt out.txt", "rg --pre=cat foo"]
        bad = [c for c in cmds if self.bash_ro(c) != "deny"]
        self.assertEqual(bad, [])

    def test_read_only_forms_stay_allowed(self):
        bad = [c for c in READ_ONLY_FORMS if self.bash_ro(c) != "allow"]
        self.assertEqual(bad, [])
        bad = [c for c in READ_ONLY_FORMS if self.preapproved(c) is None]
        self.assertEqual(bad, [])


REWRITING = [
    "black .",
    "black src/app.py",
    "ruff format .",
    "ruff check --fix .",
    "ruff --fix .",
    "prettier --write .",
    "prettier -w src",
    "gofmt -w .",
    "go fmt ./...",
    "cargo fmt",
    "isort .",
    "rustfmt src/main.rs",
    "eslint --fix src",
    "npx prettier --write .",
    "uv run black .",
    "yarn prettier --write .",
    "pnpm prettier --write .",
    "cargo clippy --fix",
    "go mod tidy",
    "yarn --cwd . prettier --write .",
    "pnpm -C . prettier --write .",
    "pnpm --filter a exec prettier --write .",
    "yarn workspace a prettier --write .",
    "bun run prettier --write .",
    "bun x prettier --write .",
    "npm exec prettier -- --write .",
    "npm exec -- prettier --write .",
    "npm exec -c 'prettier --write .'",
    "npm exec --call 'prettier --write .'",
    "npm exec sh -c 'prettier --write .'",
    "yarn exec sh -c 'prettier --write .'",
    "sh -c $'prettier\\t--write\\t.'",
    "sh -c 'prettier\t--write\t.'",
    "zsh -c 'prettier --write .'",
    "dash -c 'prettier --write .'",
    "ksh -c 'prettier --write .'",
    "fish -c 'prettier --write .'",
    "bash -ec 'prettier --write .'",
    "npm exec -c='prettier --write .'",
]

CHECK_MODES = [
    "black --check .",
    "black --diff src",
    "ruff check .",
    "ruff format --check .",
    "prettier --check .",
    "gofmt -l .",
    "cargo fmt --check",
    "isort --check-only .",
    "rustfmt --check src/main.rs",
    "yarn --cwd . prettier --check .",
    "pnpm -C . test",
    "npm test -- -t 'prettier --write works'",
]


class RewritingFormatterTest(GuardCase):
    def test_bash_ro_denies_rewriting_formatters(self):
        bad = [c for c in REWRITING if self.bash_ro(c) != "deny"]
        self.assertEqual(bad, [])

    def test_read_only_allow_list_skips_them(self):
        bad = [c for c in REWRITING if self.preapproved(c, readonly=True) is not None]
        self.assertEqual(bad, [])

    def test_check_modes_stay_allowed(self):
        bad = [c for c in CHECK_MODES if self.bash_ro(c) != "allow"]
        self.assertEqual(bad, [])

    def test_programmer_may_still_format(self):
        for cmd in ("black .", "gofmt -w .", "ruff format ."):
            self.assertIsNotNone(self.preapproved(cmd), cmd)


class PackageRunnerTest(GuardCase):
    """`npm exec` / `pnpm exec` / `yarn exec` / `bun x` get npx's checks plus a re-check of the command they run."""
    NOT_PREAPPROVED = [
        "pnpm exec node -e 1",
        "bun x node -e 1",
        "npm exec ghost-bin",
        "npm exec -- ghost-bin --check .",
        "npm exec -c 'prettier --check .'",
        # an option value is not the bin
        "npm exec --prefix /tmp cowsay",
        "npm exec --prefix ../.. cowsay",
        "npm exec --prefix prettier cowsay",
        "npx --prefix /tmp cowsay",
        "bun x --cwd /tmp cowsay",
        # an option value hides the real verb
        "npm --prefix /tmp exec cowsay",
        # npm still parses runner-level flags placed after the bin
        "npm exec prettier --prefix /tmp cowsay",
        "npx prettier --prefix /tmp cowsay",
        "npm exec prettier --prefix=/tmp cowsay",
        "npm exec prettier --pref /tmp cowsay",
        "npm exec prettier --package cowsay",
        "npm exec prettier --package=cowsay",
        "npm exec prettier --yes",
        "npm exec prettier --call 'x'",
        "npm exec prettier --workspace a",
        "npm exec prettier --ws",
        "pnpm exec prettier --dir /tmp",
        "pnpm exec prettier -C /tmp",
        "yarn exec prettier --cwd /tmp",
        "bun x prettier --cwd=/tmp",
        # a location flag before the verb that leaves the repo or expands
        "npm --prefix=/tmp exec prettier",
        "npm --prefix /tmp exec prettier",
        "npm --pref=/tmp exec prettier",
        "pnpm -C /tmp exec prettier",
        "pnpm --dir ../x exec prettier",
        "yarn --cwd ~/x exec prettier",
        "pnpm -C '$HOME' exec prettier",
        "npm --prefix=/tmp test",
        "pnpm -C /tmp test",
    ]
    PREAPPROVED = [
        "npm exec prettier --check .",
        "npm x -- prettier --check .",
        "npx prettier --check src",
        # after a bare `--` every flag belongs to the bin
        "npm exec -- prettier --prefix x",
        "npm exec prettier --check . -- --prefix x",
        # a relative in-repo location stays allowed
        "pnpm -C packages/app exec prettier --check .",
        "yarn --cwd packages/app prettier --check .",
        "pnpm --filter app exec prettier --check .",
        # `x` as an option value or after `--` is not the runner verb
        "pnpm --filter x test",
        "pnpm --filter app test",
        "npm test -- x",
        "npm test",
    ]

    def setUp(self):
        super().setUp()
        bins = Path(self.cwd, "node_modules", ".bin")
        bins.mkdir(parents=True)
        for b in ("node", "prettier"):
            (bins / b).write_text("")

    def reason(self, cmd, readonly):
        return guard.bash_allow_reason(cmd, self.cwd, footprint=[], pinned=[], readonly=readonly)

    def test_eval_flags_and_missing_bins_are_not_preapproved(self):
        for ro in (True, False):
            bad = [c for c in self.NOT_PREAPPROVED if self.reason(c, ro) is not None]
            self.assertEqual(bad, [], f"readonly={ro}")

    def test_local_bin_in_check_mode_stays_preapproved(self):
        for ro in (True, False):
            bad = [c for c in self.PREAPPROVED if self.reason(c, ro) is None]
            self.assertEqual(bad, [], f"readonly={ro}")

    def test_install_behind_a_filter_value_is_not_preapproved(self):
        self.assertIsNone(self.reason("pnpm --filter app install", False))


class DevteamStatusProbeTest(GuardCase):
    STATUS = [
        "python3 glm-dev-team/scripts/devteam.py status",
        "python3 /opt/skills/glm-dev-team/scripts/devteam.py probe",
        "python devteam.py status",
    ]
    OTHER = [
        "python3 glm-dev-team/scripts/devteam.py claim S1",
        "python3 devteam.py integrate S1",
        "python3 notdevteam.py status",
        "python3 glm-dev-team/scripts/guard.py bash-ro",
    ]

    def test_status_and_probe_allowed_for_read_only_roles(self):
        bad = [c for c in self.STATUS if self.bash_ro(c) != "allow"]
        self.assertEqual(bad, [])

    def test_other_engine_verbs_are_not_preapproved(self):
        bad = [c for c in self.OTHER if self.bash_ro(c) == "allow"]
        self.assertEqual(bad, [])

    def test_programmer_allow_list_still_skips_the_engine(self):
        self.assertIsNone(self.preapproved("python3 devteam.py status"))
