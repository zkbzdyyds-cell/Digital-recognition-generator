"""image-observer-v1: local, CPU-only Detection Build 02.3."""

import hashlib
import math
import os
import warnings
from pathlib import Path

# Disable telemetry; processing and fonts remain local.
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

import gradio as gr
from PIL import Image, UnidentifiedImageError

from processor import (
    LABEL_MODES, STROKE_WIDTHS, clean_custom_text, create_word_state,
    detect_layers, render_overlay, resize_image, shuffle_word,
)


def read_upload(path: str | None) -> Image.Image | None:
    """Validate the actual file format, orient once and cap at 1600px."""
    if not path:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(Path(path)) as uploaded:
                if uploaded.format not in {"JPEG", "PNG"}:
                    raise gr.Error("请上传 JPG 或 PNG 图片。")
                return resize_image(uploaded)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise gr.Error("图片像素过大，请先缩小后再上传。") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise gr.Error("无法读取图片，请使用完整的 JPG 或 PNG 文件。") from exc


def redraw_overlay(image, layers, stroke_width, label_mode, custom_text, word_state):
    """Use this session's cached boxes; this path never calls Detection."""
    if image is None or layers is None:
        return None
    word = word_state["word"] if word_state else None
    return render_overlay(image, layers, stroke_width=stroke_width,
                          label_mode=label_mode, word=word, custom_text=custom_text)


def update_detection(image, structure, focus, stroke_width, label_mode, custom_text, word_state):
    """Only image / Structure / Focus events need new box data."""
    if image is None:
        return None, None
    layers = detect_layers(image, structure=structure, seed=0, focus=focus)
    result = redraw_overlay(image, layers, stroke_width, label_mode, custom_text, word_state)
    return layers, result


def upload_image(path, structure, stroke_width, label_mode, custom_text):
    # Clear all previous image-bound state even when the new upload is corrupt.
    yield None, None, None, None, None, None
    original = read_upload(path)
    if original is None:
        return
    # Independent, deterministic word stream. New pixels initialize it; Focus,
    # Structure, strokes and label modes never change its state.
    word_seed = int.from_bytes(hashlib.blake2s(original.tobytes(), digest_size=4).digest(), "little")
    words = create_word_state(seed=word_seed)
    layers, result = update_detection(original, structure, None, stroke_width,
                                      label_mode, custom_text, words)
    yield original, result, original, None, layers, words


def select_focus(image, structure, stroke_width, label_mode, custom_text, word_state,
                 evt: gr.SelectData):
    if image is None:
        return None, None, None
    try:
        x, y = map(float, evt.index)
        if not (math.isfinite(x) and math.isfinite(y)):
            return gr.skip(), gr.skip(), gr.skip()
    except (TypeError, ValueError):
        return gr.skip(), gr.skip(), gr.skip()
    # Image.select already maps preview scaling and object-fit to intrinsic
    # pixels. The displayed original is capped/oriented, so do not scale again.
    focus = (max(0, min(image.width - 1, round(x))),
             max(0, min(image.height - 1, round(y))))
    layers, result = update_detection(image, structure, focus, stroke_width,
                                      label_mode, custom_text, word_state)
    return focus, layers, result


def reset_focus(image, structure, stroke_width, label_mode, custom_text, word_state):
    layers, result = update_detection(image, structure, None, stroke_width,
                                      label_mode, custom_text, word_state)
    return None, layers, result


def change_label_mode(image, layers, stroke_width, label_mode, custom_text, word_state):
    result = redraw_overlay(image, layers, stroke_width, label_mode, custom_text, word_state)
    return (gr.update(visible=label_mode == "Custom Text"),
            gr.update(visible=label_mode == "Emotion Pool"), result)


def change_custom_text(image, layers, stroke_width, label_mode, custom_text, word_state):
    text = clean_custom_text(custom_text)
    return redraw_overlay(image, layers, stroke_width, label_mode, text, word_state)


def change_word(image, layers, stroke_width, label_mode, custom_text, word_state):
    # Hidden/queued buttons cannot advance the word stream outside Pool mode.
    if image is None or layers is None or label_mode != "Emotion Pool":
        return gr.skip(), gr.skip()
    words = shuffle_word(word_state)
    return words, redraw_overlay(image, layers, stroke_width, label_mode, custom_text, words)


