let activeSession = null;
let activeMode = "ask";
let activeJob = null;
let pollTimer = null;
let masterSettings = null;
let openFilePath = null;
let modelCatalog = {};
let editingDefaultProvider = "openai";
let otherProviderKeyDrafts = {};
let selectedCodeContext = "";
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
  if (!response.ok) {
    const error = new Error(data.error || "Request failed");
    error.status = response.status;
    throw error;
  }
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
  el("jobControl").hidden = true;
  setAgentStatus(session.queue.length ? "queued" : "idle", session.queue.length ? `${session.queue.length} prompt${session.queue.length === 1 ? "" : "s"} queued` : "Agent is idle.");
  el("sessionMemory").value = session.memory || "";
  el("conversation").innerHTML = `${session.compactionSummary ? `<details class="memory-summary"><summary>Earlier chat summary</summary><p>${escapeHtml(session.compactionSummary)}</p></details>` : ""}${session.history.map((item) => `
    <article class="chat-message ${item.role === "user" ? "user-message" : "assistant-message"}">
      <strong>${item.role === "user" ? "You" : "Coding Agent"}${item.mode ? ` · ${escapeHtml(item.mode)}` : ""}</strong>
      <div class="message-body">${escapeHtml(item.content || item.prompt || "")}</div>
      ${item.selectedCode ? `<details class="code-context"><summary>${escapeHtml(item.selectedCodePath || "Selected code")}</summary><pre>${escapeHtml(item.selectedCode)}</pre></details>` : ""}
    </article>
  `).join("")}`;
  el("compactSession").disabled = (session.history || []).length <= 8;
  el("forkSession").disabled = false;
  scrollConversationToBottom();
}

function scrollConversationToBottom() {
  const conversation = el("conversation");
  conversation.scrollTop = conversation.scrollHeight;
}

function appendJobMessages(job) {
  const conversation = el("conversation");
  const selector = `[data-assistant-job="${CSS.escape(job.id)}"]`;
  if (conversation.querySelector(selector)) return;
  const input = job.input || {};
  const userText = input.prompt || "";
  const selectedCode = input.selectedCode || "";
  const selectedCodePath = input.selectedCodePath || "";
  conversation.insertAdjacentHTML("beforeend", `
    <article class="chat-message user-message" data-user-job="${escapeHtml(job.id)}">
      <strong>You${input.mode ? ` · ${escapeHtml(input.mode)}` : ""}</strong>
      <div class="message-body">${escapeHtml(userText)}</div>
      ${selectedCode ? `<details class="code-context"><summary>${escapeHtml(selectedCodePath || "Selected code")}</summary><pre>${escapeHtml(selectedCode)}</pre></details>` : ""}
      ${input.browserUrl ? `<small>Browser check: ${escapeHtml(input.browserUrl)}</small>` : ""}
    </article>
    <article class="chat-message assistant-message" data-assistant-job="${escapeHtml(job.id)}">
      <strong>Coding Agent</strong>
      <div class="message-body">${escapeHtml(job.stream || "")}</div>
      <small class="message-status">${escapeHtml(job.status === "waiting_approval" ? "Waiting for your approval" : "Thinking…")}</small>
    </article>
  `);
  scrollConversationToBottom();
}

