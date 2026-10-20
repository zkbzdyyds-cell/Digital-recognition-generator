# Image Observer — Build 02.2 验收记录

本轮在原项目上增加点击 Focus 与恢复自动，保留固定蓝色、三级框、Structure 和最多 13 框。下面 14 张 PNG 均由真实 Gradio 页面生成及下载，逐张与处理器输出像素核对一致。固定 Seed = 0。

## 输入、输出及命名

| 编号 | 内容 | 输入像素 | 输出像素 |
| --- | --- | --- | --- |
| detection_01 | 人像 | 909 × 1447 | 909 × 1447 |
| detection_02 | 牛 | 1930 × 1280 | 1600 × 1061 |

已检查图片内容，01 / 02 没有颠倒，未改名。预览原图与 Detection 导出画布尺寸一致；只有牛图执行等比缩小，短边取整误差约 0.14px。没有裁切、补边、扩展画布或拉伸。

## Structure 50 比较

坐标均为**已显示原图 / 输出 PNG 的像素坐标**，左上角为 (0,0)。主框格式为 (left, top, right, bottom)，右、下边界不包含在框内。

| 图片 | Focus | 实际点击坐标 | 主框 | PNG |
| --- | --- | --- | --- | --- |
| 人像 | 自动 | — | (497, 706, 788, 1071) | [查看](detection_01_portrait_build_02_2_gradio_s050_focus_auto.png) |
| 人像 | 脸部 | (429, 519) | (299, 333, 568, 729) | [查看](detection_01_portrait_build_02_2_gradio_s050_focus_face_x0429_y0519.png) |
| 人像 | 膝盖 | (529, 949) | (454, 743, 714, 1153) | [查看](detection_01_portrait_build_02_2_gradio_s050_focus_knee_x0529_y0949.png) |
| 牛图 | 自动 | — | (791, 355, 1466, 802) | [查看](detection_02_cow_build_02_2_gradio_s050_focus_auto.png) |
| 牛图 | 牛头 | (749, 509) | (521, 359, 975, 662) | [查看](detection_02_cow_build_02_2_gradio_s050_focus_head_x0749_y0509.png) |
| 牛图 | 牛身 | (1199, 648) | (971, 496, 1425, 799) | [查看](detection_02_cow_build_02_2_gradio_s050_focus_body_x1199_y0648.png) |

六张结果均为 1 主框 + 2 中型框 + 4 微型框。人像点击脸部与膝盖、牛图点击头与身时，主框均发生变化并覆盖点击点，中微框跟随新的局部结构。保留原自动路径；Reset 恢复该路径的逐像素相同结果。

## Structure 0 / 100 点击 Focus

| 图片 / Focus | 坐标 | Structure 0：1 + 1 + 0 | Structure 100：1 + 3 + 9 |
| --- | --- | --- | --- |
| 人像 / 脸部 | (429, 519) | [查看](detection_01_portrait_build_02_2_gradio_s000_focus_face_x0429_y0519.png) | [查看](detection_01_portrait_build_02_2_gradio_s100_focus_face_x0429_y0519.png) |
| 人像 / 膝盖 | (529, 949) | [查看](detection_01_portrait_build_02_2_gradio_s000_focus_knee_x0529_y0949.png) | [查看](detection_01_portrait_build_02_2_gradio_s100_focus_knee_x0529_y0949.png) |
| 牛图 / 牛头 | (749, 509) | [查看](detection_02_cow_build_02_2_gradio_s000_focus_head_x0749_y0509.png) | [查看](detection_02_cow_build_02_2_gradio_s100_focus_head_x0749_y0509.png) |
| 牛图 / 牛身 | (1199, 648) | [查看](detection_02_cow_build_02_2_gradio_s000_focus_body_x1199_y0648.png) | [查看](detection_02_cow_build_02_2_gradio_s100_focus_body_x1199_y0648.png) |

四处 Focus 在 0 / 50 / 100 的主框一致，Structure 只改变框数量。全部框在图内；同级中型、微型框保留原有重复抑制。

## 点击、会话与下载

- Gradio Image.select 已处理预览缩放及居中留白，直接使用 evt.index，不重复缩放。HTML 将原图 canvas 的 CSS 点击位置换算为其实际像素，再换算至分析图。
- 以真实鼠标 clientX / clientY 与实际 DOM 边界独立计算，返回坐标一致。桌面及 390px 窄屏均验证。浏览器把鼠标位置取整到 CSS 像素，因此测试意图 (430,520) 实际落在 (429,519)；牛身意图 (1200,650) 实际为 (1199,648)。这是鼠标精度差异，未出现坐标偏移。文件名采用实际收到的坐标。
- 点击后调整 Structure 保留焦点；再次点击更换焦点；上传新图清除焦点；Reset 恢复自动。两个独立浏览器会话分别保存自己的图像与焦点。
- 两张图均实际点击 Gradio Download 下载 PNG，下载像素尺寸正确；14 张保存文件与同参数处理器结果逐像素相同。相同焦点重复点击，PNG 字节相同。
- HTML 实际浏览器 PNG 导出通过，分别为 909×1447 与 1600×1061；离线上传、Focus、Reset、Structure 均通过。

## 自动尺寸验证

运行 `python -m unittest -v test_build_02_2`：6 项通过、0 项失败。补充对实际 HTML 上传六组横竖方图并断网验证，输出与独立全图缩放参考逐像素一致。

| 输入像素 | 输出像素（Python / HTML） |
| --- | --- |
| 3001 × 1999 | 1600 × 1066 |
| 1999 × 3001 | 1066 × 1600 |
| 2049 × 2049 | 1600 × 1600 |
| 321 × 179 | 321 × 179 |
| 179 × 321 | 179 × 321 |
| 257 × 257 | 257 × 257 |

另验证 EXIF 方向 6 / 8 只校正一次、1600px 边界不放大、叠加只更改蓝线像素，以及超过 1600px 的源图 Focus 坐标到输出像素的映射。

## 异常与验证边界

- 本轮未发现未处理异常。纯色、近黑、1×1、极窄图片及边角 Focus 有有效回退，主框覆盖焦点且不越界；细节不足时可以减少微型框。极端长宽比不能始终同时满足面积、形状和整数像素约束。
- 损坏 JPG 与伪装为 JPG 的 GIF 会给出明确错误；新上传在读取前先清除旧图和旧焦点。像素超大的文件保留 Pillow 解压炸弹保护，提示先缩小后上传。
- 实际环境为 Linux / Python 3.12 / Gradio 6.30 / Chromium，未在 Windows 实机测试。Windows 安装启动方式沿用 README，无新增依赖或平台文件。
- 云浏览器禁止 file:// 导航，因此测试通过临时本地 HTTP 加载同一 HTML，然后断网完成处理；不将这一过程表述为 file:// 实测。
- HTML 与 Python 保留原有独立分析路径，跨入口框坐标可能不同；同一入口相同输入、Structure、Focus、Seed 的输出可重复。

[机器可读验证记录](build_02_2_validation.json) · [14 张结果图 ZIP](image-observer-build-02-2-test-results.zip)
