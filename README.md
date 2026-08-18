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

### 1. Source Registry

`config/sources.yaml` 是单用户版本的信息源注册表。每个来源支持：

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

### 2. Groups

`config/groups.yaml` 定义信息域。当前默认包含：

- 学术
- AI / 科技
- 金融
- 社会 / 政策

可以直接增加、删除、重命名和调整顺序。

### 3. User Profile

`config/profile.yaml` 描述“我长期关心什么”，而不是把所有兴趣重复写到每个来源里。

它包含：

- `interests`
- `high_priority_signals`
- `low_priority_signals`
- `editorial_preferences`

产品的核心关系是：

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

因此重复运行同一天的 Daily，不会把旧内容机械重复送给大模型。

当前仍以静态 HTML 为主，不执行浏览器 JavaScript。动态渲染站点后续需要单独的 browser worker。

## DeepSeek 两级智能层

### Level 1: Item Intelligence

先逐批判断每条新信息：

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

这一步负责把导航、广告、常规重复内容和明显无关信息压掉。

### Level 2: Daily Editor

再把通过筛选的条目整体交给日报主编层：

- 合并重复事件
- 按分组形成今日摘要
- 提取跨来源 / 跨领域信号
- 只保留真正需要用户行动的事项
- 控制最终日报长度

DeepSeek 不可用时，系统会使用确定性 fallback，保证定时任务仍能产出日报；大模型调用诊断只保存在结构化数据的 diagnostics 中，不展示在产品首页。

## 报告数据

每日主要产物：

```text
data/reports/YYYY-MM-DD.json   # 主数据
 data/reports/YYYY-MM-DD.md    # 可读文本
 data/reports/YYYY-MM-DD.tex   # LaTeX 视图
```

JSON 使用 `schema_version: 2`。GitHub Pages 只发布 v2 日报，旧版 A/B/C/X 申请清单不会继续出现在产品界面。

PDF 可以从同一份 `.tex` 编译得到；当前仓库先生成 `.tex`，避免在每日任务中强制安装完整 TeX 环境。

## GitHub Pages

Pages 是当前产品输出窗口，不展示内部 pipeline。

首页只显示：

- 实时时间 + “世界正在发生。”
- 监控来源数
- 今日新增
- 入选日报数
- 来源健康数量
- 个性化日报
- 分组信息源

当前是单用户版本，因此网页不再提供只写入 localStorage 的“假 CRUD”。需要修改分组、兴趣画像或来源时，直接编辑：

- `config/groups.yaml`
- `config/profile.yaml`
- `config/sources.yaml`

真正的网页增删改需要安全的持久化后端和身份验证，应该作为下一阶段基础设施实现，而不是在静态 Pages 上伪装成功。

## DeepSeek 配置

复制环境变量：

```bash
cp .env.example .env
```

本地 `.env`：

```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
OPPOR_LLM_ITEM_BATCH=32
```

不要提交真实 API Key。

GitHub Actions 通过仓库 Secret 注入：

```text
Settings
→ Secrets and variables
→ Actions
→ New repository secret
→ DEEPSEEK_API_KEY
```

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

数据库仍使用：

```text
data/opportunities.sqlite3
```

文件名暂时保留是为了兼容现有 GitHub Actions 和历史数据。内部主表已经迁移到 `information_items`，旧 `opportunities` 表只作为迁移来源，不再参与新的 A/B/C/X 产品逻辑。

## 自动运行

`.github/workflows/daily.yml` 每天北京时间 08:00 运行：

1. 测试
2. 抓取来源
3. 内容去重 / 变化检测
4. Item Intelligence
5. Daily Editor
6. 生成 JSON / Markdown / LaTeX
7. 刷新 Pages 数据
8. 提交报告和数据库

Pages 部署工作流位于 `.github/workflows/pages.yml`。

## 当前边界

已经实现：

- 通用信息源与分组
- 独立用户兴趣画像
- RSS / Atom
- HTML 内容发现
- 详情页正文抽取
- Content hash / change detection
- Source health
- DeepSeek 两级智能层
- JSON / Markdown / LaTeX
- 结构化 GitHub Pages 日报
- 历史数据库迁移

尚未实现：

- JavaScript 动态站点的浏览器渲染 worker
- 真正的网页 Source Registry CRUD 后端
- 多用户账户与权限
- 外部数据库 / 队列
- 自动 PDF 编译
- 邮件 / 消息推送

这些都可以在不推倒当前 crawler、information model 和 report schema 的前提下继续增加。

## 测试

```bash
pytest -q
```
