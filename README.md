# Opportunity Radar

Opportunity Radar 是一个 **个人信息雷达**：你主动选择并分组几十到上百个信息源，系统按日扫描新内容和内容变化，再把候选信息统一交给大模型做筛选、压缩、关联和排序，最终只留下真正值得你看的内容，生成一份个性化日报。

它不再局限于“夏令营 / RA / 申请机会”。信息源可以属于学术、AI / 科技、金融、社会 / 政策、个人博客、公司公告或任何你自己定义的领域。

## 当前数据链路

```text
Source Registry + User Profile
            ↓
      RSS / Atom 优先
            ↓
       HTML 内容发现
            ↓
        详情页正文提取
            ↓
   URL 去重 + Content Hash
            ↓
    New / Changed Information
            ↓
   DeepSeek Level 1: Item Intelligence
            ↓
       Relevant Information
            ↓
   DeepSeek Level 2: Daily Editor
            ↓
       Structured JSON (source of truth)
        ├── Web
        ├── Markdown
        └── LaTeX
```

## 核心设计

### Source Registry

`config/sources.yaml` 是信息源注册表。每个来源支持：

- `group`：归属信息域
- `enabled`：是否启用
- `tags`：描述来源本身
- `watch`：可选的低成本前置关键词过滤；为空时交给后续智能层判断
- `max_items`：每次最多发现多少候选链接
- `max_detail_items`：最多深入抓取多少详情页
- `fetch_details`：是否进入详情页读取正文

示例：

```yaml
- name: Example Macro Source
  url: https://example.com/macro/
  group: 金融
  enabled: true
  tags: [宏观, 官方]
  watch: [央行, 利率, 通胀]
  max_items: 24
  max_detail_items: 16
  fetch_details: true
```

### Groups

`config/groups.yaml` 定义信息域。默认包含学术、AI / 科技、金融、社会 / 政策，可以增加、删除、重命名和排序。

### User Profile

`config/profile.yaml` 描述“我长期关心什么”，避免把所有兴趣重复写到每个来源里。

```text
Source = 世界告诉我什么
Profile = 我关心什么
```

大模型负责在二者交集里分配注意力。

## 抓取层

当前 crawler 会：

1. 获取来源主页。
2. 优先发现并解析 RSS / Atom。
3. 没有可用 feed 时，从 HTML 中发现内容型链接。
4. 对候选链接进入详情页，提取正文。
5. 计算正文 `content_hash`。
6. 只有新 URL 或正文发生实质变化时，才进入本次智能处理。

URL 是有 URL 条目的主身份键；只有 URL 缺失时，才使用 `title + source_name` 作为 fallback。这避免同一来源不同页面使用相同标题时发生冲突。

当前仍以静态 HTML 为主，不执行浏览器 JavaScript。动态渲染站点后续需要单独的 browser worker。

## DeepSeek 两级智能层

### Level 1: Item Intelligence

逐批判断每条新信息是否值得进入日报，并输出：

```json
{
  "keep": true,
  "summary": "核心事实摘要",
  "topics": ["..."],
  "importance": 0.8,
  "relevance": 0.9,
  "novelty": 0.7,
  "reason": "为什么值得用户看",
  "action": "需要做什么；没有则仅供了解",
  "time_sensitive": false
}
```

### Level 2: Daily Editor

再把通过筛选的条目整体编辑成日报：合并重复事件、按分组形成摘要、发现可靠的跨领域信号、只保留真正需要行动的事项，并控制最终长度。

DeepSeek 不可用时使用确定性 fallback，保证定时任务仍能产出；模型调用诊断只写入 JSON `diagnostics`，不展示在产品首页。

## 报告数据

每日产物：

```text
data/reports/YYYY-MM-DD.json   # 主数据
 data/reports/YYYY-MM-DD.md    # 可读文本
 data/reports/YYYY-MM-DD.tex   # LaTeX 视图
```

