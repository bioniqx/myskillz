#!/usr/bin/env python3
"""Validate installed ZCode skills (frontmatter hygiene + scope shadowing).

Usage:
    python3 validate_install.py [skill-dir ...]   # no args: scan both scopes
    python3 validate_install.py --selftest

Default scan roots: ~/.zcode/skills (user) and <cwd>/.zcode/skills (project).
Checks per skill dir: SKILL.md present; frontmatter `name` is kebab-case and
equals the directory name; `description` present and <=1024 chars; trigger
text inside the first 250 chars (heuristic WARN); body <=100KB (FAIL) and
<=500 lines (WARN). Same `name` in both scopes reports a shadowing WARN.
Exit codes: 0 all pass (warnings allowed), 1 any FAIL, 2 usage/no skills.
"""
import os
import re
import sys
import tempfile

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
DESC_LIMIT = 1024
TRIGGER_HINTS = ("use when", "use this", "when ", "use for", "for ")
FOLD_HEADS = (">-", ">", "|-", "|")


def parse_frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return {}
    fields, key = {}, None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if line[:1] not in (" ", "\t"):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
        elif key:
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def clean_value(value):
    head, _, rest = value.partition(" ")
    if head in FOLD_HEADS:
        return rest.strip()
    return value.strip("\"'")


