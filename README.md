# Image Observer — Build 02.3

本地 CPU 实验性机器视觉图形工具。Build 02.3 在现有 Python / Gradio 页面增加 **Stroke Width** 和 **Emotional Labels**，沿用 Build 02.2 的 Detection、Structure、Click to Focus、Reset、固定蓝色及 PNG 导出。本轮标签用 Pillow 和本地字体绘制，没有新增滤镜、颜色或编辑器。

路线已锁定为**一个 Python 图像处理核心 + 一个 Gradio 正式网页入口**。`app.py` 是持续试用和后续部署的同一入口；独立 HTML 仅保留为历史原型，不再同步新 Build。

## 线宽与情绪标签

- **Stroke Width**：Thin = 1px、Medium = 2px（默认）、Thick = 4px。主框、中型框、微型框全部响应；线条向框内绘制，不扩张框数据或画布。
- **Labels**：Off、Emotion Pool（默认）、Custom Text。
- **Emotion Pool**：严格使用 `processor.py` 中的 30 词常量，每张图片只选择一个词，所有可见标签重复使用它。只有主框和中型框有标签，微型框没有文字。
- **换一个 / Shuffle Word**：只推进当前会话的词语状态，新词与当前词不同。线宽、模式、Custom Text、Structure、Focus 和普通重绘不会推进词语状态。切回 Emotion Pool 恢复此前词语。
- **Custom Text**：仅在该模式显示输入框；英文词或短语自动大写，最多 32 个字符，输入过滤为英文字母、空格、连字符和撇号。空文本不绘制标签。

标签使用本机 Arial / Segoe UI / DejaVu Sans 等无衬线字体；没有可用字体时使用 Pillow 内置字体，不下载字体。文字为相同蓝色，默认靠近左上角；布局先避让、再隐藏无法清晰放置的次要中型框标签。很小的图片可能隐藏所有文字以避免越界。

检测结果在 `gr.State` 中缓存。线宽、模式、Custom Text 和 Shuffle 只调用 `render_overlay()`，不运行 Detection。词语选择使用独立 LCG 状态：上传时按缩小后图像的像素摘要初始化，同一图片和操作顺序可重复；它不修改 Detection 的固定 Seed=0。由于本地字体可能不同，不保证不同操作系统的文字像素逐点相同。

修改前已保留本地恢复分支 `backup/build-02-2-24521ba`，指向 Build 02.2 提交 `24521bacb8cfcfb3bddf1358da224002d12be055`；另有 [Build 02.2 源码备份](outputs/image-observer-build-02-2-source-backup.zip)。本轮未发布云环境，未推送远程仓库。

## 使用 Focus

1. 上传 JPG / PNG，默认生成自动识别结果。
2. 点击**原图**中的视觉关注位置，主框改为覆盖该位置附近的结构，中型框和微型框向附近集中。
3. 再次点击可更换焦点；调整 Structure 保留当前焦点。
4. 点击 **Reset Focus / 恢复自动**，恢复同一图片和 Structure 的自动结果。上传新图，包括重新上传同一文件，都会清除焦点。

焦点保存在当前 Gradio 会话 State 中，不使用共享全局焦点。固定 Seed 为 **0**，相同图片、Structure、焦点与 Seed 会得到相同结果。

## 尺寸与框数量

图片先按 EXIF 方向校正，保留完整构图；仅当最长边超过 1600px 时等比缩小。小图不放大，不裁切、拉伸、补边或扩展画布。短边只作整数像素取整。预览的自适应大小与下载 PNG 的实际像素尺寸分开处理。

| Structure | 主框 | 中型框 | 微型框 | 总数 |
| --- | --- | --- | --- | --- |
| 0 | 1 | 1 | 0 | 2 |
| 50 | 1 | 2 | 4 | 7 |
| 100 | 1 | 3 | 9 | 13 |

范围仍为 0–100，默认 45。中、微型框保留重叠、包含及相近中心的抑制；Structure 只控制密度，不移动已选主框。纯色、极小图或细节不足时允许减少微型框，稳定回退仍保留有效主框。极端长宽比下，以整数像素边界及覆盖焦点为优先，框面积和宽高比约束可能无法同时满足。

## Windows 本地 Gradio

使用 **64 位 Python 3.12**，在包含 `app.py` 的项目目录中打开 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe app.py
```

在同一台电脑访问 `http://127.0.0.1:7860`，保持终端打开。更新代码后停止旧实例，再启动。输出图工具栏的下载按钮保存 PNG；按 `Ctrl+C` 停止服务。直接调用虚拟环境 Python，无需激活脚本或修改 PowerShell 执行策略。

本轮复用现有依赖，无需新增模型、GPU 或在线服务。`opencv-python-headless` 通过 Gradio 展示结果，不需要另装桌面 OpenCV。首次安装依赖需联网，图像处理在本地执行；遥测、公开分享和监控关闭。所有事件共用 CPU 处理队列，原图、Focus、框数据和词语状态分别由 Gradio State 保存。

