# Shared helpers. Bash 3.2 compatible (macOS default shell).
sd_cpus() { getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4; }
sd_default_jobs() { local c; c=$(sd_cpus); [ "$c" -gt 64 ] && c=64; echo "$c"; }
sd_clamp_jobs() { local j=$1; case "$j" in ''|*[!0-9]*) echo "error: -j needs a number" >&2; exit 2;; esac
  [ "$j" -lt 1 ] && j=1; [ "$j" -gt 64 ] && j=64; echo "$j"; }
sd_timeout_bin() { command -v timeout 2>/dev/null || command -v gtimeout 2>/dev/null || true; }
sd_now() { date +%s; }
# Descendants of $1 as "depth pid" lines (depth 1 = direct children): BFS over ONE ps snapshot, walked in awk.
sd_levels() {
  ps -eo pid=,ppid= 2>/dev/null | awk -v root="$1" '
    { kids[$2] = kids[$2] " " $1 }
    END {
      f = root; d = 0
      while (f != "") {
        d++; nx = ""
        n = split(f, a, " ")
        for (i = 1; i <= n; i++) {
          m = split(kids[a[i]], k, " ")
          for (j = 1; j <= m; j++) { print d, k[j]; nx = nx " " k[j] }
        }
        f = nx
      }
    }'
}
# Direct children of $1 (one ps snapshot).
sd_children_of() { sd_levels "$1" | awk '$1==1{print $2}'; }
# SIGSTOP $1 and its descendants top-down, rescanning until no new descendant shows up, so nothing
# can fork a replacement child between a snapshot and the kill (SIGKILL works on stopped pids).
sd_freeze_tree() {
  local root=$1 seen=" $1 " round=0 grew=1 d pid
  kill -STOP "$root" 2>/dev/null
  while [ $grew = 1 ] && [ $round -lt 10 ]; do
    grew=0; round=$((round+1))
    while IFS=' ' read -r d pid; do
      [ -z "$pid" ] && continue
      case "$seen" in *" $pid "*) continue;; esac
      seen="$seen$pid "; grew=1; kill -STOP "$pid" 2>/dev/null
    done <<EOF
$(sd_levels "$root")
EOF
  done
}
# Freeze then kill a process and its whole descendant tree, leaves first. $1 is the root pid;
# $2 = 1 kills the root first instead of last.
sd_kill_tree() {
  local root=$1 root_first=${2:-0}; [ -z "$root" ] && return 0
  # a second Ctrl-C/TERM mid-kill must not abort us with the tree still stopped
  local oldtrap; oldtrap=$(trap -p INT TERM); trap '' INT TERM
  sd_freeze_tree "$root"
  # TERM + CONT the frozen tree, give traps ~0.3s to run
  local all="$root" init="" i=0 alive=1 x d pid
  init=$(sd_levels "$root")
  while IFS=' ' read -r d pid; do
    [ -n "$pid" ] && all="$all $pid"
  done <<EOF
$init
EOF
  kill -TERM $all 2>/dev/null; kill -CONT $all 2>/dev/null
  while [ $alive = 1 ] && [ $i -lt 6 ]; do
    alive=0; for x in $all; do kill -s 0 "$x" 2>/dev/null && { alive=1; break; }; done
    [ $alive = 1 ] && { sleep 0.05; i=$((i+1)); }
  done
  # traps may have forked new children, or the root may have exited and orphaned its subtree:
  # re-freeze and rescan from fresh ps snapshots (root, then any surviving snapshot pid not yet
  # covered) before SIGKILL
  local -a LVL; local maxd=0 covered=" " bd rel
  while IFS=' ' read -r bd x; do
    [ -z "$x" ] && continue
    case "$covered" in *" $x "*) continue;; esac
    kill -s 0 "$x" 2>/dev/null || continue
    sd_freeze_tree "$x"
    covered="$covered$x "
    if [ "$x" != "$root" ]; then
      LVL[$bd]="${LVL[$bd]:-} $x"; [ "$bd" -gt "$maxd" ] && maxd=$bd
    fi
    while IFS=' ' read -r rel pid; do
      [ -z "$pid" ] && continue
      covered="$covered$pid "; d=$((bd+rel))
      LVL[$d]="${LVL[$d]:-} $pid"; [ "$d" -gt "$maxd" ] && maxd=$d
    done <<EOF
$(sd_levels "$x")
EOF
  done <<EOF
0 $root
$init
EOF
  [ "$root_first" = 1 ] && kill -KILL "$root" 2>/dev/null
  d=$maxd
  while [ "$d" -ge 1 ]; do
    kill -KILL ${LVL[$d]:-} 2>/dev/null
    d=$((d-1))
  done
  [ "$root_first" != 1 ] && kill -KILL "$root" 2>/dev/null
  wait "$root" 2>/dev/null
  trap - INT TERM; [ -n "$oldtrap" ] && eval "$oldtrap"
  return 0
}
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
