"""image-observer-v1: local, CPU-only Detection Build 02.2."""

import math
import os
import warnings
from pathlib import Path

# Disable Gradio telemetry; image processing never needs an Internet connection.
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

import gradio as gr
from PIL import Image, UnidentifiedImageError

from processor import process_image, resize_image


def detect_upload(
    path: str | None, structure: float = 45
) -> tuple[Image.Image | None, Image.Image | None]:
    """Validate the actual file format and return the resized original and overlay."""
    if not path:
        return None, None
    try:
        with warnings.catch_warnings():
            # Reject unexpectedly huge files before allocating their decoded pixels.
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(Path(path)) as uploaded:
                if uploaded.format not in {"JPEG", "PNG"}:
                    raise gr.Error("请上传 JPG 或 PNG 图片。")
                original = resize_image(uploaded)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise gr.Error("图片像素过大，请先缩小后再上传。") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise gr.Error("无法读取图片，请使用完整的 JPG 或 PNG 文件。") from exc

    return original, process_image(original, structure=structure, seed=0)


def upload_image(path: str | None, structure: float):
    """A new upload always starts in automatic mode, including the same file."""
    # Clear the previous session image/focus before decoding a potentially bad file.
    yield None, None, None, None
    original, result = detect_upload(path, structure)
    yield original, result, original, None


def render_structure(image: Image.Image | None, structure: float, focus):
    """Structure changes keep this session's selected output-pixel focus."""
    return None if image is None else process_image(image, structure, seed=0, focus=focus)


def select_focus(image: Image.Image | None, structure: float, evt: gr.SelectData):
    if image is None:
        return None, None
    try:
        x, y = map(float, evt.index)
        if not (math.isfinite(x) and math.isfinite(y)):
            return gr.skip(), gr.skip()
    except (TypeError, ValueError):
        return gr.skip(), gr.skip()
    # Gradio 6 Image.select accounts for object-fit and preview scale itself.
    # The displayed original is already resized/oriented; do not scale evt.index again.
    focus = (max(0, min(image.width - 1, round(x))),
             max(0, min(image.height - 1, round(y))))
    return focus, process_image(image, structure, seed=0, focus=focus)


def reset_focus(image: Image.Image | None, structure: float):
    return None, render_structure(image, structure, None)


def create_app() -> gr.Blocks:
    with gr.Blocks(title="image-observer-v1 · Detection Build 02.2", analytics_enabled=False) as demo:
        # Gradio owns these per-session values; no module-global image or focus.
        image_state = gr.State(value=None)
        focus_state = gr.State(value=None)
        upload = gr.File(
            label="上传图片 · JPG / PNG",
            file_types=[".jpg", ".jpeg", ".png"],
            file_count="single",
            type="filepath",
        )
        structure = gr.Slider(
            minimum=0, maximum=100, value=45, step=1, label="Structure", interactive=True,
            elem_id="structure",
        )
        reset = gr.Button("Reset Focus / 恢复自动", elem_id="reset-focus")
        with gr.Row():
            original = gr.Image(label="原图 · 点击指定 Focus", interactive=False,
                                format="png", buttons=["download", "fullscreen"],
                                elem_id="original")
            detection = gr.Image(label="Detection · Build 02.2", interactive=False,
                                 format="png", buttons=["download", "fullscreen"],
                                 elem_id="detection")
        # All callbacks share a single CPU queue. Only the most recent pending
        # event of each type is retained when the user clicks/drags rapidly.
        event_options = dict(
            api_visibility="private",
            trigger_mode="always_last",
            concurrency_limit=1,
            concurrency_id="image-observer-processing",
            show_progress="minimal",
        )
        upload.change(
            upload_image, inputs=[upload, structure],
            outputs=[original, detection, image_state, focus_state], **event_options,
        )
        structure.change(
            render_structure, inputs=[image_state, structure, focus_state],
            outputs=detection, **event_options,
        )
        original.select(
            select_focus, inputs=[image_state, structure],
            outputs=[focus_state, detection], **event_options,
        )
        reset.click(
            reset_focus, inputs=[image_state, structure],
            outputs=[focus_state, detection], **event_options,
        )
    return demo


if __name__ == "__main__":
    create_app().launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=False,
        show_error=True,
        enable_monitoring=False,
        footer_links=[],
    )
