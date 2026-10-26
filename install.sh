#!/bin/sh
# Install hyperRouter into a per-user bin directory.
#
#   ./install.sh              install into ~/.local/bin and run `hyperrouter init`
#   ./install.sh --no-init    skip the init step
#   ./install.sh --dry-run    print what would happen, change nothing
#
# Environment:
#   HYPERROUTER_PREFIX  install prefix (default: ~/.local)
#   HYPERROUTER_SRC     path to the hyperrouter script (default: next to this file)
#
# Never uses sudo. Re-running is safe: the script is replaced, links are refreshed.
set -eu

PREFIX="${HYPERROUTER_PREFIX:-$HOME/.local}"
BIN="$PREFIX/bin"
DO_INIT=1
DRY_RUN=0

usage() {
  cat <<'EOF'
usage: install.sh [--no-init] [--dry-run]

  --no-init   do not run `hyperrouter init` after installing
  --dry-run   print the actions instead of running them
  -h, --help  show this help

environment:
  HYPERROUTER_PREFIX  install prefix (default: ~/.local)
  HYPERROUTER_SRC     path to the hyperrouter script
EOF
}

for arg in "$@"; do
  case "$arg" in
    --no-init) DO_INIT=0 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *)
      printf 'install.sh: unknown option: %s\n\n' "$arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
src="${HYPERROUTER_SRC:-$script_dir/hyperrouter}"

if [ ! -f "$src" ]; then
  printf 'install.sh: cannot find %s\n' "$src" >&2
  printf 'Set HYPERROUTER_SRC to the path of the hyperrouter script.\n' >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  printf 'install.sh: warning: python3 was not found on PATH; hyperrouter needs Python 3.11+\n' >&2
fi

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf 'would run: %s\n' "$*"
  else
    "$@"
  fi
}

printf '%s\n' "hyperRouter installer"
printf '%s\n' "  source: $src"
printf '%s\n' "  target: $BIN/hyperrouter"

run mkdir -p "$BIN"
run install -m 755 "$src" "$BIN/hyperrouter"

if [ "$DRY_RUN" -eq 1 ]; then
  printf 'would link: %s -> hyperrouter\n' "$BIN/hyperRouter"
  printf 'would link: %s -> hyperrouter\n' "$BIN/agent-router"
else
  ln -sf hyperrouter "$BIN/hyperRouter"
  ln -sf hyperrouter "$BIN/agent-router"
  printf '%s\n' "installed $BIN/hyperrouter (links: hyperRouter, agent-router)"
fi

case ":$PATH:" in
  *":$BIN:"*) ;;
  *)
    printf '\nwarning: %s is not on PATH. Add it to your shell profile, e.g.\n' "$BIN"
    printf '  export PATH="%s:$PATH"\n' "$BIN"
    ;;
esac

if [ "$DO_INIT" -eq 1 ]; then
  printf '\ninitialising config and catalog\n'
  if [ "$DRY_RUN" -eq 1 ]; then
    printf 'would run: %s init\n' "$BIN/hyperrouter"
  else
    "$BIN/hyperrouter" init
  fi
fi

printf '\nnext: run `hyperrouter doctor`, then `hyperrouter` to open the agent TUI.\n'
