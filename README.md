<p align="center">
  <img src="./assets/demo.gif" width="720" alt="AIRIS MCP Gateway Demo" />
</p>

<h1 align="center">AIRIS MCP Gateway</h1>

<p align="center">
  <em>One gateway. 60+ AI tools. All managed.</em>
</p>

<p align="center">
  <a href="https://github.com/agiletec-inc/airis-mcp-gateway/blob/main/LICENSE"><img src="https://img.shields.io/github/license/agiletec-inc/airis-mcp-gateway" alt="License" /></a>
  <a href="https://github.com/agiletec-inc/airis-mcp-gateway/actions"><img src="https://img.shields.io/github/actions/workflow/status/agiletec-inc/airis-mcp-gateway/ci.yml?branch=main" alt="CI" /></a>
  <a href="https://github.com/agiletec-inc/airis-mcp-gateway/stargazers"><img src="https://img.shields.io/github/stars/agiletec-inc/airis-mcp-gateway" alt="Stars" /></a>
</p>

---

## Quick Start

### One-Command Install

```bash
curl -fsSL https://raw.githubusercontent.com/agiletec-inc/airis-mcp-gateway/main/install.sh | bash
```

Downloads Docker images, starts the gateway, and registers with Claude Code automatically.

<details>
<summary><b>Manual Install</b> (if you prefer to see what's happening)</summary>

```bash
# 1. Clone and start the gateway
git clone https://github.com/agiletec-inc/airis-mcp-gateway.git
cd airis-mcp-gateway && docker compose up -d

# 2. Register as a global MCP server in Claude Code
claude mcp add --scope user --transport sse airis-mcp-gateway http://localhost:9400/sse

# 3. Verify in Claude Code
/mcp   # Shows: airis-mcp-gateway ✔ connected
```

</details>

That's it. 60+ tools from 20+ MCP servers, all through a single endpoint.

> **Other MCP clients** (Cursor, Zed, etc.): Connect via SSE at `http://localhost:9400/sse`

## Why AIRIS MCP Gateway?

- **One endpoint, 60+ tools** — Stripe, Supabase, Tavily, GitHub, and more. All consolidated behind a single SSE connection. No need to register each MCP server individually.
- **Centralized secrets** — API keys stay in one place (`mcp-config.json`). Never scattered across project configs or Claude Code settings.
- **Auto-enable on demand** — Servers start when called, terminate when idle. No manual management. Add a new server with one JSON entry.
- **Docker-isolated** — All MCP servers run inside Docker. No host pollution, consistent across machines.
- **Smart tool management** — LLMs pick the right tool from 60+ options. Tools are organized by server with on-demand schema loading. Works with Claude Code's deferred tool loading for zero initial context cost.
- **Works with any MCP client** — Claude Code, Cursor, Zed, or any SSE-compatible client.

## How It Works

Register 20+ MCP servers in `mcp-config.json`. The gateway consolidates them behind a single SSE endpoint. Your AI agent connects once and gets access to everything.

```
Without Gateway:                          With Gateway:
  claude mcp add stripe ...                 claude mcp add airis-mcp-gateway ...
  claude mcp add supabase ...               # Done. 60+ tools available.
  claude mcp add tavily ...
  claude mcp add memory ...
  claude mcp add context7 ...
  # Manage 20 servers individually...
```

Servers start on-demand when a tool is called and auto-terminate when idle. No resources wasted.

```
User: "Create a Stripe customer for user@example.com"

Claude: [calls stripe:create_customer arguments={email: "user@example.com"}]
→ Gateway starts Stripe server → executes → returns result → server idles out
```

> **Claude Code 2.1.85+** loads tool schemas on-demand (deferred), so even 60+ tools add zero initial context cost. The gateway handles server lifecycle, auth, and routing.

> See [Dynamic MCP deep-dive](./docs/dynamic-mcp.md) for architecture details and configuration.

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
│  AIRIS MCP Gateway (port 9400)                          │
│                                                         │
│  ┌───────────────────────────────────────────────┐      │
│  │  ProcessManager (on-demand lifecycle)         │      │
│  │  context7, tavily, supabase, stripe, ...      │      │
│  │  Starts on first call, idles out when unused  │      │
│  └───────────────────────────────────────────────┘      │
│                                                         │
│  ┌───────────────────────────────────────────────┐      │
│  │  Secrets & Auth (mcp-config.json)             │      │
│  │  API keys injected at runtime, never exposed  │      │
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

### Enabled (start on-demand)

| Server | Description |
|--------|-------------|
| **context7** | Library documentation lookup |
| **memory** | Knowledge graph (entities, relations) |
| **tavily** | Web search via Tavily API |
| **supabase** | Supabase database management |
| **stripe** | Stripe payments API |
| **fetch** | Web page fetching as markdown |
| **sequential-thinking** | Step-by-step reasoning |
| **serena** | Semantic code retrieval and editing |
| **magic** | UI component generation |
| **morphllm** | Code editing with warpgrep |
| **chrome-devtools** | Chrome debugging |

### Disabled (auto-enable when called)

| Server | Description |
|--------|-------------|
| **twilio** | Twilio voice/SMS API |
| **cloudflare** | Cloudflare management |
| **github** | GitHub API |
| **postgres** | Direct PostgreSQL access |
| **filesystem** | File system operations |
| **git** | Git operations |
| **time** | Time utilities |

All servers start on first tool call and auto-terminate when idle. Disabled servers are automatically enabled when you call their tools — no manual setup needed.

</details>

## Airis Ecosystem

- **[airis-mcp-gateway](https://github.com/agiletec-inc/airis-mcp-gateway)** — 60+ MCP tools through one gateway. The hub. *(this repo)*
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
