# zCode installer verification and dsh installer Implementation Plan

> **Execution note:** This plan is self-contained and tool-agnostic. Any AI
> agent or human engineer can execute it with only a shell, a code editor, and
> git. Follow the Execution Protocol below.

**Goal:** Verify install-zcode.sh installs every file at its zCode location unchanged, add install-dsh.sh that lands all eleven z-* skill folders in the dsh user skills root, and remove the dead four-target test file so the suite is green.

**Out of scope:** The sibling repos, root CLAUDE.md, skill bodies and frontmatter, install-zcode.sh behavior, dsh plugin or profile setup, writes to the shared agents root.

**Rollback:** git revert the two task commits in reverse order (the removed test file returns from history); undo a real dsh install with rm -rf of the z-* folders under ~/.dsh/skills.

**Architecture:** install-dsh.sh mirrors install-zcode.sh's discovery, preflight and copy machinery, retargeted at the dsh user skills root resolved as --home DIR, else $DSH_HOME, else $HOME/.dsh, then /skills. The new suite mirrors test_install_zcode.py's temp-home end-to-end style. The dead four-target test file, whose installer script was already removed from the tree, is deleted.

**Tech Stack:** POSIX sh, Python 3 standard library only (unittest, subprocess, tempfile, shutil), git.

## Execution Protocol (for any AI agent or human engineer)

1. A task may start only when every task in its **Depends** and **Runs after**
   lists is complete. Single worker: run tasks in ID order.
2. Parallel workers: follow **Execution Waves**. Tasks in the same wave touch
   disjoint files and MAY run concurrently (marked `[P]`). Never run two tasks
   that modify the same file at once.
3. Within a task, execute steps top to bottom and mark each checkbox `- [x]`
   when done. To resume, continue from the first unchecked step.
4. Run every command exactly as written and compare with **Expected**. On
   mismatch, stop and fix before continuing.
5. Code blocks are the implementation - copy them verbatim. Signatures under
   **Interfaces** are contracts with other tasks: never rename, reorder
   parameters, or change types.
6. Commit exactly where the plan says, with the given message, staging only the
   listed paths. Never batch commits across tasks.
7. **Global Constraints** apply to every task.
8. If anything is ambiguous, missing, or contradicts the codebase, STOP and ask
   the requester. Do not invent behavior.

## Global Constraints

