const $ = (selector) => document.querySelector(selector);

const state = {
  reports: [],
  sources: [],
  localSources: JSON.parse(localStorage.getItem("oppor-radar-sources") || "[]"),
};

function escapeHtml(value = "") {
  return value
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
    if (!line.trim()) {
      closeList();
      continue;
    }
    if (line.startsWith("### ")) {
      closeList();
      html.push(`<h3>${inlineMarkdown(line.slice(4))}</h3>`);
    } else if (line.startsWith("## ")) {
      closeList();
      html.push(`<h2>${inlineMarkdown(line.slice(3))}</h2>`);
    } else if (line.startsWith("# ")) {
      closeList();
      html.push(`<h1>${inlineMarkdown(line.slice(2))}</h1>`);
    } else if (line.startsWith("- ")) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${inlineMarkdown(line.slice(2))}</li>`);
    } else {
      closeList();
      html.push(`<p>${inlineMarkdown(line)}</p>`);
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
    option.textContent = report.date;
    select.appendChild(option);
  });
  select.addEventListener("change", () => loadReport(select.value));
  loadReport(state.reports[0].filename);
}

function renderSources() {
  const list = $("#source-list");
  list.innerHTML = state.sources.map((source) => `
    <div class="source-item">
      <div>
        <strong>${escapeHtml(source.name)}</strong>
        <small>${escapeHtml(source.url)}</small>
      </div>
      <div class="tags">${(source.tags || []).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div>
    </div>
  `).join("") || "<p class='section-copy'>尚未生成来源清单。</p>";
}

function persistLocalSources() {
  localStorage.setItem("oppor-radar-sources", JSON.stringify(state.localSources));
  renderLocalSources();
}

function renderLocalSources() {
  const holder = $("#local-sources");
  holder.innerHTML = state.localSources.map((source, index) => `
    <div class="local-item">
      <div><strong>${escapeHtml(source.name)}</strong><small>${escapeHtml(source.url)}</small></div>
      <button type="button" data-remove="${index}" aria-label="删除">删除</button>
    </div>
  `).join("");
  holder.querySelectorAll("[data-remove]").forEach((button) => {
    button.addEventListener("click", () => {
      state.localSources.splice(Number(button.dataset.remove), 1);
      persistLocalSources();
    });
  });
}

function yamlString(value) {
  return JSON.stringify(String(value));
}

function exportSourcesYaml() {
  const all = [...state.sources, ...state.localSources];
  const yaml = all.map((source) => {
    const tags = (source.tags || []).map(yamlString).join(", ");
    return `- name: ${yamlString(source.name)}\n  url: ${yamlString(source.url)}\n  tags: [${tags}]`;
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
  [state.sources, state.reports] = await Promise.all([
    loadJson("./data/sources.json"),
    loadJson("./data/reports.json"),
  ]);

  $("#source-count").textContent = state.sources.length;
  $("#report-count").textContent = state.reports.length;
  $("#latest-date").textContent = state.reports[0]?.date || "—";

  renderSources();
  renderReports();
  renderLocalSources();

  $("#source-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const source = {
      name: $("#source-name").value.trim(),
      url: $("#source-url").value.trim(),
      tags: $("#source-tags").value.split(",").map((x) => x.trim()).filter(Boolean),
    };
    state.localSources.push(source);
    persistLocalSources();
    event.target.reset();
  });

  $("#export-sources").addEventListener("click", exportSourcesYaml);
}

init();
