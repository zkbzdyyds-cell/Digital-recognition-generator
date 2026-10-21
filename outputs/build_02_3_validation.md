# Image Observer — Build 02.3 验收记录

状态：功能完成，等待用户验收。架构锁定为一个 Python 处理核心 + Gradio 网页入口；独立 HTML 保留在 Build 02.2，不删除、不更新。未发布云环境或网站，未推送远程仓库。

## 本轮范围与文件

- `processor.py`：增加三档线宽、准确 30 词常量、独立词语状态、本地 Pillow 字体与标签布局，以及 `render_overlay()`。原有检测、筛选和尺寸函数不变。
- `app.py`：新增线宽、标签模式、自定义文本、Shuffle；用会话内原图 / Focus / 框 / 词语四个 State 隔离数据。
- `test_build_02_3.py`：线宽、词库、边界、缓存与实际 UI 回调回归；旧 `test_build_02_2.py` 的纯蓝线像素检查显式使用 Labels Off。
- `README.md`：单一路线、启动与验收说明。`outputs/`：本轮 12 张 PNG、报告和下载包。
- `requirements.txt` 和独立 HTML 未修改，无新依赖、模型或字体下载。

## 稳定恢复点

Build 02.2 提交 `24521bacb8cfcfb3bddf1358da224002d12be055` 保留在 `build-02-2` 与本地 `backup/build-02-2-24521ba`。另有 [02.2 源码备份 ZIP](image-observer-build-02-2-source-backup.zip)，已逐文件验证与该提交一致。

## 测试输入

| 测试图 | 输入像素 | 输出像素 | 固定 Focus（输出像素） |
| --- | --- | --- | --- |
| detection_01 / 人像 | 909 × 1447 | 909 × 1447 | (429, 518) |
| detection_02 / 牛图 | 1930 × 1280 | 1600 × 1061 | (746, 507) |

两张图均为 Structure=50、Detection Seed=0，框数量保持 1 主框 + 2 中型框 + 4 微型框。Focus 由真实鼠标事件映射至输出像素，一张图的全部 A–E 操作使用同一焦点。短边只作整数取整，未裁切、拉伸、补边或放大小图。

## A / B / C 输出

| 图片 | A：Thin 1px / Off | B：Medium 2px / Emotion Pool | C：Thick 4px / Custom Text |
| --- | --- | --- | --- |
| 人像 | [PNG](detection_01_portrait_build_02_3_gradio_s050_focus_x0429_y0518_A_thin_off.png) | [REGRET](detection_01_portrait_build_02_3_gradio_s050_focus_x0429_y0518_B_medium_emotion_pool.png) | [MELANCHOLY](detection_01_portrait_build_02_3_gradio_s050_focus_x0429_y0518_C_thick_custom_melancholy.png) |
| 牛图 | [PNG](detection_02_cow_build_02_3_gradio_s050_focus_x0746_y0507_A_thin_off.png) | [ENVY](detection_02_cow_build_02_3_gradio_s050_focus_x0746_y0507_B_medium_emotion_pool.png) | [MELANCHOLY](detection_02_cow_build_02_3_gradio_s050_focus_x0746_y0507_C_thick_custom_melancholy.png) |

A 无文字；B 每张图只选一个情绪词；C 全部可见标签统一为 MELANCHOLY。两图 B / C 均显示主框与两个中型框的同词标签，微型框不显示文字。所有层级均响应 1 / 2 / 4px，向内绘制以防溢出。

## D：连续三次换词

| 图片 | 初始词 | 第一次 | 第二次 | 第三次 |
| --- | --- | --- | --- | --- |
| 人像 | REGRET | [AFFECTION](detection_01_portrait_build_02_3_gradio_s050_focus_x0429_y0518_D_medium_pool_shuffle_1.png) | [LONELINESS](detection_01_portrait_build_02_3_gradio_s050_focus_x0429_y0518_D_medium_pool_shuffle_2.png) | [FEAR](detection_01_portrait_build_02_3_gradio_s050_focus_x0429_y0518_D_medium_pool_shuffle_3.png) |
| 牛图 | ENVY | [AFFECTION](detection_02_cow_build_02_3_gradio_s050_focus_x0746_y0507_D_medium_pool_shuffle_1.png) | [GRATITUDE](detection_02_cow_build_02_3_gradio_s050_focus_x0746_y0507_D_medium_pool_shuffle_2.png) | [JOY](detection_02_cow_build_02_3_gradio_s050_focus_x0746_y0507_D_medium_pool_shuffle_3.png) |

