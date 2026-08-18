# Opportunity Radar

Opportunity Radar 是一个个人信息雷达：用户主动选择并分组几十到上百个网页信息源，爬虫按日扫描新内容，再统一交给大模型筛选、关联、压缩，最终生成一份个性化日报。

它不再局限于“夏令营 / RA / 申请机会”。信息源可以属于学术、金融、社会、科技、政策、个人博客或任何用户自定义分组。

## 当前链路

```text
Source Registry
    ↓
Crawler
    ↓
SQLite 去重 / 只取首次发现条目
    ↓
DeepSeek 日报编辑器
    ↓
Structured JSON
    ├── Markdown 日报
    └── GitHub Pages 网页归档
```

后续可以继续从同一份结构化 JSON 派生 LaTeX / PDF、邮件和消息推送。

## 功能

- 从 `config/sources.yaml` 读取监控源，支持 `group`、`tags`、`watch` 和 `max_items`。
- 使用 `requests` + `BeautifulSoup4` 抓取静态网页链接。
- 按 URL 去重；URL 缺失时按 `title + source_name` 去重。
- 每日只把数据库中首次发现的新条目送入日报层，避免重复复述旧链接。
- 使用 DeepSeek API 对来自不同分组的信息进行统一筛选、摘要、跨来源关联和行动建议。
- DeepSeek 不可用时自动退化为规则化日报，不让定时任务整体失败。
- 每次运行同时生成 `data/reports/YYYY-MM-DD.md` 与 `data/reports/YYYY-MM-DD.json`。
- GitHub Pages 展示日报、来源分组和浏览器本地的自定义来源配置。
- GitHub Actions 每天北京时间 08:00 自动运行，也支持手动触发。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell 激活虚拟环境可使用：

```powershell
.\.venv\Scripts\Activate.ps1
```

## DeepSeek

当前默认模型为 `deepseek-v4-flash`，API base URL 为 `https://api.deepseek.com`。

本地运行时在 `.env` 中设置：

```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_MODEL=deepseek-v4-flash
```

不要把真实 API Key 提交到仓库。

GitHub Actions 使用仓库 Secret：

```text
Settings → Secrets and variables → Actions → New repository secret
Name: DEEPSEEK_API_KEY
```

Daily workflow 已经把 `${{ secrets.DEEPSEEK_API_KEY }}` 注入到运行环境；Secret 没配置时会生成 fallback 日报并在“系统状态”里明确标记。

## 信息源配置

示例：

```yaml
- name: 示例研究机构
  url: https://example.edu/news/
  group: 学术
  tags: [AI, 官方]
  watch: [Agent, 大模型, 科研]
  max_items: 30

- name: 示例财经来源
  url: https://example.com/macro/
  group: 金融
  tags: [宏观]
  watch: [央行, 利率, 通胀]
  max_items: 30
```

`watch` 可为空。为空时会抓取页面中非导航类的内容链接，并把相关性判断交给大模型；设置 `watch` 可以在爬虫层先做一次低成本过滤。

## 本地运行

```bash
python -m src.scheduler.run_daily
python scripts/build_site_data.py
```

运行后主要产物：

- `data/opportunities.sqlite3`：去重数据库
- `data/reports/YYYY-MM-DD.json`：结构化日报主数据
- `data/reports/YYYY-MM-DD.md`：人类可读日报
- `docs/data/` 与 `docs/reports/`：GitHub Pages 数据

## GitHub Pages

Pages 部署工作流位于 `.github/workflows/pages.yml`。仓库 Settings → Pages 的 Source 选择 **GitHub Actions** 后，`main` 更新和成功完成的 Daily workflow 都会重新部署网页。

## 当前 MVP 限制

- 只抓静态 HTML，不执行 JavaScript。
- 当前主要读取列表页链接及其附近文本，还没有全面递归抓取详情页正文。
- 当前用“新 URL”判断新增信息；同一个 URL 内正文发生变化还没有内容哈希 / diff 检测。
- GitHub Pages 仍是静态前端；网页里新增的分组和 URL 只保存在浏览器 localStorage，尚未写入云端数据库。
- GitHub Actions + 仓库 SQLite 适合单用户 MVP；真正多用户版本应迁移到后端 Source Registry、数据库与任务队列。

## 测试

```bash
pytest -q
```