def create_app() -> gr.Blocks:
    with gr.Blocks(title="IMAGE OBSERVER · BUILD 02.3", analytics_enabled=False) as demo:
        gr.Markdown("# IMAGE OBSERVER · BUILD 02.3", elem_id="build-header")
        # Each browser session owns its image, focus, boxes and word stream.
        image_state, focus_state = gr.State(None), gr.State(None)
        layers_state, word_state = gr.State(None), gr.State(None)
        upload = gr.File(label="上传图片 · JPG / PNG", file_types=[".jpg", ".jpeg", ".png"],
                         file_count="single", type="filepath")
        structure = gr.Slider(minimum=0, maximum=100, value=45, step=1,
                              label="Structure", interactive=True, elem_id="structure")
        reset = gr.Button("Reset Focus / 恢复自动", elem_id="reset-focus")
        with gr.Row():
            stroke = gr.Radio(list(STROKE_WIDTHS), value="Medium", label="Stroke Width",
                              elem_id="stroke-width")
            mode = gr.Radio(list(LABEL_MODES), value="Emotion Pool", label="Labels",
                            elem_id="label-mode")
        custom = gr.Textbox(label="Custom Text · English · 32 characters max",
                            lines=1, max_lines=1, max_length=32, visible=False,
                            elem_id="custom-text")
        shuffle = gr.Button("换一个 / Shuffle Word", elem_id="shuffle-word")
        with gr.Row():
            original = gr.Image(label="原图 · 点击指定 Focus", interactive=False, format="png",
                                buttons=["download", "fullscreen"], elem_id="original")
            detection = gr.Image(label="Detection · Build 02.3", interactive=False, format="png",
                                 buttons=["download", "fullscreen"], elem_id="detection")
        # One CPU queue keeps stateful operations ordered. Redraw callbacks only
        # consume cached boxes, so even a Shuffle cannot regenerate Detection.
        options = dict(api_visibility="private", trigger_mode="always_last",
                       concurrency_limit=1, concurrency_id="image-observer-processing",
                       show_progress="minimal")
        overlay_inputs = [image_state, layers_state, stroke, mode, custom, word_state]
        detection_inputs = [image_state, structure, focus_state, stroke, mode, custom, word_state]
        focus_inputs = [image_state, structure, stroke, mode, custom, word_state]
        upload.change(upload_image, inputs=[upload, structure, stroke, mode, custom],
                      outputs=[original, detection, image_state, focus_state, layers_state, word_state],
                      **options)
        structure.change(update_detection, inputs=detection_inputs,
                         outputs=[layers_state, detection], **options)
        original.select(select_focus, inputs=focus_inputs,
                        outputs=[focus_state, layers_state, detection], **options)
        reset.click(reset_focus, inputs=focus_inputs,
                    outputs=[focus_state, layers_state, detection], **options)
        stroke.change(redraw_overlay, inputs=overlay_inputs, outputs=detection, **options)
        mode.change(change_label_mode, inputs=overlay_inputs,
                    outputs=[custom, shuffle, detection], **options)
        # Change observes native typing AND paste/autofill; this Gradio version
        # can emit input only for keypresses. Never return a server-side text
        # prefix to the Textbox: it could overwrite more recent user input.
        # Blur uppercases the completed field locally, and a resulting Change
        # is safe because this callback outputs only the Detection image.
        custom.change(change_custom_text, inputs=overlay_inputs,
                      outputs=detection, **options)
        custom.blur(fn=None, inputs=custom, outputs=custom,
                    js="text => String(text || '').toUpperCase().slice(0, 32)",
                    queue=False, api_visibility="private")
        shuffle.click(change_word, inputs=overlay_inputs,
                      outputs=[word_state, detection], **{**options, "trigger_mode": "multiple"})
    return demo


if __name__ == "__main__":
    # The Windows launcher selects a free local port before starting this file,
    # so an older instance on 7860 cannot be mistaken for the current build.
    try:
        port = int(os.environ.get("IMAGE_OBSERVER_PORT", "7860"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise SystemExit("启动失败：IMAGE_OBSERVER_PORT 必须是 1–65535 的整数。")
    create_app().launch(server_name="127.0.0.1", server_port=port, share=False,
                        inbrowser=os.environ.get("IMAGE_OBSERVER_OPEN_BROWSER") == "1",
                        show_error=True, enable_monitoring=False,
                        footer_links=[])
