let activeSession = null;
let activeMode = "ask";
let activeJob = null;
let pollTimer = null;
let masterSettings = null;
let openFilePath = null;
let modelCatalog = {};

const el = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "content-type": "application/json",
      ...(options.headers || {})
    }
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

function renderSessions(sessions) {
  el("sessions").innerHTML = sessions.map((session) => `
    <div class="session-item ${session.id === activeSession?.id ? "active" : ""}">
      <button class="session-open" data-session="${session.id}">
        <strong>${escapeHtml(session.name)}</strong>
        <p>${new Date(session.updatedAt).toLocaleString()}</p>
      </button>
      <div class="session-actions">
        <button data-rename-session="${session.id}" title="Rename chat">Rename</button>
        <button data-delete-session="${session.id}" class="danger" title="Delete chat">Delete</button>
      </div>
    </div>
  `).join("");
}

function renderSession(session) {
  activeSession = session;
  el("sessionName").textContent = session.name;
  el("queueState").textContent = `${session.queue.length} queued prompt${session.queue.length === 1 ? "" : "s"}`;
  el("history").innerHTML = session.history.slice().reverse().map((item) => `
    <article class="message">
      <strong>${escapeHtml(item.role)}${item.mode ? ` · ${escapeHtml(item.mode)}` : ""}</strong>
      <pre>${escapeHtml(item.content || item.prompt || "")}</pre>
    </article>
  `).join("");
}

function renderSettings(settings) {
  masterSettings = settings;
  populateProviderSelect(el("provider"), settings.provider || "openai");
  populateModelSelect(el("model"), el("provider").value, settings.model);
  el("apiKey").value = settings.apiKey || "";
  el("baseUrl").value = settings.baseUrl || "https://api.openai.com/v1";
  populateProviderSelect(el("promptProvider"), "", true);
  populateModelSelect(el("promptModel"), settings.provider || "openai", "", true);
}

function populateProviderSelect(select, selected = "openai", includeMaster = false) {
  const masterOption = includeMaster ? `<option value="">Use master provider</option>` : "";
  select.innerHTML = masterOption + Object.entries(modelCatalog).map(([id, provider]) => `
    <option value="${id}" ${id === selected ? "selected" : ""}>${escapeHtml(provider.label)}</option>
  `).join("");
}

function populateModelSelect(select, providerId, selected = "", includeMaster = false) {
  const provider = modelCatalog[providerId] || modelCatalog.openai || { models: [] };
  const masterOption = includeMaster ? `<option value="">Use master model</option>` : "";
  select.innerHTML = masterOption + provider.models.map((model) => `
    <option value="${escapeHtml(model)}" ${model === selected ? "selected" : ""}>${escapeHtml(model)}</option>
  `).join("");
}

function syncBaseUrlFromProvider(providerId) {
  const provider = modelCatalog[providerId];
  if (provider?.baseUrl) el("baseUrl").value = provider.baseUrl;
}

function renderJob(job) {
  const statusClass = job.status === "done" ? "status-done" : job.status === "failed" ? "status-failed" : "";
  el("queueState").innerHTML = `Job <span class="${statusClass}">${job.status}</span>`;
  el("timeline").innerHTML = job.events.map((event) => `
    <article class="event">
      <strong>${escapeHtml(event.agent)} · ${new Date(event.at).toLocaleTimeString()}</strong>
      <div>${escapeHtml(event.message)}</div>
      ${Object.keys(event.data || {}).length ? `<pre>${escapeHtml(JSON.stringify(event.data, null, 2))}</pre>` : ""}
    </article>
  `).join("");
}

function renderFiles(files) {
  if (!files.length) {
    el("fileList").innerHTML = `<p class="empty-state">No files in this workspace.</p>`;
    return;
  }
  el("fileList").innerHTML = files.map((file) => {
    const change = file.modified
      ? `<span class="change-pill" title="+${file.modified.added} -${file.modified.deleted}">${file.modified.total} lines</span>`
      : "";
    const disabled = file.type === "dir" ? "disabled" : "";
    return `
      <button class="file-item ${file.type}" data-file="${escapeHtml(file.path)}" ${disabled}>
        <span class="file-path">${file.type === "dir" ? "▸ " : ""}${escapeHtml(file.path)}</span>
        ${change}
      </button>
    `;
  }).join("");
}

async function refreshWorkspace() {
  const [workspace, files] = await Promise.all([
    api("/api/workspace"),
    api("/api/files")
  ]);
  el("workingPath").textContent = workspace.root;
  el("gitState").textContent = workspace.gitAvailable ? "Modified lines use git diff." : "No git baseline for modified lines.";
  renderFiles(files);
  if (openFilePath) await openFile(openFilePath, false);
}

async function openFile(path, updateSelection = true) {
  openFilePath = path;
  const file = await api(`/api/file?path=${encodeURIComponent(path)}`);
  el("openFileName").textContent = path;
  el("fileViewer").textContent = file.content || "";
  if (updateSelection) {
    const current = document.querySelector(`[data-file="${CSS.escape(path)}"] .change-pill`);
    el("openFileMeta").textContent = current?.textContent ? `${current.textContent} modified` : "";
  }
}

