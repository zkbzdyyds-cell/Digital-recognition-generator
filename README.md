# IMAGE OBSERVER · BUILD 02.3

Image Observer V1 的唯一正式路线为 **HTML + CSS + JavaScript / Canvas**。本轮以 HTML Build 02.2 为稳定基线，补齐线宽与英文情绪标签；检测算法未改。所有图像处理在当前浏览器进行，无 Python、Gradio、在线 API、模型、前端框架或安装步骤。

**当前尚未部署 GitHub Pages，没有正式网站地址。** 先验收本轮功能与视觉结果，验收后再部署同一个固定网站。

## 运行与下载

正式入口是仓库根目录的 **`image-observer-v1.html`**，顶部和浏览器标签页均显示 **IMAGE OBSERVER · BUILD 02.3**。HTML 内包含全部可读 CSS / JavaScript，没有需要额外下载的依赖文件。

- [下载 HTML 02.3 完整运行源码包](outputs/Image-Observer-HTML-Build-02.3.zip)：全部解压后，用 Chrome / Edge 打开 **`Image-Observer-Build-02.3.html`**。
- 单独下载 HTML 时，在 GitHub 文件页选择 **Download raw file**，保存为 `.html`，再用浏览器打开。GitHub 文件预览页本身不运行网页。
- [查看人像与牛图视觉对比及验收记录](outputs/html_build_02_3_validation.md)。

运行包只含本轮 HTML、简明说明和版本清单，不混入旧 HTML、Python、BAT 或历史 ZIP。下载的 HTML 就是完整应用源代码；解压打开即可试用。

## 本轮功能

- **Structure**：0–100，默认 45；0 / 50 / 100 对应约 2 / 7 / 13 个框，沿用原有规则与抑制逻辑。
- **Focus**：点击原图指定视觉重心；Reset Focus 恢复自动。调整 Structure 保留 Focus，上传新图片清除 Focus。
- **Stroke Width**：Thin 1px / Medium 2px（默认）/ Thick 4px，所有层级统一响应，线条向框内绘制。
- **Labels**：Off / Emotion Pool（默认）/ Custom Text。
- **Emotion Pool**：准确 30 个既定大写英文词，不包含 DESIRE。每张画面只使用一个词，仅在主框和中框重复显示，微框无字。
- **Shuffle Word**：每次换成不同词；只推进独立词语状态，不重新检测或更改 Structure / Focus / 线宽。切换模式后回到 Pool 恢复此前单词。
- **Custom Text**：最多 32 个字符，英文字母自动大写，可输入短语、空格、连字符和撇号。微型框不显示文字，空文本不绘字。
- **下载 PNG**：保存按钮点击时的实际画布，尺寸与预览的内在像素一致；预览 CSS 缩放不会改变导出尺寸。

标签使用系统本地无衬线字体，优先避让边缘和其他标签；必要时隐藏次要中框文字。极小图片可能没有足够空间显示标签。没有溢墨、Grain、Blur、Fragment、其他颜色或 Build 02.4 内容。

## 尺寸与可重复性

保持完整原比例，最长边超过 1600px 时等比例缩小；小图不放大，不裁切、补边或拉伸。透明 PNG 保持既有白底合成方式。图片解码和分析路径沿用 HTML 02.2。

Detection 使用固定 Seed=0。词语使用独立的图像像素摘要与确定性随机流；相同图片、参数、Focus 及操作顺序在同一浏览器可重复。只有新图初始化和主动 Shuffle 推进词语状态。线宽、标签模式和输入文字只调用 Overlay，完全不调用 Detection。

HTML 以自身 Build 02.2 为基线，不保证与已归档 Python/OpenCV 输出相同。不同浏览器或操作系统的字体、图片解码、缩放和抗锯齿可能造成像素差异。超大原图仍先由浏览器解码，可能受到设备内存限制；本轮没有改写该既有路径。

## 简单验收

1. 打开 HTML，上传 `test_images/detection_01.jpg`（人像）或 `detection_02.jpg`（牛）。
2. Structure 设为 50，在原图点一个 Focus。
3. 试 Thin + Off、Medium + Emotion Pool、Thick + Custom Text，输入 `melancholy`。
4. 切回 Emotion Pool，连续点击三次 Shuffle。标签统一换词，框的位置、大小和数量应不变。
5. 调整 Structure、再次点击 Focus，然后 Reset；最后点击下载 PNG。

| 测试图 | 输入 | 输出 |
| --- | --- | --- |
| detection_01 人像 | 909×1447 | 909×1447 |
| detection_02 牛 | 1930×1280 | 1600×1061 |

## 代码职责与历史

单一 HTML 内分三段：既有 `ObserverDetector` 负责检测和框后处理；`ObserverOverlay` 负责线宽、词语状态与标签排版绘制；页面事件负责上传、Focus、Structure、缓存框和 PNG 保存。只有图片 / Focus / Structure 事件刷新框数据。

`archive/image-observer-html-build-02.2.html` 保留稳定基线；对应 Git 恢复点为 `24521bacb8cfcfb3bddf1358da224002d12be055`。Python Build 02.3 和未部署 Render 草稿已归档，详见 [归档说明](archive/README.md)。根目录遗留 Python 文件只作历史保留，不是本轮入口，也不再维护。

后续只在本项目继续迭代 HTML。GitHub Pages 部署、固定网址和下一版本均等待用户验收后再进行。
