# Image Observer 历史归档

唯一正式入口为根目录的 `image-observer-v1.html`（HTML Build 02.3）。此目录仅保留恢复点，不是最新版运行入口。

- `image-observer-html-build-02.2.html`：原样保存的 HTML 02.2，文件 SHA-256 为 `d4ec7a9badb7ad666153626cc8d4d3a57aaf8e13d2861f6ca6e3f60d338b198c`。Git 恢复点 `24521bacb8cfcfb3bddf1358da224002d12be055`，本地分支 `backup/html-build-02-2-24521ba`。
- `python-build-02.3-archived.zip`：稳定 Python / Gradio 02.3 的运行源文件、旧说明、回归测试和两张既有测试图，来自提交 `b92bcd5fa34b0e79e02c626316f47c7547d467e7`，含逐文件校验清单。本地恢复分支 `archive/python-build-02-3-b92bcd5`。停止维护。
- `render-preparation-not-deployed.zip`：切换架构前尚未提交的 Render 部署草稿，包含当时代码、配置、说明和测试报告。仅在工作区本地保留，已加入 Git 忽略，不随正式 HTML 源码包或本轮 GitHub 交付公开上传。草稿从未部署；不再启用 Render。

归档 ZIP 已验证 CRC 和逐文件字节。根目录遗留 Python / BAT 文件与历史 outputs 文件不删除，但不纳入新的 HTML 正式运行包。旧归档中的安装或部署说明只是历史记录，不代表当前交付路线。
