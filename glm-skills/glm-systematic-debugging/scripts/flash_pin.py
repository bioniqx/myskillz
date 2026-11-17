"""Flash pin for GLM-5.3-Flash and DeepSeek V4.1 Flash.

~/.zcode/glm-flash holds one word, glm or deepseek. Agent install and the
HTTP fan-out both follow it. GLM_FLASH overrides that file for one process.
A missing HOME is "no pin file": unit tests that clear the environment stay
on GLM even when the developer has a pin installed.
"""

import os
import re

DEEPSEEK_API = "deepseek-flash"
DEEPSEEK_BASE = "https://api.deepseek.com"
API_REMAP = {
    "glm-5.3-flash": DEEPSEEK_API,
    "glm-5.3": DEEPSEEK_API,
    "GLM-5.3-Flash": DEEPSEEK_API,
    "GLM-5.3": DEEPSEEK_API,
}
_MODEL_LINE = re.compile(r"(?m)^model:[ \t]*.*(?:\n|$)")


def _word(text):
    parts = (text or "").strip().split()
    return parts[0].lower() if parts else ""


def _name(word):
    if word in ("deepseek", "ds", "deepseek-flash"):
        return "deepseek"
    if word in ("glm", "glm-5.3-flash", "flash"):
        return "glm"
    return ""


def _home(home):
    if home:
        return home
    return os.environ.get("HOME") or ""


def from_env():
    return _name(_word(os.environ.get("GLM_FLASH")))


def from_file(home=None):
    home = _home(home)
    if not home:
        return ""
    path = os.path.join(home, ".zcode", "glm-flash")
    try:
        with open(path, encoding="utf-8") as fh:
            word = _word(fh.read())
    except OSError:
        return ""
    return _name(word)


def provider(home=None):
    """glm or deepseek. GLM_FLASH wins, then the pin file, then glm."""
    return from_env() or from_file(home) or "glm"


def agent_provider(home=None):
    return provider(home)


def http_provider():
    return provider()


def stamp_agent(text, home=None, forced=None):
    """Drop every frontmatter model line. The session model is the lane.

    home and forced are accepted so older callers keep working. They do not
    write a model id back.
    """
    del home, forced
    return _MODEL_LINE.sub("", text)


def stamp_tree(home, forced=None):
    """Stamp glm-* skills and ~/.zcode/agents. Leave every other tree alone."""
    n = 0
    roots = []
    agents = os.path.join(home, ".zcode", "agents")
    if os.path.isdir(agents):
        roots.append(agents)
    skills = os.path.join(home, ".zcode", "skills")
    if os.path.isdir(skills):
        for name in sorted(os.listdir(skills)):
            if name.startswith("glm-"):
                roots.append(os.path.join(skills, name))
    for root in roots:
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in ("opencode", "__pycache__", ".idea")]
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                stamped = stamp_agent(text, home=home, forced=forced)
                if stamped == text:
                    continue
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(stamped)
                n += 1
    return n


def resolve_http_model(model):
    if http_provider() != "deepseek":
        return model
    return API_REMAP.get(model, model)
