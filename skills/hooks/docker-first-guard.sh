#!/usr/bin/env bash
# Blocks host-level package manager usage in Claude Code

INPUT=$(cat)
COMMAND=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
print(data.get('tool_input', {}).get('command', ''))
" <<< "$INPUT")

# Allow commands through docker compose exec
if echo "$COMMAND" | grep -qE '^docker (compose |)exec'; then
  exit 0
fi

BLOCKED=(
  '^npm (install|i |ci|add|update|remove|uninstall)'
  '^yarn (install|add|remove)'
  '^pnpm (install|i |add|remove|update)'
  '^pip3? install'
  '^brew install'
  '^apt(-get)? install'
  '^cargo install'
)

for pattern in "${BLOCKED[@]}"; do
  if echo "$COMMAND" | grep -qE "$pattern"; then
    cat >&2 <<EOF
BLOCKED: Docker-First violation

  Command: $COMMAND

This installs packages directly on the host.
Use docker compose exec instead:

  docker compose exec <service> $COMMAND

Why: Docker-First ensures reproducible environments.
Host pollution causes "works on my machine" bugs.
EOF
    exit 2
  fi
done

exit 0
