# Image Observer — Build 02.2

本地 CPU 实验性机器视觉图形工具。保留 Build 02.1 的固定蓝色主框、中型框、微型框和 Structure，本轮增加 **Click to Focus** 与 **Reset Focus / 恢复自动**。提供 Python / Gradio 与独立 HTML 两个入口，不增加滤镜、颜色、文字或编辑器。

## 使用 Focus

1. 上传 JPG / PNG，默认生成自动识别结果。
2. 点击**原图**中的视觉关注位置，主框改为覆盖该位置附近的结构，中型框和微型框向附近集中。
3. 再次点击可更换焦点；调整 Structure 保留当前焦点。
4. 点击 **Reset Focus / 恢复自动**，恢复同一图片和 Structure 的自动结果。上传新图，包括重新上传同一文件，都会清除焦点。

焦点保存在各自的 Gradio 会话 State / HTML 页面内，不使用共享全局焦点。固定 Seed 为 **0**，相同图片、Structure、焦点与 Seed 会得到相同结果。

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

本轮复用现有依赖，无需新增模型、GPU 或在线服务。`opencv-python-headless` 通过 Gradio 展示结果，不需要另装桌面 OpenCV。首次安装依赖需联网，图像处理在本地执行；遥测、公开分享和监控关闭。所有事件共用 CPU 处理队列，焦点和原图由 Gradio State 分别保存。

本轮在 Linux 的 Python 3.12 / Gradio 6.30 与 Chromium 中验证了真实页面交互，未在 Windows 实机执行；Windows 命令及依赖路径保持原有跨平台方式，没有新增平台脚本。

## 独立 HTML

下载 `build-02-2` 分支的 **`image-observer-v1.html`**（GitHub 文件页 → Download raw file），用 Chrome / Edge 直接打开。上传、点击原图、Structure 与恢复自动均离线工作；输出 canvas 可右键另存为 PNG。CSS 预览缩放不会改变画布实际像素。

HTML 与 Python 使用同样的交互规则、固定 Seed 和数量限制，但沿用各自的分析路径：Python 使用 512px 分析图、Pillow / OpenCV；HTML 使用 480px 分析图、Canvas / JavaScript。因此两个入口的框坐标可能不同，同一入口内结果可重复。

## 测试图与结果

已核对原图内容，命名没有颠倒：

| 文件 | 内容 | 输入尺寸 | 输出尺寸 |
| --- | --- | --- | --- |
| `test_images/detection_01.jpg` | 人像 | 909 × 1447 | 909 × 1447 |
| `test_images/detection_02.jpg` | 牛 | 1930 × 1280 | 1600 × 1061 |

本轮输出保存在 `outputs/`，文件名包含图片编号、内容、`build_02_2`、入口、Structure、Focus 名称与像素坐标；旧版本结果保留。Structure 50 分别比较人像自动 / 脸部 / 膝盖，牛图自动 / 牛头 / 牛身；四个手动焦点另外验证 Structure 0、100。

[查看本轮验收记录与输出索引](outputs/build_02_2_validation.md)。记录包含点击映射、实际尺寸、主框变化、PNG 下载、恢复自动、会话隔离与异常回退。

运行尺寸和焦点自动验证：

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_build_02_2
```

验证横图、竖图、方图在 1600px 上下的完整构图、EXIF 方向、固定蓝色叠加、焦点坐标映射、可重复性、数量上限及边界回退。

## Python 调用

```python
from PIL import Image
from processor import resize_image, detect_layers, process_image

with Image.open("test_images/detection_01.jpg") as source:
    original = resize_image(source)
    focus = (430, 520)  # 已显示原图的像素坐标；None 恢复自动。
    layers = detect_layers(original, structure=50, seed=0, focus=focus)
    result = process_image(original, structure=50, seed=0, focus=focus)
    result.save("outputs/portrait_build_02_2_s050_focus_face.png")
```

`detect_layers` 的焦点与返回框均为传入图像经 EXIF 校正后的像素坐标。`process_image` 若直接接收超过 1600px 的原文件，焦点应使用该原文件经 EXIF 校正后的坐标；函数会将焦点与图片一同映射至输出尺寸。Gradio 已显示缩小后的原图，`Image.select` 返回的坐标直接使用，不再二次缩放。

```text
app.py                   # Gradio 上传、Structure、会话焦点与 Reset
processor.py             # 图像分析、焦点评分、三级矩形与绘制
image-observer-v1.html   # 可独立离线打开的浏览器入口
requirements.txt         # 现有依赖版本，无额外模型
test_build_02_2.py        # 尺寸与焦点自动回归验证
test_images/             # 原图
outputs/                 # 各版本输出、本轮验收记录
```

Linux / macOS 使用 Python 3.12 创建虚拟环境后，将 Windows 命令中的 `.\.venv\Scripts\python.exe` 换成对应的 `.venv/bin/python`。
