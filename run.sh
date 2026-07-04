#!/usr/bin/env sh
set -eu

BUNDLED_PYTHON="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"

COMMAND="${1:-cli}"
if [ "$COMMAND" = "bot" ]; then
  shift
  MODULE="toss_roa.telegram_bot"
else
  MODULE="toss_roa.cli"
fi

if [ -x "$BUNDLED_PYTHON" ]; then
  exec "$BUNDLED_PYTHON" -m "$MODULE" "$@"
fi

exec python3 -m "$MODULE" "$@"
