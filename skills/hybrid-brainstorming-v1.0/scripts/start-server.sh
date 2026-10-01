#!/usr/bin/env bash
# Start the brainstorm server and output connection info
# Usage: start-server.sh [--project-dir <path>] [--host <bind-host>] [--url-host <display-host>] [--foreground] [--background]
#
# Starts server on a random high port, outputs JSON with URL.
# Each session gets its own directory to avoid conflicts.
#
# Options:
#   --project-dir <path>  Store session files under <path>/.hybrid-superpowers/brainstorm/
#                         instead of /tmp. Files persist after server stops.
#   --host <bind-host>    Host/interface to bind (default: 127.0.0.1).
#                         Use 0.0.0.0 in remote/containerized environments.
#   --url-host <host>     Hostname shown in returned URL JSON.
#   --idle-timeout-minutes <n>  Shut down after n minutes idle (default 240 = 4h).
#   --open                Auto-open the browser on the first screen (use only
#                         after the user approves the visual companion).
#   --foreground          Run server in the current terminal (no backgrounding).
#   --background          Force background mode (overrides Codex auto-foreground).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Parse arguments
PROJECT_DIR=""
FOREGROUND="false"
FORCE_BACKGROUND="false"
BIND_HOST="127.0.0.1"
URL_HOST=""
IDLE_TIMEOUT_MINUTES=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --host)
      BIND_HOST="$2"
      shift 2
      ;;
    --url-host)
      URL_HOST="$2"
      shift 2
      ;;
    --idle-timeout-minutes)
      IDLE_TIMEOUT_MINUTES="$2"
      shift 2
      ;;
    --open)
      export HYBRID_BRAINSTORMING_OPEN=1
      shift
      ;;
    --foreground|--no-daemon)
      FOREGROUND="true"
      shift
      ;;
    --background|--daemon)
      FORCE_BACKGROUND="true"
      shift
      ;;
    *)
      echo "{\"error\": \"Unknown argument: $1\"}"
      exit 1
      ;;
  esac
done

# Canonicalise PROJECT_DIR to an absolute path right away, before anything
# `cd`s elsewhere. A relative value (e.g. ".") is resolved against the
# caller's cwd here; resolving it later (after this script has cd'd into
# SCRIPT_DIR) would silently point the whole session at the wrong place.
if [[ -n "$PROJECT_DIR" ]]; then
  mkdir -p "$PROJECT_DIR" 2>/dev/null
  RESOLVED_PROJECT_DIR="$(cd "$PROJECT_DIR" 2>/dev/null && pwd)"
  if [[ -z "$RESOLVED_PROJECT_DIR" ]]; then
    echo "{\"error\": \"--project-dir not found or not a directory: $PROJECT_DIR\"}"
    exit 1
  fi
  PROJECT_DIR="$RESOLVED_PROJECT_DIR"
fi

if [[ -z "$URL_HOST" ]]; then
  if [[ "$BIND_HOST" == "127.0.0.1" || "$BIND_HOST" == "localhost" ]]; then
    URL_HOST="localhost"
  else
    URL_HOST="$BIND_HOST"
  fi
fi

if [[ -n "$IDLE_TIMEOUT_MINUTES" ]]; then
  if ! [[ "$IDLE_TIMEOUT_MINUTES" =~ ^[0-9]+$ ]] || [[ "$IDLE_TIMEOUT_MINUTES" -lt 1 ]]; then
    echo "{\"error\": \"--idle-timeout-minutes must be a positive integer\"}"
    exit 1
  fi
  export HYBRID_BRAINSTORMING_IDLE_TIMEOUT_MS=$(( IDLE_TIMEOUT_MINUTES * 60 * 1000 ))
fi

is_windows_like_shell() {
  case "${OSTYPE:-}" in
    msys*|cygwin*|mingw*) return 0 ;;
  esac
  if [[ -n "${MSYSTEM:-}" ]]; then
    return 0
  fi
  local uname_s
  uname_s="$(uname -s 2>/dev/null || true)"
  case "$uname_s" in
    MSYS*|MINGW*|CYGWIN*) return 0 ;;
  esac
  return 1
}