function renderSettings(settings) {
  masterSettings = settings;
  editingDefaultProvider = settings.provider || "openai";
  otherProviderKeyDrafts = { ...(settings.apiKeys || {}) };
  populateProviderSelect(el("provider"), settings.provider || "openai");
  populateModelSelect(el("model"), el("provider").value, settings.model);
  const apiKeys = settings.apiKeys || {};
  const apiKeyEnabled = settings.apiKeyEnabled || {};
  const savedKeys = {
    google: apiKeys.google || (settings.provider === "google" ? settings.apiKey || "" : ""),
    openai: apiKeys.openai || (settings.provider === "openai" ? settings.apiKey || "" : ""),
    anthropic: apiKeys.anthropic || (settings.provider === "anthropic" ? settings.apiKey || "" : "")
  };
  el("apiKeyGoogle").value = savedKeys.google;
  el("apiKeyOpenai").value = savedKeys.openai;
  el("apiKeyAnthropic").value = savedKeys.anthropic;
  ["google", "openai", "anthropic"].forEach((provider) => {
    const checked = Boolean(savedKeys[provider]) && (apiKeyEnabled[provider] ?? true);
    el(`enable${provider[0].toUpperCase()}${provider.slice(1)}Key`).checked = checked;
    el(`${provider}KeyStatus`).textContent = savedKeys[provider] ? "Secret saved" : "No key saved";
  });
  const openaiDefaultUrl = modelCatalog.openai?.baseUrl || "https://api.openai.com/v1";
  const hasBaseUrlOverrideFlag = typeof settings.baseUrlOverrideEnabled === "boolean";
  const baseUrlOverrideEnabled = hasBaseUrlOverrideFlag
    ? settings.baseUrlOverrideEnabled
    : Boolean(settings.provider === "openai" && settings.baseUrl && settings.baseUrl !== openaiDefaultUrl);
  el("overrideOpenaiBaseUrl").checked = baseUrlOverrideEnabled;
  el("openaiBaseUrl").value = settings.baseUrlOverrideEnabled || settings.provider === "openai"
    ? settings.baseUrl || openaiDefaultUrl
    : openaiDefaultUrl;
  el("openaiBaseUrlRow").hidden = !baseUrlOverrideEnabled;
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
  const labels = {
    queued: "Agent is queued…",
    running: "Agent is working…",
    pausing: "Pausing at the next safe step…",
    paused: "Agent is paused.",
    waiting_approval: "Waiting for your approval.",
    done: "Agent finished.",
    failed: "Agent stopped with an error."
  };
  setAgentStatus(job.status, labels[job.status] || `Agent status: ${job.status}`);
  const canControl = ["queued", "running", "pausing", "paused"].includes(job.status);
  el("jobControl").hidden = !canControl;
  el("jobControl").dataset.action = job.status === "paused" ? "resume" : "pause";
  el("jobControl").textContent = job.status === "paused" ? "Resume agent" : job.status === "pausing" ? "Pausing…" : "Pause agent";
  el("jobControl").disabled = job.status === "pausing";
  appendJobMessages(job);
  const assistant = el("conversation").querySelector(`[data-assistant-job="${CSS.escape(job.id)}"]`);
  if (!assistant) return;
  const body = assistant.querySelector(".message-body");
  if (["done", "failed"].includes(job.status)) body.textContent = job.result || job.stream || "";
  else if (job.stream) body.textContent = job.stream;
  else if (job.status === "waiting_approval") body.textContent = job.result || "";
  const latestEvent = job.events?.at(-1);
  assistant.querySelector(".message-status").textContent = latestEvent?.message || job.status;
  if (job.events?.length) {
    let activity = assistant.querySelector(".agent-activity");
    if (!activity) {
      assistant.insertAdjacentHTML("beforeend", `<details class="agent-activity"><summary></summary><div class="activity-items"></div></details>`);
      activity = assistant.querySelector(".agent-activity");
    }
    activity.querySelector("summary").textContent = `Agent activity · ${job.events.length} steps`;
    activity.querySelector(".activity-items").innerHTML = job.events.map((item) => `
      <div><strong>${escapeHtml(item.agent)}</strong><span>${escapeHtml(item.message)}</span></div>
    `).join("");
  }
  if (job.checkpoints?.length) {
    let checkpoints = assistant.querySelector(".job-checkpoints");
    if (!checkpoints) {
      assistant.insertAdjacentHTML("beforeend", `<details class="job-checkpoints"><summary></summary><ol></ol></details>`);
      checkpoints = assistant.querySelector(".job-checkpoints");
    }
    checkpoints.querySelector("summary").textContent = `Checkpoints · ${job.checkpoints.length}`;
    checkpoints.querySelector("ol").innerHTML = job.checkpoints.map((item) => `<li><strong>${escapeHtml(item.node)}</strong> ${escapeHtml(item.summary)}</li>`).join("");
  }
  const commands = job.approval?.developer_output?.commands || [];
  let approvalCard = assistant.querySelector(".approval-card");
  if (job.status === "waiting_approval" && !approvalCard) {
    assistant.insertAdjacentHTML("beforeend", `
      <section class="approval-card">
      <strong>Review commands before they run</strong>
      <pre>${escapeHtml(commands.map((item) => `${item.command}${item.why ? `  # ${item.why}` : ""}`).join("\n"))}</pre>
      <button class="primary" data-approve-job="${escapeHtml(job.id)}">Approve and run commands</button>
      </section>
    `);
  } else if (job.status !== "waiting_approval" && approvalCard) {
    approvalCard.remove();
  }
  scrollConversationToBottom();
}

