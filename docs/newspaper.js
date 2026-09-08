(() => {
  const SECTION_DEFS = [
    { id: "front", number: "01", title: "今日总览", subtitle: "如果今天只能看三分钟，这一版必须已经足够。" },
    { id: "ai", number: "02", title: "AI Frontier", subtitle: "Frontier model、Agent、RL、Reasoning、Safety。" },
    { id: "research", number: "03", title: "科研前沿", subtitle: "真正会改变你接下来怎么做研究、怎么写、怎么投的信号。" },
    { id: "math", number: "04", title: "数学 × AI", subtitle: "AI for Mathematics、Lean、证明与重要数学进展。" },
    { id: "opportunity", number: "05", title: "机会雷达", subtitle: "Deadline、实习、Workshop、Summer School、奖学金与可行动机会。" },
    { id: "engineering", number: "06", title: "Engineering", subtitle: "开源、框架、GPU、推理基础设施与真正值得使用的新工具。" },
    { id: "business", number: "07", title: "AI 商业 / 产业", subtitle: "公司、融资、市场与可能改变 AI 发展路径的产业信号。" },
    { id: "world", number: "08", title: "世界状态", subtitle: "重大政策、国际、宏观与不应因为沉浸在 AI 中而错过的变化。" },
  ];

  const KEYWORDS = {
    ai: ["ai", "gpt", "llm", "agent", "agentic", "claude", "openai", "anthropic", "deepmind", "qwen", "gemini", "reinforcement", "reasoning", "人工智能", "大模型", "智能体", "强化学习", "推理模型"],
    research: ["research", "paper", "arxiv", "openreview", "iclr", "icml", "neurips", "conference", "workshop", "academic", "科研", "学术", "论文", "研究", "会议", "大学", "学院", "实验室", "bimsa"],
    math: ["math", "mathematics", "lean", "theorem", "proof", "geometry", "algebra", "probability", "sde", "数学", "定理", "证明", "几何", "代数", "概率", "随机微分"],
    opportunity: ["deadline", "cfp", "internship", "fellowship", "scholarship", "summer school", "winter school", "call for", "apply", "application", "招生", "报名", "截止", "实习", "奖学金", "招聘", "机会", "申请"],
    engineering: ["github", "pytorch", "cuda", "vllm", "sglang", "code", "coding", "engineering", "open source", "framework", "tool", "开源", "工程", "框架", "工具", "gpu"],
    business: ["market", "finance", "funding", "ipo", "company", "startup", "nvidia", "revenue", "earnings", "市场", "金融", "融资", "公司", "创业", "财报", "商业", "产业"],
    world: ["policy", "regulation", "government", "global", "geopolit", "china", "united states", "政策", "监管", "国际", "中美", "全球", "宏观", "政府", "世界"],
  };

  const state = {
    reports: [],
    activeReportIndex: 0,
    activePage: "front",
    payload: null,
    refreshTimer: null,
  };

  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value = "") => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  async function loadJson(path, fallback = null) {
    try {
      const joiner = path.includes("?") ? "&" : "?";
      const response = await fetch(`${path}${joiner}_=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn(`[OR Morning] failed to load ${path}`, error);
      return fallback;
    }
  }

  function flattenDigest(payload) {
    const digest = payload?.digest || {};
    const groups = Array.isArray(digest.groups) ? digest.groups : [];
    return groups.flatMap((group) => (group.highlights || []).map((item) => ({
      title: item.title || "未命名条目",
      summary: item.summary || item.why || "",
      why: item.why || "",
      action: item.action || "",
      source: item.source || "未知来源",
      url: item.url || "",
      group: group.name || "未分组",
      groupSummary: group.summary || "",
    })));
  }

  function itemHaystack(item) {
    return [item.title, item.summary, item.why, item.source, item.group, item.groupSummary]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
  }

  function matchSection(item, sectionId) {
    const words = KEYWORDS[sectionId] || [];
    const haystack = itemHaystack(item);
    return words.some((word) => haystack.includes(word));
  }

  function normalizeStructuredPages(payload) {
    const pages = payload?.newspaper?.pages;
    if (!Array.isArray(pages) || !pages.length) return null;
    const byId = new Map(pages.map((page, index) => [page.id || SECTION_DEFS[index]?.id, page]));
    return SECTION_DEFS.map((def) => {
      const page = byId.get(def.id) || {};
      const items = Array.isArray(page.items) ? page.items : [];
      return {
        ...def,
        title: page.title || def.title,
        subtitle: page.subtitle || def.subtitle,
        headline: page.headline || "",
        overview: page.overview || "",
        items,
      };
    });
  }

  function buildPages(payload) {
    const structured = normalizeStructuredPages(payload);
    if (structured) return structured;

    const items = flattenDigest(payload);
    const digest = payload?.digest || {};
    return SECTION_DEFS.map((def) => {
      if (def.id === "front") {
        return {
          ...def,
          headline: digest.headline || "世界正在发生；这是今天与你最相关的变化。",
          overview: digest.overview || "",
          items: items.slice(0, 8),
        };
      }
      return {
        ...def,
        headline: "",
        overview: "",
        items: items.filter((item) => matchSection(item, def.id)),
      };
    });
  }

  function sourceLine(item) {
    const source = escapeHtml(item?.source || "未知来源");
    if (!item?.url) return `<div class="story-source">来源：${source}</div>`;
    return `<div class="story-source">来源：<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${source} ↗</a></div>`;
  }

  function renderFrontPage(page, pages, payload) {
    const items = page.items || [];
    const lead = items[0];
    const briefs = items.slice(1, 6);
    const headline = lead?.title || page.headline || "今天没有需要占用注意力的重大更新";
    const deck = lead?.summary || page.overview || "OR 会继续监听你的信息源；没有高信号时，不用新闻填满注意力。";

    const briefHtml = briefs.length
      ? briefs.map((item, index) => `
        <article class="brief-item">
          <span class="brief-index">${index + 1}</span>
          <div class="brief-copy">
            <strong>${escapeHtml(item.title)}</strong>
            ${item.summary ? `<p>${escapeHtml(item.summary)}</p>` : ""}
          </div>
        </article>
      `).join("")
      : `<div class="paper-empty" style="min-height:260px"><div><strong>没有更多高信号更新</strong><p>这是刻意的。OR 不为了填满版面而塞入低价值信息。</p></div></div>`;

    const rundown = pages.slice(1).map((section) => {
      const first = section.items?.[0];
      return `
        <article class="rundown-card">
          <span class="rundown-no">${escapeHtml(section.number)} · ${escapeHtml(section.title)}</span>
          <strong>${escapeHtml(first?.title || "今日暂无高信号更新")}</strong>
          <p>${first ? escapeHtml(first.summary || section.subtitle) : escapeHtml(section.subtitle)}</p>
        </article>
      `;
    }).join("");

    return `
      <div class="edition-page-head">
        <div><p class="section-no">FRONT PAGE · ${escapeHtml(payload?.date || "")}</p><h2>今日总览</h2></div>
        <p>${escapeHtml(page.subtitle)}</p>
      </div>
      <div class="front-grid">
        <article class="front-lead">
          <p class="story-label">LEAD STORY</p>
          <h3>${escapeHtml(headline)}</h3>
          <p class="front-deck">${escapeHtml(deck)}</p>
          ${page.overview && page.overview !== deck ? `<p class="front-overview">${escapeHtml(page.overview)}</p>` : ""}
          ${lead?.why ? `<div class="why-you"><b>与你有关</b>${escapeHtml(lead.why)}</div>` : ""}
          ${lead ? sourceLine(lead) : ""}
        </article>
        <aside class="front-briefs">
          <h3>今日必须知道</h3>
          ${briefHtml}
        </aside>
      </div>
      <div class="front-rundown">${rundown}</div>
      <div class="newspaper-footnote">OR Morning · Web Edition · 页面会自动轮询最新日报；内容更新频率由后端抓取与编辑流程决定。</div>
    `;
  }

  function renderSectionPage(page, payload) {
    const items = page.items || [];
    if (!items.length) {
      return `
        <div class="edition-page-head">
          <div><p class="section-no">SECTION ${escapeHtml(page.number)} · ${escapeHtml(payload?.date || "")}</p><h2>${escapeHtml(page.title)}</h2></div>
          <p>${escapeHtml(page.subtitle)}</p>
        </div>
        <div class="paper-empty"><div><strong>今日无重大更新</strong><p>本版暂未发现足够重要、足够相关且来源可靠的信息。宁缺毋滥，而不是把互联网噪声重新包装给你。</p></div></div>
        <div class="newspaper-footnote">OR Morning · ${escapeHtml(page.title)} · 0 个高信号事件</div>
      `;
    }

    const lead = items[0];
    const rest = items.slice(1, 7);
    return `
      <div class="edition-page-head">
        <div><p class="section-no">SECTION ${escapeHtml(page.number)} · ${escapeHtml(payload?.date || "")}</p><h2>${escapeHtml(page.title)}</h2></div>
        <p>${escapeHtml(page.subtitle)}</p>
      </div>
      <div class="section-grid">
        <article class="section-lead">
          <p class="story-label">TOP SIGNAL</p>
          <h3>${escapeHtml(lead.title || page.headline || "今日信号")}</h3>
          <div class="story-body">${escapeHtml(lead.summary || lead.why || page.overview || "")}</div>
          ${lead.why && lead.why !== lead.summary ? `<div class="why-you"><b>与你有关</b>${escapeHtml(lead.why)}</div>` : ""}
          ${sourceLine(lead)}
          <p class="page-count">本版共筛出 ${items.length} 个高信号事件。</p>
        </article>
        <div class="section-list">
          ${rest.map((item) => `
            <article class="section-item">
              <strong>${escapeHtml(item.title)}</strong>
              ${item.summary ? `<p>${escapeHtml(item.summary)}</p>` : ""}
              ${item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">查看原文 ↗</a>` : ""}
            </article>
          `).join("") || `<div class="section-item"><strong>本版只有这一条值得占用注意力。</strong><p>低信息量不是缺陷；它意味着筛选器没有为了版面完整性降低标准。</p></div>`}
        </div>
      </div>
      <div class="newspaper-footnote">OR Morning · ${escapeHtml(page.title)} · ${items.length} 个高信号事件</div>
    `;
  }

  function renderTabs(pages) {
    const holder = $("#edition-tabs");
    if (!holder) return;
    holder.innerHTML = pages.map((page) => `
      <button class="edition-tab ${state.activePage === page.id ? "active" : ""}" type="button" data-page="${escapeHtml(page.id)}" role="tab" aria-selected="${state.activePage === page.id}">
        <b>${escapeHtml(page.number)}</b><span>${escapeHtml(page.title)}</span>
      </button>
    `).join("");

    holder.querySelectorAll("[data-page]").forEach((button) => {
      button.addEventListener("click", () => {
        state.activePage = button.dataset.page;
        renderNewspaper();
      });
    });
  }

  function renderNewspaper() {
    const viewer = $("#newspaper-viewer");
    if (!viewer || !state.payload) return;
    const pages = buildPages(state.payload);
    renderTabs(pages);
    const active = pages.find((page) => page.id === state.activePage) || pages[0];
    viewer.classList.remove("loading");
    viewer.innerHTML = active.id === "front"
      ? renderFrontPage(active, pages, state.payload)
      : renderSectionPage(active, state.payload);
  }

  async function loadReport(index, { keepPage = false } = {}) {
    const viewer = $("#newspaper-viewer");
    const report = state.reports[index];
    if (!report?.files?.json || !viewer) return;
    state.activeReportIndex = index;
    if (!keepPage) state.activePage = "front";
    viewer.classList.add("loading");
    viewer.textContent = "正在编排这一天的时报…";
    const payload = await loadJson(`./reports/${report.files.json}`, null);
    if (!payload) {
      viewer.textContent = "这份日报暂时无法读取。";
      return;
    }
    state.payload = payload;
    renderNewspaper();
  }

  function renderDateSelect() {
    const select = $("#newspaper-select");
    if (!select) return;
    select.innerHTML = "";
    if (!state.reports.length) {
      select.innerHTML = '<option value="">暂无时报</option>';
      return;
    }
    state.reports.forEach((report, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = report.date;
      select.appendChild(option);
    });
    select.value = String(state.activeReportIndex);
    select.addEventListener("change", () => loadReport(Number(select.value)));
  }

  async function init() {
    const reports = await loadJson("./data/reports.json", []);
    state.reports = Array.isArray(reports) ? reports : [];
    renderDateSelect();
    if (!state.reports.length) {
      const viewer = $("#newspaper-viewer");
      if (viewer) viewer.textContent = "今天的时报尚未生成。";
      return;
    }
    await loadReport(0);

    if (state.refreshTimer) clearInterval(state.refreshTimer);
    state.refreshTimer = setInterval(async () => {
      const latestManifest = await loadJson("./data/reports.json", []);
      if (Array.isArray(latestManifest) && latestManifest.length) {
        const previousLatest = state.reports[0]?.files?.json;
        state.reports = latestManifest;
        if (latestManifest[0]?.files?.json !== previousLatest) {
          state.activeReportIndex = 0;
          renderDateSelect();
          await loadReport(0, { keepPage: true });
          return;
        }
      }
      if (state.activeReportIndex === 0) {
        await loadReport(0, { keepPage: true });
      }
    }, 5 * 60 * 1000);
  }

  init();
})();
