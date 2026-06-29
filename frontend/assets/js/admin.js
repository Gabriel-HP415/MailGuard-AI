(function () {
  UI.mountNavbar({ active: "admin" });

  const tbody = document.getElementById("mv-tbody");
  const form = document.getElementById("create-form");

  async function load() {
    tbody.innerHTML = `<tr><td colspan="7" class="mg-empty">Loading…</td></tr>`;
    try {
      const items = await api.listModels();
      if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="mg-empty">No model versions yet.</td></tr>`;
        return;
      }
      tbody.innerHTML = items
        .map(
          (m) => `
          <tr>
            <td><code>${UI.escapeHtml(m.version)}</code></td>
            <td><span class="badge-class class-normal">${UI.escapeHtml(m.algorithm)}</span></td>
            <td>${(m.accuracy ?? 0).toFixed(4)}</td>
            <td>${m.is_active ? '<span class="badge-class class-notification">ACTIVE</span>' : ""}</td>
            <td>${UI.fmtDate(m.created_at)}</td>
            <td class="small text-muted">${UI.escapeHtml(m.description || "—")}</td>
            <td>
              ${m.is_active ? "" : `<button class="btn btn-sm btn-outline-primary" data-id="${m.id}" data-action="activate">Activate</button>`}
            </td>
          </tr>`,
        )
        .join("");
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="7" class="mg-empty">${UI.escapeHtml(err.message)}</td></tr>`;
    }
  }

  tbody.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action='activate']");
    if (!btn) return;
    try {
      await api.activateModel(parseInt(btn.dataset.id, 10));
      UI.toast("Model activated", "success");
      load();
    } catch (err) { UI.toast(err.message, "danger"); }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const payload = {
        version: document.getElementById("mv-version").value.trim(),
        algorithm: document.getElementById("mv-algorithm").value,
        accuracy: parseFloat(document.getElementById("mv-accuracy").value) || 0.0,
        artifact_path: document.getElementById("mv-path").value.trim() || null,
        description: document.getElementById("mv-desc").value.trim() || null,
      };
      await api.createModel(payload);
      UI.toast("Model registered", "success");
      form.reset();
      load();
    } catch (err) { UI.toast(err.message, "danger"); }
  });

  load();
})();