# Some environments reap detached/background processes. Auto-foreground when detected.
if [[ -n "${CODEX_CI:-}" && "$FOREGROUND" != "true" && "$FORCE_BACKGROUND" != "true" ]]; then
  FOREGROUND="true"
fi

# Windows/Git Bash reaps nohup background processes. Auto-foreground when detected.
if [[ "$FOREGROUND" != "true" && "$FORCE_BACKGROUND" != "true" ]]; then
  if is_windows_like_shell; then
    FOREGROUND="true"
  fi
fi

# Session files (server.log, server-info, .last-token) embed the session key —
# keep everything this script and the server create owner-only.
umask 077

# Stop any prior sessions for this same project dir. Each start used to try
# to kill a pid file inside its OWN brand-new session dir, which never
# existed, so old servers just piled up. Delegate to stop-server.sh, which
# verifies each session's per-start instance id before signalling anything —
# an unrelated process is never touched.
if [[ -n "$PROJECT_DIR" ]]; then
  HYBRID_BRAINSTORMING_ROOT="${PROJECT_DIR}/.hybrid-superpowers/brainstorm"
  if [[ -d "$HYBRID_BRAINSTORMING_ROOT" ]]; then
    for prior in "$HYBRID_BRAINSTORMING_ROOT"/*/; do
      [[ -d "$prior" ]] || continue
      prior="${prior%/}"
      if [[ -f "${prior}/state/server.pid" ]]; then
        "$SCRIPT_DIR/stop-server.sh" "$prior" >/dev/null 2>&1 || true
      fi
    done
  fi
fi

# Generate unique session directory
SESSION_ID="$$-$(date +%s)"

if [[ -n "$PROJECT_DIR" ]]; then
  SESSION_DIR="${PROJECT_DIR}/.hybrid-superpowers/brainstorm/${SESSION_ID}"
  # Persist the bound port and key per project so a restart reuses them and an
  # already-open browser tab reconnects to the same URL with a valid cookie.
  export HYBRID_BRAINSTORMING_PORT_FILE="${PROJECT_DIR}/.hybrid-superpowers/brainstorm/.last-port"
  export HYBRID_BRAINSTORMING_TOKEN_FILE="${PROJECT_DIR}/.hybrid-superpowers/brainstorm/.last-token"
else
  SESSION_DIR="/tmp/hybrid-brainstorming-${SESSION_ID}"
fi

STATE_DIR="${SESSION_DIR}/state"
PID_FILE="${STATE_DIR}/server.pid"
LOG_FILE="${STATE_DIR}/server.log"
SERVER_ID_FILE="${STATE_DIR}/server-instance-id"
OWNER_PID_FILE="${STATE_DIR}/owner-pid"

# Create fresh session directory with content and state peers
mkdir -p "${SESSION_DIR}/content" "$STATE_DIR"

SERVER_ID=""
if [[ -r /dev/urandom ]]; then
  SERVER_ID="$(od -An -N24 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n' || true)"
fi
if ! [[ "$SERVER_ID" =~ ^[A-Za-z0-9_-]{32,64}$ ]]; then
  SERVER_ID="$(printf '%08x%08x%08x%08x' "$$" "$(date +%s)" "${RANDOM:-0}" "${RANDOM:-0}")"
fi
printf '%s\n' "$SERVER_ID" > "$SERVER_ID_FILE"
chmod 600 "$SERVER_ID_FILE" 2>/dev/null || true

cd "$SCRIPT_DIR" || exit 1

# Resolve the real process that owns this server by walking up the parent
# chain past shell/wrapper processes (sh, bash, zsh, dash, env, time,
# timeout, nohup). A single-hop assumption breaks as soon as the caller adds
# one more wrapper (e.g. `/usr/bin/time nohup sh -c '...'`), which used to
# make the server watch an intermediate wrapper's pid instead of the real
# owner and self-stop the moment that wrapper (not the owner) exited.
resolve_owner_pid() {
  local pid="$PPID"
  local hops=0
  while [[ $hops -lt 15 ]]; do
    local comm
    comm="$(ps -o comm= -p "$pid" 2>/dev/null | tr -d ' ')"
    comm="${comm##*/}"
    # Strip a leading '-' some shells use for login shells (e.g. "-bash").
    comm="${comm#-}"
    case "$comm" in
      sh|bash|zsh|dash|ksh|env|time|timeout|gtimeout|nohup)
        local parent
        parent="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')"
        if [[ -z "$parent" || "$parent" == "1" || "$parent" == "$pid" ]]; then
          break
        fi
        pid="$parent"
        ;;
      *)
        break
        ;;
    esac
    hops=$((hops+1))
  done
  printf '%s\n' "$pid"
}

