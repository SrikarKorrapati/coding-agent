let activeSession = null;
let activeMode = "ask";
let activeJob = null;
let pollTimer = null;
let masterSettings = null;
let openFilePath = null;
let modelCatalog = {};
let editingDefaultProvider = "openai";
let otherProviderKeyDrafts = {};
const CORE_KEY_PROVIDERS = ["google", "openai", "anthropic"];

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
  editingDefaultProvider = settings.provider || "openai";
  otherProviderKeyDrafts = { ...(settings.apiKeys || {}) };
  populateProviderSelect(el("provider"), settings.provider || "openai");
  populateModelSelect(el("model"), el("provider").value, settings.model);
  el("baseUrl").value = settings.baseUrl || modelCatalog[settings.provider]?.baseUrl || "";
  const apiKeys = settings.apiKeys || {};
  el("apiKeyGoogle").value = apiKeys.google || (settings.provider === "google" ? settings.apiKey || "" : "");
  el("apiKeyOpenai").value = apiKeys.openai || (settings.provider === "openai" ? settings.apiKey || "" : "");
  el("apiKeyAnthropic").value = apiKeys.anthropic || (settings.provider === "anthropic" ? settings.apiKey || "" : "");
  el("apiKeyOther").value = CORE_KEY_PROVIDERS.includes(settings.provider)
    ? ""
    : apiKeys[settings.provider] || settings.apiKey || "";
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

function showView(view) {
  const settingsOpen = view === "settings";
  el("shell").classList.toggle("settings-open", settingsOpen);
  el("settingsPage").hidden = !settingsOpen;
  el("homeView").classList.toggle("selected", !settingsOpen);
  el("settingsView").classList.toggle("selected", settingsOpen);
}

function renderJob(job) {
  const statusClass = job.status === "done" ? "status-done" : job.status === "failed" ? "status-failed" : "";
  el("queueState").innerHTML = `Job <span class="${statusClass}">${job.status}</span>`;
  const commands = job.approval?.developer_output?.commands || [];
  const approval = job.status === "waiting_approval" ? `
    <section class="approval-card">
      <strong>Review commands before they run</strong>
      <pre>${escapeHtml(commands.map((item) => `${item.command}${item.why ? `  # ${item.why}` : ""}`).join("\n"))}</pre>
      <button class="primary" data-approve-job="${escapeHtml(job.id)}">Approve and run commands</button>
    </section>
  ` : "";
  el("timeline").innerHTML = approval + job.events.map((event) => `
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
  let sessions;
  try {
    sessions = await api("/api/sessions");
  } catch (error) {
    el("queueState").textContent = `Could not load chats: ${error.message}`;
    return;
  }
  if (activeSession && !sessions.some((session) => session.id === activeSession.id)) {
    activeSession = null;
  }
  // Render the list before loading a session so a slow session request cannot hide the chats.
  renderSessions(sessions);
  if (!activeSession && sessions[0]) {
    el("queueState").textContent = "Loading latest chat…";
    try {
      await loadSession(sessions[0].id);
    } catch (error) {
      el("queueState").textContent = `Could not open the latest chat: ${error.message}`;
    }
  }
}

async function loadSession(id) {
  clearTimeout(pollTimer);
  pollTimer = null;
  activeJob = null;
  el("timeline").innerHTML = "";
  const session = await api(`/api/sessions/${id}`);
  renderSession(session);
  renderSessions(await api("/api/sessions"));
  for (const jobId of session.queue) {
    const job = await api(`/api/jobs/${jobId}`).catch(() => null);
    if (job && ["queued", "running", "waiting_approval"].includes(job.status)) {
      activeJob = job.id;
      renderJob(job);
      pollJob();
      break;
    }
  }
}

async function createSession() {
  showView("home");
  const session = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ name: "New Chat" })
  });
  await loadSession(session.id);
}

async function saveSettings() {
  el("settingsStatus").textContent = "Saving…";
  try {
    const provider = el("provider").value;
    const apiKeyOther = el("apiKeyOther").value.trim();
    const apiKeys = {
      ...otherProviderKeyDrafts,
      google: el("apiKeyGoogle").value.trim(),
      openai: el("apiKeyOpenai").value.trim(),
      anthropic: el("apiKeyAnthropic").value.trim()
    };
    if (!CORE_KEY_PROVIDERS.includes(provider)) apiKeys[provider] = apiKeyOther;
    const settings = await api("/api/settings", {
      method: "PATCH",
      body: JSON.stringify({
        apiKey: CORE_KEY_PROVIDERS.includes(provider) ? "" : apiKeyOther,
        apiKeys,
        provider,
        baseUrl: el("baseUrl").value.trim() || modelCatalog[provider]?.baseUrl || masterSettings.baseUrl,
        model: el("model").value
      })
    });
    renderSettings(settings);
    el("settingsStatus").textContent = "Settings saved.";
  } catch (error) {
    el("settingsStatus").textContent = `Save failed: ${error.message}`;
  }
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
    }
    el("queueState").textContent = "Chat deleted.";
    await loadSessions();
  } catch (error) {
    el("queueState").textContent = `Delete failed: ${error.message}`;
  }
}

async function sendPrompt() {
  if (!activeSession) await createSession();
  const rawPrompt = el("prompt").value.trim();
  const codeBlocks = [...rawPrompt.matchAll(/```[^\n]*\n([\s\S]*?)```/g)];
  const selectedCode = codeBlocks.map((match) => match[1].trim()).filter(Boolean).join("\n\n");
  const prompt = rawPrompt.replace(/```[^\n]*\n[\s\S]*?```/g, " ").trim()
    || (selectedCode ? "Review the code in the provided context." : "");
  if (!prompt) return;
  const job = await api(`/api/sessions/${activeSession.id}/prompts`, {
    method: "POST",
    body: JSON.stringify({
      mode: activeMode,
      prompt,
      selectedCode,
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
  if (!CORE_KEY_PROVIDERS.includes(editingDefaultProvider)) {
    otherProviderKeyDrafts[editingDefaultProvider] = el("apiKeyOther").value.trim();
  }
  editingDefaultProvider = el("provider").value;
  populateModelSelect(el("model"), el("provider").value, el("model").value);
  el("baseUrl").value = modelCatalog[editingDefaultProvider]?.baseUrl || "";
  el("apiKeyOther").value = CORE_KEY_PROVIDERS.includes(editingDefaultProvider)
    ? ""
    : otherProviderKeyDrafts[editingDefaultProvider] || "";
  if (!el("promptProvider").value) {
    populateModelSelect(el("promptModel"), el("provider").value, "", true);
  }
});
el("promptProvider").addEventListener("change", () => {
  const provider = el("promptProvider").value || el("provider").value;
  populateModelSelect(el("promptModel"), provider, "", true);
});
el("sendPrompt").addEventListener("click", sendPrompt);
el("timeline").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-approve-job]");
  if (!button) return;
  button.disabled = true;
  try {
    const job = await api(`/api/jobs/${button.dataset.approveJob}/approve`, { method: "POST" });
    activeJob = job.id;
    pollJob();
  } catch (error) {
    button.disabled = false;
    el("queueState").textContent = `Approval failed: ${error.message}`;
  }
});
el("homeView").addEventListener("click", () => showView("home"));
el("settingsView").addEventListener("click", () => showView("settings"));
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
  if (openButton) {
    showView("home");
    loadSession(openButton.dataset.session);
  }
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
await Promise.allSettled([refreshWorkspace(), loadSessions()]);
document.documentElement.dataset.codingAgentReady = "true";
