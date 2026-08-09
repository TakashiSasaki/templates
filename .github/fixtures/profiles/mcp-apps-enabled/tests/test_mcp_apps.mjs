import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

import {
  APP_MIME_TYPE,
  APPS_EXTENSION_ID,
  APPS_REVISION,
  HostBridgeSession,
  appInventory,
  assertAppCallAllowed,
  modelInventory,
} from "../mcp/apps/host_bridge.mjs";
import { UI_RESOURCE_URI } from "../mcp/server.mjs";

const fixtureRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const serverPath = path.join(fixtureRoot, "mcp", "server.mjs");

async function connectClient({ apps }) {
  const capabilities = apps
    ? {
        extensions: {
          [APPS_EXTENSION_ID]: {
            mimeTypes: [APP_MIME_TYPE],
          },
        },
      }
    : {};
  const client = new Client(
    { name: apps ? "apps-host" : "core-host", version: "1.0.0" },
    {
      capabilities,
      versionNegotiation: { mode: { pin: "2026-07-28" } },
    },
  );
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [serverPath],
    stderr: "pipe",
  });
  await client.connect(transport);
  return client;
}

async function callTextStats(client, text = "alpha beta\ngamma") {
  return client.callTool({
    name: "text_stats",
    arguments: { text },
  });
}

test("Modern discovery advertises the MCP Apps extension settings", async () => {
  const client = await connectClient({ apps: true });
  try {
    assert.equal(client.getProtocolEra(), "modern");
    assert.equal(client.getNegotiatedProtocolVersion(), "2026-07-28");
    assert.deepEqual(client.getServerCapabilities()?.extensions?.[APPS_EXTENSION_ID], {
      mimeTypes: [APP_MIME_TYPE],
    });
  } finally {
    await client.close();
  }
});

test("tool metadata links the primary tool to a ui resource and preserves visibility", async () => {
  const client = await connectClient({ apps: true });
  try {
    const { tools } = await client.listTools();
    const primary = tools.find((tool) => tool.name === "text_stats");
    const refresh = tools.find((tool) => tool.name === "refresh_stats");
    const modelOnly = tools.find((tool) => tool.name === "model_summary");

    assert.equal(primary?._meta?.ui?.resourceUri, UI_RESOURCE_URI);
    assert.deepEqual(primary?._meta?.ui?.visibility, ["model", "app"]);
    assert.deepEqual(refresh?._meta?.ui?.visibility, ["app"]);
    assert.deepEqual(modelOnly?._meta?.ui?.visibility, ["model"]);

    assert.deepEqual(modelInventory(tools).map((tool) => tool.name), [
      "text_stats",
      "model_summary",
    ]);
    assert.deepEqual(appInventory(tools).map((tool) => tool.name), [
      "text_stats",
      "refresh_stats",
    ]);

    assert.equal(assertAppCallAllowed({ sourceServer: "one", targetServer: "one", tool: refresh }), true);
    assert.throws(
      () => assertAppCallAllowed({ sourceServer: "one", targetServer: "one", tool: modelOnly }),
      /not app-visible/,
    );
    assert.throws(
      () => assertAppCallAllowed({ sourceServer: "one", targetServer: "two", tool: refresh }),
      /cross-server/,
    );
  } finally {
    await client.close();
  }
});

test("ui resource resolves with the Apps media type and restrictive metadata", async () => {
  const client = await connectClient({ apps: true });
  try {
    const inventory = await client.listResources();
    const resource = inventory.resources.find((item) => item.uri === UI_RESOURCE_URI);
    assert.equal(resource?.mimeType, APP_MIME_TYPE);

    const result = await client.readResource({ uri: UI_RESOURCE_URI });
    assert.equal(result.contents.length, 1);
    const content = result.contents[0];
    assert.equal(content.uri, UI_RESOURCE_URI);
    assert.equal(content.mimeType, APP_MIME_TYPE);
    assert.match(content.text, /ui\/initialize/);
    assert.match(content.text, /ui\/notifications\/initialized/);
    assert.match(content.text, /ui\/notifications\/tool-result/);
    assert.deepEqual(content._meta?.ui?.csp, {
      connectDomains: [],
      resourceDomains: [],
      frameDomains: [],
      baseUriDomains: [],
    });
    assert.deepEqual(content._meta?.ui?.permissions, {});
    assert.equal(content._meta?.ui?.prefersBorder, true);
    assert.doesNotMatch(content.text, /https?:\/\//);
  } finally {
    await client.close();
  }
});

test("core tool result remains meaningful when the Host does not advertise Apps", async () => {
  const appsClient = await connectClient({ apps: true });
  const coreClient = await connectClient({ apps: false });
  try {
    const appResult = await callTextStats(appsClient);
    const coreResult = await callTextStats(coreClient);
    const expected = { bytes: 16, lines: 2, words: 3 };

    assert.deepEqual(appResult.structuredContent, expected);
    assert.deepEqual(coreResult.structuredContent, expected);
    assert.equal(appResult.content[0]?.type, "text");
    assert.equal(coreResult.content[0]?.type, "text");
    assert.equal(appResult.content[0]?.text, coreResult.content[0]?.text);

    const trailingNewline = await callTextStats(coreClient, "alpha\n");
    assert.deepEqual(trailingNewline.structuredContent, {
      bytes: 6,
      lines: 1,
      words: 1,
    });
  } finally {
    await Promise.all([appsClient.close(), coreClient.close()]);
  }
});

test("Apps bridge initialization is independent of the removed core initialize handshake", () => {
  const bridge = new HostBridgeSession();

  assert.throws(
    () => bridge.notificationForView("ui/notifications/tool-result", {}),
    /before View initialization completes/,
  );
  assert.throws(
    () => bridge.receiveFromView({ jsonrpc: "2.0", id: 1, method: "initialize", params: {} }),
    /first View message must be ui\/initialize/,
  );
  assert.throws(
    () => bridge.receiveFromView({ jsonrpc: "2.0", id: 1, method: "ui/initialize", params: {} }),
    /appCapabilities/,
  );

  const response = bridge.receiveFromView({
    jsonrpc: "2.0",
    id: 7,
    method: "ui/initialize",
    params: {
      appCapabilities: {
        availableDisplayModes: ["inline"],
      },
    },
  });
  assert.equal(response.id, 7);
  assert.equal(response.result.protocolVersion, APPS_REVISION);
  assert.equal(response.result.hostInfo.name, "fixture-host");
  assert.equal(bridge.initialized, false);

  assert.throws(
    () => bridge.notificationForView("ui/notifications/tool-result", {}),
    /before View initialization completes/,
  );

  assert.equal(
    bridge.receiveFromView({
      jsonrpc: "2.0",
      method: "ui/notifications/initialized",
    }),
    null,
  );
  assert.equal(bridge.initialized, true);

  const resultNotification = bridge.notificationForView("ui/notifications/tool-result", {
    content: [{ type: "text", text: "ok" }],
    structuredContent: { bytes: 2, lines: 1, words: 1 },
  });
  assert.equal(resultNotification.method, "ui/notifications/tool-result");
  assert.deepEqual(resultNotification.params.structuredContent, {
    bytes: 2,
    lines: 1,
    words: 1,
  });
});
