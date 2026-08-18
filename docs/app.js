const $ = (selector) => document.querySelector(selector);

const state = {
  reports: [],
  sources: [],
  groups: [],
  status: {},
  runtime: {},
  activeGroup: "全部",
};

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function loadJson(path, fallback = null) {
  try {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) throw new Error(`${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn(`Failed to load ${path}`, error);
    return fallback;
  }
}

function startLiveClock() {
  const formatter = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Asia/Shanghai",
    timeZoneName: "short",
  });
  const tick = () => { $("#live-time").textContent = formatter.format(new Date()); };
  tick();
  setInterval(tick, 1000);
}

function formatUpdated(value) {
  if (!value) return "尚无更新记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `最后更新 ${new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    hour12: false, timeZone: "Asia/Shanghai",
  }).format(date)}`;
}

function renderStatus() {
  const status = state.status || {};
  $("#source-count").textContent = status.configured_sources ?? state.sources.filter((s) => s.enabled !== false).length;
  $("#new-count").textContent = status.new_items ?? 0;
  $("#selected-count").textContent = status.selected_items ?? 0;
  $("#healthy-count").textContent = status.healthy_sources ?? "—";
  $("#last-updated").textContent = formatUpdated(status.last_updated_at);
}

function reportDownloads(report) {
  const files = report.files || {};
  const links = [];
  if (files.md) links.push(`<a href="./reports/${escapeHtml(files.md)}">Markdown</a>`);
  if (files.tex) links.push(`<a href="./reports/${escapeHtml(files.tex)}">LaTeX</a>`);
  if (files.pdf) links.push(`<a href="./reports/${escapeHtml(files.pdf)}">PDF</a>`);
  return links.length ? `<div class="report-downloads">${links.join("<span>·</span>")}</div>` : "";
}

function renderDigest(report, payload) {
  const viewer = $("#report-viewer");
  const digest = payload?.digest || {};
  const groups = digest.groups || [];
  const signals = digest.cross_group_signals || [];
  const actions = digest.action_items || [];

  const groupHtml = groups.map((group) => `
    <section class="digest-group">
      <div class="digest-group-heading">
        <h2>${escapeHtml(group.name || "未分组")}</h2>
        <p>${escapeHtml(group.summary || "")}</p>
      </div>
      <div class="highlight-list">
        ${(group.highlights || []).map((item) => `
          <article class="highlight-card">
            <div class="highlight-meta">${escapeHtml(item.source || "未知来源")}</div>
            <h3>${escapeHtml(item.title || "未命名条目")}</h3>
            ${item.why ? `<p>${escapeHtml(item.why)}</p>` : ""}
            <div class="highlight-footer">
              ${item.action && item.action !== "仅供了解" ? `<span class="action-chip">${escapeHtml(item.action)}</span>` : "<span></span>"}
              ${item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">原文 ↗</a>` : ""}
            </div>
          </article>
        `).join("")}
      </div>
    </section>
  `).join("");

  const signalHtml = signals.length ? `
    <section class="digest-block"><h2>跨领域信号</h2><ul>${signals.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul></section>
  ` : "";
  const actionHtml = actions.length ? `
    <section class="digest-block action-block"><h2>今天值得做</h2><ul>${actions.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul></section>
  ` : "";

  viewer.innerHTML = `
    <div class="report-header">
      <p class="eyebrow">${escapeHtml(payload.date || report.date)}</p>
      <h1>${escapeHtml(digest.headline || "世界正在发生。")}</h1>
      <p class="report-overview">${escapeHtml(digest.overview || "今天没有需要占用注意力的新信息。")}</p>
      ${reportDownloads(report)}
    </div>
    ${groupHtml || '<div class="empty-state">今天没有值得占用注意力的新信息。</div>'}
    ${signalHtml}
    ${actionHtml}
  `;
  viewer.classList.remove("loading");
}

async function loadReport(report) {
  const viewer = $("#report-viewer");
  viewer.classList.add("loading");
  viewer.textContent = "正在载入日报…";
  const filename = report?.files?.json;
  if (!filename) {
    viewer.textContent = "这份日报暂时无法读取。";
    return;
  }
  const payload = await loadJson(`./reports/${filename}`, null);
  if (!payload || payload.schema_version !== 2) {
    viewer.textContent = "日报暂时无法读取。";
    return;
  }
  renderDigest(report, payload);
}

function renderReports() {
  const select = $("#report-select");
  select.innerHTML = "";
  if (!state.reports.length) {
    select.innerHTML = '<option value="">暂无日报</option>';
    $("#report-viewer").textContent = "今天的日报尚未生成。";
    return;
  }

  state.reports.forEach((report, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = report.date;
    select.appendChild(option);
  });
  select.addEventListener("change", () => loadReport(state.reports[Number(select.value)]));
  loadReport(state.reports[0]);
}

function groupNames() {
  const configured = state.groups
    .filter((group) => group.enabled !== false)
    .sort((a, b) => (a.order || 0) - (b.order || 0))
    .map((group) => group.name);
  const fromSources = state.sources.map((source) => source.group || "未分组");
  return [...new Set([...configured, ...fromSources])];
}

function renderGroupTabs() {
  const holder = $("#source-groups");
  holder.innerHTML = ["全部", ...groupNames()].map((group) => `
    <button type="button" class="group-tab ${state.activeGroup === group ? "active" : ""}" data-group="${escapeHtml(group)}">${escapeHtml(group)}</button>
  `).join("");
  holder.querySelectorAll("[data-group]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeGroup = button.dataset.group;
      renderGroupTabs();
      renderSources();
    });
  });
}

function renderSources() {
  const list = $("#source-list");
  const enabled = state.sources.filter((source) => source.enabled !== false);
  const visible = state.activeGroup === "全部"
    ? enabled
    : enabled.filter((source) => (source.group || "未分组") === state.activeGroup);

  list.innerHTML = visible.map((source) => `
    <article class="source-item">
      <div>
        <div class="source-title-row">
          <strong>${escapeHtml(source.name)}</strong>
          <span class="group-badge">${escapeHtml(source.group || "未分组")}</span>
        </div>
        <a class="source-url" href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.url)}</a>
        ${(source.watch || []).length ? `<small>重点关注：${escapeHtml(source.watch.join(" · "))}</small>` : ""}
      </div>
      <div class="tags">${(source.tags || []).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div>
    </article>
  `).join("") || '<div class="empty-state">这个分组还没有启用的信息源。</div>';
}

function renderRuntimeFeatures() {
  if (state.runtime?.registry_api_url) {
    $("#registry-admin-button")?.classList.remove("hidden");
  }
}

async function init() {
  startLiveClock();
  [state.sources, state.groups, state.reports, state.status, state.runtime] = await Promise.all([
    loadJson("./data/sources.json", []),
    loadJson("./data/groups.json", []),
    loadJson("./data/reports.json", []),
    loadJson("./data/status.json", {}),
    loadJson("./data/runtime.json", {}),
  ]);

  renderStatus();
  renderReports();
  renderGroupTabs();
  renderSources();
  renderRuntimeFeatures();
}

init();
