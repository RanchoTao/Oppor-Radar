# Opportunity Radar Runbook

这份文件只回答三个问题：OR 每天怎么跑、用了什么模型、坏了去哪里看。

## 每天怎么跑

生产环境由 GitHub Actions 驱动，不需要常驻服务器。

北京时间每天 08:00，`.github/workflows/daily.yml` 自动执行：

1. checkout `main`
2. 安装 Python 依赖
3. `pytest -q`
4. `python -m src.scheduler.run_daily`
5. `python scripts/build_site_data.py`
6. 提交当日日报、Pages 数据和 SQLite 数据库
7. Pages workflow 发布 `docs/` 到网站

`run_daily` 内部流程：

```text
config/sources.yaml + config/profile.yaml
        ↓
抓 RSS / HTML / 详情页
        ↓
URL + content hash 去重 / 变化检测
        ↓
Level 1：逐条筛选、摘要、相关性判断
        ↓
Level 2：整份日报编辑 + Opportunity-first 排序
        ↓
JSON / Markdown / LaTeX
        ↓
可选 SMTP 邮件推送
```

## 当前模型与 API

Provider: **DeepSeek official API**

- Base URL: `https://api.deepseek.com`
- Production model: `deepseek-flash`
- 代码入口: `src/llm/deepseek_digest.py`
- GitHub Secret: `DEEPSEEK_API_KEY`

不要把真实 key 写进仓库。

如果 `DEEPSEEK_API_KEY` 缺失，OR 不会停机，而会进入 deterministic fallback。这样仍能生成网页，但英文原文可能直接进入摘要，个性化和中文编辑质量会显著下降。运行日志会明确给出 warning，JSON diagnostics 也会记录 `missing_api_key`。

## Opportunity-first

`config/sources.yaml` 的机会源可以配置：

- `reachability`: 0–1，当前用户真实可参与/申请的先验
- `locality`: 北京 / 全国线上 / 海外等参与范围

机会版会优先：北京线下、全国/线上、本科生/学生/个人开发者开放、短期可报名的 Hackathon、竞赛、科研招募、实习、Workshop、Meetup 等。

海外高级全职职位仍会保留为信息，但不应压过当前真正可行动的机会。

## 邮件

日报生成后可以通过 SMTP 发出简版邮件。邮件只放最值得行动/关注的约 8 条，完整内容仍在网页。

GitHub Secrets：

- `OR_SMTP_USERNAME`: 发件 Gmail 地址
- `OR_SMTP_PASSWORD`: Gmail App Password，不是 Google 账户密码
- `OR_EMAIL_TO`: 收件地址；不填时本地逻辑会回退到发件地址，但 Actions 中建议明确配置

Workflow 已设置 `OR_EMAIL_ENABLED=true`。如果 SMTP secrets 尚未配置，邮件会被安全跳过，不影响日报和网站更新。

## 常见故障

### 网站每天更新，但内容大多是英文

优先查看日报 JSON 的 diagnostics。若 `item_intelligence` / `newspaper_editor` 出现 `missing_api_key`，说明 DeepSeek Secret 没有注入成功。

### 没收到邮件

先确认 `OR_SMTP_USERNAME`、`OR_SMTP_PASSWORD`、`OR_EMAIL_TO` 三个 GitHub Secrets 已配置，再看 Daily workflow 日志中的 `OR Morning email`。

### 新来源没有内容

当前 crawler 以 RSS / Atom 和静态 HTML 为主，不执行浏览器 JavaScript。纯前端动态站可能需要后续 browser worker，或者换成该平台的公开 API / feed / 可抓取列表页。
