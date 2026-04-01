<p align="center">
  <img src="./assets/demo.gif" width="720" alt="AIRIS MCP Gateway Demo" />
</p>

<h1 align="center">Universal MCP Hub: AIRIS MCP Gateway</h1>

<p align="center">
  <em>One gateway. 100+ AI tools. Every AI client. <b>Connect once, use everywhere.</b></em>
</p>

<p align="center">
  <a href="https://github.com/agiletec-inc/airis-mcp-gateway/blob/main/LICENSE"><img src="https://img.shields.io/github/license/agiletec-inc/airis-mcp-gateway" alt="License" /></a>
  <a href="https://github.com/agiletec-inc/airis-mcp-gateway/actions"><img src="https://img.shields.io/github/actions/workflow/status/agiletec-inc/airis-mcp-gateway/ci.yml?branch=main" alt="CI" /></a>
  <a href="https://github.com/agiletec-inc/airis-mcp-gateway/stargazers"><img src="https://img.shields.io/github/stars/agiletec-inc/airis-mcp-gateway" alt="Stars" /></a>
</p>

---

## 🛠️ Quick Install & Universal Setup

### 1. Start the Gateway
```bash
curl -fsSL https://raw.githubusercontent.com/agiletec-inc/airis-mcp-gateway/main/install.sh | bash
```

### 2. Connect Your AI Client
Register the gateway once, and access all backend MCP servers (Stripe, Supabase, GitHub, etc.) through a single connection.

| Client | Connection Command / Setup |
| :--- | :--- |
| **Claude Code** | `claude mcp add --transport sse airis http://localhost:8000/sse` |
| **Gemini CLI** | `gemini mcp add --transport sse airis http://localhost:8000/sse` |
| **Cursor** | Settings > Features > MCP > **Add New MCP Server**<br>Name: `airis`, Type: `SSE`, URL: `http://localhost:8000/sse` |
| **Windsurf** | Add SSE URL `http://localhost:8000/sse` to `~/.codeium/config.json` |
| **Zed** | Add `http://localhost:8000/sse` to `extensions.mcp` in `settings.json` |

---

## 🧠 Why Universal MCP Hub?

### 1. Single Source of Truth
No more repeating API keys and server configs across different projects or AI tools. Manage all secrets in one place (`mcp-config.json`) and share them across Claude Code, Gemini CLI, Cursor, and more.

### 2. Intelligent Noise Reduction
Even with large context windows, exposing 100+ tools simultaneously leads to "tool selection hallucinations." Airis provides **`airis-find`** to dynamically help models discover only the tools they need, reducing inference noise and improving success rates.

### 3. Performance & Evaluation (Moving beyond "Vibes")
Stop guessing if your toolset is actually helping. Airis tracks and visualizes real performance:
- **Token Efficiency**: Measurable reduction in initial context overhead.
- **Workflow Precision**: Tracking steps-to-success for complex tasks.
- **Latency & Reliability**: Real-time monitoring of each MCP server's health and response time.

## How It Works

Airis aggregates 20+ MCP servers behind a single SSE endpoint. Your AI agent connects once and gets access to everything.

```
Without Gateway:                          With Gateway:
  claude mcp add stripe ...                 claude mcp add airis ...
  claude mcp add supabase ...               # Done. 100+ tools available.
  claude mcp add tavily ...                 # Shared across Gemini, Cursor, etc.
  ... Manage 20 servers individually ...
```

Servers start on-demand when a tool is called and auto-terminate when idle. No resources wasted.

## Architecture

```
Claude / Gemini / Cursor / Windsurf
    │
    ▼ SSE (Unified Interface)
┌─────────────────────────────────────────────────────────┐
│  AIRIS MCP Gateway (The Intelligent Hub)                │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────┐ │
│  │ Intelligent      │  │ Lifecycle        │  │ Auth & │ │
│  │ Routing (Find)   │  │ Manager (On-Demand)│  │ Secrets│ │
│  └──────────────────┘  └──────────────────┘  └────────┘ │
│            │                    │                 │     │
└────────────┼────────────────────┼─────────────────┼─────┘
             ▼                    ▼                 ▼
      [ uvx / npx ]        [ Docker MCP ]    [ Remote SSE ]
    Stripe, Supabase,     Mindbase, Tavily,   Custom APIs
    GitHub, etc.          etc.
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

## Documentation

- [Dynamic MCP deep-dive](./docs/dynamic-mcp.md) — Architecture, cache behavior, auto-enable flow
- [Configuration reference](./docs/configuration.md) — Environment variables, TTL settings, server config
- [Gateway vs Plugins](./docs/gateway-vs-plugins.md) — When to use Gateway vs Claude Code plugins
- [Deployment guide](./DEPLOYMENT.md) — Production setup, API auth, monitoring, reverse proxy
- [Architecture](./ARCHITECTURE.md) — System design and component responsibilities
- [Contributing](./CONTRIBUTING.md) — Development setup, Devbox, go-task, PR guidelines

## License

MIT
