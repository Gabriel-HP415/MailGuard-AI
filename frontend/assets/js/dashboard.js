(async function () {
  UI.mountNavbar({ active: "dashboard" });

  const statTotal   = document.getElementById("stat-total");
  const statHigh    = document.getElementById("stat-high");
  const statAvg     = document.getElementById("stat-avg");
  const statFb      = document.getElementById("stat-feedback");
  const recentTable = document.getElementById("recent-table");
  const aiHealth    = document.getElementById("ai-health");

  const palette = {
    normal: "#16a34a",
    notification: "#2563eb",
    spam: "#d97706",
    scam: "#dc2626",
    low: "#22c55e",
    medium: "#facc15",
    high: "#f97316",
    critical: "#dc2626",
  };

  // ----- Stats -----
  try {
    const stats = await api.getStats(30);
    statTotal.textContent = stats.total ?? 0;
    const high = (stats.by_threat?.high || 0) + (stats.by_threat?.critical || 0);
    statHigh.textContent  = high;
    statAvg.textContent   = (stats.avg_risk ?? 0).toFixed(1);

    // Class distribution
    const byClass = stats.by_class || {};
    new Chart(document.getElementById("chart-class"), {
      type: "doughnut",
      data: {
        labels: Object.keys(byClass),
        datasets: [{
          data: Object.values(byClass),
          backgroundColor: Object.keys(byClass).map((k) => palette[k] || "#94a3b8"),
        }],
      },
      options: { plugins: { legend: { position: "bottom" } } },
    });

    // Threat levels
    const byThreat = stats.by_threat || {};
    new Chart(document.getElementById("chart-threat"), {
      type: "bar",
      data: {
        labels: Object.keys(byThreat),
        datasets: [{
          label: "Count",
          data: Object.values(byThreat),
          backgroundColor: Object.keys(byThreat).map((k) => palette[k] || "#94a3b8"),
        }],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      },
    });
  } catch (err) {
    UI.toast(`Stats error: ${err.message}`, "danger");
  }

  // ----- Feedback count -----
  try {
    const fb = await api._request("/feedback?limit=1"); // count via response if needed
    statFb.textContent = (fb?.length || (fb?.results?.length || 0));
  } catch (err) {
    statFb.textContent = "0";
  }

  // ----- Recent predictions -----
  try {
    const data = await api.getRecent(10);
    const items = data.results || data || [];
    if (!items.length) {
      recentTable.innerHTML = `<tr><td colspan="6" class="mg-empty">No predictions yet.</td></tr>`;
    } else {
      recentTable.innerHTML = items
        .map((p) => `
          <tr>
            <td>${UI.fmtDate(p.created_at)}</td>
            <td>${UI.badge(p.predicted_class)}</td>
            <td>${(p.risk_score ?? 0).toFixed(1)}</td>
            <td><span class="badge-class ${UI.threatClass(p.threat_level)}">${p.threat_level}</span></td>
            <td>${UI.escapeHtml(p.email?.sender || "—")}</td>
            <td><a class="btn btn-sm btn-outline-primary" href="/prediction.html?id=${p.id}">View</a></td>
          </tr>`)
        .join("");
    }
  } catch (err) {
    recentTable.innerHTML = `<tr><td colspan="6" class="mg-empty">Failed: ${UI.escapeHtml(err.message)}</td></tr>`;
  }

  // ----- AI health -----
  try {
    const h = await api.getAIHealth();
    aiHealth.textContent = JSON.stringify(h, null, 2);
  } catch (err) {
    aiHealth.textContent = `Could not reach AI service: ${err.message}`;
  }
})();