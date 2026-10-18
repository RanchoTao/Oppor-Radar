# 内嵌浏览器按键复核

2026-10-18，在真实 localhost 页面通过内嵌浏览器操作，独立于 axe 自动扫描：

1. 读取八个 tab 的真实 DOM 标签与当前选中状态。
2. 今日总览按 ArrowRight：焦点变成 tab-opportunity，选中机会雷达，面板标题同步。
3. 按 End：焦点变成 tab-world，面板标题为世界状态。
4. 按 Home：回到 tab-front。
5. 按 Tab：进入“规则筛选版 · 阅读说明” summary。
6. 再按 Tab：进入 newspaper-viewer，观察到赭色实线焦点轮廓。

证据 `iab-keyboard.jpg` 是内嵌浏览器可视区域截图（受侧栏宽度裁切，不作为指定 1440px 视口证据）。完整 1440×900 的相同焦点状态见 `keyboard-focus.png`。
测试后恢复默认浏览器视口，并保留本地预览标签页。

这是代理实际发送按键的检查，未进行 NVDA/JAWS/VoiceOver 屏幕阅读器认证。
