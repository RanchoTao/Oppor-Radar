const $ = (selector) => document.querySelector(selector);

const savedGroups = localStorage.getItem("oppor-radar-groups");
const state = {
  reports: [],
  sources: [],
  localSources: JSON.parse(localStorage.getItem("oppor-radar-sources") || "[]"),
  localGroups: savedGroups ? JSON.parse(savedGroups) : ["金融", "社会"],
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

function inlineMarkdown(text) {
  const escaped = escapeHtml(text);
  return escaped
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noreferrer">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function renderMarkdown(markdown) {
  const lines = markdown.split(/\r?\n/);
  const html = [];
  let inList = false;

  const closeList = () => {
    if (inList) html.push("</ul>");
    inList = false;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const content = line.trimStart();
    if (!content) {
      closeList();
      continue;
    }
    if (content.startsWith("> ")) {
      closeList();
      html.push(`<blockquote>${inlineMarkdown(content.slice(2))}</blockquote>`);
    } else if (content.startsWith("### ")) {
      closeList();
      html.push(`<h3>${inlineMarkdown(content.slice(4))}</h3>`);
    } else if (content.startsWith("## ")) {
      closeList();
      html.push(`<h2>${inlineMarkdown(content.slice(3))}</h2>`);
    } else if (content.startsWith("# ")) {
      closeList();
      html.push(`<h1>${inlineMarkdown(content.slice(2))}</h1>`);
    } else if (content.startsWith("- ")) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${inlineMarkdown(content.slice(2))}</li>`);
    } else {
      closeList();
      html.push(`<p>${inlineMarkdown(content)}</p>`);
    }
  }
  closeList();
  return html.join("\n");
}

async function loadJson(path, fallback = []) {
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
    timeZoneName: "short",
  });
  const tick = () => {
    $("#live-time").textContent = formatter.format(new Date());
  };
  tick();
  setInterval(tick, 1000);
}

async function loadReport(filename) {
  const viewer = $("#report-viewer");
  viewer.classList.add("loading");
  viewer.textContent = "正在载入日报…";
  try {
    const response = await fetch(`./reports/${filename}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`${response.status}`);
    viewer.innerHTML = renderMarkdown(await response.text());
    viewer.classList.remove("loading");
  } catch (error) {
    viewer.textContent = "日报暂时无法载入。请检查 docs/reports 是否已由每日任务生成。";
  }
}

async function updateLatestLlmStatus() {
  const latest = state.reports[0];
  if (!latest?.json_filename) {
    $("#llm-status").textContent = "待首次运行";
    return;
  }
  const data = await loadJson(`./reports/${latest.json_filename}`, null);
  const llm = data?.digest?.llm;
  if (!llm) {
    $("#llm-status").textContent = "未知";
  } else if (llm.used) {
    $("#llm-status").textContent = llm.model || "DeepSeek";
  } else {
    $("#llm-status").textContent = "规则回退";
  }
}

function renderReports() {
  const select = $("#report-select");
  select.innerHTML = "";
  if (!state.reports.length) {
    select.innerHTML = '<option value="">暂无日报</option>';
    $("#report-viewer").textContent = "当前还没有可展示的日报。";
    return;
  }

  state.reports.forEach((report) => {
    const option = document.createElement("option");
    option.value = report.filename;
    option.textContent = `${report.date}${report.format === "legacy-v1" ? " · legacy" : ""}`;
    select.appendChild(option);
  });
  select.addEventListener("change", () => loadReport(select.value));
  loadReport(state.reports[0].filename);
}

function allGroups() {
  const groups = new Set(["未分组"]);
  state.sources.forEach((source) => groups.add(source.group || "未分组"));
  state.localGroups.forEach((group) => groups.add(group));
  state.localSources.forEach((source) => groups.add(source.group || "未分组"));
  return [...groups].filter(Boolean);
}

