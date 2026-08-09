import { fileURLToPath } from "node:url";

import { McpServer } from "@modelcontextprotocol/server";
import { serveStdio } from "@modelcontextprotocol/server/stdio";
import * as z from "zod/v4";

import { textStats } from "../src/text_stats.mjs";

export function createServer() {
  const server = new McpServer({
    name: "text-stat-modern-fixture",
    version: "1.0.0",
  });

  server.registerTool(
    "text_stats",
    {
      description: "Compute deterministic UTF-8 byte, line, and word counts.",
      inputSchema: z.object({
        text: z.string(),
      }),
      outputSchema: z.object({
        bytes: z.number().int().nonnegative(),
        lines: z.number().int().nonnegative(),
        words: z.number().int().nonnegative(),
      }),
    },
    async ({ text }) => {
      const stats = textStats(text);
      return {
        content: [{ type: "text", text: JSON.stringify(stats) }],
        structuredContent: stats,
      };
    },
  );

  return server;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  serveStdio(createServer, { legacy: "reject" });
  console.error("text-stat Modern MCP server listening on stdio");
}
