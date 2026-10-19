# image-observer-v1 — Detection Build 01

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
2. 在最长边不超过 512px 的分析副本上，用 OpenCV 组合边缘强度、局部亮度对比和 Lab 色彩中心 / 周边对比。
3. 从轮廓与空间分离的信息峰值生成候选框，按信息覆盖程度与面积评分，去除过度重复的辅助框。
4. Main Box 面积约束为画面面积的 8%–80%，宽高比限制约为 1:3.5–3.5:1；辅助框较小。最后映射回输出尺寸，使用 RGB `(0, 80, 255)` 的 1–2px 蓝线绘制。
5. 纯色图或分析异常使用固定、可重复的 fallback。极小图片或极端长宽比可能无法同时满足面积、宽高比和整数像素约束，此时优先保证框位于图内、输出非空；1px 之类的图片会有重叠框。

仅实现 Detection Build 01；没有文字叠加、Grain、Mono、Glitch、颜色设置或后续模式。无须任何 API 密钥或模型文件。

## 文件

```text
app.py             # 上传校验与本地 Gradio 页面
processor.py       # 缩放、结构分析、矩形选择与绘制
requirements.txt   # 已验证的直接依赖版本
test_images/       # 两张测试输入
outputs/           # 本地生成结果（Git 忽略）
```

Linux / macOS 同样可使用 Python 3.12：创建 `.venv` 后，将上述 `.\.venv\Scripts\python.exe` 换成 `.venv/bin/python`。
