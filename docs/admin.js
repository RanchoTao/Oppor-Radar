const $ = (selector) => document.querySelector(selector);

const state = {
  apiUrl: null,
  token: "",
  groups: [],
  sources: [],
  profile: {},
  connected: false,
  dirty: false,
  baseline: null,
  busy: false,
};

function markDirty(dirty = true) {
  state.dirty = dirty;
  $("#save-state").textContent = dirty ? "有未保存的修改，仅保留在当前页面。" : "没有未保存的修改。";
  $("#save-state").dataset.dirty = String(dirty);
  $("#save-registry").disabled = !dirty || state.busy;
  $("#discard-changes").disabled = !dirty || state.busy;
}

function rememberBaseline() {
  state.baseline = JSON.stringify({ groups: state.groups, sources: state.sources });
  markDirty(false);
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function message(text, kind = "") {
  const node = $("#admin-message");
  node.textContent = text;
  node.dataset.kind = kind;
}

async function loadRuntime() {
  try {
    const response = await fetch("./data/runtime.json", { cache: "no-store" });
    if (!response.ok) throw new Error(String(response.status));
    const runtime = await response.json();
    state.apiUrl = runtime.registry_api_url || null;
  } catch (error) {
    state.apiUrl = null;
  }

  $("#registry-endpoint").textContent = state.apiUrl
    ? `Registry API: ${state.apiUrl}`
    : "Registry API 尚未配置。部署管理服务并设置 docs/data/runtime.json 后，这个页面才会启用。";
  $("#connect-registry").disabled = !state.apiUrl;
  $("#admin-token").disabled = !state.apiUrl;
  if (!state.apiUrl) message("当前为未连接状态，来源编辑尚未启用。");
}

async function registryRequest(method, body = null) {
  if (!state.apiUrl) throw new Error("Registry API 未配置");
  const response = await fetch(state.apiUrl, {
    method,
    mode: "cors",
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${state.token}`,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : null,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.error || `HTTP ${response.status}`);
  return data;
}

function enabledGroups() {
  return state.groups.filter((group) => group.enabled !== false);
}

function updateGroupSelect() {
  const select = $("#new-source-group");
  select.innerHTML = ["未分组", ...enabledGroups().map((group) => group.name)]
    .map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`)
    .join("");
}

function renderGroups() {
  const holder = $("#admin-groups");
  holder.innerHTML = state.groups.map((group, index) => `
    <div class="admin-row">
      <div><strong>${escapeHtml(group.name)}</strong><span class="muted">order ${group.order ?? (index + 1) * 10}</span></div>
      <button type="button" class="danger-link" aria-label="删除分组 ${escapeHtml(group.name)}" data-remove-group="${index}">删除</button>
    </div>
  `).join("") || '<p class="muted">暂无分组。</p>';

  holder.querySelectorAll("[data-remove-group]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.removeGroup);
      const name = state.groups[index]?.name;
      if (!name) return;
      if (!confirm(`删除“${name}”后，其来源会移到“未分组”。保存前可撤销。继续删除？`)) return;
      state.groups.splice(index, 1);
      state.sources.forEach((source) => {
        if (source.group === name) source.group = "未分组";
      });
      renderAll();
      markDirty();
    });
  });
}

function renderSources() {
  const holder = $("#admin-sources");
  $("#admin-source-count").textContent = `${state.sources.length} 个来源`;
  holder.innerHTML = state.sources.map((source, index) => `
    <div class="admin-row admin-source-row">
      <div>
        <div class="source-title-row"><strong>${escapeHtml(source.name)}</strong><span class="group-badge">${escapeHtml(source.group || "未分组")}</span>${source.enabled === false ? '<span class="tag">已暂停</span>' : ""}</div>
        <a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer" class="source-url">${escapeHtml(source.url)}</a>
        ${(source.watch || []).length ? `<small>关注：${escapeHtml(source.watch.join(" · "))}</small>` : ""}
      </div>
      <div class="admin-row-actions">
        <button type="button" class="text-link" aria-label="${source.enabled === false ? "启用" : "暂停"} ${escapeHtml(source.name)}" data-toggle-source="${index}">${source.enabled === false ? "启用" : "暂停"}</button>
        <button type="button" class="danger-link" aria-label="删除来源 ${escapeHtml(source.name)}" data-remove-source="${index}">删除</button>
      </div>
    </div>
  `).join("") || '<p class="muted">暂无信息源。</p>';

  holder.querySelectorAll("[data-toggle-source]").forEach((button) => {
    button.addEventListener("click", () => {
      const source = state.sources[Number(button.dataset.toggleSource)];
      source.enabled = source.enabled === false;
      renderSources();
      markDirty();
    });
  });
  holder.querySelectorAll("[data-remove-source]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!confirm("将此来源移出列表？保存前可撤销。")) return;
      state.sources.splice(Number(button.dataset.removeSource), 1);
      renderSources();
      markDirty();
    });
  });
}