JSON 使用 `schema_version: 2`。Pages 只发布 v2 日报，旧版 A/B/C/X 申请清单不会继续出现在产品界面。PDF 可以从同一份 `.tex` 编译；当前 Daily 不强制安装完整 TeX 环境。

## GitHub Pages

Pages 是产品输出窗口，不展示内部 pipeline。首页只展示实时时间、来源数量、今日新增、入选日报、来源健康度、日报和分组来源。

`docs/admin.html` 是真正的 Source Registry 管理客户端。只有 `docs/data/runtime.json` 配置了 Registry API URL 后，主页才会显示“管理信息源”入口；后端不存在时不会展示假按钮或 localStorage CRUD。

## Source Registry API

仓库包含一个可部署到 Vercel Python Functions 的管理后端：

```text
api/registry.py
src/registry/github_store.py
src/registry/validation.py
```

管理客户端通过 Bearer Admin Token 连接该 API；API 再使用服务端 GitHub Token 读写：

- `config/groups.yaml`
- `config/sources.yaml`
- `config/profile.yaml`

保存后修改直接进入 GitHub `main`，因此下一次 Daily 会使用新配置。`pages.yml` 也会在 `config/**` 变化时重新构建 Pages 数据。

### Vercel 环境变量

部署管理 API 时在服务端设置：

```text
OPPOR_GITHUB_TOKEN       # fine-grained GitHub token，只给本仓库 Contents read/write
OPPOR_ADMIN_TOKEN        # 你自己生成的高熵管理口令
OPPOR_GITHUB_REPO        # 默认 RanchoTao/Oppor-Radar
OPPOR_GITHUB_BRANCH      # 默认 main
OPPOR_ALLOWED_ORIGINS    # 例如 https://ranchotao.github.io
```

不要把 `OPPOR_GITHUB_TOKEN` 或 `OPPOR_ADMIN_TOKEN` 写入仓库。

部署后，把 API 地址写入：

```json
{
  "registry_api_url": "https://YOUR-PROJECT.vercel.app/api/registry"
}
```

文件位置：`docs/data/runtime.json`。此后首页会自动显示 Registry 管理入口。

## DeepSeek 配置

本地 `.env`：

```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
OPPOR_LLM_ITEM_BATCH=32
```

不要提交真实 API Key。GitHub Actions 使用仓库 Secret `DEEPSEEK_API_KEY`。

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.scheduler.run_daily
python scripts/build_site_data.py
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
```

数据库文件仍保留为 `data/opportunities.sqlite3` 以兼容历史数据和 Actions，但内部主表已经迁移到 `information_items`。旧 `opportunities` 表仅作为迁移来源。

## 自动运行

`.github/workflows/daily.yml` 每天北京时间 08:00：

1. 测试
2. 抓取来源
3. 内容去重 / 变化检测
4. Item Intelligence
5. Daily Editor
6. 生成 JSON / Markdown / LaTeX
7. 刷新 Pages 数据
8. 提交报告和数据库

`.github/workflows/pages.yml` 负责 Pages 部署；来源配置变化和 Daily 完成都能触发重新构建。

## 当前边界

已经实现：

- 通用信息源、分组和独立用户兴趣画像
- RSS / Atom、HTML 内容发现和详情页正文抽取
- Content hash / run-scoped change detection
- URL-first identity 和历史数据库迁移
- Source health
- DeepSeek 两级智能层
- JSON / Markdown / LaTeX
- 结构化 GitHub Pages 日报
- 认证 Source Registry API 与管理客户端

仍需要外部部署/凭证或后续工程：

- 为 Registry API 配置 Vercel 服务端 Secret 并填入 runtime URL
- 为 GitHub Actions 配置真实 `DEEPSEEK_API_KEY`
- JavaScript 动态站点的 browser worker
- 多用户账户 / 权限 / 外部数据库 / 队列
- 自动 PDF 编译
- 邮件 / 消息推送

## 测试

```bash
pytest -q
```
