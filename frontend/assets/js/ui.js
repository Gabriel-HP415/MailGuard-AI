/**
 * UI helpers used across pages: navbar, auth guard, toasts, formatting.
 */

const UI = {
  /**
   * Render a Bootstrap navbar and return whether the user is allowed
   * to see the requested page (based on pageAuth meta tag).
   */
  mountNavbar({ active = "", showAuth = true, showAdmin = false } = {}) {
    const template = document.getElementById("navbar-template");
    if (!template) return;
    const host = document.getElementById("navbar-mount");
    host.innerHTML = "";
    host.appendChild(template.content.cloneNode(true));

    const links = [
      { id: "dashboard", href: "/dashboard.html", label: "Dashboard", auth: false },
      { id: "predictions", href: "/predictions.html", label: "Predictions", auth: false },
      { id: "lists", href: "/lists.html", label: "Lists", auth: false },
      { id: "admin", href: "/admin.html", label: "Admin", auth: true, admin: true },
    ];
    const ul = host.querySelector("[data-nav-links]");
    ul.innerHTML = "";
    links.forEach((l) => {
      if (l.admin && !api.isAdmin()) return;
      const li = document.createElement("li", { class: "nav-item" });
      li.className = "nav-item";
      const a = document.createElement("a", { class: "nav-link" });
      a.className = "nav-link" + (l.id === active ? " active" : "");
      a.href = l.href;
      a.textContent = l.label;
      li.appendChild(a);
      ul.appendChild(li);
    });

    const userSlot = host.querySelector("[data-nav-user]");
    if (api.isAuthenticated() && api.user) {
      userSlot.innerHTML = `
        <span class="navbar-text me-2">${UI.escapeHtml(api.user.full_name || api.user.email)}</span>
        <button class="btn btn-sm btn-light" id="nav-logout">Sign out</button>
      `;
      document.getElementById("nav-logout").addEventListener("click", async () => {
        await api.logout();
        window.location.href = "/login.html";
      });
    } else if (showAuth) {
      userSlot.innerHTML = `
        <a class="btn btn-sm btn-light" href="/login.html">Sign in</a>
      `;
    }

    // Page auth guard
    const pageAuth = document.querySelector("meta[name='page-auth']")?.content;
    if (pageAuth === "required" && !api.isAuthenticated()) {
      window.location.href = `/login.html?next=${encodeURIComponent(window.location.pathname)}`;
    }
    if (pageAuth === "admin" && !api.isAdmin()) {
      window.location.href = "/dashboard.html";
      UI.toast("Admin role required", "warning");
    }
  },

  toast(message, type = "info", durationMs = 3500) {
    let stack = document.getElementById("mg-toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.id = "mg-toast-stack";
      stack.className = "mg-toast-stack";
      document.body.appendChild(stack);
    }
    const el = document.createElement("div");
    el.className = `mg-toast mg-toast--${type}`;
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => {
      el.style.transition = "opacity 0.3s";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 350);
    }, durationMs);
  },

  escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  },

  fmtDate(d) {
    if (!d) return "—";
    try {
      return new Date(d).toLocaleString();
    } catch (err) {
      return d;
    }
  },

  fmtPct(x) {
    return `${(Number(x || 0) * 100).toFixed(1)}%`;
  },

  badgeClass(predictedClass) {
    return `badge-class class-${predictedClass || "normal"}`;
  },

  threatClass(level) {
    return `threat-${level || "low"}`;
  },

  /**
   * Render a span badge for the predicted class.
   */
  badge(predictedClass) {
    const cls = predictedClass || "normal";
    return `<span class="${UI.badgeClass(cls)}">${cls.toUpperCase()}</span>`;
  },

  /**
   * Render suspicious spans (highlighted_spans) into safe HTML.
   * `spans` is an array of { start, end, text, category, reason }.
   */
  highlightIntoHtml(text, spans) {
    if (!spans || !spans.length) return UI.escapeHtml(text);
    const sorted = spans
      .filter((s) => Number.isInteger(s.start) && Number.isInteger(s.end) && s.end > s.start)
      .sort((a, b) => a.start - b.start);
    let cursor = 0;
    let out = "";
    for (const s of sorted) {
      if (s.start < cursor) continue;
      out += UI.escapeHtml(text.slice(cursor, s.start));
      out += `<mark class="mg-mark${s.category === "url" ? " mg-mark--url" : ""}"
                title="${UI.escapeHtml(s.reason || s.text || "")}">${UI.escapeHtml(text.slice(s.start, s.end))}</mark>`;
      cursor = s.end;
    }
    out += UI.escapeHtml(text.slice(cursor));
    return out;
  },
};