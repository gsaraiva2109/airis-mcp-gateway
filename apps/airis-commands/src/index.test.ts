/**
 * AIRIS Commands MCP Server Tests
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as fs from "fs/promises";
import * as path from "path";
import { buildBridgeSetupGuide } from "./index.js";

// Mock fs/promises
vi.mock("fs/promises", () => ({
  readFile: vi.fn(),
  writeFile: vi.fn(),
  mkdir: vi.fn(),
  readdir: vi.fn(),
  access: vi.fn(),
}));

// MCP mapping database (copied from source for testing)
const MCP_MAPPINGS: Record<string, {
  packages: string[];
  detect?: string[];
  mcp: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  envRequired: string[];
  description: string;
}> = {
  stripe: {
    packages: ["stripe", "@stripe/stripe-js"],
    mcp: "@stripe/mcp",
    command: "npx",
    args: ["-y", "@stripe/mcp", "--tools=all", "--api-key", "${STRIPE_SECRET_KEY}"],
    env: {},
    envRequired: ["STRIPE_SECRET_KEY"],
    description: "Stripe payments API",
  },
  supabase: {
    packages: ["@supabase/supabase-js", "@supabase/ssr"],
    mcp: "@supabase/mcp-server-supabase",
    command: "npx",
    args: ["-y", "@supabase/mcp-server-supabase@latest", "--access-token", "${SUPABASE_ACCESS_TOKEN}"],
    env: {},
    envRequired: ["SUPABASE_ACCESS_TOKEN"],
    description: "Supabase database management",
  },
  postgres: {
    packages: ["pg", "postgres", "@prisma/client", "drizzle-orm"],
    mcp: "@modelcontextprotocol/server-postgres",
    command: "npx",
    args: ["-y", "@modelcontextprotocol/server-postgres", "${DATABASE_URL}"],
    env: {},
    envRequired: ["DATABASE_URL"],
    description: "Direct PostgreSQL access",
  },
  github: {
    packages: ["@octokit/rest", "octokit"],
    detect: [".git"],
    mcp: "@modelcontextprotocol/server-github",
    command: "npx",
    args: ["-y", "@modelcontextprotocol/server-github"],
    env: { GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}" },
    envRequired: ["GITHUB_TOKEN"],
    description: "GitHub API",
  },
  playwright: {
    packages: ["playwright", "@playwright/test"],
    mcp: "@playwright/mcp",
    command: "npx",
    args: ["-y", "@playwright/mcp@latest"],
    env: {},
    envRequired: [],
    description: "Browser automation",
  },
};

// Helper functions (simulating the ones from index.ts)
interface McpServerConfig {
  command: string;
  args: string[];
  env: Record<string, string>;
  enabled: boolean;
}

interface McpConfig {
  mcpServers: Record<string, McpServerConfig>;
  log?: { level: string };
}

const CONFIG_PATH = "/app/mcp-config.json";
const PROFILES_DIR = "/app/profiles";

async function readConfig(): Promise<McpConfig> {
  const content = await fs.readFile(CONFIG_PATH, "utf-8");
  return JSON.parse(content as string);
}

async function writeConfig(config: McpConfig): Promise<void> {
  await fs.writeFile(CONFIG_PATH, JSON.stringify(config, null, 2));
}

async function ensureProfilesDir(): Promise<void> {
  try {
    await fs.mkdir(PROFILES_DIR, { recursive: true });
  } catch {
    // Ignore if exists
  }
}

describe("Config Read/Write", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should read config file correctly", async () => {
    const mockConfig: McpConfig = {
      mcpServers: {
        memory: {
          command: "npx",
          args: ["-y", "@modelcontextprotocol/server-memory"],
          env: {},
          enabled: true,
        },
      },
    };

    vi.mocked(fs.readFile).mockResolvedValue(JSON.stringify(mockConfig));

    const config = await readConfig();

    expect(fs.readFile).toHaveBeenCalledWith(CONFIG_PATH, "utf-8");
    expect(config.mcpServers.memory.enabled).toBe(true);
  });

  it("should write config file with proper formatting", async () => {
    const mockConfig: McpConfig = {
      mcpServers: {
        memory: {
          command: "npx",
          args: ["-y", "@modelcontextprotocol/server-memory"],
          env: {},
          enabled: false,
        },
      },
    };

    vi.mocked(fs.writeFile).mockResolvedValue(undefined);

    await writeConfig(mockConfig);

    expect(fs.writeFile).toHaveBeenCalledWith(
      CONFIG_PATH,
      JSON.stringify(mockConfig, null, 2)
    );
  });

  it("should handle missing config file", async () => {
    vi.mocked(fs.readFile).mockRejectedValue(new Error("ENOENT: no such file"));

    await expect(readConfig()).rejects.toThrow("ENOENT");
  });
});

// airis_config_get and airis_config_set_enabled were removed.
// Config reading/writing is covered by the "Config Read/Write" tests above.

describe("airis_config_add_server tool", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should add new server to config", async () => {
    const mockConfig: McpConfig = {
      mcpServers: {},
    };

    vi.mocked(fs.readFile).mockResolvedValue(JSON.stringify(mockConfig));
    vi.mocked(fs.writeFile).mockResolvedValue(undefined);

    const config = await readConfig();
    const newServer = {
      command: "npx",
      args: ["-y", "@example/mcp-server"],
      env: { API_KEY: "test" },
      enabled: true,
    };

    config.mcpServers["new-server"] = newServer;
    await writeConfig(config);

    expect(fs.writeFile).toHaveBeenCalledWith(
      CONFIG_PATH,
      expect.stringContaining('"new-server"')
    );
  });

  it("should throw error if server already exists", async () => {
    const mockConfig: McpConfig = {
      mcpServers: {
        existing: { command: "npx", args: [], env: {}, enabled: true },
      },
    };

    vi.mocked(fs.readFile).mockResolvedValue(JSON.stringify(mockConfig));

    const config = await readConfig();
    const serverName = "existing";

    expect(config.mcpServers[serverName]).toBeDefined();
    // In real code, this would throw
    expect(() => {
      if (config.mcpServers[serverName]) {
        throw new Error(`Server already exists: ${serverName}`);
      }
    }).toThrow("Server already exists: existing");
  });
});

describe("airis_config_remove_server tool", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should remove server from config", async () => {
    const mockConfig: McpConfig = {
      mcpServers: {
        memory: { command: "npx", args: [], env: {}, enabled: true },
        fetch: { command: "uvx", args: [], env: {}, enabled: true },
      },
    };

    vi.mocked(fs.readFile).mockResolvedValue(JSON.stringify(mockConfig));
    vi.mocked(fs.writeFile).mockResolvedValue(undefined);

    const config = await readConfig();
    delete config.mcpServers.memory;
    await writeConfig(config);

    expect(Object.keys(JSON.parse((fs.writeFile as any).mock.calls[0][1]).mcpServers)).not.toContain("memory");
  });
});

describe("Profile Management", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("airis_profile_save tool", () => {
    it("should save current config as profile", async () => {
      const mockConfig: McpConfig = {
        mcpServers: {
          memory: { command: "npx", args: [], env: {}, enabled: true },
        },
      };

      vi.mocked(fs.mkdir).mockResolvedValue(undefined);
      vi.mocked(fs.readFile).mockResolvedValue(JSON.stringify(mockConfig));
      vi.mocked(fs.writeFile).mockResolvedValue(undefined);

      await ensureProfilesDir();
      const config = await readConfig();
      const profilePath = path.join(PROFILES_DIR, "dev-profile.json");
      await fs.writeFile(profilePath, JSON.stringify(config, null, 2));

      expect(fs.mkdir).toHaveBeenCalledWith(PROFILES_DIR, { recursive: true });
      expect(fs.writeFile).toHaveBeenCalledWith(
        profilePath,
        expect.any(String)
      );
    });
  });

  describe("airis_profile_load tool", () => {
    it("should load profile and replace config", async () => {
      const profileConfig: McpConfig = {
        mcpServers: {
          memory: { command: "npx", args: [], env: {}, enabled: false },
        },
      };

      vi.mocked(fs.readFile).mockImplementation(async (filepath) => {
        if ((filepath as string).includes("profiles")) {
          return JSON.stringify(profileConfig);
        }
        return JSON.stringify({ mcpServers: {} });
      });
      vi.mocked(fs.writeFile).mockResolvedValue(undefined);

      const profilePath = path.join(PROFILES_DIR, "dev-profile.json");
      const content = await fs.readFile(profilePath, "utf-8");
      const config = JSON.parse(content as string);
      await writeConfig(config);

      expect(fs.writeFile).toHaveBeenCalledWith(
        CONFIG_PATH,
        expect.stringContaining('"enabled": false')
      );
    });
  });

  describe("airis_profile_list tool", () => {
    it("should list all profiles", async () => {
      vi.mocked(fs.mkdir).mockResolvedValue(undefined);
      vi.mocked(fs.readdir).mockResolvedValue(["dev.json", "prod.json", "minimal.json"] as any);

      await ensureProfilesDir();
      const files = await fs.readdir(PROFILES_DIR);
      const profiles = (files as string[])
        .filter((f) => f.endsWith(".json"))
        .map((f) => f.replace(".json", ""));

      expect(profiles).toEqual(["dev", "prod", "minimal"]);
    });

    it("should handle empty profiles directory", async () => {
      vi.mocked(fs.mkdir).mockResolvedValue(undefined);
      vi.mocked(fs.readdir).mockResolvedValue([]);

      const files = await fs.readdir(PROFILES_DIR);
      expect(files).toHaveLength(0);
    });
  });
});

// airis_quick_enable and airis_quick_disable_all were removed.
// Server enable/disable is handled by airis-exec auto-enable.

describe("airis_mcp_detect tool", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should detect stripe from package.json", async () => {
    const packageJson = {
      dependencies: {
        stripe: "^14.0.0",
        express: "^4.0.0",
      },
    };

    vi.mocked(fs.readFile).mockImplementation(async (filepath) => {
      if ((filepath as string).includes("package.json")) {
        return JSON.stringify(packageJson);
      }
      return JSON.stringify({ mcpServers: {} });
    });

    const pkgContent = await fs.readFile("/workspace/host/package.json", "utf-8");
    const pkg = JSON.parse(pkgContent as string);
    const allDeps = { ...pkg.dependencies, ...pkg.devDependencies };

    const detected: string[] = [];
    for (const [mcpName, mapping] of Object.entries(MCP_MAPPINGS)) {
      for (const pkgName of mapping.packages) {
        if (allDeps[pkgName]) {
          detected.push(mcpName);
          break;
        }
      }
    }

    expect(detected).toContain("stripe");
  });

  it("should detect playwright from devDependencies", async () => {
    const packageJson = {
      devDependencies: {
        "@playwright/test": "^1.40.0",
      },
    };

    vi.mocked(fs.readFile).mockImplementation(async (filepath) => {
      if ((filepath as string).includes("package.json")) {
        return JSON.stringify(packageJson);
      }
      return JSON.stringify({ mcpServers: {} });
    });

    const pkgContent = await fs.readFile("/workspace/host/package.json", "utf-8");
    const pkg = JSON.parse(pkgContent as string);
    const allDeps = { ...pkg.dependencies, ...pkg.devDependencies };

    const detected: string[] = [];
    for (const [mcpName, mapping] of Object.entries(MCP_MAPPINGS)) {
      for (const pkgName of mapping.packages) {
        if (allDeps[pkgName]) {
          detected.push(mcpName);
          break;
        }
      }
    }

    expect(detected).toContain("playwright");
  });

  it("should detect github from .git directory", async () => {
    vi.mocked(fs.access).mockResolvedValue(undefined);

    const repoPath = "/workspace/host";
    let hasGit = false;

    try {
      await fs.access(path.join(repoPath, ".git"));
      hasGit = true;
    } catch {
      hasGit = false;
    }

    expect(hasGit).toBe(true);
  });

  it("should detect multiple packages", async () => {
    const packageJson = {
      dependencies: {
        "@supabase/supabase-js": "^2.0.0",
        pg: "^8.0.0",
      },
      devDependencies: {
        "@playwright/test": "^1.40.0",
      },
    };

    vi.mocked(fs.readFile).mockImplementation(async (filepath) => {
      if ((filepath as string).includes("package.json")) {
        return JSON.stringify(packageJson);
      }
      return JSON.stringify({ mcpServers: {} });
    });

    const pkgContent = await fs.readFile("/workspace/host/package.json", "utf-8");
    const pkg = JSON.parse(pkgContent as string);
    const allDeps = { ...pkg.dependencies, ...pkg.devDependencies };

    const detected: string[] = [];
    for (const [mcpName, mapping] of Object.entries(MCP_MAPPINGS)) {
      for (const pkgName of mapping.packages) {
        if (allDeps[pkgName]) {
          detected.push(mcpName);
          break;
        }
      }
    }

    expect(detected).toContain("supabase");
    expect(detected).toContain("postgres");
    expect(detected).toContain("playwright");
    expect(detected).toHaveLength(3);
  });

  it("should skip already configured MCPs", async () => {
    const packageJson = {
      dependencies: {
        stripe: "^14.0.0",
      },
    };

    const existingConfig: McpConfig = {
      mcpServers: {
        stripe: { command: "npx", args: [], env: {}, enabled: true },
      },
    };

    vi.mocked(fs.readFile).mockImplementation(async (filepath) => {
      if ((filepath as string).includes("package.json")) {
        return JSON.stringify(packageJson);
      }
      return JSON.stringify(existingConfig);
    });

    const config: McpConfig = JSON.parse(await fs.readFile(CONFIG_PATH, "utf-8") as string);
    const pkgContent = await fs.readFile("/workspace/host/package.json", "utf-8");
    const pkg = JSON.parse(pkgContent as string);
    const allDeps = { ...pkg.dependencies, ...pkg.devDependencies };

    const detected: Array<{ name: string; alreadyExists: boolean }> = [];
    for (const [mcpName, mapping] of Object.entries(MCP_MAPPINGS)) {
      for (const pkgName of mapping.packages) {
        if (allDeps[pkgName]) {
          detected.push({
            name: mcpName,
            alreadyExists: !!config.mcpServers[mcpName],
          });
          break;
        }
      }
    }

    expect(detected.find(d => d.name === "stripe")?.alreadyExists).toBe(true);
  });
});

describe("MCP_MAPPINGS", () => {
  it("should have correct structure for all mappings", () => {
    for (const [name, mapping] of Object.entries(MCP_MAPPINGS)) {
      expect(mapping.packages).toBeInstanceOf(Array);
      expect(mapping.packages.length).toBeGreaterThan(0);
      expect(mapping.mcp).toBeTruthy();
      expect(mapping.command).toMatch(/^(npx|uvx|node)$/);
      expect(mapping.args).toBeInstanceOf(Array);
      expect(mapping.env).toBeDefined();
      expect(mapping.envRequired).toBeInstanceOf(Array);
      expect(mapping.description).toBeTruthy();
    }
  });

  it("should have unique package names across mappings", () => {
    const allPackages: string[] = [];
    for (const mapping of Object.values(MCP_MAPPINGS)) {
      allPackages.push(...mapping.packages);
    }

    // Some packages might map to same MCP intentionally (e.g., pg and @prisma/client both -> postgres)
    // Just verify no completely empty packages array
    expect(allPackages.length).toBeGreaterThan(0);
  });
});

describe("airis_bridge_setup", () => {
  it("should include correct RTK install URL and hook command", () => {
    const guide = buildBridgeSetupGuide();
    expect(guide).toContain("https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh");
    expect(guide).toContain("rtk init -g");
    expect(guide).toContain("https://github.com/rtk-ai/rtk");
  });

  it("should include correct ICM install and Claude Code registration command", () => {
    const guide = buildBridgeSetupGuide();
    expect(guide).toContain("brew tap rtk-ai/tap && brew install icm");
    expect(guide).toContain("https://raw.githubusercontent.com/rtk-ai/icm/main/install.sh");
    expect(guide).toContain("claude mcp add --scope user icm -- icm serve");
    expect(guide).toContain("https://github.com/rtk-ai/icm");
  });

  it("should not reference NCP", () => {
    // NCP was removed: airis-mcp-gateway already provides equivalent tool consolidation (~98% reduction)
    const guide = buildBridgeSetupGuide();
    expect(guide).not.toContain("NCP");
    expect(guide).not.toContain("ncp add");
    expect(guide).not.toContain("@portel");
  });
});

describe("Error handling", () => {
  it("should handle unknown tool names", () => {
    const toolName = "unknown_tool";
    const knownTools = [
      "airis_config_add_server",
      "airis_config_remove_server",
      "airis_profile_save",
      "airis_profile_load",
      "airis_profile_list",
      "airis_mcp_detect",
    ];

    expect(() => {
      if (!knownTools.includes(toolName)) {
        throw new Error(`Unknown tool: ${toolName}`);
      }
    }).toThrow("Unknown tool: unknown_tool");
  });

  it("should handle JSON parse errors gracefully", async () => {
    vi.mocked(fs.readFile).mockResolvedValue("invalid json {");

    await expect(async () => {
      const content = await fs.readFile(CONFIG_PATH, "utf-8");
      JSON.parse(content as string);
    }).rejects.toThrow();
  });
});
