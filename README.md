# Image Observer — Build 02.1

本地 CPU 实验性机器视觉图形工具。上传 JPG / PNG，在原图上生成固定蓝色的大、中、微型矩形，不绘制文字。提供独立 HTML 和 Python / Gradio 两个入口。

## Structure 与三级框

唯一新增控件是 **Structure**：0–100，默认 **45**。

- **大型主框：1 个。** 沿用 Build 01.1 的主体候选评分，调整 Structure 不移动主框。
- **中型分析框：1–3 个。** 围绕主框及其附近分布。
- **微型识别框：0–9 个。** 在主体附近的边缘、局部对比变化和细节处生成，具有不同大小、宽高比，允许局部聚集。

Structure 越高，框数量平滑增加，最高总框数为 13。LOW（0）为 1 主框 + 1 中型框；MEDIUM（50）为 1 + 2 + 4；HIGH（100）为 1 + 3 + 9。默认 45 为 1 + 2 + 4。纯色或极小图片可以减少微型框。微型候选来自图像结构，不在全画面均匀随机撒布。

中、微型框会抑制近中心、严重重叠和包含关系过强的候选：IoU ≥ 0.32、相交面积 / 较小框面积 ≥ 0.68，或按平均宽高归一化的中心距离 < 0.65，满足任一条件就跳过。允许少量交叠，优先分配到不同局部细节。

界面固定随机种子为 **0**，没有额外的种子控件。同一入口内，相同输入、Structure 和种子产生相同结果；调高密度会延续同一个微型候选序列。Python 调用时可显式指定 `seed`：

```python
from PIL import Image
from processor import process_image, detect_layers, resize_image

with Image.open("test_images/detection_01.jpg") as source:
    original = resize_image(source)
    layers = detect_layers(original, structure=45, seed=0)
    result = process_image(original, structure=45, seed=0)
    result.save("outputs/detection_01_build_02_1_s045.png")
    print({name: len(boxes) for name, boxes in layers.items()})
```

不调用在线 API，不下载模型，不使用 GPU / CUDA；首次安装 Python 依赖需要联网，正常处理图片完全在本地完成。没有文字叠加、滤镜、Glitch、颜色选择或后续模式。

## 直接打开 HTML

只需下载 **`image-observer-v1.html`** 一个文件：

1. 在 GitHub 的 `build-02-1` 分支打开该文件，点击右上角 **Download raw file**（下载箭头）。
2. 保存后，用 Chrome 或 Edge 打开 `.html` 文件。
3. 上传图片，拖动 Structure 查看不同疏密。

HTML 内嵌全部样式与检测逻辑，无需 Python、服务器或网络，图片保留在当前浏览器中。输出图可右键另存为图片。

### Structure=45 的双入口差异核查

Build 02 的两份源码来自同一提交，HTML 和 Python 的界面固定 Seed 都为 0，LCG 常数也相同；差异来自独立的图像处理路径：

- Python：最长边 512px 的分析图、Pillow LANCZOS 缩放、OpenCV Gaussian / Sobel / Lab 特征。
- HTML：最长边 480px 的分析图、Canvas 缩放、JavaScript box blur / RGB 特征。
- Build 02 的 Python 中型框为 2px，而 HTML 为 1px；Build 02.1 已统一为 1px。

Build 02.1 的版本标记、固定 Seed、密度公式和重复框抑制规则一致；45 时两个入口都以 1 主框 + 2 中型框 + 4 微型框为目标。主检测路径保持原有实现，因此跨入口的框坐标和原图解码像素仍可能不同；同一入口内相同输入、参数和 Seed 会重复得到相同结果。没有把坐标差异误归因为 Seed，也没有为了逐像素一致重写检测模型。

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

## 两张测试图和保存输出（Build 02.1）

- `test_images/detection_01.jpg`：人像。
- `test_images/detection_02.jpg`：牛图。

| 原图 | LOW · 0 | MEDIUM · 50 | HIGH · 100 |
| --- | --- | --- | --- |
| 人像 | [查看](outputs/detection_01_build_02_1_s000.png) | [查看](outputs/detection_01_build_02_1_s050.png) | [查看](outputs/detection_01_build_02_1_s100.png) |
| 牛图 | [查看](outputs/detection_02_build_02_1_s000.png) | [查看](outputs/detection_02_build_02_1_s050.png) | [查看](outputs/detection_02_build_02_1_s100.png) |

依次上传两张图，在 Structure **0、50、100** 比较：主框一致，低值稀疏，高值出现更多大小及宽高比不同的局部微框。重复设置同一个值应得到同样的框选结果。

在 Windows 项目目录，可一次保存两张图的三个 Structure 输出：

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from PIL import Image; from processor import process_image; out = Path('outputs'); out.mkdir(exist_ok=True); [process_image(Image.open(p), structure=s, seed=0).save(out / (p.stem + '_build_02_1_python_s' + str(s).zfill(3) + '.png')) for p in sorted(Path('test_images').glob('detection_0*.jpg')) for s in (0, 50, 100)]"
```

`outputs/` 中本轮保存的 6 张 `*_build_02_1_s000/s050/s100.png` 来自独立 HTML，分别对应人像与牛图的三个密度。旧 Build 02 输出保留用于对照；Python 使用同样两张图核查密度、去重和确定性，另对 45 做路径差异诊断。

## 处理与边界

Pillow 校正 EXIF 方向，保持原比例将最长边限制在 1600px，小图不放大。透明 PNG 使用白底合成。主框继续依据低频颜色显著性、背景颜色统计、连通性、填充率和环带对比评分，并抑制重复纹理及近黑背景。

微型框只在主框附近的候选范围内根据局部结构生成，再用局部随机种子改变候选顺序、大小与宽高比，避免全图散点。蓝线按层级绘制，微型框使用细线。检测不代表准确物体识别。

纯色图、极小图和分析异常有稳定回退。极小或极端长宽比图片可能无法同时满足面积、形状和整数像素约束，允许框重叠或减少微型框，以保证输出有效。

本轮只用两张原图验证 Structure 0 / 50 / 100 的数量、相同 Seed 的可重复性、框序列前缀、重复框筛选、图内边界、固定蓝色和主框不漂移。HTML 通过实际加载、断网后的上传与滑杆、窄屏预览及 LOW 异常回退检查。45 只用于两入口路径诊断，没有额外保存该参数的图片。

运行验证在 Python 3.12 和 Chromium 中执行；本轮优先交付独立 HTML，没有新增安装文件或平台启动脚本。

```text
image-observer-v1.html # 可独立、离线打开的浏览器版本
app.py                # 上传、Structure 与本地 Gradio 页面
processor.py          # 图像分析、三级矩形与绘制
requirements.txt      # 已验证的直接依赖版本
test_images/          # 原图与合成示例
outputs/              # 本地输出及本轮保存的示例
```

Linux / macOS 使用 Python 3.12 创建 `.venv` 后，将 Windows 命令中的 `.\.venv\Scripts\python.exe` 换成 `.venv/bin/python`。
