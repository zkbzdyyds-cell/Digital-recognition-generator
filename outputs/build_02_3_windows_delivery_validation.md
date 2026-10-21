# Build 02.3 — Windows 本地交付验证

本轮只修复交付和启动。Detection、Focus、Structure、Overlay 与情绪词功能没有重写，不进入 Build 02.4。等待用户在 Windows 实机验收。

## 唯一正式运行包

[下载 Image-Observer-Build-02.3-Windows.zip](Image-Observer-Build-02.3-Windows.zip)

右键 ZIP → 全部解压到新文件夹 → 双击 **启动工具.bat**。首次缺少 Python 时按 **先读我.txt** 安装 Python 3.12 64 位；启动器自动创建环境、安装依赖并打开浏览器。页面顶部必须为 **IMAGE OBSERVER · BUILD 02.3**。

ZIP 为 1,028,962 字节，包含以下 10 个文件，已经解压、逐文件核对当前源码哈希及检查 CRC：

```text
Image-Observer-Build-02.3-Windows/
  启动工具.bat
  先读我.txt
  launcher.py
  app.py
  processor.py
  requirements.txt
  BUILD_INFO.json
  test_images/detection_01.jpg
  test_images/detection_02.jpg
  outputs/.gitkeep
```

不包含旧 HTML、旧 ZIP 或预装虚拟环境。历史 HTML 仍在仓库中，字节与 Build 02.2 一致。旧 `image-observer-build-02-3-source.zip` 的内容已更新为上述运行包的相同字节，避免旧链接继续分发混合入口。

## 修改文件

- `app.py`：增加明确的可见版本标题；接收启动器选择的本地端口和自动打开浏览器设置。既有处理回调未改。
- `launcher.py`：新增标准库启动器，检查 Python 3.12 / 64 位、创建专用环境、验证固定依赖、必要时安装或修复，选择可用本地端口，保留启动及安装日志。
- `启动工具.bat`：Windows 双击入口，探测合适的 Python；未完整解压、缺 Python、启动失败时显示提示并保留窗口。
- `先读我.txt`、`README.md`：面向使用者的安装、启动和故障说明。
- `outputs/`：正式运行包、清单、验收记录、两张实际页面截图与两张实际下载 PNG。同步修正旧验收文档的交付入口。

`processor.py`、`requirements.txt` 和历史 HTML 未改。Build 02.2 恢复点仍为 `24521bacb8cfcfb3bddf1358da224002d12be055`，源码备份保留。

## 实际验证

| 检查 | 结果 |
| --- | --- |
| 空目录首次运行 | 在中文及空格路径创建全新 `.venv`，实际安装固定依赖，导入与 `pip check` 通过 |
| 重复启动 | 复用环境；安装日志未更新，没有再次安装 |
| 旧 7860 被占用 | 自动使用 7861；实际自动打开浏览器的 URL 对应 Build 02.3，服务就绪后才打开 |
| Windows 依赖可用性 | 按 Windows x64 / CPython 3.12 解析全部依赖成功，全部为 wheel，无需本地编译；这不是 Windows 实机安装测试 |
| 从最终 ZIP 解压运行 | 实际启动解压目录中的 Python 文件，而非仓库或旧目录文件 |
| 页面版本与控件 | H1 和浏览器标题正确；Thin / Medium / Thick、Off / Emotion Pool / Custom Text、Shuffle 与自定义输入均正常 |
| 两张测试图 | 人像 909×1447 → 909×1447；牛图 1930×1280 → 1600×1061 |
| Focus 与缓存 | 两图均在原图真实点击；切换线宽、标签和换词保持 Focus 与框数据，增加 Detection 调用 0 次 |
| 自定义英文 | 输入 `melancholy`，字段与最终图片使用 MELANCHOLY |
| PNG 下载 | 实际点击两图下载按钮；下载字节与预览渲染 PNG 的 SHA-256 一致 |
| 页面异常 | 无 JavaScript 错误；图像处理页面无外部网络请求 |
| 既有回归 | 14 项通过，0 项失败；先前 A–E 功能验收保留 |

## 真实页面和下载结果

| 输入 | 页面截图 | 实际下载的 PNG |
| --- | --- | --- |
| detection_01 人像 | [页面](detection_01_build_02_3_windows_delivery_page.png) | [Medium / Custom MELANCHOLY](detection_01_build_02_3_windows_delivery_s050_medium_custom_melancholy.png) |
| detection_02 牛 | [页面](detection_02_build_02_3_windows_delivery_page.png) | [Medium / Custom MELANCHOLY](detection_02_build_02_3_windows_delivery_s050_medium_custom_melancholy.png) |

上述处理和启动集成测试在 Linux / Python 3.12 / Gradio 6.30.0 / Chromium 完成。BAT 的 UTF-8 无 BOM、CRLF、路径引号、Python 探测和错误保留已经静态检查；环境没有 Windows CMD，**尚未在 Windows 实机双击执行**，不能将其报告为通过。用户首次实机验收仍是待办项。

仅向现有 GitHub 分支交付代码与 ZIP，没有部署公共网站或发布云环境。

[逐文件包清单](build_02_3_windows_package_manifest.json) · [机器可读验证](build_02_3_windows_delivery_validation.json) · [原 Build 02.3 功能验收](build_02_3_validation.md)
