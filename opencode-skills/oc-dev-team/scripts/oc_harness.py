"""Shared OpenCode harness: version detection, v2 agent rendering and skill install."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys


def detect(binary: str = "opencode") -> int:
    try:
        result = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return 0
    text = (result.stdout or "") + (result.stderr or "")
    match = re.search(r"(\d+)\.\d+\.\d+", text)
    if not match:
        return 0
    return int(match.group(1))


OC_SKILL_DIRS = (os.path.join(".opencode", "skills"), os.path.join(".config", "opencode", "skills"))
MAJOR_MARKER = ".oc-major"


def _require_v2(major):
    if major != 2:
        raise ValueError("OpenCode v2 required")


def _skill_dir_for(script_path):
    """The skill folder of a script: its parent, or the parent's parent for a `scripts/` dir."""
    folder = os.path.dirname(os.path.abspath(script_path))
    return os.path.dirname(folder) if os.path.basename(folder) == "scripts" else folder


def _has_part(path, rel):
    return (os.sep + rel.strip(os.sep) + os.sep) in path


def _within(path, root):
    for base in (os.path.abspath(root), os.path.realpath(root)):
        base = base.rstrip(os.sep)
        if path == base or path.startswith(base + os.sep):
            return True
    return False


def harness(script_path: str = "") -> str:
    """Return 'opencode' or 'unknown' for the harness running script_path.

    v2 sets only OPENCODE_TERMINAL=1 in shell children, so the script location and the
    install marker count as evidence too. script_path defaults to this module's own file."""
    env = os.environ
    if env.get("OPENCODE") or env.get("OPENCODE_TERMINAL"):
        return "opencode"
    script = os.path.abspath(script_path or __file__)
    paths = [script, os.path.realpath(script)]
    config_dir = env.get("OPENCODE_CONFIG_DIR", "")
    for path in paths:
        if any(_has_part(path, rel) for rel in OC_SKILL_DIRS):
            return "opencode"
        if config_dir and _within(path, config_dir):
            return "opencode"
    for folder in (os.path.dirname(script), _skill_dir_for(script)):
        if os.path.isfile(os.path.join(folder, MAJOR_MARKER)):
            return "opencode"
    return "unknown"


_DETECT_CACHE = {}


def _read_marker(skill_dir):
    try:
        with open(os.path.join(skill_dir, MAJOR_MARKER)) as fh:
            value = int(fh.read().strip())
    except (OSError, ValueError):
        return 0
    return value if value > 0 else 0


def major(skill_dir: str = "", binary: str = "opencode") -> int:
    """OpenCode major version: the skill's .oc-major marker first, then detect() cached per binary.

    skill_dir defaults to the skill folder holding this module. 0 means unknown / not found."""
    found = _read_marker(skill_dir or _skill_dir_for(__file__))
    if found:
        return found
    if binary not in _DETECT_CACHE:
        _DETECT_CACHE[binary] = detect(binary)
    return _DETECT_CACHE[binary]


FALLBACK_AGENT = "general"


def dispatch_line(agent: str, prompt_path: str, description: str, major: int, background: bool = True) -> str:
    """The tool call a model copies to start one lane: the v2 `subagent` tool with
    agent/description/prompt/background. It never names a model, so the lane runs on the model
    of the agent that launches it. An empty agent name falls back to the built-in `general`."""
    _require_v2(major)
    name = (agent or "").strip() or FALLBACK_AGENT
    prompt = "Read %s and follow it exactly." % prompt_path
    quoted = [json.dumps(value, ensure_ascii=False) for value in (name, description, prompt)]
    return "subagent(agent=%s, description=%s, prompt=%s, background=%s)" % (
        quoted[0], quoted[1], quoted[2], "true" if background else "false")


def _harness_line(script_path: str = "") -> str:
    """`<harness> <major>` for the CLI; major stays 0 outside OpenCode so no binary is spawned."""
    script = script_path or __file__
    name = harness(script)
    found = major(_skill_dir_for(script)) if name == "opencode" else 0
    return "%s %d" % (name, found)


