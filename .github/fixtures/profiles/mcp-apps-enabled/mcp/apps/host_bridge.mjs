export const APPS_EXTENSION_ID = "io.modelcontextprotocol/ui";
export const APPS_REVISION = "2026-01-26";
export const APP_MIME_TYPE = "text/html;profile=mcp-app";

function uiMeta(tool) {
  const meta = tool?._meta;
  return meta && typeof meta === "object" && meta.ui && typeof meta.ui === "object"
    ? meta.ui
    : {};
}

export function visibleToModel(tool) {
  const visibility = uiMeta(tool).visibility;
  return !Array.isArray(visibility) || visibility.includes("model");
}

export function visibleToApp(tool) {
  const visibility = uiMeta(tool).visibility;
  return !Array.isArray(visibility) || visibility.includes("app");
}

export function modelInventory(tools) {
  return tools.filter(visibleToModel);
}

export function appInventory(tools) {
  return tools.filter(visibleToApp);
}

export function assertAppCallAllowed({ sourceServer, targetServer, tool }) {
  if (sourceServer !== targetServer) {
    throw new Error("cross-server App tool calls are not allowed");
  }
  if (!visibleToApp(tool)) {
    throw new Error(`tool ${tool?.name ?? "<unknown>"} is not app-visible`);
  }
  return true;
}

export class HostBridgeSession {
  #initializeResponseSent = false;
  #initialized = false;
  #sourceServer;
  #targetServer;
  #tools;
  #callTool;

  constructor({
    sourceServer = "fixture-server",
    targetServer = "fixture-server",
    tools = [],
    callTool = null,
  } = {}) {
    this.#sourceServer = sourceServer;
    this.#targetServer = targetServer;
    this.#tools = tools;
    this.#callTool = callTool;
  }

  async receiveFromView(message) {
    if (!message || message.jsonrpc !== "2.0" || typeof message.method !== "string") {
      throw new Error("invalid JSON-RPC bridge message");
    }

    if (!this.#initializeResponseSent) {
      if (message.method !== "ui/initialize" || message.id === undefined) {
        throw new Error("the first View message must be ui/initialize request");
      }
      if (
        !message.params ||
        typeof message.params !== "object" ||
        !message.params.appCapabilities ||
        typeof message.params.appCapabilities !== "object" ||
        Array.isArray(message.params.appCapabilities)
      ) {
        throw new Error("ui/initialize requires appCapabilities");
      }

      this.#initializeResponseSent = true;
      return {
        jsonrpc: "2.0",
        id: message.id,
        result: {
          protocolVersion: APPS_REVISION,
          hostCapabilities: {
            serverTools: {},
          },
          hostInfo: {
            name: "fixture-host",
            version: "1.0.0",
          },
          hostContext: {
            theme: "light",
          },
        },
      };
    }

    if (!this.#initialized) {
      if (message.method !== "ui/notifications/initialized" || message.id !== undefined) {
        throw new Error("View must send ui/notifications/initialized before ordinary bridge traffic");
      }
      this.#initialized = true;
      return null;
    }

    if (message.method === "tools/call") {
      if (message.id === undefined) {
        throw new Error("App tools/call must be a JSON-RPC request with an id");
      }
      const name = message.params?.name;
      if (typeof name !== "string" || !name) {
        throw new Error("App tools/call requires a tool name");
      }
      const tool = this.#tools.find((candidate) => candidate.name === name);
      if (!tool) {
        throw new Error(`unknown App tool ${name}`);
      }
      assertAppCallAllowed({
        sourceServer: this.#sourceServer,
        targetServer: this.#targetServer,
        tool,
      });
      if (typeof this.#callTool !== "function") {
        throw new Error("no App tool dispatcher is configured");
      }

      return {
        jsonrpc: "2.0",
        id: message.id,
        result: await this.#callTool({
          name,
          arguments: message.params?.arguments ?? {},
        }),
      };
    }

    throw new Error(`unsupported initialized View method ${message.method}`);
  }

  notificationForView(method, params) {
    if (!this.#initialized) {
      throw new Error("Host must not send requests or notifications before View initialization completes");
    }
    const notification = {
      jsonrpc: "2.0",
      method,
    };
    if (params !== undefined) {
      notification.params = params;
    }
    return notification;
  }

  get initialized() {
    return this.#initialized;
  }
}
