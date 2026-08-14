# Opportunity Radar

Opportunity Radar 是面向本科生与科研新人的“学术机会雷达”MVP。它会从高校、研究院、实验室官网抓取信息，筛选数学、人工智能、机器学习、AI for Science、暑期学校、夏令营、科研训练、RA、讲座、竞赛、推免等机会，保存到 SQLite，并生成每日 Markdown 报告。

> Logo 预留路径：`assets/OR.png`。当前仓库尚未包含该文件，放入后可在 README 中加入图片引用。

## 功能

- 从 `config/sources.yaml` 读取监控源。
- 使用 `requests` + `BeautifulSoup4` 抓取并解析网页链接。
- 按 URL 去重；URL 缺失时按 `title + source_name` 去重。
- 使用关键词规则打分并分为 A/B/C/X 四类。
- 使用 SQLite 保存机会及 `first_seen_at` / `last_seen_at`。
- 每次运行生成 `data/reports/YYYY-MM-DD.md`。
- 提供 GitHub Actions，每天北京时间 08:00 自动运行，也支持手动触发。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

可选：复制环境变量示例。

```bash
cp .env.example .env
```

## 本地运行

```bash
python -m src.scheduler.run_daily
```

运行后会生成：

- SQLite 数据库：`data/opportunities.sqlite3`
- 每日报告：`data/reports/YYYY-MM-DD.md`
- 简单网页快照：`data/snapshots/*.html`

## 添加新的监控源

编辑 `config/sources.yaml`，追加：

```yaml
- name: 示例实验室
  url: https://example.edu/lab/
  tags: [AI, 数学, 科研训练]
```

`tags` 会作为解析和筛选的辅助上下文。第一版解析逻辑是通用链接提取，因此适合官网首页、通知页、新闻页等结构相对简单的页面。

## 调整关键词和打分

- 关键词：`config/keywords.yaml`
- 分数和分类阈值：`config/scoring.yaml`

分类规则：

- A：必须关注/申请
- B：值得申请
- C：可围观
- X：不适合/已过期

## 查看报告

打开当天报告：

```bash
cat data/reports/$(date +%F).md
```

报告包含 Summary 以及 A/B/C/X 分类列表，每条机会包含来源、日期、地点、分数、推荐理由和链接。

## 启用 GitHub Actions

工作流文件位于 `.github/workflows/daily.yml`。

1. 将项目推送到 GitHub。
2. 确认仓库 Settings → Actions → General 中允许 workflow 写入仓库。
3. Actions 会每天 UTC 00:00（北京时间 08:00）运行。
4. 也可以在 Actions 页面手动触发 `workflow_dispatch`。
5. 工作流运行 `python -m src.scheduler.run_daily`，并将生成的报告和数据库 commit 回仓库。

## 当前 MVP 限制

- 只抓静态 HTML，不执行 JavaScript。
- 日期、地点提取基于简单规则，复杂页面可能解析不到。
- 只提取列表页中的链接文本和父节点文本，不会递归进入详情页。
- 推荐理由由规则生成，暂未接入大模型 API。
- GitHub Actions 会提交 SQLite，适合个人 MVP；多人协作时建议改为 artifact 或外部存储。

## 测试

```bash
pytest
```
