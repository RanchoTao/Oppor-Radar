(() => {
  const SECTION_DEFS = [
    { id: "front", number: "01", title: "今日总览", subtitle: "如果今天只能看三分钟，这一版必须已经足够。" },
    { id: "opportunity", number: "02", title: "机会雷达", subtitle: "北京、全国与线上真正可报名的 Hackathon、竞赛、科研招募、实习、Workshop 与截止。" },
    { id: "research", number: "03", title: "科研前沿", subtitle: "真正会改变你接下来怎么做研究、怎么写、怎么投的信号。" },
    { id: "ai", number: "04", title: "AI Frontier", subtitle: "Frontier model、Agent、RL、Reasoning、Safety。" },
    { id: "math", number: "05", title: "数学 × AI", subtitle: "AI for Mathematics、Lean、证明与重要数学进展。" },
    { id: "engineering", number: "06", title: "Engineering", subtitle: "开源、框架、GPU、推理基础设施与真正值得使用的新工具。" },
    { id: "business", number: "07", title: "AI 商业 / 产业", subtitle: "公司、融资、市场与可能改变 AI 发展路径的产业信号。" },
    { id: "world", number: "08", title: "世界状态", subtitle: "重大政策、国际、宏观与不应因为沉浸在 AI 中而错过的变化。" },
  ];

  const KEYWORDS = {
    ai: ["ai", "gpt", "llm", "agent", "agentic", "claude", "openai", "anthropic", "deepmind", "qwen", "gemini", "reinforcement", "reasoning", "人工智能", "大模型", "智能体", "强化学习", "推理模型"],
    research: ["research", "paper", "arxiv", "openreview", "iclr", "icml", "neurips", "conference", "workshop", "academic", "科研", "学术", "论文", "研究", "会议", "大学", "学院", "实验室", "bimsa"],
    math: ["math", "mathematics", "lean", "theorem", "proof", "geometry", "algebra", "probability", "sde", "数学", "定理", "证明", "几何", "代数", "概率", "随机微分"],
    opportunity: ["deadline", "cfp", "internship", "fellowship", "scholarship", "summer school", "winter school", "call for", "apply", "application", "hackathon", "competition", "contest", "meetup", "招生", "报名", "截止", "实习", "奖学金", "招聘", "机会", "申请", "黑客松", "竞赛", "比赛", "挑战赛", "活动", "招募", "本科生", "开发者"],
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
    requestId: 0,
  };

  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value = "") => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  // loadJson and showState are shared with app.js, loaded immediately before this file.

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
      locality: item.locality || "",
      group: group.name || "未分组",
      groupSummary: group.summary || "",
    })));
  }

  function itemHaystack(item) {
    return [item.title, item.summary, item.why, item.source, item.locality, item.group, item.groupSummary]
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
          headline: digest.headline || "先看今天能行动的机会，再看世界发生了什么。",
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
    const locality = item?.locality ? `<span class="locality">参与范围 · ${escapeHtml(item.locality)}</span>` : "";
    if (!item?.url) return `<div class="story-source">来源：${source}${locality}</div>`;
    return `<div class="story-source">来源：<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${source} ↗</a>${locality}</div>`;
  }

  // Only change presentation: every character remains available in the disclosure.
  function summaryText(value, limit = 180) {
    const text = String(value || "");
    if (!text) return "";
    let split = limit;
    if (text.length > limit && /[a-zA-Z]/.test(text[limit])) {
      const space = text.lastIndexOf(" ", limit);
      if (space > limit / 2) split = space;
    }
    const more = text.length > limit;
    return `<div class="story-summary"><p>${escapeHtml(more ? text.slice(0, split) : text)}${more ? '<span aria-hidden="true">…</span>' : ""}</p>${more ? `<details><summary>继续阅读摘要</summary><p>${escapeHtml(text.slice(split))}</p></details>` : ""}</div>`;
  }

  function headlineText(value) {
    const title = String(value || "今日信号");
    return `<h3${title.length > 100 ? ' class="long-headline"' : ""}>${escapeHtml(title)}</h3>`;
  }

  function activatePage(id, focus = true) {
    state.activePage = id;
    renderNewspaper();
    const button = document.getElementById(`tab-${id}`);
    if (focus && button) {
      button.focus({ preventScroll: true });
      button.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "instant" });
    }
  }

  function renderFrontPage(page, pages, payload) {
    const items = page.items || [];
    const lead = items[0];
    const briefs = items.slice(1, 4);
    const headline = lead?.title || page.headline || "今天没有需要占用注意力的重大更新";
    const deck = lead?.summary || page.overview || "OR 会继续监听你的信息源；没有高信号时，不用新闻填满注意力。";

    const briefHtml = briefs.length
      ? briefs.map((item, index) => `
        <article class="brief-item">
          <span class="brief-index">${index + 1}</span>
          <div class="brief-copy">
            <strong>${escapeHtml(item.title)}</strong>
            ${summaryText(item.summary, 100)}
            ${sourceLine(item)}
          </div>
        </article>
      `).join("")
      : `<div class="paper-empty" style="min-height:180px"><div><strong>没有更多高信号更新</strong><p>这是刻意的。OR 不为了填满版面而塞入低价值信息。</p></div></div>`;

    const rundown = pages.slice(1).map((section) => {
      const first = section.items?.[0];
      return `
        <article class="rundown-card">
          <button class="rundown-link" type="button" data-open-page="${section.id}">${escapeHtml(section.number)} · ${escapeHtml(section.title)}<span aria-hidden="true">→</span></button>
          <strong>${escapeHtml(first?.title || "今日暂无高信号更新")}</strong>
          <p>${section.items.length} 条收录${first?.source ? ` · ${escapeHtml(first.source)}` : ""}</p>
        </article>
      `;
    }).join("");

    return `
      <div class="edition-page-head front-page-head">
        <div><p class="section-no">FRONT PAGE · ${escapeHtml(payload?.date || "")}</p><h2>今日总览</h2></div>
        <p>先看机会，再看世界。</p>
      </div>
      <div class="front-grid">
        <article class="front-lead">
          <p class="story-label">今日头条 / LEAD STORY</p>
          ${lead && headline.length > 100 ? sourceLine(lead) : ""}
          ${headlineText(headline)}
          ${lead && headline.length <= 100 ? sourceLine(lead) : ""}
          ${summaryText(deck)}
          ${lead?.why ? `<div class="why-you"><b>与你有关</b>${escapeHtml(lead.why)}</div>` : ""}
          ${lead?.action && lead.action !== "仅供了解" ? `<div class="why-you action"><b>下一步</b>${escapeHtml(lead.action)}</div>` : ""}
        </article>
        <aside class="front-briefs">
          <h3>同时值得关注 / THE BRIEF</h3>
          ${briefHtml}
        </aside>
      </div>
      <div class="front-rundown">${rundown}</div>
      <div class="newspaper-footnote"><span>OR Morning · ${escapeHtml(payload?.date || "")}</span><span>每 5 分钟检查更新 · 以原始出处为准</span></div>
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
    const rest = items.slice(1);
    return `
      <div class="edition-page-head">
        <div><p class="section-no">SECTION ${escapeHtml(page.number)} · ${escapeHtml(payload?.date || "")}</p><h2>${escapeHtml(page.title)}</h2></div>
        <p>${escapeHtml(page.subtitle)}</p>
      </div>
      <div class="section-grid">
        <article class="section-lead">
          <p class="story-label">${page.id === "opportunity" ? "重点机会 / TOP ACTION" : "本版焦点 / TOP SIGNAL"}</p>
          ${(lead.title || page.headline || "").length > 100 ? sourceLine(lead) : ""}
          ${headlineText(lead.title || page.headline)}
          ${(lead.title || page.headline || "").length <= 100 ? sourceLine(lead) : ""}
          ${summaryText(lead.summary || lead.why || page.overview)}
          ${lead.why && lead.why !== lead.summary ? `<div class="why-you"><b>与你有关</b>${escapeHtml(lead.why)}</div>` : ""}
          ${lead.action && lead.action !== "仅供了解" ? `<div class="why-you action"><b>下一步</b>${escapeHtml(lead.action)}</div>` : ""}
          <p class="page-count">本版共筛出 ${items.length} 个高信号事件。</p>
        </article>
        <div class="section-list">
          ${rest.map((item) => `
            <article class="section-item">
              <strong>${escapeHtml(item.title)}</strong>
              ${summaryText(item.summary, 150)}
              ${item.why && item.why !== item.summary ? `<p><b>与你有关：</b>${escapeHtml(item.why)}</p>` : ""}
              ${item.action && item.action !== "仅供了解" ? `<p><b>下一步：</b>${escapeHtml(item.action)}</p>` : ""}
              ${item.locality ? `<p>${escapeHtml(item.locality)}</p>` : ""}
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
    $(".tab-hint").classList.remove("hidden");
    holder.innerHTML = pages.map((page) => `
      <button id="tab-${escapeHtml(page.id)}" class="edition-tab ${state.activePage === page.id ? "active" : ""}" type="button" data-page="${escapeHtml(page.id)}" role="tab" aria-controls="newspaper-viewer" tabindex="${state.activePage === page.id ? 0 : -1}" aria-selected="${state.activePage === page.id}">
        <b>${escapeHtml(page.number)}</b><span>${escapeHtml(page.title)}</span>
      </button>
    `).join("");

    holder.querySelectorAll("[data-page]").forEach((button, index) => {
      button.addEventListener("click", () => activatePage(button.dataset.page));
      button.addEventListener("keydown", (event) => {
        let next;
        if (event.key === "ArrowRight") next = (index + 1) % pages.length;
        if (event.key === "ArrowLeft") next = (index - 1 + pages.length) % pages.length;
        if (event.key === "Home") next = 0;
        if (event.key === "End") next = pages.length - 1;
        if (next !== undefined) { event.preventDefault(); activatePage(pages[next].id); }
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
    viewer.setAttribute("aria-busy", "false");
    viewer.setAttribute("aria-labelledby", `tab-${active.id}`);
    viewer.innerHTML = active.id === "front"
      ? renderFrontPage(active, pages, state.payload)
      : renderSectionPage(active, state.payload);
    viewer.querySelectorAll("[data-open-page]").forEach((button) => {
      button.addEventListener("click", () => activatePage(button.dataset.openPage));
    });
    renderEditionNotice();
  }

  function renderEditionNotice() {
    const notice = $("#edition-notice");
    const fallback = state.payload.diagnostics?.newspaper_editor?.used === false;
    notice.classList.toggle("hidden", !fallback);
    notice.innerHTML = fallback ? "<summary>规则筛选版 · 阅读说明</summary><p>本期使用规则筛选，摘要可能包含原文片段。行动前请核对原始出处。</p>" : "";
    $("#edition-state").textContent = state.activeReportIndex === 0 ? "最新一期" : "历史归档";
  }

  async function loadReport(index, { keepPage = false } = {}) {
    const viewer = $("#newspaper-viewer");
    const report = state.reports[index];
    if (!report?.files?.json || !viewer) return;
    const requestId = ++state.requestId;
    state.activeReportIndex = index;
    if (!keepPage) state.activePage = "front";
    if (!keepPage) {
      $("#edition-state").textContent = "载入中";
      $("#edition-tabs").innerHTML = "";
      $(".tab-hint").classList.add("hidden");
      viewer.removeAttribute("aria-labelledby");
      $("#edition-notice").classList.add("hidden");
      showState(viewer, "loading", "正在载入这一天的时报…", report.date);
    }
    const payload = await loadJson(`./reports/${report.files.json}`, null);
    if (requestId !== state.requestId) return;
    if (!payload || payload.schema_version !== 2) {
      if (keepPage && state.payload) {
        $("#edition-notice").innerHTML = "<summary>自动更新暂时失败</summary><p>继续显示上次成功载入的内容，将在下次自动检查时重试。</p>";
        $("#edition-notice").classList.remove("hidden");
      } else {
        $("#edition-state").textContent = "读取失败";
        showState(viewer, "error", "这份时报暂时无法读取。", "请检查连接后重试，或选择其他日期。", () => loadReport(index));
      }
      return;
    }
    if (state.activeReportIndex === 0) updateLatestStatus(payload);
    if (keepPage && JSON.stringify(payload) === JSON.stringify(state.payload)) {
      renderEditionNotice();
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
      select.disabled = true;
      return;
    }
    state.reports.forEach((report, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = report.date;
      select.appendChild(option);
    });
    select.value = String(state.activeReportIndex);
    select.disabled = false;
    select.onchange = () => loadReport(Number(select.value));
  }

  async function init() {
    const reports = await loadJson("./data/reports.json", null);
    state.reports = Array.isArray(reports) ? reports : [];
    renderDateSelect();
    if (!state.reports.length) {
      const viewer = $("#newspaper-viewer");
      $(".tab-hint").classList.add("hidden");
      if (reports === null) $("#newspaper-select").innerHTML = '<option>目录读取失败</option>';
      if (viewer) showState(viewer, reports === null ? "error" : "empty", reports === null ? "无法载入时报目录。" : "时报尚未生成。", reports === null ? "请检查连接后重试。" : "下一份日报生成后，这里会自动更新。", reports === null ? init : null);
      $("#edition-state").textContent = reports === null ? "连接失败" : "等待新刊";
    } else {
      await loadReport(0);
    }

    if (state.refreshTimer) clearInterval(state.refreshTimer);
    state.refreshTimer = setInterval(async () => {
      const latestManifest = await loadJson("./data/reports.json", []);
      if (Array.isArray(latestManifest) && latestManifest.length) {
        const previousLatest = state.reports[0]?.files?.json;
        const selectedFile = state.reports[state.activeReportIndex]?.files?.json;
        const followingLatest = state.activeReportIndex === 0;
        state.reports = latestManifest;
        if (latestManifest[0]?.files?.json !== previousLatest) {
          const previousIndex = latestManifest.findIndex((report) => report.files?.json === selectedFile);
          state.activeReportIndex = followingLatest || previousIndex < 0 ? 0 : previousIndex;
          renderDateSelect();
          if (state.activeReportIndex === 0) await loadReport(0, { keepPage: true });
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