function setAgentStatus(status, label) {
  const statusEl = el("queueState");
  statusEl.dataset.status = status;
  statusEl.textContent = label;
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
  if (path !== openFilePath) clearSelectedCodeContext();
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
  if (!sessions.length && !activeSession) {
    el("conversation").innerHTML = "";
    el("sessionMemory").value = "";
    el("forkSession").disabled = true;
    el("compactSession").disabled = true;
    setAgentStatus("idle", "Agent is idle. Start a chat to begin.");
  }
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
  clearSelectedCodeContext();
  el("conversation").innerHTML = "";
  const session = await api(`/api/sessions/${id}`);
  renderSession(session);
  renderSessions(await api("/api/sessions"));
  for (const jobId of session.queue) {
    const job = await api(`/api/jobs/${jobId}`).catch(() => null);
    if (job && ["queued", "running", "pausing", "paused", "waiting_approval"].includes(job.status)) {
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
        apiKeyEnabled: {
          google: el("enableGoogleKey").checked,
          openai: el("enableOpenaiKey").checked,
          anthropic: el("enableAnthropicKey").checked
        },
        provider,
        baseUrl: el("openaiBaseUrl").value.trim() || modelCatalog.openai?.baseUrl || "https://api.openai.com/v1",
        baseUrlOverrideEnabled: el("overrideOpenaiBaseUrl").checked,
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

async function deleteSessionById(sessionId, button) {
  if (button) button.disabled = true;
  try {
    const session = sessionId === activeSession?.id ? activeSession : await api(`/api/sessions/${sessionId}`);
    if (!session) return;
    const ok = confirm(`Delete "${session.name}"? This removes the chat history and queued jobs.`);
    if (!ok) return;
    await api(`/api/sessions/${session.id}`, { method: "DELETE" });
    if (activeSession?.id === session.id) {
      activeSession = null;
      el("conversation").innerHTML = "";
    }
    el("queueState").textContent = "Chat deleted.";
    await loadSessions();
  } catch (error) {
    if (error.status === 404) {
      if (activeSession?.id === sessionId) {
        activeSession = null;
        el("conversation").innerHTML = "";
      }
      el("queueState").textContent = "Chat deleted.";
      await loadSessions();
      return;
    }
    el("queueState").textContent = `Delete failed: ${error.message}`;
  } finally {
    if (button?.isConnected) button.disabled = false;
  }
}

async function sendPrompt() {
  if (!activeSession) await createSession();
  const rawPrompt = el("prompt").value.trim();
  const codeBlocks = [...rawPrompt.matchAll(/```[^\n]*\n([\s\S]*?)```/g)];
  const pastedCode = codeBlocks.map((match) => match[1].trim()).filter(Boolean).join("\n\n");
  const selectedCode = [selectedCodeContext, pastedCode].filter(Boolean).join("\n\n");
  const selectedCodePath = selectedCodeContext ? openFilePath || "" : "";
  const prompt = rawPrompt.replace(/```[^\n]*\n[\s\S]*?```/g, " ").trim()
    || (selectedCode ? "Review the code in the provided context." : "");
  if (!prompt) return;
  const job = await api(`/api/sessions/${activeSession.id}/prompts`, {
    method: "POST",
    body: JSON.stringify({
      mode: activeMode,
      prompt,
      selectedCode,
      selectedCodePath,
      browserUrl: el("browserUrl").value.trim(),
      provider: el("promptProvider").value,
      model: el("promptModel").value,
      permissionMode: el("permissionMode").value
    })
  });
  activeJob = job.id;
  renderJob(job);
  el("prompt").value = "";
  el("browserUrl").value = "";
  clearSelectedCodeContext();
  pollJob();
}

function clearSelectedCodeContext() {
  selectedCodeContext = "";
  el("selectionContext").hidden = true;
  el("selectionContextLabel").textContent = "";
}

function captureSelectedCode() {
  const browserSelection = window.getSelection();
  const selection = browserSelection?.toString().trim();
  if (!selection || !browserSelection.anchorNode || !el("fileViewer").contains(browserSelection.anchorNode)) return;
  selectedCodeContext = selection;
  const lineCount = selection.split("\n").length;
  el("selectionContextLabel").textContent = `${openFilePath || "File"} · ${lineCount} selected line${lineCount === 1 ? "" : "s"}`;
  el("selectionContext").hidden = false;
}

function askAboutSelection() {
  if (!selectedCodeContext) return;
  activeMode = "ask";
  document.querySelectorAll("[data-mode]").forEach((node) => node.classList.toggle("selected", node.dataset.mode === "ask"));
  el("prompt").value = `Explain this code from ${openFilePath || "the selected file"} and how it works.`;
  el("prompt").focus();
}

async function forkActiveSession() {
  if (!activeSession) return;
  try {
    const fork = await api(`/api/sessions/${activeSession.id}/fork`, { method: "POST" });
    await loadSession(fork.id);
    await loadSessions();
  } catch (error) {
    setAgentStatus("failed", `Could not fork chat: ${error.message}`);
  }
}

async function compactActiveSession() {
  if (!activeSession) return;
  const button = el("compactSession");
  button.disabled = true;
  try {
    setAgentStatus("running", "Compacting earlier messages…");
    const result = await api(`/api/sessions/${activeSession.id}/compact`, { method: "POST" });
    renderSession(result.session);
    setAgentStatus("idle", result.message);
  } catch (error) {
    setAgentStatus("failed", `Compaction failed: ${error.message}`);
  } finally {
    button.disabled = (activeSession?.history || []).length <= 8;
  }
}

async function saveSessionMemory() {
  if (!activeSession) return;
  try {
    const updated = await api(`/api/sessions/${activeSession.id}`, {
      method: "PATCH",
      body: JSON.stringify({ memory: el("sessionMemory").value })
    });
    activeSession = updated;
    el("memoryStatus").textContent = "Saved to this chat.";
  } catch (error) {
    el("memoryStatus").textContent = `Could not save: ${error.message}`;
  }
}

async function controlActiveJob() {
  if (!activeJob) return;
  const action = el("jobControl").dataset.action;
  el("jobControl").disabled = true;
  try {
    const job = await api(`/api/jobs/${activeJob}/${action}`, { method: "POST" });
    renderJob(job);
  } catch (error) {
    el("jobControl").disabled = false;
    setAgentStatus("failed", `Could not ${action} the agent: ${error.message}`);
  }
}

async function pollJob() {
  if (!activeJob) return;
  const jobId = activeJob;
  try {
    const job = await api(`/api/jobs/${jobId}`);
    if (activeJob !== jobId) return;
    renderJob(job);
    if (job.status === "done" || job.status === "failed") {
      clearTimeout(pollTimer);
      pollTimer = null;
      await loadSession(job.sessionId);
      if (job.status === "failed" && !activeJob) setAgentStatus("failed", "Agent stopped with an error.");
      await refreshWorkspace();
      return;
    }
    pollTimer = setTimeout(pollJob, 350);
  } catch (error) {
    if (activeJob !== jobId) return;
    clearTimeout(pollTimer);
    pollTimer = null;
    setAgentStatus("failed", `Could not read agent status: ${error.message}`);
  }
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
  el("apiKeyOther").value = CORE_KEY_PROVIDERS.includes(editingDefaultProvider)
    ? ""
    : otherProviderKeyDrafts[editingDefaultProvider] || "";
  if (!el("promptProvider").value) {
    populateModelSelect(el("promptModel"), el("provider").value, "", true);
  }
});
el("overrideOpenaiBaseUrl").addEventListener("change", () => {
  el("openaiBaseUrlRow").hidden = !el("overrideOpenaiBaseUrl").checked;
});
["google", "openai", "anthropic"].forEach((provider) => {
  const titleCase = provider[0].toUpperCase() + provider.slice(1);
  el(`apiKey${titleCase}`).addEventListener("input", (event) => {
    if (event.target.value) el(`enable${titleCase}Key`).checked = true;
  });
});
el("promptProvider").addEventListener("change", () => {
  const provider = el("promptProvider").value || el("provider").value;
  populateModelSelect(el("promptModel"), provider, "", true);
});
el("sendPrompt").addEventListener("click", sendPrompt);
el("jobControl").addEventListener("click", controlActiveJob);
el("forkSession").addEventListener("click", forkActiveSession);
el("compactSession").addEventListener("click", compactActiveSession);
el("saveMemory").addEventListener("click", saveSessionMemory);
el("askAboutSelection").addEventListener("click", askAboutSelection);
el("prompt").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendPrompt();
  }
});
el("conversation").addEventListener("click", async (event) => {
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
    deleteSessionById(deleteButton.dataset.deleteSession, deleteButton);
    return;
  }
  const openButton = event.target.closest("[data-session]");
  if (openButton) {
    showView("home");
    loadSession(openButton.dataset.session);
  }
});
el("refreshFiles").addEventListener("click", refreshWorkspace);
el("fileViewer").addEventListener("mouseup", captureSelectedCode);
el("fileViewer").addEventListener("keyup", captureSelectedCode);
el("clearSelectionContext").addEventListener("click", clearSelectedCodeContext);
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