- stdlib Python 3 + POSIX sh only; pytest is not installed, use unittest; run suites from inside z-skills, never from the repo root.
- Work on main, commit on main, never create branches.
- `git add`/`git rm` name exact paths only, never `.` or `-A`; one `git commit` per task.
- Shell scripts mirror install-zcode.sh's style: `set -eu`, a `run()` dry-run wrapper, python3 heredoc blocks, the interactive `pause` trap, POSIX-safe constructs.
- Junk excluded from every copy: `.DS_Store`, `__pycache__`, `*.pyc`, `.idea`, `opencode`.
- Only z-* folders are replaced in a target (rm -rf then copy); folders that are not z-* are never touched; stale old-name installs warn and stay.
- The preflight aborts non-zero before the first copy on any violation: description empty or over 1024 characters, SKILL.md over 100KB, frontmatter name missing or not kebab-case.
- dsh target resolution: `--home DIR` wins, else `$DSH_HOME`, else `$HOME/.dsh`; skills land in `skills/` under that home.
- English plain ASCII in all files and commit messages; no emoji; no angle-bracket placeholder tokens.
- Suite command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests` run from z-skills.

## References

- `install-zcode.sh` - the installer to mirror: discovery loop, preflight python block, junk-exclusion find, `run()` dry-run wrapper, inventory print, stale-name warnings.
- `_shared/tests/test_install_zcode.py` - the end-to-end test patterns to mirror: temp HOME per test, copied_tree junk tests, preflight-abort asserts, inventory asserts.

## File Structure

- `./` — install-dsh.sh (T01)
- `_shared/tests/` — test_install_dsh.py (T01), test_install_all.py (T02)

## Contracts

#### T01: dsh installer with its end-to-end suite
- Files: `install-dsh.sh`, `_shared/tests/test_install_dsh.py`
- Produces: `sh install-dsh.sh [--home DIR] [--dry-run]`; `SKILLS = discover_skills(GLM_ROOT)`; `class InstallDshTests(unittest.TestCase)`; `def run_install(self, *args, root=None, dsh_home=None, with_home=True)`; `def target(self, *parts)`
- Spec: L1-5, L6-14, L15-30, L31-40, L41-46, L57-62, L63-69

#### T02: retire the dead four-target suite; verify both installers for real
- Depends: T01
- Files: `_shared/tests/test_install_all.py`
- Produces: full z-skills suite green; real installs run against the user home
- Consumes: `sh install-dsh.sh [--home DIR] [--dry-run]`
- Spec: L47-56

<!-- WAVES -->
## Execution Waves

Every task in a wave has all its Depends/Runs-after tasks in earlier waves. Tasks in the
same wave touch disjoint files, so a wave's `[P]` tasks may all run at once.

- **Wave 1:** T01
- **Wave 2:** T02
<!-- /WAVES -->

<!-- TASKS -->

### T01: dsh installer with its end-to-end suite

**Depends:** —

**Interfaces:**
- Produces: `sh install-dsh.sh [--home DIR] [--dry-run]`; `SKILLS = discover_skills(GLM_ROOT)`; `class InstallDshTests(unittest.TestCase)`; `def run_install(self, *args, root=None, dsh_home=None, with_home=True)`; `def target(self, *parts)`

**Files:**
- Create: `install-dsh.sh`
- Test: `_shared/tests/test_install_dsh.py`

- [ ] **Step 1: Write the failing end-to-end suite**

```python
import os
import shutil
import subprocess
import tempfile
import unittest

GLM_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SCRIPT = os.path.join(GLM_ROOT, "install-dsh.sh")


def discover_skills(root):
    names = []
    for name in sorted(os.listdir(root)):
        if name.startswith("z-") and os.path.isfile(os.path.join(root, name, "SKILL.md")):
            names.append(name)
    return names


SKILLS = discover_skills(GLM_ROOT)


class InstallDshTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def run_install(self, *args, root=None, dsh_home=None, with_home=True):
        env = dict(os.environ)
        env.pop("DSH_HOME", None)
        if dsh_home is not None:
            env["DSH_HOME"] = dsh_home
        if with_home:
            env["HOME"] = self.home
        else:
            env.pop("HOME", None)
        return subprocess.run(["sh", os.path.join(root or GLM_ROOT, "install-dsh.sh")] + list(args),
                              capture_output=True, text=True, timeout=120, env=env)

    def target(self, *parts):
        return os.path.join(self.home, ".dsh", "skills", *parts)

    def copied_tree(self):
        copy_root = os.path.join(self.home, "tree")
        shutil.copytree(GLM_ROOT, copy_root,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        return copy_root

    def test_dry_run_writes_nothing(self):
        r = self.run_install("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.listdir(self.home), [])
        self.assertIn("Nothing written.", r.stdout)
        self.assertIn("files in %d skill folders" % len(SKILLS), r.stdout)

    def test_installs_every_skill_as_is_and_prunes_junk(self):
        copy_root = self.copied_tree()
        junk = os.path.join(copy_root, "z-brainstorming", "__pycache__")
        os.makedirs(junk)
        with open(os.path.join(junk, "ask.pyc"), "wb") as fh:
            fh.write(b"\x00junk")
        with open(os.path.join(copy_root, "z-brainstorming", ".DS_Store"), "wb") as fh:
            fh.write(b"\x00junk")
        r = self.run_install(root=copy_root)
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in SKILLS:
            self.assertTrue(os.path.isfile(self.target(name, "SKILL.md")), name)
        for dirpath, dirnames, filenames in os.walk(os.path.dirname(self.target())):
            self.assertNotIn("__pycache__", dirnames, dirpath)
            self.assertNotIn(".DS_Store", filenames, dirpath)
            self.assertFalse([f for f in filenames if f.endswith(".pyc")], dirpath)
        with open(self.target("z-brainstorming", "agents", "z-explorer.md"), encoding="utf-8") as fh:
            with open(os.path.join(GLM_ROOT, "z-brainstorming", "agents", "z-explorer.md"),
                      encoding="utf-8") as src:
                self.assertEqual(fh.read(), src.read())

    def test_home_flag_and_dsh_home_env_pick_the_root(self):
        by_flag = os.path.join(self.home, "flagroot")
        r = self.run_install("--home", by_flag)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(by_flag, "skills", "z-brainstorming", "SKILL.md")))
        self.assertFalse(os.path.exists(self.target()))
        by_env = os.path.join(self.home, "envroot")
        r = self.run_install(dsh_home=by_env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(by_env, "skills", "z-brainstorming", "SKILL.md")))
        flag_and_env = os.path.join(self.home, "bothroot")
        r = self.run_install("--home", flag_and_env, dsh_home=os.path.join(self.home, "ignored"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(flag_and_env, "skills", "z-brainstorming", "SKILL.md")))
        self.assertFalse(os.path.exists(os.path.join(self.home, "ignored")))

    def test_oversize_description_is_rejected_before_any_copy(self):
        copy_root = self.copied_tree()
        skill_md = os.path.join(copy_root, "z-git-diff-summary", "SKILL.md")
        with open(skill_md, encoding="utf-8") as fh:
            text = fh.read()
        with open(skill_md, "w", encoding="utf-8") as fh:
            fh.write(text.replace("description: ", "description: " + "x" * 1100, 1))
        r = self.run_install(root=copy_root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("1024", r.stderr)
        self.assertEqual(os.listdir(self.home), ["tree"])

    def test_non_kebab_case_name_is_rejected_before_any_copy(self):
        copy_root = self.copied_tree()
        skill_md = os.path.join(copy_root, "z-idea-to-spec", "SKILL.md")
        with open(skill_md, encoding="utf-8") as fh:
            text = fh.read()
        with open(skill_md, "w", encoding="utf-8") as fh:
            fh.write(text.replace("name: z-idea-to-spec\n", "name: Not Kebab!\n", 1))
        r = self.run_install(root=copy_root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("kebab-case", r.stderr)
        self.assertEqual(os.listdir(self.home), ["tree"])

    def test_tree_without_installable_skills_fails_loudly(self):
        copy_root = self.copied_tree()
        for name in SKILLS:
            os.remove(os.path.join(copy_root, name, "SKILL.md"))
        r = self.run_install(root=copy_root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no z-*/SKILL.md", r.stderr)

    def test_foreign_and_stale_folders_are_warned_not_touched(self):
        foreign = self.target("my-own-skill", "nested")
        os.makedirs(foreign)
        with open(os.path.join(foreign, "keep.md"), "w", encoding="utf-8") as fh:
            fh.write("keep\n")
        stale = self.target("brainstorming")
        os.makedirs(stale)
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isdir(foreign))
        with open(os.path.join(foreign, "keep.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "keep\n")
        self.assertIn("WARN: stale: " + stale, r.stdout)
        self.assertTrue(os.path.isdir(stale))
        self.assertTrue(os.path.isfile(self.target("z-brainstorming", "SKILL.md")))

    def test_rerun_is_idempotent_and_replaces_changed_files(self):
        self.assertEqual(self.run_install().returncode, 0)
        installed = self.target("z-brainstorming", "SKILL.md")
        with open(installed, "a", encoding="utf-8") as fh:
            fh.write("my edit\n")
        self.assertEqual(self.run_install().returncode, 0)
        with open(installed, encoding="utf-8") as fh:
            self.assertNotIn("my edit", fh.read())
        for dirpath, dirnames, filenames in os.walk(os.path.dirname(self.target())):
            self.assertEqual([f for f in filenames if f.endswith(".bak")], [], dirpath)

    def test_inventory_prints_dest_and_counts(self):
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        self.assertIn("dest: " + self.target() + "/", out)
        self.assertIn("    SKILL.md\n", out)
        self.assertIn("  " + self.target("z-brainstorming") + "/", out)
        self.assertIn("files in %d skill folders" % len(SKILLS), out)
        self.assertEqual(len(SKILLS), 11)

    def test_missing_home_is_rejected(self):
        r = self.run_install(with_home=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("HOME", r.stderr)
        self.assertEqual(os.listdir(self.home), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the suite to verify it fails for the right reason**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_install_dsh.py -v`
Expected: `FAILED` - every case that invokes the script errors with `sh: .../install-dsh.sh: No such file or directory` (the shell exits 127 because the installer does not exist yet)

- [ ] **Step 3: Write the installer**

```sh
#!/bin/sh
# Install every z-* skill folder that has SKILL.md at its root into DeepSeek Harness (dsh).
#
#   skills    z-FOLDER/  ->  DSH_HOME/skills/z-FOLDER/   (copied as-is minus junk)
#
# dsh discovers skills in the user root under its home: the home is --home DIR when given,
# else $DSH_HOME, else $HOME/.dsh. A skill is a FOLDER/SKILL.md directory bundle at the top
# level of a scanned root; nested SKILL.md files are deliberately not discovered. dsh
# requires a kebab-case name and a non-empty description in the frontmatter; the preflight
# below rejects violations before the first copy.
#
# The harness itself is not installed here; see the harness README. Folders that are not
# z-* in the target are never touched. The script does not read or write any dsh config.
#
# Usage: sh install-dsh.sh [--home DIR] [--dry-run]
# In an interactive terminal the script waits for Enter before the window closes.
set -eu

HOME_DIR="${DSH_HOME:-${HOME:-}}"
DRY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --home) [ $# -ge 2 ] || { echo "Error: --home needs a value" >&2; exit 1; }; HOME_DIR="$2"; shift 2 ;;
        --dry-run) DRY=1; shift ;;
        *) echo "Usage: $0 [--home DIR] [--dry-run]" >&2; exit 1 ;;
    esac
done

[ -n "$HOME_DIR" ] || { echo "Error: HOME is unset; pass --home DIR" >&2; exit 1; }

pause() {
    [ -t 0 ] && [ -t 1 ] || return 0
    printf "Press Enter to close. "
    read -r _ || true
}
trap pause EXIT

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME_DIR/skills"

# Discover installable skills: directories named z-* with SKILL.md at the root.
FOLDERS=$(
    for d in "$SCRIPT_DIR"/z-*; do
        [ -d "$d" ] || continue
        [ -f "$d/SKILL.md" ] || continue
        basename "$d"
    done | sort | tr '\n' ' '
)
FOLDERS=${FOLDERS%" "}
SKIPPED=$(
    for d in "$SCRIPT_DIR"/z-*; do
        [ -d "$d" ] || continue
        [ -f "$d/SKILL.md" ] && continue
        basename "$d"
    done | sort | tr '\n' ' '
)
SKIPPED=${SKIPPED%" "}
[ -n "$FOLDERS" ] || { echo "Error: no z-*/SKILL.md folders under $SCRIPT_DIR" >&2; exit 1; }
skill_n=0
for _folder in $FOLDERS; do
    skill_n=$((skill_n + 1))
done

run() { if [ "$DRY" -eq 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

# Print relative file paths under root, skipping the same junk the copy step deletes.
list_rel_files() {
    python3 - "$1" <<'PY'
import os, sys
root = sys.argv[1]
skip_dir = {"opencode", ".idea", "__pycache__"}
out = []
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d not in skip_dir]
    for fn in filenames:
        if fn == ".DS_Store" or fn.endswith(".pyc"):
            continue
        rel = os.path.relpath(os.path.join(dirpath, fn), root)
        out.append(rel.replace("\\", "/"))
for rel in sorted(out):
    print(rel)
PY
}

# Read-only pre-flight. dsh drops a skill whose description is missing and requires a
# kebab-case name; a body over 100KB would be truncated when loaded.
python3 - "$SCRIPT_DIR" $FOLDERS <<'PY' || exit 1
import os, re, sys
root, bad = sys.argv[1], []
for folder in sys.argv[2:]:
    path = os.path.join(root, folder, "SKILL.md")
    if not os.path.isfile(path):
        bad.append("%s: SKILL.md not found" % folder)
        continue
    text = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    fm = m.group(1) if m else ""
    d = re.search(r"^description:[ \t]*(.*?)(?=^\S|\Z)", fm, re.S | re.M)
    desc = " ".join(l.strip() for l in d.group(1).splitlines()) if d else ""
    head, _, rest = desc.partition(" ")
    if head in (">-", ">", "|-", "|"):
        desc = rest
    if not desc:
        bad.append("%s: no description" % folder)
    elif len(desc.strip("\"'")) > 1024:
        bad.append("%s: description is %d characters (dsh requires a shorter one)" % (folder, len(desc)))
    if len(text.encode("utf-8")) > 100 * 1024:
        bad.append("%s: SKILL.md is over 100KB" % folder)
    n = re.search(r"(?m)^name:[ \t]*(.+)$", fm)
    name = n.group(1).strip().strip("\"'") if n else ""
    if not name:
        bad.append("%s: no name in frontmatter" % folder)
    elif not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
        bad.append("%s: name %s is not kebab-case" % (folder, name))
for line in bad:
    print("Error: " + line, file=sys.stderr)
sys.exit(1 if bad else 0)
PY

echo "dsh skills dir: $SKILLS_DIR$([ "$DRY" -eq 1 ] && echo '  (dry run)')"
echo "== skills"
echo "    dest: $SKILLS_DIR/   (rm -rf then copy)"
run mkdir -p "$SKILLS_DIR"
skill_files=0
for folder in $FOLDERS; do
    src="$SCRIPT_DIR/$folder"
    [ -d "$src" ] || { echo "Error: $src not found" >&2; exit 1; }
    dest="$SKILLS_DIR/$folder"
    run rm -rf "$dest"
    run mkdir -p "$dest"
    if [ "$DRY" -eq 0 ]; then
        # cp, not a tar pipe: macOS tar adds com.apple.provenance xattrs the extracting side cannot write.
        cp -R "$src/." "$dest/"
        find "$dest" \( -name opencode -o -name .DS_Store -o -name .idea -o -name __pycache__ -o -name '*.pyc' \) -prune -exec rm -rf {} +
        tree="$dest"
    else
        tree="$src"
    fi
    n=0
    echo "  $dest/"
    while IFS= read -r rel; do
        [ -n "$rel" ] || continue
        echo "    $rel"
        n=$((n + 1))
    done <<EOF
$(list_rel_files "$tree")
EOF
    echo "    ($n files)"
    skill_files=$((skill_files + n))
done
echo "  $skill_files files in $skill_n skill folders -> $SKILLS_DIR"

# Leftover installs under the old unprefixed (or -glm) folder names would load a second
# skill with a confusingly similar name next to the z- one.
STALE=""
for folder in $FOLDERS; do
    for old in "glm-${folder#z-}" "${folder#z-}" "${folder#z-}-glm"; do
        path="$SKILLS_DIR/$old"
        if [ -e "$path" ] || [ -L "$path" ]; then
            echo "WARN: stale: $path is an old install of $folder; the new install is $SKILLS_DIR/$folder"
            STALE="$STALE \"$path\""
        fi
    done
done
[ -z "$STALE" ] || echo "To remove the stale installs, run: rm -rf$STALE"

echo "== skipped"
if [ -n "$SKIPPED" ]; then
    for skip in $SKIPPED; do
        echo "    $SCRIPT_DIR/$skip/   (z-* folder with no SKILL.md at root; not installed)"
    done
fi

if [ "$DRY" -eq 1 ]; then
    echo
    echo "Dry run. Nothing written."
    exit 0
fi

cat <<MSG

Done. $skill_files files in $skill_n skill folders -> $SKILLS_DIR.
Skills load from the scanned roots when dsh starts; restart dsh to pick up changes.
MSG
```

- [ ] **Step 4: Run the suite to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_install_dsh.py -v`
Expected: `OK` - all ten tests pass

- [ ] **Step 5: Smoke the dry run**

Run: `sh install-dsh.sh --dry-run`
Expected: exit 0, the dest line and per-skill file lists printed, `Dry run. Nothing written.` as the last line

- [ ] **Step 6: Commit the failing suite (RED)**

```bash
git add _shared/tests/test_install_dsh.py
git commit -m "test(S1): RED - dsh installer end-to-end suite (fails without install-dsh.sh)"
```

- [ ] **Step 7: Commit the installer (GREEN)**

```bash
git add install-dsh.sh
git commit -m "feat(S1): GREEN - install-dsh.sh for the dsh user skills root"
```

---

### T02: retire the dead four-target suite; verify both installers for real

**Depends:** T01

**Interfaces:**
- Consumes: `sh install-dsh.sh [--home DIR] [--dry-run]`

**Files:**
- Modify: `_shared/tests/test_install_all.py`

- [ ] **Step 1: Remove the dead suite**

The four-target installer script was removed from the tree, and this file pins it by path, so the file fails the suite and its requirement is gone. Delete the file and stage the deletion:

Run: `rm _shared/tests/test_install_all.py`
Expected: the file is gone from `_shared/tests/`

- [ ] **Step 2: Stage the deletion**

Run: `git add _shared/tests/test_install_all.py`
Expected: `git status --short` shows `D  _shared/tests/test_install_all.py`

- [ ] **Step 3: Run the full suite to verify it is green**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: `OK` - no failures and no errors across all test modules

- [ ] **Step 4: Real install into the zCode tree**

Run: `sh install-zcode.sh`
Expected: exit 0, the per-skill inventory printed for all eleven folders, and the closing `Done.` block naming the flash pin

- [ ] **Step 5: Real install into the dsh tree**

Run: `sh install-dsh.sh`
Expected: exit 0, `Done. ...` with the total file count and the destination under `~/.dsh/skills`

- [ ] **Step 6: Verify both targets hold the eleven glm folders**

Run: `ls ~/.zcode/skills | grep -c "^z-"`
Expected: `11`

Run: `ls ~/.dsh/skills | grep -c "^z-"`
Expected: `11`

- [ ] **Step 7: Commit**

```bash
git add _shared/tests/test_install_all.py
git commit -m "chore: drop the four-target suite whose installer is gone"
```

```json

{
 "request": "Verify install-zcode.sh installs every file at its zCode location unchanged, add install-dsh.sh that lands all eleven z-* skill folders in the dsh user skills root (dsh home: --home DIR, else $DSH_HOME, else $HOME/.dsh), and remove the dead four-target test file so the suite is green. Spec: docs/specs/2026-11-20-zcode-dsh-installers.md",
 "profile": "balanced",
 "glm": {
  "tier": "api"
 },
 "commands": {
  "build": "none",
  "test": "cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests",
  "test_file": "cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_install_dsh.py",
  "lint": "none",
  "lint_file": "none",
  "typecheck": "none",
  "typecheck_file": "none"
 },
 "contracts": [
  "C1 dsh installer CLI: sh install-dsh.sh [--home DIR] [--dry-run] - established in S1, consumed by S2",
  "C2 suite module: _shared/tests/test_install_dsh.py exposing InstallDshTests - established in S1"
 ],
 "notes": "Work happens inside z-skills (suites run from there, never the repo root). The plan task bodies above hold the exact code: follow the T01 body verbatim (RED suite first, then the script, then green, then one commit adding both files). Mirror install-zcode.sh's structure: set -eu, run() dry-run wrapper, python3 heredoc preflight, pause trap. Junk excluded on every copy: .DS_Store, __pycache__, *.pyc, .idea, opencode. Only z-* folders are replaced in a target; foreign folders untouched; stale old-name installs warn and stay. Preflight aborts non-zero before the first copy (description empty or over 1024 chars, SKILL.md over 100KB, frontmatter name missing or not kebab-case). Representative test file: _shared/tests/test_install_zcode.py. Commit messages English, conventional prefixes, exact paths only. Footprint and context paths are git-root-relative; test commands cd into z-skills first. Code slices commit the failing suite before the implementation: RED commit message starts test(SLICEID): and contains only test files, GREEN commit follows.",
 "test_globs": [
  "_shared/tests/test_*.py"
 ],
 "slices": [
  {
   "id": "S1",
   "title": "install-dsh.sh with its end-to-end suite",
   "goal": "Create _shared/tests/test_install_dsh.py exactly as the T01 Step 1 body, watch it fail with the missing-script error, then create install-dsh.sh exactly as the T01 Step 3 body, watch the suite pass, smoke the dry run, and make the two commits from the T01 Step 6 and Step 7 bodies: the failing-suite RED commit test(S1): ... first, then the installer GREEN commit feat(S1): ...",
   "kind": "code",
   "size": "small",
   "deps": [],
   "files": [
    "z-skills/install-dsh.sh",
    "z-skills/_shared/tests/test_install_dsh.py"
   ],
   "risk": "low",
   "isolation": true,
   "criteria": [
    "the dsh suite passes: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_install_dsh.py -v reports OK",
    "a dry run exits 0, prints the per-skill inventory and Dry run. Nothing written., and creates nothing",
    "a real run into a temp HOME puts every skill folder under <home>/.dsh/skills with junk pruned and foreign folders untouched",
    "the preflight rejects an over-1024-characters description and a non-kebab-case name before any copy",
    "a rerun is idempotent and replaces changed files; stale unprefixed folders warn and stay"
   ],
   "edge_cases": [
    "HOME and DSH_HOME both unset exits non-zero with a HOME error",
    "a tree with no z-*/SKILL.md folders fails loudly",
    "--home DIR overrides $DSH_HOME"
   ],
   "context": [
    "z-skills/install-zcode.sh",
    "z-skills/_shared/tests/test_install_zcode.py"
   ]
  },
  {
   "id": "S2",
   "title": "retire the dead four-target suite; verify both installers for real",
   "goal": "Delete _shared/tests/test_install_all.py (it pins a script the tree no longer contains), run the full z-skills suite green, run sh install-zcode.sh and sh install-dsh.sh for real, verify eleven z-* folders under both ~/.zcode/skills and ~/.dsh/skills, then the one commit from the T02 Step 7 body.",
   "kind": "chore",
   "size": "trivial",
   "deps": [
    "S1"
   ],
   "files": [
    "z-skills/_shared/tests/test_install_all.py",
    "z-skills/_shared/tests/test_install_dsh.py",
    "z-skills/install-dsh.sh"
   ],
   "risk": "low",
   "isolation": true,
   "criteria": [
    "the full suite is green: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests reports OK",
    "sh install-zcode.sh exits 0 with the closing Done. block",
    "sh install-dsh.sh exits 0 with the closing Done. block",
    "ls ~/.zcode/skills | grep -c '^z-' prints 11 and ls ~/.dsh/skills | grep -c '^z-' prints 11"
   ],
   "edge_cases": [
    "the deletion is staged with git add of the exact path before the commit"
   ],
   "context": [
    "z-skills/docs/specs/2026-11-20-zcode-dsh-installers.md"
   ],
   "verify": "cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests",
   "notes_extra": "footprint widened at integrate: the diff base predates S1's merge, so S1's two files ride in S2's footprint"
  }
 ]
}
```
