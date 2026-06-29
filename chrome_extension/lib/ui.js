/**
 * MailGuard-AI — UI helpers (used by content scripts and popup).
 *
 * Provides a minimal, dependency-free toast + button helper.
 */

const UI = {
  /**
   * Show a transient toast at the bottom of the page.
   * @param {string} message
   * @param {string} type info | success | warning | danger
   */
  toast(message, type = "info", durationMs = 3500) {
    let container = document.getElementById("__mailguard_toast_container__");
    if (!container) {
      container = document.createElement("div");
      container.id = "__mailguard_toast_container__";
      Object.assign(container.style, {
        position: "fixed",
        bottom: "20px",
        right: "20px",
        zIndex: "999999",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        fontFamily: "Inter, system-ui, sans-serif",
      });
      document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    toast.textContent = message;
    Object.assign(toast.style, {
      padding: "10px 14px",
      borderRadius: "8px",
      color: "#fff",
      boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
      fontSize: "13px",
      maxWidth: "360px",
      animation: "mg-fade-in 0.2s ease-out",
    });
    const palette = {
      info: "#2563eb",
      success: "#16a34a",
      warning: "#d97706",
      danger: "#dc2626",
    };
    toast.style.background = palette[type] || palette.info;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.transition = "opacity 0.3s";
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 350);
    }, durationMs);
  },

  /**
   * Inject a `<style>` block once (idempotent).
   */
  injectStyles(id, css) {
    if (document.getElementById(id)) return;
    const tag = document.createElement("style");
    tag.id = id;
    tag.textContent = css;
    document.head.appendChild(tag);
  },
};

if (typeof window !== "undefined") {
  window.MailGuardUI = UI;
}