def parse_frontmatter(text: str) -> tuple:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return ({}, text)
    fields = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i]
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                try:
                    value = json.loads(value)
                except ValueError:
                    value = value[1:-1]
            elif value == "true":
                value = True
            elif value == "false":
                value = False
            elif re.match(r"^-?\d+$", value):
                value = int(value)
            elif re.match(r"^-?\d+\.\d+$", value):
                value = float(value)
            fields[key] = value
        i += 1
    body = "\n".join(lines[i + 1:]).strip("\n")
    return (fields, body)


def render_agent(text: str, major: int) -> str:
    """Render one source agent file as an OpenCode v2 subagent.

    The `model` and `effort` keys of a source file are ignored: the agent runs on the model of
    the agent that launches it."""
    _require_v2(major)
    fields, body = parse_frontmatter(text)
    description = fields.get("description", "")
    steps = fields.get("steps")
    access = fields.get("access", "read")
    bash = fields.get("bash", False)
    web = fields.get("web", False)
    temperature = fields.get("temperature")
    write_paths = fields.get("write_paths") if access == "write" else None

    edit_perm = "allow" if access == "write" else "deny"
    bash_perm = "allow" if bash else "deny"
    web_perm = "allow" if web else "deny"

    lines = ["---"]
    lines.append("description: {}".format(json.dumps(description)))
    lines.append("mode: subagent")
    lines.append("hidden: true")
    if steps is not None:
        lines.append("steps: {}".format(steps))
    if temperature is not None:
        lines.append("temperature: {}".format(temperature))
    # `permission` is the nested map shape in agent frontmatter. opencode v2.0.22 names the shell
    # tool `shell`; earlier v2 builds read `bash`. Both keys carry the identical rule.
    lines.append("permission:")
    if write_paths:
        lines.append("  edit:")
        lines.append('    "*": deny')
        lines.append('    "{}": allow'.format(write_paths))
    else:
        lines.append("  edit: {}".format(edit_perm))
    lines.append("  bash: {}".format(bash_perm))
    lines.append("  shell: {}".format(bash_perm))
    lines.append("  webfetch: {}".format(web_perm))
    if write_paths:
        lines.append("  task: deny")
    # websearch is gated separately from webfetch, so it gets an explicit value. `execute` runs
    # code outside the bash permission, so it is always denied.
    lines.append("  websearch: {}".format(web_perm))
    lines.append("  execute: deny")
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)


def render_command(text: str, major: int, skill_dir: str) -> str:
    _require_v2(major)
    fields, body = parse_frontmatter(text)
    description = fields.get("description", "")
    rendered_body = body.replace("{{SKILL_DIR}}", skill_dir)
    lines = ["---", "description: {}".format(json.dumps(description)), "---", "", rendered_body]
    return "\n".join(lines)


def skill_name(skill_dir: str) -> str:
    """Install name = SKILL.md frontmatter name; the folder name when the field is absent."""
    with open(os.path.join(skill_dir, "SKILL.md")) as fh:
        fields, _ = parse_frontmatter(fh.read())
    return str(fields.get("name") or os.path.basename(os.path.normpath(skill_dir)))