async function loadSessions() {
  const sessions = await api("/api/sessions");
  if (activeSession && !sessions.some((session) => session.id === activeSession.id)) {
    activeSession = null;
  }
  if (!activeSession && sessions[0]) {
    await loadSession(sessions[0].id);
  }
  renderSessions(sessions);
}

async function loadSession(id) {
  const session = await api(`/api/sessions/${id}`);
  renderSession(session);
  await loadSessions();
}

async function createSession() {
  const session = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ name: "New Chat" })
  });
  await loadSession(session.id);
}

async function saveSettings() {
  const settings = await api("/api/settings", {
    method: "PATCH",
    body: JSON.stringify({
      apiKey: el("apiKey").value.trim(),
      provider: el("provider").value,
      baseUrl: el("baseUrl").value.trim(),
      model: el("model").value
    })
  });
  renderSettings(settings);
  el("queueState").textContent = "Master API settings saved.";
}

async function renameSessionById(sessionId) {
  const session = sessionId === activeSession?.id ? activeSession : await api(`/api/sessions/${sessionId}`);
  if (!session) return;
  const name = prompt("Rename chat", session.name);
  if (!name?.trim()) return;
  try {
    const updated = await api(`/api/sessions/${session.id}`, {
      method: "PATCH",
      body: JSON.stringify({ name: name.trim(), isAutoNamed: false })
    });
    if (activeSession?.id === updated.id) renderSession(updated);
    el("queueState").textContent = "Chat renamed.";
    await loadSessions();
  } catch (error) {
    el("queueState").textContent = `Rename failed: ${error.message}`;
  }
}

async function deleteSessionById(sessionId) {
  const session = sessionId === activeSession?.id ? activeSession : await api(`/api/sessions/${sessionId}`);
  if (!session) return;
  const ok = confirm(`Delete "${session.name}"? This removes the chat history and queued jobs.`);
  if (!ok) return;
  try {
    await api(`/api/sessions/${session.id}`, { method: "DELETE" });
    if (activeSession?.id === session.id) {
      activeSession = null;
      el("timeline").innerHTML = "";
      el("history").innerHTML = "";
      el("sessionName").textContent = "No session";
    }
    el("queueState").textContent = "Chat deleted.";
    await loadSessions();
  } catch (error) {
    el("queueState").textContent = `Delete failed: ${error.message}`;
  }
}

async function sendPrompt() {
  if (!activeSession) await createSession();
  const prompt = el("prompt").value.trim();
  if (!prompt) return;
  const job = await api(`/api/sessions/${activeSession.id}/prompts`, {
    method: "POST",
    body: JSON.stringify({
      mode: activeMode,
      prompt,
      selectedCode: el("selectedCode").value,
      provider: el("promptProvider").value,
      model: el("promptModel").value,
      permissionMode: el("permissionMode").value
    })
  });
  activeJob = job.id;
  el("prompt").value = "";
  pollJob();
}

async function pollJob() {
  if (!activeJob) return;
  const job = await api(`/api/jobs/${activeJob}`);
  renderJob(job);
  if (job.status === "done" || job.status === "failed") {
    clearTimeout(pollTimer);
    pollTimer = null;
    await loadSession(job.sessionId);
    await refreshWorkspace();
    return;
  }
  pollTimer = setTimeout(pollJob, 1200);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

el("newSession").addEventListener("click", createSession);
el("saveSettings").addEventListener("click", saveSettings);
el("provider").addEventListener("change", () => {
  syncBaseUrlFromProvider(el("provider").value);
  populateModelSelect(el("model"), el("provider").value, el("model").value);
});
el("promptProvider").addEventListener("change", () => {
  const provider = el("promptProvider").value || el("provider").value;
  populateModelSelect(el("promptModel"), provider, "", true);
});
el("renameSession").addEventListener("click", () => {
  if (activeSession) renameSessionById(activeSession.id);
});
el("deleteSession").addEventListener("click", () => {
  if (activeSession) deleteSessionById(activeSession.id);
});
el("sendPrompt").addEventListener("click", sendPrompt);
el("sessions").addEventListener("click", (event) => {
  const renameButton = event.target.closest("[data-rename-session]");
  if (renameButton) {
    renameSessionById(renameButton.dataset.renameSession);
    return;
  }
  const deleteButton = event.target.closest("[data-delete-session]");
  if (deleteButton) {
    deleteSessionById(deleteButton.dataset.deleteSession);
    return;
  }
  const openButton = event.target.closest("[data-session]");
  if (openButton) loadSession(openButton.dataset.session);
});
el("refreshFiles").addEventListener("click", refreshWorkspace);
el("fileList").addEventListener("click", (event) => {
  const button = event.target.closest("[data-file]");
  if (button && !button.disabled) openFile(button.dataset.file);
});
el("modes").addEventListener("click", (event) => {
  const button = event.target.closest("[data-mode]");
  if (!button) return;
  activeMode = button.dataset.mode;
  document.querySelectorAll("[data-mode]").forEach((node) => node.classList.toggle("selected", node === button));
});

modelCatalog = await api("/api/models");
renderSettings(await api("/api/settings"));
await refreshWorkspace();
loadSessions();
