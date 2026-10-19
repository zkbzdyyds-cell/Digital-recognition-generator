"""image-observer-v1: local, CPU-only Detection Build 02."""

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


def create_app() -> gr.Blocks:
    with gr.Blocks(title="image-observer-v1 · Detection Build 02", analytics_enabled=False) as demo:
        upload = gr.File(
            label="上传图片 · JPG / PNG",
            file_types=[".jpg", ".jpeg", ".png"],
            file_count="single",
            type="filepath",
        )
        structure = gr.Slider(
            minimum=0, maximum=100, value=45, step=1, label="Structure", interactive=True
        )
        with gr.Row():
            original = gr.Image(label="原图", interactive=False, format="png")
            detection = gr.Image(label="Detection · Build 02", interactive=False, format="png")
        # Share one queue for upload/slider changes; keep only the latest pending
        # value when a user drags quickly on a CPU-only Windows machine.
        gr.on(
            triggers=[upload.change, structure.change],
            fn=detect_upload,
            inputs=[upload, structure],
            outputs=[original, detection],
            api_visibility="private",
            trigger_mode="always_last",
            concurrency_limit=1,
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
