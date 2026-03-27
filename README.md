<p align="center">
  <img src="./assets/demo.gif" width="720" alt="AIRIS MCP Gateway Demo" />
</p>

<h1 align="center">AIRIS MCP Gateway</h1>

<p align="center">
  <em>One command. 60+ AI tools. Zero config.</em>
</p>

<p align="center">
  <a href="https://github.com/agiletec-inc/airis-mcp-gateway/blob/main/LICENSE"><img src="https://img.shields.io/github/license/agiletec-inc/airis-mcp-gateway" alt="License" /></a>
  <a href="https://github.com/agiletec-inc/airis-mcp-gateway/actions"><img src="https://img.shields.io/github/actions/workflow/status/agiletec-inc/airis-mcp-gateway/ci.yml?branch=main" alt="CI" /></a>
  <a href="https://github.com/agiletec-inc/airis-mcp-gateway/stargazers"><img src="https://img.shields.io/github/stars/agiletec-inc/airis-mcp-gateway" alt="Stars" /></a>
</p>

---

## Quick Start

```bash
# 1. Start the gateway
git clone https://github.com/agiletec-inc/airis-mcp-gateway.git
cd airis-mcp-gateway && docker compose up -d

# 2. Connect to Claude Code (or any MCP client)
claude mcp add --scope user --transport sse airis-mcp-gateway http://localhost:9400/sse

# 3. Verify
curl http://localhost:9400/health
```

That's it. 60+ tools are now available through 7 token-efficient meta-tools.

## Why AIRIS MCP Gateway?