def install(skill_dir: str, major: int, home: str = "") -> list:
    _require_v2(major)
    root = os.path.join(home or os.path.expanduser("~"), ".config", "opencode")
    skill_dst = os.path.join(root, "skills", skill_name(skill_dir))
    if os.path.realpath(skill_dir) != os.path.realpath(skill_dst):
        if os.path.isdir(skill_dst):
            shutil.rmtree(skill_dst)
        shutil.copytree(skill_dir, skill_dst,
                        ignore=shutil.ignore_patterns("__pycache__", ".idea", ".DS_Store"))
    written = [skill_dst]
    for kind in ("agents", "commands"):
        src = os.path.join(skill_dir, "opencode", kind)
        if not os.path.isdir(src):
            continue
        dst = os.path.join(root, kind)
        os.makedirs(dst, exist_ok=True)
        for fname in sorted(os.listdir(src)):
            if not fname.endswith(".md"):
                continue
            with open(os.path.join(src, fname)) as fh:
                text = fh.read()
            if kind == "agents":
                text = render_agent(text, major)
            else:
                text = render_command(text, major, skill_dst)
            path = os.path.join(dst, fname)
            with open(path, "w") as fh:
                fh.write(text)
            written.append(path)
    guards_src = os.path.join(skill_dir, "opencode", "plugins")
    if os.path.isdir(guards_src):
        guards_dst = os.path.join(root, "plugins")
        os.makedirs(guards_dst, exist_ok=True)
        for fname in sorted(os.listdir(guards_src)):
            # `<base>.js` and `<base>.v2.js` install as `<base>.js`; a `.v1.js` file is skipped.
            match = re.match(r"^(.+?)(?:\.v(\d+))?\.js$", fname)
            if not match or match.group(2) not in (None, "2"):
                continue
            with open(os.path.join(guards_src, fname)) as fh:
                # skill_dst sits inside a JS string literal in the template, so it must be
                # JS/JSON-escaped, not pasted in raw (a quote or backslash would break the JS).
                text = fh.read().replace("{{SKILL_DIR}}", json.dumps(skill_dst)[1:-1])
            path = os.path.join(guards_dst, match.group(1) + ".js")
            with open(path, "w") as fh:
                fh.write(text)
            written.append(path)
    marker = os.path.join(skill_dst, MAJOR_MARKER)
    with open(marker, "w") as fh:
        fh.write(str(major))
    written.append(marker)
    return written


def check(skill_dir: str, home: str = "") -> list:
    name = skill_name(skill_dir)
    root = os.path.join(home or os.path.expanduser("~"), ".config", "opencode")
    marker = os.path.join(root, "skills", name, MAJOR_MARKER)
    if not os.path.isfile(marker):
        return ["MISSING: %s is not installed for OpenCode" % name]
    with open(marker) as fh:
        installed = int(fh.read().strip())
    lines = ["INSTALLED: %s (major %d)" % (name, installed)]
    detected = detect()
    if not detected:
        lines.append("FAIL: opencode binary not found")
    elif detected != 2:
        lines.append("FAIL: OpenCode v2 required, found major %d" % detected)
    elif detected != installed:
        lines.append("FAIL: installed major %d != detected major %d, re-run install-opencode.sh"
                     % (installed, detected))
    return lines


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(prog="oc_harness.py", description="OpenCode harness helpers")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("detect", help="print the OpenCode major version (0 = not found)")
    p = sub.add_parser("install", help="install one skill with its agents and commands")
    p.add_argument("skill_dir")
    p.add_argument("major", nargs="?", type=int, default=0)
    p.add_argument("home", nargs="?", default="")
    p = sub.add_parser("check", help="verify installed skills against the local opencode")
    p.add_argument("skill_dirs", nargs="+")
    p.add_argument("--home", default="", help="home dir holding .config/opencode (default ~)")
    p = sub.add_parser("harness", help="print '<harness> <major>' for the running script")
    p.add_argument("--script", default="", help="script whose location is checked (default: this file)")
    try:
        a = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if a.cmd == "detect":
        found = detect()
        print(found)
        return 0 if found else 1
    if a.cmd == "install":
        found = a.major or detect()
        if not found:
            print("opencode not found; OpenCode v2 required")
            return 1
        try:
            written = install(a.skill_dir, found, a.home)
        except ValueError as exc:
            print(exc)
            return 1
        for path in written:
            print(path)
        print("NEXT: python3 %s check %s  (verify the install)" % (os.path.abspath(__file__), a.skill_dir))
        return 0
    if a.cmd == "check":
        failed = False
        for skill_dir in a.skill_dirs:
            for line in check(skill_dir, a.home):
                print(line)
                failed = failed or line.startswith(("FAIL", "MISSING"))
        return 1 if failed else 0
    print(_harness_line(a.script))
    return 0


if __name__ == "__main__":
    sys.exit(main())
