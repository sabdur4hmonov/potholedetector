"""Shared browser-test setup that never puts credentials in URLs or server logs."""

SECURE_CREDENTIALS_MOCK = r"""
(() => {
  const capacitor = window.Capacitor;
  if (!capacitor || !capacitor.isNativePlatform()) return;
  let openAiConfigured = false;
  let dashcamRtspConfigured = false;
  const status = () => ({openAiConfigured, dashcamRtspConfigured});
  const plugin = {
    getStatus: async () => status(),
    migrateLegacyCredentials: async (options = {}) => {
      openAiConfigured ||= !!options.openAiKey;
      dashcamRtspConfigured ||= !!options.dashcamRtspUrl;
      return status();
    },
    storeCredentials: async (options = {}) => {
      openAiConfigured ||= !!options.openAiKey;
      dashcamRtspConfigured ||= !!options.dashcamRtspUrl;
      return status();
    },
    clearCredentials: async () => {
      openAiConfigured = false;
      dashcamRtspConfigured = false;
      return status();
    },
  };
  capacitor.Plugins ||= {};
  capacitor.Plugins.SecureCredentials = plugin;
  let mediaToken = null;
  const managedMedia = {
    beginOperation: async () => {
      if (mediaToken) throw new Error("Active media operation");
      mediaToken = crypto.randomUUID();
      return {token: mediaToken};
    },
    endOperation: async ({token}) => {
      if (token !== mediaToken) throw new Error("Invalid media operation");
      mediaToken = null;
      return {cleaned: true};
    },
  };
  capacitor.Plugins.ManagedMedia = managedMedia;
  if (capacitor.registerPlugin) {
    const original = capacitor.registerPlugin.bind(capacitor);
    capacitor.registerPlugin = (name) => name === "SecureCredentials" ? plugin
      : name === "ManagedMedia" ? managedMedia : original(name);
  }
})();
"""


def open_app(page, key):
    page.goto("http://localhost:8765/")
    page.wait_for_load_state("domcontentloaded")
    page.evaluate("key => localStorage.setItem('openai_key', key)", key)
    page.reload()
    page.wait_for_load_state("networkidle")


# The browser build deliberately refuses paid AI calls (SEC-006): the only authoritative
# usage ledger lives in the Android bridge. Tests that exercise detection, deduplication
# and repair logic therefore run the page as a native app whose single fixed OpenAI
# operation is answered by the test's own mocked window.fetch. No real service is reached.
NATIVE_PLATFORM_STUB = r"""
(() => {
  if (!window.Capacitor) {
    Object.defineProperty(window, "Capacitor", {configurable: true, writable: true, value: {
      isNativePlatform: () => true,
      Plugins: {},
    }});
  }
})();
"""

NATIVE_OPENAI_BRIDGE = r"""
(() => {
  const plugin = window.Capacitor && window.Capacitor.Plugins
    && window.Capacitor.Plugins.SecureCredentials;
  if (!plugin) return;
  plugin.openAiRequest = async (envelope) => {
    const response = await window.fetch("https://api.openai.com/v1/responses", {
      method: "POST", body: envelope.body,
    });
    return {status: response.status, ok: response.ok, body: await response.text()};
  };
})();
"""

NATIVE_AI_PAGE_SCRIPT = NATIVE_PLATFORM_STUB + SECURE_CREDENTIALS_MOCK + NATIVE_OPENAI_BRIDGE
