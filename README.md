# image-observer-v1 — Detection Build 01

## Build 01.1：主体附近的框选修正

此版本仅调整 Detection 的候选评分和筛选，HTML / Gradio 的页面与操作保持不变。

- 主框更看重相对背景颜色的显著性、区域连通性、填充率和周围环带对比，降低单纯边缘密度的影响。
- 对重复细纹理、近黑背景、过大、贴边和细长候选降权。颜色统计不绑定肤色或某张图片中的固定位置。
- 辅助框中心位于主框内，至少 80% 面积位于主框向外扩展 10% 的邻域；不足时在主框内补充局部窗口，仍为 2–4 个。
- 蓝色线框、1600px 尺寸限制、纯本地 CPU 运算和异常 fallback 保持原有行为。

开发回归使用确定性合成场景检查了强纹理背景中的主体、主体平移、暗背景中的平滑区域以及辅助框与主框的邻近关系。用户给出的 `detection_01` / `detection_02` 目前仅以聊天预览图可见，尚未获得可读取的原图文件，因此这两张图的新版结果仍待原图复跑；合成回归不代表已验证这两张照片。

## 直接打开 HTML（无需安装）

**只想查看并使用工具，请下载 `image-observer-v1.html` 这一个文件。**

1. 在 GitHub 的 `build-01` 分支打开 `image-observer-v1.html`，点击文件右上角 **Download raw file**（下载箭头）。
2. 保存后，用 Chrome 或 Edge 双击打开这个 `.html` 文件；无需解压整个项目、安装 Python、执行命令或启动服务器。
3. 点击上传区或拖入一张 JPG / PNG，页面会显示原图和蓝色矩形输出图。

HTML 内已包含全部样式和检测逻辑，可以断网使用，不加载 CDN、在线 API、模型或外部资源。图片留在当前浏览器中。结果图可以右键另存为图片。

这个入口用浏览器原生 JavaScript / Canvas 实现 CPU 图像分析，以支持直接打开文件。它是 Build 01 的独立浏览器实现，不依赖 Python / Gradio 服务；框的位置与下面的 Python 实现不要求逐像素相同。功能仍只有 Detection Build 01：原比例缩放至最长边 1600px、1 个主框和 2–4 个辅助框、结构依据、面积和形状约束、稳定 fallback、统一蓝色细线。

浏览器版已在 Chromium 断网状态下加载完整 HTML 内容进行验证：两张示例、重复输入、1600px 缩放、透明图、1px 小图、EXIF 方向、异常回退及窄屏布局均通过，未发起 HTTP 请求。未在 Windows 主机上实测。

## Python / Gradio 版本

本地 CPU 图像效果原型。上传 JPG / PNG 后自动生成 **1 个 Main Box + 2–4 个 Auxiliary Boxes**，统一使用高饱和蓝色细线；不绘制文字。这里的矩形表达图像信息分布，不是物体识别结果。

仅使用 Python、Gradio、OpenCV、Pillow、NumPy。不调用在线 API，不下载模型，不使用 GPU / CUDA。首次安装依赖需要联网，安装完成后运行与处理图片不需要互联网；Gradio 遥测与公开分享已关闭。

## Windows 安装与启动

1. 安装 **64 位 Python 3.12**（当前验证版本为 3.12），并安装 Windows Python Launcher。打开 PowerShell，进入包含 `app.py` 的项目目录，例如：

   ```powershell
   cd C:\projects\Digital-recognition-generator
   ```

2. 创建虚拟环境并安装依赖。直接使用虚拟环境中的 Python，无需激活，也无需修改 PowerShell 执行策略：

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m pip check
   ```

   `opencv-python-headless` 是不包含桌面窗口组件的 OpenCV；本项目在浏览器显示图片，因此无需额外安装 `opencv-python`。

3. 启动：

   ```powershell
   .\.venv\Scripts\python.exe app.py
   ```

4. 在**运行程序的同一台电脑**打开浏览器，访问 `http://127.0.0.1:7860`。上传图片后，页面自动显示原图和 Detection 输出。停止时在终端按 `Ctrl+C`。

如果没有 `py` 命令，可以用已安装的 Python 3.12 的完整路径替代 `py -3.12`。若 7860 已被占用，先关闭占用该端口的旧实例。

## 测试 Build 01

依次上传随项目提供的两张原创合成测试图：

- `test_images/desk.png`：横向桌面场景，包含集中分布的屏幕细节和杯子轮廓。
- `test_images/building.jpg`：纵向建筑场景，包含重复窗格、建筑轮廓和局部高对比区域。

应看到两张图都生成蓝色矩形，位置随结构变化；重复上传同一图片应得到相同结果。原图区域显示经过方向校正和尺寸限制的未画框图片，输出图尺寸与之相同。

也可以用自己的照片检查：

- 上传最长边超过 1600px 的图片，下载结果后确认最长边不超过 1600px，宽高比例保持一致（整数像素会有舍入）。
- 上传纯色、低对比度或透明 PNG，确认仍有稳定输出；透明部分按白底合成。
- 清除上传内容后，两张展示图也会清空。

开发验证在 Linux + Python 3.12 下完成：两张示例经过实际 Gradio 上传 / 队列处理 / 下载验证；另检查了缩放、EXIF、重复输入、透明图、纯色 / 极小图和分析异常回退。Windows 安装步骤已提供，未在 Windows 主机上实测。

点击 Gradio 输出图的下载按钮可以保存图片。若想直接将两张示例的结果保存到 `outputs/`，在项目目录执行：

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from PIL import Image; from processor import process_image; out = Path('outputs'); out.mkdir(exist_ok=True); [process_image(Image.open(p)).save(out / (p.stem + '_detection.png')) for p in Path('test_images').iterdir() if p.suffix.lower() in ('.jpg', '.png')]"
```

## 处理方式与边界

1. Pillow 修正 EXIF 方向，按原比例将最长边缩小至不超过 1600px，小图不放大。
2. 在最长边不超过 512px 的分析副本上，组合边框颜色统计、低频色彩显著性和少量细边缘支持，对重复纹理及近黑背景降权。
3. 从连通区域与显著性峰值生成候选框，按显著性集中度、连通性、填充率、周围环带对比评分，并惩罚过大、贴边及细长区域。辅助框仅从主框内部或近邻筛选，去除过度重复的结果。
4. Main Box 面积约束为画面面积的 8%–80%，宽高比限制约为 1:3.5–3.5:1；辅助框较小。最后映射回输出尺寸，使用 RGB `(0, 80, 255)` 的 1–2px 蓝线绘制。
5. 纯色图或分析异常使用固定、可重复的 fallback。极小图片或极端长宽比可能无法同时满足面积、宽高比和整数像素约束，此时优先保证框位于图内、输出非空；1px 之类的图片会有重叠框。

仅实现 Detection Build 01；没有文字叠加、Grain、Mono、Glitch、颜色设置或后续模式。无须任何 API 密钥或模型文件。

## 文件

```text
image-observer-v1.html # 可独立、离线打开的完整浏览器版本
app.py             # 上传校验与本地 Gradio 页面
processor.py       # 缩放、结构分析、矩形选择与绘制
requirements.txt   # 已验证的直接依赖版本
test_images/       # 两张测试输入
outputs/           # 本地生成结果（Git 忽略）
```

Linux / macOS 同样可使用 Python 3.12：创建 `.venv` 后，将上述 `.\.venv\Scripts\python.exe` 换成 `.venv/bin/python`。
