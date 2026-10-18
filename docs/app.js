const $ = (selector) => document.querySelector(selector);

const state = {
  reports: [],
  sources: [],
  groups: [],
  status: {},
  runtime: {},
  activeGroup: "全部",
  health: [],
  healthDate: "",
  reportRequest: 0,
  sourcesReady: false,
};
const jsonRequests = new Map();

function showState(node, kind, title, copy = "", retry = null) {
  node.classList.remove("loading");
  node.setAttribute("aria-busy", String(kind === "loading"));
  node.innerHTML = `<div class="state-panel" data-state="${kind}" role="${kind === "error" ? "alert" : "status"}"><strong>${escapeHtml(title)}</strong>${copy ? `<p>${escapeHtml(copy)}</p>` : ""}${retry ? '<button class="button" type="button">重新载入</button>' : ""}</div>`;
  if (retry) node.querySelector("button").addEventListener("click", retry);
}

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
    // Newspaper and archive share in-flight reads, without caching future refreshes.
    if (!jsonRequests.has(path)) {
      const request = fetch(path, { cache: "no-store" }).then((response) => {
        if (!response.ok) throw new Error(`${response.status}`);
        return response.json();
      }).finally(() => jsonRequests.delete(path));
      jsonRequests.set(path, request);
    }
    return await jsonRequests.get(path);
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
  return `最近运行 ${new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    hour12: false, timeZone: "Asia/Shanghai",
  }).format(date)}`;
}

function renderStatus() {
  const status = state.status || {};
  $("#source-count").textContent = status.configured_sources ?? (state.sourcesReady ? state.sources.filter((s) => s.enabled !== false).length : "—");
  $("#new-count").textContent = status.new_items ?? "—";
  $("#selected-count").textContent = status.selected_items ?? "—";
  $("#healthy-count").textContent = status.healthy_sources ?? "—";
  $("#last-updated").textContent = formatUpdated(status.last_updated_at);
}

