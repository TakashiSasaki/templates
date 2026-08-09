import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { McpServer } from "@modelcontextprotocol/server";
import { serveStdio } from "@modelcontextprotocol/server/stdio";
import * as z from "zod/v4";

import { textStats } from "../src/text_stats.mjs";
import { APP_MIME_TYPE, APPS_EXTENSION_ID } from "./apps/host_bridge.mjs";

export const UI_RESOURCE_URI = "ui://text-stats/result";
const appHtml = readFileSync(new URL("./apps/result.html", import.meta.url), "utf8");
const uiResourceMeta = {
  ui: {
    csp: {
      connectDomains: [],
      resourceDomains: [],
      frameDomains: [],
      baseUriDomains: [],
    },
    permissions: {},
    prefersBorder: true,
  },
};
const outputSchema = z.object({
  bytes: z.number().int().nonnegative(),
  lines: z.number().int().nonnegative(),
  words: z.number().int().nonnegative(),
});

function resultFor(text) {
  const stats = textStats(text);
  return {
    content: [{ type: "text", text: JSON.stringify(stats) }],
    structuredContent: stats,
  };
}

export function createServer() {
  const mcp = new McpServer({
    name: "text-stat-mcp-apps-fixture",
    version: "1.0.0",
  });

  mcp.server.registerCapabilities({
    extensions: {
      [APPS_EXTENSION_ID]: {
        mimeTypes: [APP_MIME_TYPE],
      },
    },
  });

  mcp.registerResource(
    "text-stat-result-view",
    UI_RESOURCE_URI,
    {
      title: "Text statistics result",
      description: "Sandboxed MCP App View for text statistics.",
      mimeType: APP_MIME_TYPE,
      _meta: uiResourceMeta,
    },
    async (uri) => ({
      contents: [
        {
          uri: uri.href,
          mimeType: APP_MIME_TYPE,
          text: appHtml,
          _meta: uiResourceMeta,
        },
      ],
    }),
  );

  mcp.registerTool(
    "text_stats",
    {
      description: "Compute text statistics with optional rich MCP App presentation.",
      inputSchema: z.object({ text: z.string() }),
      outputSchema,
      _meta: {
        ui: {
          resourceUri: UI_RESOURCE_URI,
          visibility: ["model", "app"],
        },
      },
    },
    async ({ text }) => resultFor(text),
  );

  mcp.registerTool(
    "refresh_stats",
    {
      description: "App-only helper for refreshing displayed statistics.",
      inputSchema: z.object({ text: z.string() }),
      outputSchema,
      _meta: {
        ui: {
          visibility: ["app"],
        },
      },
    },
    async ({ text }) => resultFor(text),
  );

  mcp.registerTool(
    "model_summary",
    {
      description: "Model-only statistics operation unavailable to the App View.",
      inputSchema: z.object({ text: z.string() }),
      outputSchema,
      _meta: {
        ui: {
          visibility: ["model"],
        },
      },
    },
    async ({ text }) => resultFor(text),
  );

  return mcp;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  serveStdio(createServer, { legacy: "reject" });
  console.error("text-stat MCP Apps fixture serving Modern MCP on stdio");
}
