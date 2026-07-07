(async function () {
  await UI.mountNavbarAsync({ active: "predictions" });

  const tbody = document.getElementById("table-body");
  const form  = document.getElementById("filter-form");
  const limitSel = document.getElementById("filter-limit");
  const classSel = document.getElementById("filter-class");
  document.getElementById("refresh-btn").addEventListener("click", () => load());

  async function load() {
    tbody.innerHTML = `<tr><td colspan="7" class="mg-empty">Loading…</td></tr>`;
    try {
      const params = { limit: parseInt(limitSel.value, 10) };
      if (classSel.value) params.predicted_class = classSel.value;
      const data = await api.listPredictions(params);
      const items = Array.isArray(data) ? data : (data.results || []);
      if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="mg-empty">No predictions found.</td></tr>`;
        return;
      }
      tbody.innerHTML = items
        .map((p) => `
          <tr>
            <td>${UI.fmtDate(p.created_at)}</td>
            <td>${UI.badge(p.predicted_class)}</td>
            <td>${(p.risk_score ?? 0).toFixed(1)}</td>
            <td><span class="badge-class ${UI.threatClass(p.threat_level)}">${p.threat_level}</span></td>
            <td>${UI.escapeHtml(p.email?.subject || "—")}</td>
            <td>${UI.escapeHtml(p.email?.sender || "—")}</td>
            <td><a class="btn btn-sm btn-outline-primary" href="/prediction.html?id=${p.id}">View</a></td>
          </tr>`)
        .join("");
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="7" class="mg-empty">Failed: ${UI.escapeHtml(err.message)}</td></tr>`;
    }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); load(); });
  load();
})();