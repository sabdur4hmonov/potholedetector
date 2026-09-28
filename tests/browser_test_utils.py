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
