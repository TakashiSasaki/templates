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

  receiveFromView(message) {
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

    return null;
  }

  notificationForView(method, params) {
    if (!this.#initialized) {
      throw new Error("Host must not send requests or notifications before View initialization completes");
    }
    return {
      jsonrpc: "2.0",
      method,
      params,
    };
  }

  get initialized() {
    return this.#initialized;
  }
}
