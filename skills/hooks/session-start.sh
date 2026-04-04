#!/usr/bin/env bash
# Detect project type and stack from CWD for AIRIS MCP Gateway hints.

project_types=()
stack=()

# Detect project type
[[ -f package.json ]] && project_types+=("node")
[[ -f pyproject.toml ]] && project_types+=("python")
[[ -f Cargo.toml ]] && project_types+=("rust")
[[ -f go.mod ]] && project_types+=("go")
[[ -f CLAUDE.md ]] && project_types+=("claude")

# Detect stack
[[ -d supabase ]] && stack+=("supabase")
[[ -f package.json ]] && grep -q '"stripe"' package.json 2>/dev/null && stack+=("stripe")
[[ -f package.json ]] && grep -q '"prisma"' package.json 2>/dev/null && stack+=("prisma")
[[ -f docker-compose.yml || -f compose.yml ]] && stack+=("docker")
[[ -f .env ]] && stack+=("env")
[[ -d .github/workflows ]] && stack+=("github-actions")

# Detect MCP servers from manifest.toml [mcp] section
mcp_servers=()
if [[ -f manifest.toml ]]; then
  in_mcp=false
  while IFS= read -r line; do
    if [[ "$line" =~ ^\[mcp\] ]]; then
      in_mcp=true
      continue
    fi
    if [[ "$in_mcp" == true && "$line" =~ ^\[ ]]; then
      break
    fi
    if [[ "$in_mcp" == true && "$line" =~ ^servers ]]; then
      servers_raw=$(echo "$line" | sed 's/.*\[//;s/\].*//;s/"//g;s/,/ /g')
      for s in $servers_raw; do
        s=$(echo "$s" | xargs)
        [[ -n "$s" ]] && mcp_servers+=("$s")
      done
    fi
  done < manifest.toml
fi

# Format output
type_str="${project_types[*]:-unknown}"
stack_str="${stack[*]:-none}"

output="Project: ${type_str// /, } | Stack: [${stack_str// /, }]"

if [[ ${#mcp_servers[@]} -gt 0 ]]; then
  mcp_str="${mcp_servers[*]}"
  output="$output | MCP: [${mcp_str// /, }]"
fi

output="$output | Tip: Use airis-route for optimal tool selection"
echo "$output"