- **97% token savings** — 7 meta-tools instead of 60+ raw tool definitions (~42,000 → ~1,400 tokens). Follows [Anthropic's recommendation](https://www.anthropic.com/engineering/code-execution-with-mcp) for progressive disclosure.
- **Auto-enable on demand** — Disabled servers are discoverable and auto-start when called. No manual enable/disable needed.
- **HOT/COLD lifecycle** — HOT servers are always ready; COLD servers start on-demand and auto-terminate when idle. Resource-efficient.
- **Docker-isolated** — All MCP servers run inside Docker. No host pollution, consistent across machines.
- **Works with any MCP client** — Claude Code, Cursor, Zed, or any SSE-compatible client.
- **Extensible** — Add any MCP server (npx, uvx, mcp-remote) via a single JSON config entry.

## How It Works

Dynamic MCP exposes 7 meta-tools instead of 60+. The key innovation: **`airis-exec` embeds a compact tool listing in its description**, so LLMs already know every available tool and can call them directly — no discovery step needed.

| Meta-Tool | Description |
|-----------|-------------|
| `airis-exec` | **Execute any tool in one call.** Tool listing embedded in description. |
| `airis-find` | Search for tools not listed in airis-exec (fallback) |
| `airis-schema` | Get full input schema (when arguments are unclear) |
| `airis-confidence` | Pre-implementation confidence check |
| `airis-repo-index` | Generate repository structure overview |
| `airis-suggest` | Tool recommendations from natural language |
| `airis-route` | Route task to optimal tool chain |

### One-Call Workflow

```
User: "Save this note about the meeting"

Claude sees airis-exec description:
  Available tools:
  [memory] create_entities, search_nodes, add_observations, ...
  [tavily] tavily-search, tavily-extract
  [stripe] create_customer, create_payment_intent, ...

Claude: [calls airis-exec tool="memory:create_entities" arguments={...}]
→ Done! (1 call)
```

No `airis-find` needed — the LLM already knows what tools exist. If arguments are wrong, the schema is returned automatically so the next call succeeds.

```
Traditional: 60+ tools × ~700 tokens = ~42,000 tokens
Dynamic MCP: 7 meta-tools × ~200 tokens = ~1,400 tokens (97% reduction)
```

> See [Dynamic MCP deep-dive](./docs/dynamic-mcp.md) for architecture details, cache behavior, and configuration.

## Choose Your Level

Start at Level 1. Add layers as you need them.

| Level | What you get | How to add |
|-------|-------------|------------|
| **1** | 60+ AI tools via MCP | `docker compose up -d` (this repo) |
| **2** | + workflow automation (TDD, debugging, planning) | Install [superpowers](https://github.com/obra/superpowers) plugin |
| **3** | + cross-session AI memory | Enable [mindbase](https://github.com/agiletec-inc/mindbase) in Docker setup |
| **4** | + Docker-first dev environment | Add [airis-monorepo](https://github.com/agiletec-inc/airis-monorepo) CLI |

### Recommended Companion Plugins

The Gateway handles API/service integrations. For host-dependent capabilities:

```bash
# In Claude Code, run /plugin to install:
superpowers          # TDD, debugging, planning workflows (by obra)
claude-api           # File generation: docx, xlsx, pptx, pdf (by Anthropic)

# Browser automation (standalone skill):
playwright-cli install --skills
```

> See [Gateway vs Plugins](./docs/gateway-vs-plugins.md) for when to use each.

## Architecture

```
Claude Code / Cursor / Zed
    │
    ▼ SSE (http://localhost:9400/sse)
┌─────────────────────────────────────────────────────────┐
│  FastAPI Hybrid MCP Multiplexer (port 9400)             │
│                                                         │
│  ┌───────────────────────────────────────────────┐      │
│  │  Dynamic MCP Layer (7 meta-tools)             │      │
│  └───────────────────────────────────────────────┘      │
│                                                         │
│  ┌───────────────────────────────────────────────┐      │
│  │  ProcessManager (HOT + COLD servers)          │      │
│  │  context7, tavily, supabase, stripe, ...      │      │
│  └───────────────────────────────────────────────┘      │
│                                                         │
│  ┌───────────────────────────────────────────────┐      │
│  │  Docker Gateway (9390) - mindbase, etc.       │      │
│  └───────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────┘
```

> See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full system design.

<details>
<summary><h2>Available Servers</h2></summary>

### Enabled by Default

| Server | Mode | Description |
|--------|------|-------------|
| **airis-mcp-gateway-control** | HOT | Gateway management tools |
| **airis-commands** | HOT | Config and profile management |
| **context7** | COLD | Library documentation lookup |
| **fetch** | COLD | Web page fetching as markdown |
| **memory** | COLD | Knowledge graph (entities, relations) |
| **sequential-thinking** | COLD | Step-by-step reasoning |
| **serena** | COLD | Semantic code retrieval and editing |
| **tavily** | COLD | Web search via Tavily API |
| **magic** | COLD | UI component generation |
| **morphllm** | COLD | Code editing with warpgrep |
| **chrome-devtools** | COLD | Chrome debugging |
| **supabase** | COLD | Supabase database management |
| **stripe** | COLD | Stripe payments API |

### Disabled by Default (Auto-Enable via airis-exec)

| Server | Description |
|--------|-------------|
| **twilio** | Twilio voice/SMS API |
| **cloudflare** | Cloudflare management |
| **github** | GitHub API |
| **postgres** | Direct PostgreSQL access |
| **filesystem** | File system operations |
| **git** | Git operations |
| **time** | Time utilities |

**HOT**: Always running, immediate response. **COLD**: Start on-demand, auto-terminate when idle.

Disabled servers are discoverable via `airis-find` and automatically enabled when you call `airis-exec`.

</details>

## Airis Ecosystem

- **[airis-mcp-gateway](https://github.com/agiletec-inc/airis-mcp-gateway)** — 60+ MCP tools through 7 meta-tools. The hub. *(this repo)*
- **[airis-monorepo](https://github.com/agiletec-inc/airis-monorepo)** — Docker-first monorepo CLI. `manifest.toml` generates Dockerfile, compose, and CI configs automatically.
- **[mindbase](https://github.com/agiletec-inc/mindbase)** — Cross-session AI memory with semantic search. Included in the Docker setup.

## Documentation

- [Dynamic MCP deep-dive](./docs/dynamic-mcp.md) — Architecture, cache behavior, auto-enable flow
- [Configuration reference](./docs/configuration.md) — Environment variables, TTL settings, server config
- [Gateway vs Plugins](./docs/gateway-vs-plugins.md) — When to use Gateway vs Claude Code plugins
- [Deployment guide](./DEPLOYMENT.md) — Production setup, API auth, monitoring, reverse proxy
- [Architecture](./ARCHITECTURE.md) — System design and component responsibilities
- [Troubleshooting](./docs/troubleshooting.md) — Common issues and debugging
- [Contributing](./CONTRIBUTING.md) — Development setup, Devbox, go-task, PR guidelines

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup and guidelines.

## License

MIT