本轮在 Linux 的 Python 3.12 / Gradio 6.30 与 Chromium 中验证了真实页面交互，未在 Windows 实机执行；Windows 命令及依赖路径保持原有跨平台方式，没有新增平台脚本。

## 历史 HTML（停止同步）

独立 HTML 保留为 **Build 02.2 历史原型**，不包含 02.3 的线宽和文字，不再作为后续 Build 的开发或验收入口。它在浏览器使用 Canvas，无法直接执行 Pillow；文件保留原样，不删除、不继续同步算法。

下载 `build-02-2` 分支的 **`image-observer-v1.html`**（GitHub 文件页 → Download raw file），用 Chrome / Edge 直接打开。上传、点击原图、Structure 与恢复自动均离线工作；输出 canvas 可右键另存为 PNG。CSS 预览缩放不会改变画布实际像素。

HTML 与 Python 使用同样的交互规则、固定 Seed 和数量限制，但沿用各自的分析路径：Python 使用 512px 分析图、Pillow / OpenCV；HTML 使用 480px 分析图、Canvas / JavaScript。因此两个入口的框坐标可能不同，同一入口内结果可重复。

## 测试图与结果

已核对原图内容，命名没有颠倒：

| 文件 | 内容 | 输入尺寸 | 输出尺寸 |
| --- | --- | --- | --- |
| `test_images/detection_01.jpg` | 人像 | 909 × 1447 | 909 × 1447 |
| `test_images/detection_02.jpg` | 牛 | 1930 × 1280 | 1600 × 1061 |

本轮输出保存在 `outputs/`，文件名包含图片编号、`build_02_3`、固定 Focus 坐标、Structure 50、线宽及标签模式。两图分别保存 A（Thin / Off）、B（Medium / Pool）、C（Thick / Custom MELANCHOLY）及 D（三次 Shuffle）；这些操作同时验收 E（手动 Focus、尺寸、框数据保持不变）。旧版本输出保留。

[查看 Build 02.3 验收记录与输出索引](outputs/build_02_3_validation.md) · [此前 Build 02.2 记录](outputs/build_02_2_validation.md)。

在已有本地页面测试：停止旧实例，用原虚拟环境重新运行 `app.py`，浏览器刷新至标题 Build 02.3。上传人像或牛图，把 Structure 设为 50，点击一个 Focus；依次切换三档线宽和三种标签模式，在 Custom Text 输入 `melancholy`，再返回 Emotion Pool 连续点击三次 Shuffle。观察框数据和 Focus 不动、同一画面的标签统一变化，最后用输出工具栏下载 PNG。无需重新安装依赖。

运行尺寸和焦点自动验证：

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_build_02_2 test_build_02_3
```

验证尺寸、EXIF、Focus 和数量限制，以及准确 30 词、词语状态确定性、1/2/4px 向内描线、主中框同词标签、文字边界与避让、缓存 Overlay 不执行检测。

## Python 调用

```python
from PIL import Image
from processor import resize_image, detect_layers, process_image

with Image.open("test_images/detection_01.jpg") as source:
    original = resize_image(source)
    focus = (430, 520)  # 已显示原图的像素坐标；None 恢复自动。
    layers = detect_layers(original, structure=50, seed=0, focus=focus)
    result = process_image(original, structure=50, seed=0, focus=focus,
                           stroke_width="Medium", label_mode="Emotion Pool",
                           word="MELANCHOLY")
    result.save("outputs/portrait_build_02_3_s050_medium_pool.png")
```

`detect_layers` 的焦点与返回框均为传入图像经 EXIF 校正后的像素坐标。`process_image` 若直接接收超过 1600px 的原文件，焦点应使用该原文件经 EXIF 校正后的坐标；函数会将焦点与图片一同映射至输出尺寸。Gradio 已显示缩小后的原图，`Image.select` 返回的坐标直接使用，不再二次缩放。

```text
app.py                   # Gradio 操作、会话图像/Focus/框/词语状态
processor.py             # Detection、筛选、底图尺寸处理、Overlay 与词库
image-observer-v1.html   # 保留的独立 Build 02.2 浏览器入口
requirements.txt         # 现有依赖版本，无额外模型
test_build_02_2.py        # 尺寸与焦点自动回归验证
test_build_02_3.py        # 线宽、词库、Overlay 与状态验证
test_images/             # 原图
outputs/                 # 各版本输出、本轮验收记录
```

模块职责沿用现有结构：`detect_boxes` / `detect_layers` 生成框；`_medium_pool` / `_near_duplicate` 等整理候选；`resize_image` 处理完整底图；`render_overlay` 绘制框和文字；`app.py` 接收操作并缓存会话状态。未增加新的处理模块。

Linux / macOS 使用 Python 3.12 创建虚拟环境后，将 Windows 命令中的 `.\.venv\Scripts\python.exe` 换成对应的 `.venv/bin/python`。
