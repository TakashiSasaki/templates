import assert from "node:assert/strict";
import { once } from "node:events";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import test from "node:test";

import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

const fixtureRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const serverPath = path.join(fixtureRoot, "mcp", "server.mjs");

async function connectModernClient() {
  const client = new Client(
    { name: "fixture-test-client", version: "1.0.0" },
    { versionNegotiation: { mode: { pin: "2026-07-28" } } },
  );
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [serverPath],
    stderr: "pipe",
  });
  await client.connect(transport);
  return client;
}

async function firstWireResponse(request) {
  const child = spawn(process.execPath, [serverPath], {
    cwd: fixtureRoot,
    stdio: ["pipe", "pipe", "pipe"],
  });

  let buffer = "";
  const responsePromise = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("timed out waiting for MCP response")), 5000);
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      buffer += chunk;
      const newline = buffer.indexOf("\n");
      if (newline === -1) return;
      clearTimeout(timer);
      const line = buffer.slice(0, newline).trim();
      try {
        resolve(JSON.parse(line));
      } catch (error) {
        reject(error);
      }
    });
    child.on("error", reject);
  });

  child.stdin.end(`${JSON.stringify(request)}\n`);
  try {
    return await responsePromise;
  } finally {
    child.kill("SIGTERM");
    await Promise.race([once(child, "exit"), new Promise((resolve) => setTimeout(resolve, 1000))]);
    if (child.exitCode === null) child.kill("SIGKILL");
  }
}

test("Modern client discovers the server, lists the tool, and calls it", async () => {
  const client = await connectModernClient();
  try {
    assert.equal(client.getProtocolEra(), "modern");
    const serverInfo = client.getServerVersion();
    assert.equal(serverInfo?.name, "text-stat-modern-fixture");

    const inventory = await client.listTools();
    assert.deepEqual(inventory.tools.map((tool) => tool.name), ["text_stats"]);

    const result = await client.callTool({
      name: "text_stats",
      arguments: { text: "alpha beta\ngamma" },
    });
    assert.deepEqual(result.structuredContent, {
      bytes: 16,
      lines: 2,
      words: 3,
    });
    assert.equal(result.isError, undefined);

    const trailingNewline = await client.callTool({
      name: "text_stats",
      arguments: { text: "alpha\n" },
    });
    assert.deepEqual(trailingNewline.structuredContent, {
      bytes: 6,
      lines: 1,
      words: 1,
    });
  } finally {
    await client.close();
  }
});

test("Legacy initialize opening is rejected by the Modern-only server", async () => {
  const response = await firstWireResponse({
    jsonrpc: "2.0",
    id: 1,
    method: "initialize",
    params: {
      protocolVersion: "2025-11-25",
      capabilities: {},
      clientInfo: { name: "legacy-probe", version: "1.0.0" },
    },
  });

  assert.equal(response.error?.code, -32022);
  assert.deepEqual(response.error?.data?.supported, ["2026-07-28"]);
});

test("unsupported Modern revision receives UnsupportedProtocolVersionError", async () => {
  const response = await firstWireResponse({
    jsonrpc: "2.0",
    id: 2,
    method: "server/discover",
    params: {
      _meta: {
        "io.modelcontextprotocol/protocolVersion": "2099-01-01",
        "io.modelcontextprotocol/clientCapabilities": {},
        "io.modelcontextprotocol/clientInfo": {
          name: "future-probe",
          version: "1.0.0",
        },
      },
    },
  });

  assert.equal(response.error?.code, -32022);
  assert.equal(response.error?.data?.requested, "2099-01-01");
  assert.deepEqual(response.error?.data?.supported, ["2026-07-28"]);
});
