# Shared helpers. Bash 3.2 compatible (macOS default shell).
sd_cpus() { getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4; }
sd_default_jobs() { local c; c=$(sd_cpus); [ "$c" -gt 64 ] && c=64; echo "$c"; }
sd_clamp_jobs() { local j=$1; case "$j" in ''|*[!0-9]*) echo "error: -j needs a number" >&2; exit 2;; esac
  [ "$j" -lt 1 ] && j=1; [ "$j" -gt 64 ] && j=64; echo "$j"; }
sd_timeout_bin() { command -v timeout 2>/dev/null || command -v gtimeout 2>/dev/null || true; }
sd_now() { date +%s; }
# Create a detached worktree at $2 from commit $1 (inside repo). Quiet.
sd_worktree_add() { git worktree add --detach --force "$2" "$1" >/dev/null 2>&1; }
# Symlink each dir listed in SD_LINKS (newline separated, repo-relative) from repo root into worktree $1.
sd_link_deps() { local wt=$1 d; [ -z "${SD_LINKS:-}" ] && return 0
  while IFS= read -r d; do [ -z "$d" ] && continue
    if [ -e "$SD_ROOT/$d" ] && [ ! -e "$wt/$d" ]; then mkdir -p "$(dirname "$wt/$d")"; ln -s "$SD_ROOT/$d" "$wt/$d"; fi
  done <<LINKS
$SD_LINKS
LINKS
}