function renderAll() {
  renderGroups();
  updateGroupSelect();
  renderSources();
}

async function connect() {
  if (!state.apiUrl || state.busy) return;
  if (state.dirty && !confirm("重新连接会放弃未保存的修改。继续？")) return;
  const token = $("#admin-token").value.trim();
  if (!token) {
    message("请输入 Admin Token。", "error");
    return;
  }
  state.token = token;
  state.busy = true;
  $("#connect-registry").disabled = true;
  $("#admin-token").value = "";
  message("正在连接…");
  try {
    const data = await registryRequest("GET");
    state.groups = data.groups || [];
    state.sources = data.sources || [];
    state.profile = data.profile || {};
    state.connected = true;
    $("#registry-editor").classList.remove("hidden");
    renderAll();
    rememberBaseline();
    $("#disconnect-registry").classList.remove("hidden");
    message("已连接。修改后点击“保存到 Registry”才会写入仓库。", "success");
  } catch (error) {
    state.connected = false;
    state.token = "";
    $("#registry-editor").classList.add("hidden");
    message(`连接失败：${error.message}`, "error");
  } finally {
    state.busy = false;
    $("#connect-registry").disabled = !state.apiUrl;
  }
}

async function saveRegistry() {
  if (!state.connected || !state.dirty || state.busy) return;
  const button = $("#save-registry");
  button.disabled = true;
  state.busy = true;
  $("#registry-editor").inert = true;
  $("#connect-registry").disabled = true;
  $("#disconnect-registry").disabled = true;
  message("正在写入 GitHub 配置…");
  try {
    const data = await registryRequest("PUT", {
      groups: state.groups,
      sources: state.sources,
      message: "chore: update information registry from admin",
    });
    if (!data.registry || !Array.isArray(data.commits)) throw new Error("服务未返回完整保存结果，请重新读取配置后核对。");
    state.groups = data.registry?.groups || state.groups;
    state.sources = data.registry?.sources || state.sources;
    renderAll();
    rememberBaseline();
    message(`保存成功。产生 ${data.commits?.length || 0} 个配置提交。`, "success");
  } catch (error) {
    message(`保存失败：${error.message}`, "error");
  } finally {
    state.busy = false;
    $("#registry-editor").inert = false;
    $("#connect-registry").disabled = false;
    $("#disconnect-registry").disabled = false;
    markDirty(state.dirty);
  }
}

function bindForms() {
  $("#connect-registry").addEventListener("click", connect);
  $("#admin-token").addEventListener("keydown", (event) => {
    if (event.key === "Enter") connect();
  });

  $("#add-group-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const name = $("#new-group-name").value.trim();
    if (!name) return;
    if (state.groups.some((group) => group.name === name)) { message("这个分组已存在。", "error"); return; }
    const maxOrder = Math.max(0, ...state.groups.map((group) => Number(group.order) || 0));
    state.groups.push({ name, order: maxOrder + 10, enabled: true });
    event.target.reset();
    renderAll();
    markDirty();
  });

  $("#add-source-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const source = {
      name: $("#new-source-name").value.trim(),
      url: $("#new-source-url").value.trim(),
      group: $("#new-source-group").value || "未分组",
      enabled: true,
      watch: $("#new-source-watch").value.split(",").map((x) => x.trim()).filter(Boolean),
      tags: $("#new-source-tags").value.split(",").map((x) => x.trim()).filter(Boolean),
      max_items: 24,
      max_detail_items: 16,
      fetch_details: true,
    };
    if (!source.name || !source.url) return;
    state.sources.push(source);
    event.target.reset();
    updateGroupSelect();
    renderSources();
    markDirty();
  });

  $("#save-registry").addEventListener("click", saveRegistry);
  $("#discard-changes").addEventListener("click", () => {
    if (!state.baseline) return;
    const saved = JSON.parse(state.baseline);
    state.groups = saved.groups;
    state.sources = saved.sources;
    renderAll();
    markDirty(false);
    message("已恢复到上次读取或保存的配置。");
  });
  $("#disconnect-registry").addEventListener("click", () => {
    if (state.dirty && !confirm("断开连接会放弃未保存的修改。继续？")) return;
    state.token = "";
    state.connected = false;
    state.baseline = null;
    state.groups = [];
    state.sources = [];
    state.profile = {};
    $("#admin-token").value = "";
    $("#registry-editor").classList.add("hidden");
    $("#disconnect-registry").classList.add("hidden");
    markDirty(false);
    message("已断开连接，当前会话凭证已清除。");
  });
  window.addEventListener("beforeunload", (event) => {
    if (state.dirty) { event.preventDefault(); event.returnValue = ""; }
  });
}

async function init() {
  bindForms();
  await loadRuntime();
}

init();
