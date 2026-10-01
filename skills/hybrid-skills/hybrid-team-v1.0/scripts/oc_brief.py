"""Pre-chewed opencode brief builder."""
from pathlib import Path

BRIEF_CAP = 40000


def _read_text(worktree, rel_path):
    path = Path(worktree) / rel_path
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data:
        return None
    return data.decode("utf-8", errors="replace")


def build_brief(claim_text: str, s: dict, worktree: Path, frozen: list, cap: int = BRIEF_CAP) -> str:
    worktree = Path(worktree)
    sections = []
    sections.append("# opencode brief\n\n## Claim\n\n" + claim_text.strip())

    goal = s.get("goal", "")
    if goal:
        sections.append("## Goal\n\n" + goal.strip())

    criteria = s.get("criteria") or []
    if criteria:
        lines = "\n".join("- " + str(c) for c in criteria)
        sections.append("## Acceptance criteria\n\n" + lines)

    contracts = s.get("contracts") or []
    if contracts:
        lines = "\n".join("- " + str(c) for c in contracts)
        sections.append("## Contracts\n\n" + lines)

    footprint = s.get("footprint") or []
    if footprint:
        lines = "\n".join("- " + str(p) for p in footprint)
        sections.append("## Footprint\n\n" + lines)

    if frozen:
        blocks = ["## Frozen RED test (expect GREEN)\n"]
        for rel in frozen:
            content = _read_text(worktree, rel) or ""
            blocks.append("### " + str(rel) + "\n\n```\n" + content + "\n```")
        sections.append("\n\n".join(blocks))

    commands = s.get("commands") or []
    if commands:
        blocks = ["```\n" + str(c) + "\n```" for c in commands]
        sections.append("## Commands\n\n" + "\n".join(blocks))

    context = s.get("context") or []
    if context:
        blocks = []
        for rel in context:
            rel_path = str(rel).split("#", 1)[0].strip()
            if not rel_path:
                continue
            content = _read_text(worktree, rel_path)
            if content is None:
                continue
            blocks.append("### " + str(rel) + "\n\n```\n" + content + "\n```")
        if blocks:
            sections.append("## Context files\n\n" + "\n\n".join(blocks))

    brief = "\n\n".join(sections) + "\n"

    if len(brief) > cap:
        marker = "\n\n...[truncated: brief exceeded cap]\n"
        keep = cap - len(marker)
        if keep < 0:
            keep = 0
        brief = brief[:keep] + marker

    return brief
