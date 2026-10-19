# Image Observer — Build 02

本地 CPU 实验性机器视觉图形工具。上传 JPG / PNG，在原图上生成固定蓝色的大、中、微型矩形，不绘制文字。提供独立 HTML 和 Python / Gradio 两个入口。

## Structure 与三级框

唯一新增控件是 **Structure**：0–100，默认 **45**。

- **大型主框：1 个。** 沿用 Build 01.1 的主体候选评分，调整 Structure 不移动主框。
- **中型分析框：2–5 个。** 围绕主框及其附近分布。
- **微型识别框：0–30 个。** 在主体附近的边缘、局部对比变化和细节处生成，具有不同大小、宽高比，允许局部聚集。

Structure 越高，微型框数量和局部密度越高。普通细节图在 0 / 45 / 100 时分别以 0 / 10 / 30 个微型框为目标；纯色或极小图片可以没有微型框。微型候选来自图像结构，不在全画面均匀随机撒布。

界面固定随机种子为 **0**，没有额外的种子控件。同一入口内，相同输入、Structure 和种子产生相同结果；调高密度会延续同一个微型候选序列。Python 调用时可显式指定 `seed`：

```python
from PIL import Image
from processor import process_image, detect_layers, resize_image

with Image.open("test_images/detection_01.jpg") as source:
    original = resize_image(source)
    layers = detect_layers(original, structure=45, seed=0)
    result = process_image(original, structure=45, seed=0)
    result.save("outputs/detection_01_build_02_s045.png")
    print({name: len(boxes) for name, boxes in layers.items()})
```

不调用在线 API，不下载模型，不使用 GPU / CUDA；首次安装 Python 依赖需要联网，正常处理图片完全在本地完成。没有文字叠加、滤镜、Glitch、颜色选择或后续模式。

## 直接打开 HTML

只需下载 **`image-observer-v1.html`** 一个文件：

1. 在 GitHub 的 `build-02` 分支打开该文件，点击右上角 **Download raw file**（下载箭头）。
2. 保存后，用 Chrome 或 Edge 打开 `.html` 文件。
3. 上传图片，拖动 Structure 查看不同疏密。

HTML 内嵌全部样式与检测逻辑，无需 Python、服务器或网络，图片保留在当前浏览器中。输出图可右键另存为图片。

HTML 使用原生 JavaScript / Canvas 实现相同的三级框规则，Python 使用 OpenCV / Pillow / NumPy；两个入口不承诺框的位置逐像素相同。

## Windows 本地 Gradio

安装 **64 位 Python 3.12**（安装程序中启用 Python Launcher）。解压项目后，在**包含 `app.py` 的文件夹**中打开 PowerShell。

依次运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe app.py
```

保持终端打开，在**运行 Python 的同一台电脑**用浏览器访问 `http://127.0.0.1:7860`。上传图片后拖动 Structure，结果自动更新。按 `Ctrl+C` 停止。修改代码或更新项目后，停止旧实例再启动。

直接调用虚拟环境的 Python，无需执行激活脚本或更改 PowerShell 执行策略。若提示找不到 `py`，使用 Python 安装程序启用 Launcher，或用 Python 3.12 的完整路径替换第一条命令中的 `py -3.12`。若 7860 端口已占用，先关闭之前启动的实例。

`opencv-python-headless` 是不带桌面窗口的 OpenCV，本项目通过 Gradio 显示图片，无需另外安装 `opencv-python`。上传和滑杆共享一个处理队列，快速拖动时仅保留最新的待处理参数，避免积压。Gradio 遥测、公开分享与监控已关闭。

## 两张测试图和保存输出

- `test_images/detection_01.jpg`：人像。
- `test_images/detection_02.jpg`：牛图。

依次上传两张图，在 Structure **0、45、100** 比较：主框一致，低值稀疏，高值出现更多大小及宽高比不同的局部微框。重复设置同一个值应得到同样的框选结果。

在 Windows 项目目录，可一次保存两张图的三个 Structure 输出：

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from PIL import Image; from processor import process_image; out = Path('outputs'); out.mkdir(exist_ok=True); [process_image(Image.open(p), structure=s, seed=0).save(out / (p.stem + '_build_02_s' + str(s).zfill(3) + '.png')) for p in sorted(Path('test_images').glob('detection_0*.jpg')) for s in (0, 45, 100)]"
```

`outputs/` 中保存了上述 Python 输出；文件名带 `html` 的两张默认值输出来自独立 HTML，便于分别查看两个入口。

## 处理与边界

Pillow 校正 EXIF 方向，保持原比例将最长边限制在 1600px，小图不放大。透明 PNG 使用白底合成。主框继续依据低频颜色显著性、背景颜色统计、连通性、填充率和环带对比评分，并抑制重复纹理及近黑背景。

微型框只在主框附近的候选范围内根据局部结构生成，再用局部随机种子改变候选顺序、大小与宽高比，避免全图散点。蓝线按层级绘制，微型框使用细线。检测不代表准确物体识别。

纯色图、极小图和分析异常有稳定回退。极小或极端长宽比图片可能无法同时满足面积、形状和整数像素约束，允许框重叠或减少微型框，以保证输出有效。

已用两张原图验证 Structure 0 / 45 / 100 的数量变化、相同种子的可重复性、微型框局部性、大小与宽高比变化、主框不漂移，以及上传 / 滑杆 / 下载 / 清空流程。HTML 另验证了断网、拖放、快速切换图片和窄屏显示。

运行验证在 Linux + Python 3.12 和 Chromium 中执行；未在 Windows 主机上实测。Windows CPython 3.12 x64 的完整依赖解析已通过，53 个依赖包均有可用 wheel。Windows 启动使用标准 venv 和跨平台 Python / Gradio 代码。

```text
image-observer-v1.html # 可独立、离线打开的浏览器版本
app.py                # 上传、Structure 与本地 Gradio 页面
processor.py          # 图像分析、三级矩形与绘制
requirements.txt      # 已验证的直接依赖版本
test_images/          # 原图与合成示例
outputs/              # 本地输出及本轮保存的示例
```

Linux / macOS 使用 Python 3.12 创建 `.venv` 后，将 Windows 命令中的 `.\.venv\Scripts\python.exe` 换成 `.venv/bin/python`。
