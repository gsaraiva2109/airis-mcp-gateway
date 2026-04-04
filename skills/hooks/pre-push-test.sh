#!/usr/bin/env bash
# Runs airis test before git push to catch errors early

INPUT=$(cat)
COMMAND=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
print(data.get('tool_input', {}).get('command', ''))
" <<< "$INPUT")

# Only trigger on git push
if ! echo "$COMMAND" | grep -qE 'git\s+push'; then
  exit 0
fi

# Check if push target matches current project
push_repo=$(echo "$COMMAND" | sed -n 's/.*cd \([^ ;]*\).*/\1/p')
push_root=$(cd "${push_repo:-.}" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null || echo ".")
project_root=$(cd "$CLAUDE_PROJECT_DIR" && git rev-parse --show-toplevel 2>/dev/null || echo "$CLAUDE_PROJECT_DIR")

if [ "$push_root" != "$project_root" ]; then
  echo "Push target differs from project — skipping airis test"
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR" || exit 0

# Only run for projects with manifest.toml (airis-managed)
if [ ! -f manifest.toml ]; then
  exit 0
fi

# Check if there are turbo-managed package changes
changed=$(git diff --name-only origin/stg...HEAD 2>/dev/null || git diff --name-only HEAD~1 HEAD)
if [ -z "$changed" ]; then
  echo "No changes to test"
  exit 0
fi

has_turbo_pkg=$(echo "$changed" | grep -cE "^(apps|libs|products)/" || true)
if [ "$has_turbo_pkg" -eq 0 ]; then
  echo "Changes only in non-turbo paths — skipping airis test"
  exit 0
fi

# Check if containers are running
proj=$(grep -m1 "^name" manifest.toml 2>/dev/null | sed 's/.*= *"\(.*\)"/\1/')
if [ -z "$proj" ] || ! docker compose ps --status running 2>/dev/null | grep -q .; then
  echo "No project containers running — skipping local test. CI will validate."
  exit 0
fi

airis test || {
  echo '{"decision": "block", "reason": "テスト失敗。push 前に修正してください"}' >&2
  exit 2
}