def check_skill(path):
    """Return (name, rows) where rows are (level, message) tuples."""
    skill_md = os.path.join(path, "SKILL.md")
    rows = []
    if not os.path.isfile(skill_md):
        return None, [("FAIL", "no SKILL.md at folder root")]
    with open(skill_md, encoding="utf-8") as fh:
        text = fh.read()
    fm = parse_frontmatter(text)
    if not fm:
        return None, [("FAIL", "no frontmatter block")]
    name = clean_value(fm.get("name", ""))
    if not name:
        rows.append(("FAIL", "frontmatter name missing"))
    elif not NAME_RE.match(name):
        rows.append(("FAIL", "name %r is not lowercase kebab-case (1-64)" % name))
    elif name != os.path.basename(os.path.normpath(path)):
        rows.append(("FAIL", "name %r != directory %r" % (name, os.path.basename(os.path.normpath(path)))))
    desc = clean_value(fm.get("description", ""))
    if not desc:
        rows.append(("FAIL", "description missing (ZCode drops the skill)"))
    else:
        if len(desc) > DESC_LIMIT:
            rows.append(("FAIL", "description is %d chars (ZCode drops above %d)" % (len(desc), DESC_LIMIT)))
        head = desc[:250].lower()
        if not any(h in head for h in TRIGGER_HINTS):
            rows.append(("WARN", "no trigger phrasing in the first 250 chars of description"))
    size = len(text.encode("utf-8"))
    if size > 100 * 1024:
        rows.append(("FAIL", "SKILL.md is %dKB (loaded body truncates above 100KB)" % (size // 1024)))
    lines = text.count("\n")
    if lines > 500:
        rows.append(("WARN", "body is %d lines (target under 500)" % lines))
    if not rows:
        rows.append(("PASS", "name=%s description=%d chars" % (name, len(desc))))
    return name, rows


def scan(roots):
    """Return (report rows, fail count) across every skill dir under roots.

    A root may itself be a skill dir (SKILL.md at its root); other roots are
    scanned one level down, skipping entries without SKILL.md."""
    rows, fails, names = [], 0, {}
    seen = set()
    for root_idx, root in enumerate(roots):
        if not os.path.isdir(root):
            continue
        if os.path.isfile(os.path.join(root, "SKILL.md")):
            candidates = [root]
        else:
            candidates = [os.path.join(root, e) for e in sorted(os.listdir(root))]
        for path in candidates:
            if not os.path.isdir(path) or not os.path.isfile(os.path.join(path, "SKILL.md")):
                continue
            real = os.path.realpath(path)
            if real in seen:
                continue
            seen.add(real)
            name, skill_rows = check_skill(path)
            rows.append((path, skill_rows))
            fails += sum(1 for level, _ in skill_rows if level == "FAIL")
            if name:
                names.setdefault(name, []).append((root_idx, path))
    for name, hits in sorted(names.items()):
        scopes = [idx for idx, _ in hits]
        if len(set(scopes)) > 1:
            for idx, path in hits[1:]:
                rows.append((path, [("WARN", "name %r also installed at %s; the earlier scope shadows this one" % (name, hits[0][1]))]))
    return rows, fails


def main(argv):
    if "--selftest" in argv:
        return selftest()
    if argv:
        roots = argv
    else:
        roots = [os.path.expanduser("~/.zcode/skills"), os.path.join(os.getcwd(), ".zcode", "skills")]
    rows, fails = scan(roots)
    if not rows:
        print("RESULT fail=2 no skill folders found under: %s" % ", ".join(roots))
        return 2
    warns = 0
    for path, skill_rows in rows:
        for level, msg in skill_rows:
            print("%s %s - %s" % (level, path, msg))
            warns += level == "WARN"
    print("RESULT fail=%d warn=%d" % (fails, warns))
    if fails:
        print("NEXT: fix every FAIL (rename dir / trim description), then start a new ZCode session")
        return 1
    print("NEXT: start a new ZCode session to load the installed skill(s)")
    return 0


def make_skill(root, folder, name, desc="Use when the user needs this skill. " * 2, body_lines=10):
    path = os.path.join(root, folder)
    os.makedirs(path, exist_ok=True)
    body = "\n".join("line %d" % i for i in range(body_lines))
    with open(os.path.join(path, "SKILL.md"), "w", encoding="utf-8") as fh:
        fh.write("---\nname: %s\ndescription: %s\n---\n# Skill\n%s\n" % (name, desc, body))
    return path


def selftest():
    ok = 0
    with tempfile.TemporaryDirectory() as tmp:
        a, b = os.path.join(tmp, "user"), os.path.join(tmp, "proj")
        os.makedirs(a), os.makedirs(b)
        make_skill(a, "good-skill", "good-skill")
        _, rows = check_skill(os.path.join(a, "good-skill"))
        assert all(l == "PASS" for l, _ in rows), rows
        ok += 1
        make_skill(a, "wrong-name", "other-name")
        _, rows = check_skill(os.path.join(a, "wrong-name"))
        assert any(l == "FAIL" and "!=" in m for l, m in rows), rows
        ok += 1
        make_skill(a, "long-desc", "long-desc", desc="x" * 1100)
        _, rows = check_skill(os.path.join(a, "long-desc"))
        assert any(l == "FAIL" and "1024" in m for l, m in rows), rows
        ok += 1
        make_skill(a, "bad-case", "Bad_Name")
        _, rows = check_skill(os.path.join(a, "bad-case"))
        assert any(l == "FAIL" and "kebab" in m for l, m in rows), rows
        ok += 1
        make_skill(a, "big-body", "big-body", body_lines=15000)
        _, rows = check_skill(os.path.join(a, "big-body"))
        assert any(l == "FAIL" and "100KB" in m for l, m in rows), rows
        assert any(l == "WARN" and "500" in m for l, m in rows), rows
        ok += 1
        empty = os.path.join(a, "no-skill-md")
        os.makedirs(empty, exist_ok=True)
        _, rows = check_skill(empty)
        assert any(l == "FAIL" and "SKILL.md" in m for l, m in rows), rows
        ok += 1
        rows, fails = scan([a, b])
        assert fails == 4, fails
        assert any(l == "WARN" and "shadows" not in m for _p, rs in rows for l, m in rs), rows
        ok += 1
        make_skill(b, "good-skill", "good-skill")
        rows, _fails = scan([a, b])
        flat = [(l, m) for _p, rs in rows for l, m in rs]
        assert any("shadows" in m for l, m in flat if l == "WARN"), flat
        ok += 1
        rows, _fails = scan([os.path.join(a, "good-skill")])
        assert len(rows) == 1 and all(l == "PASS" for l, _m in rows[0][1]), rows
        ok += 1
    print("SELFTEST ok=%d" % ok)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
