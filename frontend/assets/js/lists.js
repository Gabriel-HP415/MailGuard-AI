(function () {
  UI.mountNavbar({ active: "lists" });

  const wlList = document.getElementById("wl-list");
  const blList = document.getElementById("bl-list");

  async function loadWl() {
    wlList.innerHTML = `<li class="mg-empty">Loading…</li>`;
    try {
      const items = await api.getWhitelist();
      if (!items.length) {
        wlList.innerHTML = `<li class="mg-empty">No entries yet.</li>`;
        return;
      }
      wlList.innerHTML = items
        .map(
          (i) => `
          <li class="list-group-item d-flex justify-content-between align-items-center">
            <div>
              <strong>${UI.escapeHtml(i.sender)}</strong>
              ${i.note ? `<div class="small text-muted">${UI.escapeHtml(i.note)}</div>` : ""}
            </div>
            <button class="btn btn-sm btn-outline-danger" data-id="${i.id}" data-action="wl">Remove</button>
          </li>`,
        )
        .join("");
    } catch (err) {
      wlList.innerHTML = `<li class="mg-empty">${UI.escapeHtml(err.message)}</li>`;
    }
  }
  async function loadBl() {
    blList.innerHTML = `<li class="mg-empty">Loading…</li>`;
    try {
      const items = await api.getBlacklist();
      if (!items.length) {
        blList.innerHTML = `<li class="mg-empty">No entries yet.</li>`;
        return;
      }
      blList.innerHTML = items
        .map(
          (i) => `
          <li class="list-group-item d-flex justify-content-between align-items-center">
            <div>
              <strong>${UI.escapeHtml(i.sender)}</strong>
              ${i.reason ? `<div class="small text-muted">${UI.escapeHtml(i.reason)}</div>` : ""}
            </div>
            <button class="btn btn-sm btn-outline-danger" data-id="${i.id}" data-action="bl">Remove</button>
          </li>`,
        )
        .join("");
    } catch (err) {
      blList.innerHTML = `<li class="mg-empty">${UI.escapeHtml(err.message)}</li>`;
    }
  }

  document.getElementById("wl-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api.addWhitelist({
        sender: document.getElementById("wl-sender").value.trim(),
        note: document.getElementById("wl-note").value.trim() || null,
      });
      UI.toast("Added to whitelist", "success");
      e.target.reset();
      loadWl();
    } catch (err) { UI.toast(err.message, "danger"); }
  });

  document.getElementById("bl-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api.addBlacklist({
        sender: document.getElementById("bl-sender").value.trim(),
        reason: document.getElementById("bl-reason").value.trim() || null,
      });
      UI.toast("Added to blacklist", "warning");
      e.target.reset();
      loadBl();
    } catch (err) { UI.toast(err.message, "danger"); }
  });

  wlList.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action='wl']");
    if (!btn) return;
    try {
      await api.removeWhitelist(parseInt(btn.dataset.id, 10));
      UI.toast("Removed", "info");
      loadWl();
    } catch (err) { UI.toast(err.message, "danger"); }
  });

  blList.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action='bl']");
    if (!btn) return;
    try {
      await api.removeBlacklist(parseInt(btn.dataset.id, 10));
      UI.toast("Removed", "info");
      loadBl();
    } catch (err) { UI.toast(err.message, "danger"); }
  });

  loadWl();
  loadBl();
})();