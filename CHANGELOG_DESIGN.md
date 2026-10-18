# OR Morning 本地设计升级

日期：2026-10-18。工作分支：`design/or-morning-upgrade`。
基线：`775f3d5298b207412e179ccf50de15096658f13a`。

## 用户可见变化

- 纸白/墨绿的统一报刊设计：收紧刊头和重复层级，正文、来源与行动说明更清晰。
- 手机保留时报 / 日报 / 信息源 / 设置四入口；运行指标可展开。
- 八版完整标签可横滑或用左右键、Home、End 切换；Tab 可进入正文；总览索引可直达版面。
- 原文来源提前；长摘要保留全文并可展开。分版显示全部真实条目，修复原有最多七条的显示截断。
- 异常长头条保留完整文字，使用更适合阅读的字号，并优先展示原始出处。
- 归档支持原有日期，并提供真实文件下载；没有文件时不显示下载入口。
- 来源分组保留选中与焦点，展示最新日报内真实来源健康记录。
- 设置使用相同设计语言，明确打开 GitHub 配置编辑。
- 管理页提供准确连接状态、真正的未保存状态、撤销、断开连接、失败保留修改、删除提醒与离开保护。未配置时输入/连接禁用。
- 明确 Loading / Empty / Error 和重试；旧日期响应不覆盖新选择；刷新不打断展开内容或历史阅读。
- 前台共享进行中的 JSON 请求，减少同一日报重复下载；没有持久数据缓存。

## 实际源码清单

| 文件 | 修改 |
|---|---|
| docs/index.html | 导航、语义、运行状态折叠、日期标签、下载/健康区域、说明和 footer |
| docs/styles.css | 共享 tokens、导航、档案、来源、设置、状态、焦点与减少动态效果 |
| docs/newspaper.css | 刊头、版签、文章双栏、摘要、索引、四类响应式布局 |
| docs/app.js | 日期竞态保护、错误反馈、共享请求、健康记录、导航状态、真实下载 |
| docs/newspaper.js | tabs 键盘语义、完整条目、摘要展开、规则版说明、轮询稳定性 |
| docs/admin.html | 表单标签、连接/断开、未保存状态、撤销与主导航 |
| docs/admin.css | 管理页共享视觉体系、输入/列表/保存栏与窄屏处理 |
| docs/admin.js | dirty/busy 状态、撤销基线、凭证清理、失败反馈和保存响应核对 |
| .gitignore | 忽略本地 QA 依赖与预览日志 |
| requirements-design.txt | 只用于本地 QA 的 Playwright 版本 |
| scripts/capture_design.py | 可复现真实数据多视口与多页面截图 |
| scripts/check_design.py | 浏览器验收、axe、下载、错误夹具、管理页隔离测试与本地性能观察 |

文档：`DESIGN_AUDIT_BEFORE.md`、`DESIGN_SYSTEM.md`、`DESIGN_QA_REPORT.md`、本文件。
证据：`artifacts/design/`，其中 `qa/` 中明确标记 LOCAL QA 的页面均为测试响应夹具。

## 保留的数据与运行契约

没有修改 `src/`、`api/`、`config/`、`data/`、`docs/data/`、`docs/reports/`、`.github/` 或 `scripts/build_site_data.py`。
JSON schema、来源排序、科学/业务含义、DeepSeek、抓取、Daily 与 Pages 发布链路均保持。
上海时区时钟与五分钟刷新仍然运行。Registry API 认证协议保持不变，未使用真实凭证或修改远程 Registry。
QA 依赖不被网页加载；`docs/` 可按原 workflow 直接发布。

## 本地预览

当前预览：<http://127.0.0.1:8765/>；管理页：<http://127.0.0.1:8765/admin.html>。
若本地预览进程停止，在仓库目录运行：

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory docs
```

这是本地只读静态预览。发布仍由作者另行决定，本次没有 push、merge 或部署。

## 复现验收

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-design.txt
npm install --prefix .qa-tools --no-save --no-audit --no-fund axe-core@4.14.0
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python scripts/check_design.py
.\.venv\Scripts\python scripts/capture_design.py local-review
```

截图和浏览器检查要求上面的静态服务器已运行，以及已安装 Google Chrome；使用独立无头实例，不读取个人浏览器配置。
基线截图文件来自升级前真实站点；要重新生成基线，应使用基线提交的单独 checkout，不能在升级后运行 `capture_design.py before` 代替。

## 回滚

本轮工作隔离在本地分支，基线 main 未被合并。需要回退时，可对本轮设计提交执行 `git revert <设计提交>`；先检查并保存后续未提交修改。不要使用 reset --hard 覆盖其他工作。