function renderGroupTabs() {
  const groups = allGroups();
  const holder = $("#source-groups");
  holder.innerHTML = ["全部", ...groups].map((group) => `
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
  const all = [
    ...state.sources.map((source) => ({ ...source, local: false })),
    ...state.localSources.map((source) => ({ ...source, local: true })),
  ];
  const visible = state.activeGroup === "全部"
    ? all
    : all.filter((source) => (source.group || "未分组") === state.activeGroup);

  list.innerHTML = visible.map((source) => `
    <div class="source-item">
      <div>
        <div class="source-title-row"><strong>${escapeHtml(source.name)}</strong><span class="group-badge">${escapeHtml(source.group || "未分组")}</span></div>
        <small>${escapeHtml(source.url)}</small>
        ${(source.watch || []).length ? `<small>关注：${escapeHtml(source.watch.join(" · "))}</small>` : ""}
      </div>
      <div class="tags">${(source.tags || []).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div>
    </div>
  `).join("") || "<p class='section-copy'>这个分组还没有信息源。</p>";
}

function persistLocalState() {
  localStorage.setItem("oppor-radar-sources", JSON.stringify(state.localSources));
  localStorage.setItem("oppor-radar-groups", JSON.stringify(state.localGroups));
  renderLocalGroups();
  renderLocalSources();
  renderGroupTabs();
  renderSources();
  updateGroupSelect();
}

function renderLocalGroups() {
  const holder = $("#local-groups");
  holder.innerHTML = state.localGroups.map((group, index) => `
    <span class="editable-group">${escapeHtml(group)}<button type="button" data-remove-group="${index}" aria-label="删除 ${escapeHtml(group)}">×</button></span>
  `).join("") || "<small class='muted'>尚未添加自定义分组。</small>";

  holder.querySelectorAll("[data-remove-group]").forEach((button) => {
    button.addEventListener("click", () => {
      const group = state.localGroups[Number(button.dataset.removeGroup)];
      state.localGroups.splice(Number(button.dataset.removeGroup), 1);
      state.localSources.forEach((source) => {
        if (source.group === group) source.group = "未分组";
      });
      if (state.activeGroup === group) state.activeGroup = "全部";
      persistLocalState();
    });
  });
}

function renderLocalSources() {
  const holder = $("#local-sources");
  holder.innerHTML = state.localSources.map((source, index) => `
    <div class="local-item">
      <div><strong>${escapeHtml(source.name)}</strong><small>${escapeHtml(source.group || "未分组")} · ${escapeHtml(source.url)}</small></div>
      <button type="button" data-remove="${index}" aria-label="删除">删除</button>
    </div>
  `).join("");
  holder.querySelectorAll("[data-remove]").forEach((button) => {
    button.addEventListener("click", () => {
      state.localSources.splice(Number(button.dataset.remove), 1);
      persistLocalState();
    });
  });
}

function updateGroupSelect() {
  const select = $("#source-group");
  const current = select.value;
  select.innerHTML = allGroups().map((group) => `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`).join("");
  if ([...select.options].some((option) => option.value === current)) select.value = current;
}

function yamlString(value) {
  return JSON.stringify(String(value));
}

function exportSourcesYaml() {
  const all = [...state.sources, ...state.localSources];
  const yaml = all.map((source) => {
    const tags = (source.tags || []).map(yamlString).join(", ");
    const watch = (source.watch || []).map(yamlString).join(", ");
    return [
      `- name: ${yamlString(source.name)}`,
      `  url: ${yamlString(source.url)}`,
      `  group: ${yamlString(source.group || "未分组")}`,
      `  tags: [${tags}]`,
      `  watch: [${watch}]`,
      `  max_items: ${source.max_items || 30}`,
    ].join("\n");
  }).join("\n\n") + "\n";
  const blob = new Blob([yaml], { type: "text/yaml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "sources.yaml";
  link.click();
  URL.revokeObjectURL(url);
}

async function init() {
  startLiveClock();
  [state.sources, state.reports] = await Promise.all([
    loadJson("./data/sources.json"),
    loadJson("./data/reports.json"),
  ]);

  $("#source-count").textContent = state.sources.length + state.localSources.length;
  $("#report-count").textContent = state.reports.length;

  renderGroupTabs();
  renderSources();
  renderReports();
  renderLocalGroups();
  renderLocalSources();
  updateGroupSelect();
  updateLatestLlmStatus();

  $("#group-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const group = $("#group-name").value.trim();
    if (group && !allGroups().includes(group)) state.localGroups.push(group);
    event.target.reset();
    persistLocalState();
  });

  $("#source-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const source = {
      name: $("#source-name").value.trim(),
      url: $("#source-url").value.trim(),
      group: $("#source-group").value || "未分组",
      watch: $("#source-watch").value.split(",").map((x) => x.trim()).filter(Boolean),
      tags: $("#source-tags").value.split(",").map((x) => x.trim()).filter(Boolean),
      max_items: 30,
    };
    state.localSources.push(source);
    event.target.reset();
    persistLocalState();
  });

  $("#export-sources").addEventListener("click", exportSourcesYaml);
}

init();