每次新词均不同于当前词；主框和中型框同步变化。额外连续快速点击三次也逐次处理，没有吞掉换词操作。随机选择只推进独立词语状态，不改变 Detection Seed、Structure、Focus、线宽或框数据。切回 Emotion Pool 恢复之前的词。

## E：Focus、检测缓存与导出

- 对实际 Gradio 服务的 `detect_layers` 和 Overlay 做临时计数，12 张 A–D 输出中，每张原图的检测次数保持恒定；线宽、模式、自定义文本和换词增加的检测调用数为 **0**。
- 每张原图 6 个输出的框坐标、宽高、数量和 Focus 完全一致。仅上传、Structure、Focus 与 Reset 事件可以重新检测。
- 两个独立浏览器会话的文字、Focus 与缓存框互不影响；Structure 0 / 100 / 50 保留 Focus 和当前词，返回 50 恢复相同框数据。Reset 恢复自动，新图清除旧 Focus。
- 两图均实际点击 Gradio 下载按钮获得 PNG。12 个保存 PNG 与相同框数据、词语和线宽的 Pillow 渲染逐像素一致。
- 输入英文词和短语自动以大写绘制；离开输入框后在浏览器本地显示为大写。修复了快速输入时服务端旧前缀覆盖后续字符的问题，完整 MELANCHOLY 和多词短语均验证通过。
- 自定义文本最长 32 字符，渲染端再次过滤和截断；空文本不绘制文字。字体来自本地，标签边界与碰撞避让验证通过。

## 回归结果与验证边界

- 自动回归 **14 项通过，0 项失败**。命令：`python -m unittest -v test_build_02_2 test_build_02_3`。
- 两图、自动及两处 Focus、Structure 0 / 50 / 100 共 18 组框数据与 Build 02.2 一致；16 个既有缩放 / 检测 / 筛选函数 AST 不变。
- 真实页面 A–E、默认 Medium / Pool、标签模式切换、切回 Pool 恢复原词、快速换词、Reset、原图更新清 Focus、PNG 下载均通过；页面 JavaScript 错误和外部网络请求均为空。
- 标签在主 / 中框之间优先避让，必要时隐藏次要标签；纯色或极小图的框及文字边界回退保留。局部字体会随操作系统有所不同。
- A–E 未发现验收失败项。运行环境为 Linux / Python 3.12 / Gradio 6.30 / Chromium，**未在 Windows 实机测试**；依赖和启动方式沿用现有项目。
- 补充真实剪贴板验收通过：Ctrl+V 粘贴 80 字符，原生输入限制为 32 字符，字段与输出均为 32 个大写 A。将自定义文本绑定从 keypress 型 Input 改为 Change，覆盖粘贴 / 自动填充；不回传服务端旧前缀，仍只重绘 Overlay。

## 在现有本地页面验收

停止旧实例后，使用原虚拟环境运行 `app.py`，刷新页面并确认标题为 Build 02.3；无需重新安装依赖。依次上传人像与牛图，设置 Structure=50，点击 Focus，再完成 A / B / C / D 操作。检查框不动、可见标签同词、三次换词均改变，最后下载 PNG。验收后再决定下一 Build，本轮不进入 02.4。

[查看 A/B/C 对比预览](build_02_3_comparison.png) · [下载 12 张结果 PNG ZIP](image-observer-build-02-3-test-results.zip) · [Build 02.3 源码包](image-observer-build-02-3-source.zip) · [机器可读记录](build_02_3_validation.json)