function reportDownloads(report) {
  const files = report.files || {};
  const links = [];
  if (files.md) links.push(`<a href="./reports/${escapeHtml(files.md)}" download>Markdown</a>`);
  if (files.tex) links.push(`<a href="./reports/${escapeHtml(files.tex)}" download>LaTeX</a>`);
  if (files.pdf) links.push(`<a href="./reports/${escapeHtml(files.pdf)}" download>PDF</a>`);
  return links.length ? `<div class="report-downloads" role="group" aria-label="下载本期日报"><span>下载本期</span>${links.join("")}</div>` : "";
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
        <h4>${escapeHtml(group.name || "未分组")}</h4>
        <p>${escapeHtml(group.summary || "")}</p>
      </div>
      <div class="highlight-list">
        ${(group.highlights || []).map((item) => `
          <article class="highlight-card">
            <div class="highlight-meta">${escapeHtml(item.source || "未知来源")}</div>
            <h5>${escapeHtml(item.title || "未命名条目")}</h5>
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
    <section class="digest-block"><h4>跨领域信号</h4><ul>${signals.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul></section>
  ` : "";
  const actionHtml = actions.length ? `
    <section class="digest-block action-block"><h4>今天值得做</h4><ul>${actions.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul></section>
  ` : "";

  viewer.innerHTML = `
    <div class="report-header">
      <p class="eyebrow">${escapeHtml(payload.date || report.date)}</p>
      <h3>${escapeHtml(digest.headline || "世界正在发生。")}</h3>
      <p class="report-overview">${escapeHtml(digest.overview || "今天没有需要占用注意力的新信息。")}</p>
      ${reportDownloads(report)}
    </div>
    ${groupHtml || '<div class="empty-state">今天没有值得占用注意力的新信息。</div>'}
    ${signalHtml}
    ${actionHtml}
  `;
  viewer.classList.remove("loading");
  viewer.setAttribute("aria-busy", "false");
}

async function loadReport(report) {
  const viewer = $("#report-viewer");
  const request = ++state.reportRequest;
  showState(viewer, "loading", "正在载入日报…", report?.date || "");
  const filename = report?.files?.json;
  if (!filename) {
    showState(viewer, "error", "这份日报缺少可读取的文件。", "请选择其他日期。");
    return;
  }
  const payload = await loadJson(`./reports/${filename}`, null);
  if (request !== state.reportRequest) return;
  if (!payload || payload.schema_version !== 2) {
    showState(viewer, "error", "日报暂时无法读取。", "请检查连接后重试，或选择其他日期。", () => loadReport(report));
    return;
  }
  renderDigest(report, payload);
}

function renderReports() {
  const select = $("#report-select");
  select.innerHTML = "";
  if (!state.reports.length) {
    select.innerHTML = '<option value="">暂无日报</option>';
    select.disabled = true;
    showState($("#report-viewer"), "empty", "还没有归档日报。", "生成后的日报会保存在这里。");
    return;
  }

  state.reports.forEach((report, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = report.date;
    select.appendChild(option);
  });
  select.disabled = false;
  select.onchange = () => loadReport(state.reports[Number(select.value)]);
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
    <button type="button" class="group-tab ${state.activeGroup === group ? "active" : ""}" data-group="${escapeHtml(group)}" aria-pressed="${state.activeGroup === group}">${escapeHtml(group)}</button>
  `).join("");
  holder.querySelectorAll("[data-group]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeGroup = button.dataset.group;
      holder.querySelectorAll("button").forEach((tab) => {
        tab.classList.toggle("active", tab === button);
        tab.setAttribute("aria-pressed", String(tab === button));
      });
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

  $("#source-summary").textContent = `${visible.length} 个启用来源${state.healthDate ? ` · 健康状态取自 ${state.healthDate} 日报` : " · 暂无来源健康记录"}`;
  list.innerHTML = visible.map((source) => `
    <article class="source-item">
      <div>
        <div class="source-title-row">
          <strong>${escapeHtml(source.name)}</strong>
          <span class="group-badge">${escapeHtml(source.group || "未分组")}</span>
        </div>
        <a class="source-url" href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.url)}</a>
        ${(source.watch || []).length ? `<small>重点关注：${escapeHtml(source.watch.join(" · "))}</small>` : ""}
        ${sourceHealth(source)}
      </div>
      <div class="tags">${(source.tags || []).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div>
    </article>
  `).join("") || '<div class="empty-state">这个分组还没有启用的信息源。</div>';
}

function sourceHealth(source) {
  const health = state.health.find((entry) => entry.source_url === source.url);
  if (!health) return '<span class="health">状态未记录</span>';
  const label = health.status === "healthy" ? "正常" : health.status === "error" || health.status === "failed" ? "抓取异常" : health.status;
  return `<span class="health" data-status="${escapeHtml(health.status)}">最近抓取：${escapeHtml(label)}${Number.isFinite(health.discovered_items) ? ` · 发现 ${health.discovered_items} 条` : ""}</span>`;
}

function updateLatestStatus(payload) {
  const health = payload?.diagnostics?.source_health || [];
  const changed = JSON.stringify(health) !== JSON.stringify(state.health) || (health.length && state.healthDate !== payload.date);
  state.health = health;
  state.healthDate = state.health.length ? payload.date : "";
  if (payload.metrics) state.status = payload.metrics;
  renderStatus();
  if (state.sourcesReady && changed) renderSources();
}

function renderRuntimeFeatures() {
  if (state.runtime?.registry_api_url) {
    $("#registry-admin-button")?.classList.remove("hidden");
  }
}

async function init() {
  startLiveClock();
  const compact = window.matchMedia("(max-width: 600px)");
  $("#run-status").open = !compact.matches;
  compact.addEventListener("change", (event) => { $("#run-status").open = !event.matches; });
  [state.sources, state.groups, state.reports, state.status, state.runtime] = await Promise.all([
    loadJson("./data/sources.json", null),
    loadJson("./data/groups.json", []),
    loadJson("./data/reports.json", null),
    loadJson("./data/status.json", {}),
    loadJson("./data/runtime.json", {}),
  ]);

  const sourcesFailed = !Array.isArray(state.sources);
  state.sourcesReady = !sourcesFailed;
  const reportsFailed = !Array.isArray(state.reports);
  state.sources = Array.isArray(state.sources) ? state.sources : [];
  state.reports = Array.isArray(state.reports) ? state.reports : [];
  state.groups = Array.isArray(state.groups) ? state.groups : [];
  renderStatus();
  if (reportsFailed) {
    $("#report-select").innerHTML = '<option>载入失败</option>';
    $("#report-select").disabled = true;
    showState($("#report-viewer"), "error", "无法载入日报目录。", "请检查连接后重试。", () => location.reload());
  } else renderReports();
  renderGroupTabs();
  if (sourcesFailed) {
    $("#source-summary").textContent = "信息源尚未载入，暂时无法筛选。";
    document.querySelectorAll("#source-groups button").forEach((button) => { button.disabled = true; });
    showState($("#source-list"), "error", "无法载入信息源。", "请检查连接后重试。", () => location.reload());
  }
  else renderSources();
  renderRuntimeFeatures();
}

// Keep location and keyboard focus visible without replacing navigation nodes.
const navigation = [...document.querySelectorAll('nav a[href^="#"]')];
const setCurrent = (id) => navigation.forEach((link) => {
  if (link.hash === `#${id}`) link.setAttribute("aria-current", "location");
  else link.removeAttribute("aria-current");
});
navigation.forEach((link) => link.addEventListener("click", () => setCurrent(link.hash.slice(1))));
const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => { if (entry.isIntersecting) setCurrent(entry.target.id); });
}, { rootMargin: "-15% 0px -65% 0px" });
document.querySelectorAll("main > section[id]").forEach((section) => observer.observe(section));
init();