if is_windows_like_shell; then
  # Windows/MSYS2: Node.js cannot see POSIX PIDs from the MSYS2 namespace.
  # Passing a PID node cannot verify causes server to log owner-pid-invalid
  # and self-terminate at the 60-second lifecycle check. Clear it so the
  # watchdog is disabled and the idle timeout becomes the only shutdown trigger.
  OWNER_PID=""
else
  OWNER_PID="$(resolve_owner_pid)"
fi

if [[ -n "$OWNER_PID" ]]; then
  printf '%s\n' "$OWNER_PID" > "$OWNER_PID_FILE"
  chmod 600 "$OWNER_PID_FILE" 2>/dev/null || true
fi

# JSON-escape a chunk of arbitrary log text for embedding as a string value.
json_escape_log() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk 'BEGIN{ORS="\\n"} {print} END{if(NR==0) printf ""}' | sed 's/\\n$//'
}

# Foreground mode for environments that reap detached/background processes.
if [[ "$FOREGROUND" == "true" ]]; then
  env HYBRID_BRAINSTORMING_DIR="$SESSION_DIR" HYBRID_BRAINSTORMING_HOST="$BIND_HOST" HYBRID_BRAINSTORMING_URL_HOST="$URL_HOST" HYBRID_BRAINSTORMING_OWNER_PID="$OWNER_PID" node server.cjs "--hybrid-brainstorming-server-id=$SERVER_ID" &
  SERVER_PID=$!
  echo "$SERVER_PID" > "$PID_FILE"
  wait "$SERVER_PID"
  exit $?
fi

# Start server, capturing output to log file
# Use nohup to survive shell exit; disown to remove from job table
nohup env HYBRID_BRAINSTORMING_DIR="$SESSION_DIR" HYBRID_BRAINSTORMING_HOST="$BIND_HOST" HYBRID_BRAINSTORMING_URL_HOST="$URL_HOST" HYBRID_BRAINSTORMING_OWNER_PID="$OWNER_PID" node server.cjs "--hybrid-brainstorming-server-id=$SERVER_ID" > "$LOG_FILE" 2>&1 &
SERVER_PID=$!
disown "$SERVER_PID" 2>/dev/null
echo "$SERVER_PID" > "$PID_FILE"

# Wait for server-started message (check log file). 0.05s steps: the server
# typically boots in 100-300ms, so fine polling shaves startup latency.
# Bail out the instant the process dies instead of polling the full window,
# so a dead-on-arrival node fails in ~1 step rather than up to 5s.
for _ in {1..100}; do
  if grep -q "server-started" "$LOG_FILE" 2>/dev/null; then
    # Verify server is still alive after a short window (catches process reapers).
    # 4 x 0.05s is enough: reapers that kill on detach do so within milliseconds.
    alive="true"
    for _ in {1..4}; do
      if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        alive="false"
        break
      fi
      sleep 0.05
    done
    if [[ "$alive" != "true" ]]; then
      echo "{\"error\": \"Server started but was killed. Retry in a persistent terminal with: $SCRIPT_DIR/start-server.sh${PROJECT_DIR:+ --project-dir $PROJECT_DIR} --host $BIND_HOST --url-host $URL_HOST --foreground\"}"
      exit 1
    fi
    grep "server-started" "$LOG_FILE" | head -1
    exit 0
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    tail_text="$(tail -n 3 "$LOG_FILE" 2>/dev/null)"
    escaped="$(json_escape_log "$tail_text")"
    echo "{\"error\": \"Server process exited before starting\", \"log_tail\": \"${escaped}\"}"
    exit 1
  fi
  sleep 0.05
done

# Timeout - server didn't start
echo '{"error": "Server failed to start within 5 seconds"}'
exit 1
