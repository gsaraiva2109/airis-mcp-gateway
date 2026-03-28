#!/usr/bin/env node
/**
 * AIRIS Commands MCP Server
 *
 * Config management tools that require file-system writes to mcp-config.json:
 * - airis_config_add_server / airis_config_remove_server
 * - airis_profile_save / airis_profile_load / airis_profile_list
 * - airis_mcp_detect (repo scan → auto-suggest servers)
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import * as fs from "fs/promises";
import * as path from "path";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

import {
  MCP_MAPPINGS,
  readConfig,
  writeConfig,
  addServer,
  removeServer,
  saveProfile,
  loadProfile,
  listProfiles,
  detectFromPackageJson,
  detectFromRequirementsTxt,
  formatDetectionOutput,
  type McpServerConfig,
} from "./lib.js";

const CONFIG_PATH = process.env.MCP_CONFIG_PATH || "/app/mcp-config.json";
const PROFILES_DIR = process.env.PROFILES_DIR || "/app/profiles";
const WORKSPACE_DIR = process.env.HOST_WORKSPACE_DIR || "/workspace/host";

interface AddServerArgs {
  name: string;
  command: string;
  args?: string[];
  env?: Record<string, string>;
  enabled?: boolean;
}

interface ServerNameArgs {
  server_name: string;
}

interface ProfileNameArgs {
  profile_name: string;
}

interface DetectArgs {
  path?: string;
  autoAdd?: boolean;
}

const server = new Server(
  {
    name: "airis-commands",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      // ── MCP Gateway Config Management ──
      {
        name: "airis_config_add_server",
        description: "Add a new MCP server to the gateway configuration. Specify the command (npx, uvx, node), args, and optional env vars. The server is enabled by default. Requires gateway restart. Use airis_mcp_detect first to auto-discover servers for your tech stack.",
        inputSchema: {
          type: "object",
          properties: {
            name: {
              type: "string",
              description: "Unique server name (e.g., 'my-server'). Must not already exist.",
            },
            command: {
              type: "string",
              description: "Command to launch the server (e.g., 'npx', 'uvx', 'node')",
            },
            args: {
              type: "array",
              items: { type: "string" },
              description: "Command arguments (e.g., ['-y', '@stripe/mcp', '--tools=all'])",
            },
            env: {
              type: "object",
              description: "Environment variables as key-value pairs. Use ${VAR_NAME} for values from host env.",
            },
            enabled: {
              type: "boolean",
              description: "Whether to enable immediately (default: true). Set false if env vars aren't configured yet.",
            },
          },
          required: ["name", "command", "args"],
        },
      },
      {
        name: "airis_config_remove_server",
        description: "Remove an MCP server from the gateway configuration permanently. This deletes the server entry from mcp-config.json. To disable without removing, edit mcp-config.json and set enabled=false.",
        inputSchema: {
          type: "object",
          properties: {
            server_name: {
              type: "string",
              description: "Server name to remove (must exist in config)",
            },
          },
          required: ["server_name"],
        },
      },

      // ── Profile Management ──
      {
        name: "airis_profile_save",
        description: "Save the entire current MCP configuration as a named profile. Profiles are stored in /app/profiles/ and can be loaded later to switch between different server configurations (e.g., 'minimal', 'full', 'project-x').",
        inputSchema: {
          type: "object",
          properties: {
            profile_name: {
              type: "string",
              description: "Profile name (e.g., 'minimal', 'full-stack', 'frontend-only')",
            },
          },
          required: ["profile_name"],
        },
      },
      {
        name: "airis_profile_load",
        description: "Load a saved profile, replacing the current MCP configuration entirely. Use airis_profile_list to see available profiles. Requires gateway restart to apply.",
        inputSchema: {
          type: "object",
          properties: {
            profile_name: {
              type: "string",
              description: "Profile name to load (must exist in profiles directory)",
            },
          },
          required: ["profile_name"],
        },
      },
      {
        name: "airis_profile_list",
        description: "List all saved MCP configuration profiles. Returns profile names that can be loaded with airis_profile_load.",
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },

      // ── Discovery ──
      {
        name: "airis_mcp_detect",
        description: "Scan a repository's package.json/requirements.txt to detect tech stack and suggest relevant MCP servers. For example, finding '@supabase/supabase-js' suggests adding the Supabase MCP server. Set autoAdd=true to automatically add detected servers (disabled by default, so you can set env vars first).",
        inputSchema: {
          type: "object",
          properties: {
            path: {
              type: "string",
              description: "Repository path to scan (default: /workspace/host). Must contain package.json or requirements.txt.",
            },
            autoAdd: {
              type: "boolean",
              description: "true = add detected servers to config (disabled, awaiting env vars). false = just show suggestions (default).",
            },
          },
          required: [],
        },
      },

      // ── Bridge Extensions ──
      {
        name: "airis_bridge_setup",
        description: "(Optional) Setup the Infinite Context Bridge. Links NCP discovery and ICM memory to the Airis Gateway for token efficiency and project-specific ranking. Requires NCP and ICM to be installed on the host.",
        inputSchema: {
          type: "object",
          properties: {
            link_ncp: {
              type: "boolean",
              description: "Register core tools in NCP using the Airis bridge (default: true)",
            },
            link_icm: {
              type: "boolean",
              description: "Link ICM memory database to RTK context for better ranking (default: true)",
            },
          },
        },
      },

    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "airis_config_add_server": {
        const { name: serverName, command, args: cmdArgs, env, enabled } = args as unknown as AddServerArgs;

        await addServer(CONFIG_PATH, serverName, {
          command,
          args: cmdArgs || [],
          env: env || {},
          enabled: enabled !== false,
        });

        return {
          content: [
            {
              type: "text",
              text: `Server "${serverName}" added to config. Restart API to apply.`,
            },
          ],
        };
      }

      case "airis_config_remove_server": {
        const serverName = (args as unknown as ServerNameArgs).server_name;
        await removeServer(CONFIG_PATH, serverName);

        return {
          content: [
            {
              type: "text",
              text: `Server "${serverName}" removed from config.`,
            },
          ],
        };
      }

      case "airis_profile_save": {
        const profileName = (args as unknown as ProfileNameArgs).profile_name;
        await saveProfile(CONFIG_PATH, PROFILES_DIR, profileName);

        return {
          content: [
            {
              type: "text",
              text: `Profile "${profileName}" saved.`,
            },
          ],
        };
      }

      case "airis_profile_load": {
        const profileName = (args as unknown as ProfileNameArgs).profile_name;
        await loadProfile(CONFIG_PATH, PROFILES_DIR, profileName);

        return {
          content: [
            {
              type: "text",
              text: `Profile "${profileName}" loaded. Restart API to apply.`,
            },
          ],
        };
      }

      case "airis_profile_list": {
        const profiles = await listProfiles(PROFILES_DIR);

        if (profiles.length === 0) {
          return {
            content: [{ type: "text", text: "No profiles saved yet." }],
          };
        }

        return {
          content: [
            {
              type: "text",
              text: `Saved profiles:\n${profiles.map((p) => `- ${p}`).join("\n")}`,
            },
          ],
        };
      }

      case "airis_mcp_detect": {
        const { path: repoPath = WORKSPACE_DIR, autoAdd = false } = (args ?? {}) as unknown as DetectArgs;
        const config = await readConfig(CONFIG_PATH);

        const detected: Array<{
          name: string;
          reason: string;
          mcp: string;
          description: string;
          envRequired: string[];
          alreadyExists: boolean;
        }> = [];

        // Scan package.json
        try {
          const pkgPath = path.join(repoPath, "package.json");
          const pkgContent = await fs.readFile(pkgPath, "utf-8");
          detected.push(...detectFromPackageJson(pkgContent, config.mcpServers));
        } catch {
          // No package.json
        }

        // Check for .git directory
        try {
          await fs.access(path.join(repoPath, ".git"));
          const githubMapping = MCP_MAPPINGS.github;
          if (!detected.find(d => d.name === "github")) {
            detected.push({
              name: "github",
              reason: "Found .git directory",
              mcp: githubMapping.mcp,
              description: githubMapping.description,
              envRequired: githubMapping.envRequired,
              alreadyExists: !!config.mcpServers.github,
            });
          }
        } catch {
          // No .git directory
        }

        // Scan requirements.txt
        try {
          const reqPath = path.join(repoPath, "requirements.txt");
          const reqContent = await fs.readFile(reqPath, "utf-8");
          const alreadyDetected = detected.map(d => d.name);
          detected.push(...detectFromRequirementsTxt(reqContent, config.mcpServers, alreadyDetected));
        } catch {
          // No requirements.txt
        }

        if (detected.length === 0) {
          return {
            content: [{
              type: "text",
              text: `No known MCPs detected in ${repoPath}.\n\nAvailable MCPs: ${Object.keys(MCP_MAPPINGS).join(", ")}`,
            }],
          };
        }

        // Auto-add new MCPs if requested
        if (autoAdd) {
          const newMcps = detected.filter(d => !d.alreadyExists);
          for (const mcp of newMcps) {
            const mapping = MCP_MAPPINGS[mcp.name];
            config.mcpServers[mcp.name] = {
              command: mapping.command,
              args: mapping.args,
              env: mapping.env,
              enabled: false,
            };
          }
          if (newMcps.length > 0) {
            await writeConfig(CONFIG_PATH, config);
          }
        }

        const output = formatDetectionOutput(detected, repoPath, autoAdd);

        return {
          content: [{ type: "text", text: output }],
        };
      }

      case "airis_bridge_setup": {
        const results: string[] = [];

        results.push("The **Infinite Context** stack optimizes your AI workflow by combining intelligent discovery (NCP), efficient filtering (RTK), and long-term memory (ICM).\n");

        results.push("### 1. Install CLI Tools");
        results.push("These tools run on your host machine to augment the Airis Gateway:");
        results.push("- **RTK (Runtime Token Kit):** [GitHub](https://github.com/rtk-ai/rtk) | [Site](https://www.rtk-ai.app/)");
        results.push("  `curl -fsSL https://rtk-ai.app/install.sh | bash` (Example command)");
        results.push("- **ICM (Infinite Context Memory):** [GitHub](https://github.com/rtk-ai/icm)");
        results.push("  `curl -fsSL https://rtk-ai.app/icm/install.sh | bash` (Example command)");
        results.push("- **NCP (Natural Context Protocol):** [GitHub](https://github.com/portel-dev/ncp)");
        results.push("  `npm install -g @portel-dev/ncp` (Example command)");
        results.push("");

        results.push("### 2. Configure Bridge");
        results.push("Once installed, run these commands on your host to link everything together:");
        results.push("```bash");
        results.push("# A. Link ICM Memory to RTK context");
        results.push("mkdir -p ~/.rtk");
        results.push("ln -sf \"$HOME/.local/share/icm/memories.db\" \"$HOME/.rtk/icm.db\"");
        results.push("");
        results.push("# B. Link Airis tools to NCP discovery");
        results.push("ncp_bin=\"$(which ncp)\"");
        results.push("for tool in filesystem memory github tavily supabase stripe context7 sequential-thinking serena; do");
        results.push("  $ncp_bin add \"$tool\" \"airis-mcp-gateway exec $tool\"");
        results.push("done");
        results.push("```");

        return {
          content: [{
            type: "text",
            text: "# Infinite Context Bridge Setup Guide\n\n" + results.join("\n")
          }]
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      content: [{ type: "text", text: `Error: ${message}` }],
      isError: true,
    };
  }
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("AIRIS Commands MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
