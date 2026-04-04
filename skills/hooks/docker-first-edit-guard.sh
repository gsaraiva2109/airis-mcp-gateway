#!/usr/bin/env bash
# Blocks Docker-First violations in Edit/Write tool calls.
# Checks BOTH the new content being written AND the existing file content.

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
print(data.get('tool_input', {}).get('file_path', ''))
" <<< "$INPUT")

BASENAME=$(basename "$FILE_PATH")

# Only check Docker/CI target files by name pattern
if [[ ! "$BASENAME" =~ ^(Dockerfile|Dockerfile\..+|compose\.ya?ml|docker-compose\.ya?ml|ci\.ya?ml|deploy\.ya?ml)$ ]]; then
  exit 0
fi

NEW_CONTENT=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
# Write tool uses 'content', Edit tool uses 'new_string'
print(data.get('tool_input', {}).get('content', '') or data.get('tool_input', {}).get('new_string', ''))
" <<< "$INPUT")

# Check function: scans text for violations
# Args: $1=text_to_check, $2=source_label ("new content" or "existing file")
check_violations() {
  local text="$1"
  local source="$2"

  # Host-specific absolute paths
  # For CI workflow files, allow ~/.ssh (standard runner SSH setup)
  local check_text="$text"
  if [[ "$BASENAME" =~ ^(ci|deploy)\. ]]; then
    check_text=$(echo "$text" | sed 's|~/.ssh[^ "'"'"']*||g')
  fi
  if echo "$check_text" | grep -qE '(/Users/[a-z]|~/)'; then
    cat >&2 <<BLOCK
BLOCKED: Host path in Docker/CI file ($source)

  Host-specific path (/Users/..., ~/) detected in $BASENAME.
  This WILL fail in CI.

  Fix: Use container-internal paths only.
  - pnpm store: PNPM_STORE_DIR=/pnpm/store (named volume)
  - node_modules: /app/node_modules (named volume)
  - /home/app is OK (container user), /Users/kazuki is NOT

  If this violation is in existing code, fix it before making other changes.
BLOCK
    return 1
  fi

  # Local .pnpm-store path
  if echo "$text" | grep -qE '\.pnpm-store|\.pnpm/store|node_modules/\.pnpm'; then
    cat >&2 <<BLOCK
BLOCKED: Local pnpm store path in Docker/CI file ($source)

  .pnpm-store or .pnpm/store are host-local paths.
  Use PNPM_STORE_DIR=/pnpm/store with a named volume.

  If this violation is in existing code, fix it before making other changes.
BLOCK
    return 1
  fi

  # Bind mount of node_modules (compose files only)
  if [[ "$BASENAME" =~ ^(compose\.ya?ml|docker-compose\.ya?ml)$ ]]; then
    if echo "$text" | grep -qE '\./node_modules\s*:|\./\.pnpm'; then
      cat >&2 <<BLOCK
BLOCKED: Bind mount of node_modules in compose file ($source)

  node_modules MUST use named volumes, not bind mounts.

  Correct: node_modules:/app/node_modules   (named volume)
  Wrong:   ./node_modules:/app/node_modules  (bind mount)

  If this violation is in existing code, fix it before making other changes.
BLOCK
      return 1
    fi
  fi

  # PNPM_STORE_DIR pointing to host paths
  if echo "$text" | grep -qE "PNPM_STORE_DIR\s*=\s*[\"']?\.(\/|pnpm)|PNPM_STORE_DIR\s*=\s*[\"']?(/Users|/home|~/)"; then
    cat >&2 <<BLOCK
BLOCKED: PNPM_STORE_DIR set to host-local path ($source)

  PNPM_STORE_DIR must point to a named volume mount.

  Correct: PNPM_STORE_DIR=/pnpm/store
  Wrong:   PNPM_STORE_DIR=./.pnpm-store

  If this violation is in existing code, fix it before making other changes.
BLOCK
    return 1
  fi

  return 0
}

# Check new content being written
check_violations "$NEW_CONTENT" "new content" || exit 2

# Check the file content AFTER the edit would be applied
if [[ -f "$FILE_PATH" ]]; then
  RESULT_CONTENT=$(python3 -c "
import json, sys, pathlib
data = json.loads(sys.stdin.read())
ti = data.get('tool_input', {})
file_path = ti.get('file_path', '')
old_string = ti.get('old_string', '')
new_string = ti.get('new_string', '')
replace_all = ti.get('replace_all', False)
content = ti.get('content', '')

if content:
    # Write tool: result is the new content (already checked)
    sys.exit(0)

# Edit tool: apply replacement to current file
existing = pathlib.Path(file_path).read_text()
if old_string and old_string in existing:
    if replace_all:
        result = existing.replace(old_string, new_string)
    else:
        result = existing.replace(old_string, new_string, 1)
else:
    result = existing
print(result)
" <<< "$INPUT" 2>/dev/null || true)

  if [[ -n "$RESULT_CONTENT" ]]; then
    check_violations "$RESULT_CONTENT" "resulting file" || exit 2
  fi
fi

exit 0
