(async function () {
  UI.mountNavbar({ active: "predictions" });

  const params = new URLSearchParams(window.location.search);
  const id = params.get("id");
  const detail = document.getElementById("detail");
  const fbStatus = document.getElementById("fb-status");

  if (!id) {
    detail.innerHTML = `<div class="mg-empty">No prediction id provided.</div>`;
    return;
  }

  try {
    const p = await api.getPrediction(id);
    const explanation = p.explanation || {};
    const components = explanation.components || {};
    const highlights = p.highlighted_spans || [];
    const suspUrls = p.suspicious_urls || [];

    detail.innerHTML = `
      <div class="d-flex justify-content-between align-items-start">
        <div>
          <h3 class="mb-1">${UI.badge(p.predicted_class)}</h3>
          <p class="text-muted mb-0">Threat: <span class="badge-class ${UI.threatClass(p.threat_level)}">${p.threat_level}</span> · Risk ${(p.risk_score ?? 0).toFixed(1)} · Confidence ${UI.fmtPct(p.confidence)}</p>
        </div>
        <small class="text-muted">${UI.fmtDate(p.created_at)}</small>
      </div>

      <hr/>

      <div class="row mb-3">
        <div class="col-md-6">
          <h6 class="text-muted">Subject</h6>
          <p>${UI.escapeHtml(p.email?.subject || "—")}</p>
        </div>
        <div class="col-md-6">
          <h6 class="text-muted">Sender</h6>
          <p>${UI.escapeHtml(p.email?.sender || "—")}</p>
        </div>
      </div>

      <h6 class="text-muted">Summary</h6>
      <p>${UI.escapeHtml(explanation.summary || "—")}</p>

      <h6 class="text-muted mt-3">Body (with highlights)</h6>
      <div class="border rounded p-3 bg-light" style="white-space: pre-wrap;">
        ${UI.highlightIntoHtml(p.email?.body_text || "", highlights)}
      </div>

      <h6 class="text-muted mt-3">Risk components</h6>
      <ul class="list-group">
        ${Object.entries(components)
          .map(([k, v]) => `<li class="list-group-item d-flex justify-content-between">
              <span>${UI.escapeHtml(k)}</span><strong>+${typeof v === "number" ? v.toFixed(1) : UI.escapeHtml(v)}</strong>
            </li>`)
          .join("")}
      </ul>

      ${suspUrls.length ? `
        <h6 class="text-muted mt-3">Suspicious URLs</h6>
        <ul>
          ${suspUrls.map((u) => `<li><code>${UI.escapeHtml(u.url || u)}</code>
            ${u.reasons ? `<div class="small text-muted">${UI.escapeHtml(u.reasons.join(", "))}</div>` : ""}
          </li>`).join("")}
        </ul>
      ` : ""}
    `;

    document.querySelectorAll("[data-fb]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        try {
          await api.sendFeedback({
            prediction_id: parseInt(id, 10),
            is_correct: btn.dataset.fb === "true",
            comment: null,
          });
          fbStatus.textContent = "Feedback sent — thank you!";
          UI.toast("Thanks for your feedback", "success");
        } catch (err) {
          fbStatus.textContent = `Failed: ${err.message}`;
        }
      }),
    );
  } catch (err) {
    detail.innerHTML = `<div class="mg-empty">Failed to load: ${UI.escapeHtml(err.message)}</div>`;
  }
})();