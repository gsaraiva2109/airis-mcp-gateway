#!/usr/bin/env bash
# Runs test check when Claude finishes responding (airis-managed projects only)

cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0

if [ -f manifest.toml ]; then
  airis test 2>&1 | tail -20
fi
