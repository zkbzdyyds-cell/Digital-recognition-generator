"""Deterministic, CPU-only pseudo detection for image-observer-v1 Build 02.3.

The rectangles describe visual information, not recognized objects. No model,
network access, or global random state is used.
"""

import logging
import math
import os
import re
from functools import lru_cache
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


MAX_IMAGE_SIZE = 1600
ANALYSIS_SIZE = 512
BOX_COLOR = (0, 80, 255)
STROKE_WIDTHS = {"Thin": 1, "Medium": 2, "Thick": 4}
LABEL_MODES = ("Off", "Emotion Pool", "Custom Text")
CUSTOM_TEXT_MAX_LENGTH = 32
# This is the complete pool. Label selection is deliberately unrelated to image
# information, detected object categories, and the Detection random sequence.
EMOTION_POOL = (
    "MELANCHOLY", "HESITATION", "SORROW", "UNEASE", "ANXIETY", "GRIEF",
    "REGRET", "SHAME", "GUILT", "JEALOUSY", "ENVY", "LONELINESS", "FEAR",
    "DREAD", "ANGER", "FRUSTRATION", "SADNESS", "JOY", "DELIGHT", "RELIEF",
    "HOPE", "GRATITUDE", "AFFECTION", "TENDERNESS", "NOSTALGIA", "AWE",
    "SERENITY", "CALM", "AMBIVALENCE", "DETACHMENT",
)
Box = tuple[int, int, int, int]
Focus = tuple[float, float]
_LOGGER = logging.getLogger(__name__)


def create_word_state(seed: int = 0) -> dict[str, str | int]:
    """Initialize a session's independent, reproducible emotion-word sequence."""
    state = (1664525 * (int(seed) & 0xFFFFFFFF) + 1013904223) & 0xFFFFFFFF
    return {"word": EMOTION_POOL[state % len(EMOTION_POOL)], "rng_state": state}


def shuffle_word(state: dict[str, str | int] | None) -> dict[str, str | int]:
    """Advance only the word state, returning a new word different from before."""
    current = dict(state) if state else create_word_state()
    word = current.get("word")
    if word not in EMOTION_POOL:
        current = create_word_state()
        word = current["word"]
    next_state = (1664525 * (int(current["rng_state"]) & 0xFFFFFFFF)
                  + 1013904223) & 0xFFFFFFFF
    # Select from the other 29 entries without retry loops or shared RNG state.
    index = next_state % (len(EMOTION_POOL) - 1)
    if index >= EMOTION_POOL.index(word):
        index += 1
    return {"word": EMOTION_POOL[index], "rng_state": next_state}


def clean_custom_text(text: str | None) -> str:
    """Uppercase a short English phrase; 32 characters is the hard render limit."""
    # Bound work even for programmatic input; the UI also exposes maxlength=32.
    text = re.sub(r"[^A-Za-z '\-]+", " ", str(text or "")[:256])
    return " ".join(text.upper().split())[:CUSTOM_TEXT_MAX_LENGTH].strip()


def _stroke_pixels(stroke_width: str | int) -> int:
    if isinstance(stroke_width, str):
        return STROKE_WIDTHS.get(stroke_width, STROKE_WIDTHS["Medium"])
    return int(stroke_width) if stroke_width in STROKE_WIDTHS.values() else 2


@lru_cache(maxsize=16)
def _label_font(size: int):
    """Use local sans-serif fonts, including an offline Pillow fallback."""
    windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates = (
        windows_fonts / "arial.ttf",
        windows_fonts / "segoeui.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
    )
    for path in candidates:
        try:
            return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue
    # Pillow carries this clear sans-serif font; no network/font download needed.
    return ImageFont.load_default(size=size)


def layout_labels(size: tuple[int, int], layers: dict[str, list[Box]], text: str,
                  stroke_width: str | int = "Medium") -> list[dict]:
    """Place bounded main/medium labels, preserving the supplied box data.

    Bounds are exclusive ink bounds; position and font can be used directly with
    ImageDraw.text. Main is placed first. Unreadable secondary labels are hidden
    when no nearby candidate avoids an existing label. Micro labels never exist.
    """
    width, height = size
    text = clean_custom_text(text)
    if not text or min(size) < 8:
        return []
    font_size = max(11, min(20, round(min(size) * 0.018)))
    margin, gap = 2, max(4, _stroke_pixels(stroke_width) + 2)
    # Keep whole phrases visible, reducing the local default only for small
    # canvases. The UI deliberately has no typography controls.
    while font_size >= 8:
        font = _label_font(font_size)
        left, top, right, bottom = font.getbbox(text)
        tw, th = right - left, bottom - top
        if tw <= width - 2 * margin and th <= height - 2 * margin:
            break
        font_size -= 1
    else:
        return []

    def overlap(a, b):
        return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
            0, min(a[3], b[3]) - max(a[1], b[1]))

    placed = []
    for tier in ("main", "medium"):
        for index, box in enumerate(layers.get(tier, [])):
            x1, y1, x2, y2 = box
            positions = (
                (x1, y1 - gap - th),
                (x1 + gap, y1 + gap),
                (x2 - tw, y1 - gap - th),
                (x1, y2 + gap),
                (x2 + gap, y1 + gap),
                (x1 - gap - tw, y1 + gap),
                (x1 + gap, y2 - gap - th),
            )
            ranked = []
            seen = set()
            for priority, (x, y) in enumerate(positions):
                x = max(margin, min(width - margin - tw, round(x)))
                y = round(y)
                # At the image's top edge prefer a genuinely inset label rather
                # than clamping an above-box label onto the thick top stroke.
                if y < margin or y + th > height - margin:
                    continue
                bounds = (x, y, x + tw, y + th)
                if bounds in seen:
                    continue
                seen.add(bounds)
                # A little breathing room also prevents touching text baselines.
                inflated = (x - 2, y - 2, x + tw + 2, y + th + 2)
                collision = sum(overlap(inflated, label["bounds"]) for label in placed)
                ranked.append((collision, priority, bounds))
            if not ranked:
                # Very small canvases may have no room for the normal gap.
                x = max(margin, min(width - margin - tw, round(x1)))
                y = max(margin, min(height - margin - th, round(y1)))
                bounds = (x, y, x + tw, y + th)
                collision = sum(overlap(bounds, label["bounds"]) for label in placed)
                ranked.append((collision, 0, bounds))
            collision, _, bounds = min(ranked)
            if tier == "medium" and collision > 0.15 * max(tw * th, 1):
                continue
            placed.append({"tier": tier, "index": index, "text": text,
                           "bounds": bounds,
                           "position": (bounds[0] - left, bounds[1] - top),
                           "font": font})
    return placed


def render_overlay(image: Image.Image, layers: dict[str, list[Box]],
                   stroke_width: str | int = "Medium", label_mode: str = "Emotion Pool",
                   word: str | None = None, custom_text: str = "") -> Image.Image:
    """Render only: copy the base, then draw inward blue lines and Pillow text.

    No analysis or random-state transition is allowed here. This lets the UI
    redraw stroke/labels/Shuffle from cached boxes without rerunning Detection.
    """
    result = image.convert("RGB").copy()
    draw = ImageDraw.Draw(result)
    stroke = _stroke_pixels(stroke_width)
    for tier in ("main", "medium", "micro"):
        for x1, y1, x2, y2 in layers.get(tier, []):
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(result.width, int(x2)), min(result.height, int(y2))
            if x2 <= x1 or y2 <= y1:
                continue
            line = min(stroke, x2 - x1, y2 - y1)
            # Explicit inward strips avoid thick-stroke expansion outside either
            # its box or the image, including a one-pixel canvas/rectangle.
            for bounds in ((x1, y1, x2 - 1, y1 + line - 1),
                           (x1, y2 - line, x2 - 1, y2 - 1),
                           (x1, y1, x1 + line - 1, y2 - 1),
                           (x2 - line, y1, x2 - 1, y2 - 1)):
                draw.rectangle(bounds, fill=BOX_COLOR)
    if label_mode == "Emotion Pool":
        text = word if word in EMOTION_POOL else str(create_word_state()["word"])
    elif label_mode == "Custom Text":
        text = clean_custom_text(custom_text)
    else:
        text = ""
    for label in layout_labels(result.size, layers, text, stroke_width):
        draw.text(label["position"], label["text"], font=label["font"], fill=BOX_COLOR)
    return result


def resize_image(image: Image.Image, max_size: int = MAX_IMAGE_SIZE) -> Image.Image:
    """Apply EXIF orientation and return RGB, keeping aspect ratio without enlarging."""
    if not isinstance(image, Image.Image):
        raise TypeError("Expected a Pillow image.")
    if max_size < 1:
        raise ValueError("max_size must be positive.")

    oriented = ImageOps.exif_transpose(image)
    # Transparent PNG pixels have arbitrary hidden colors. Analyze the same white
    # composite that the user sees instead of those hidden colors.
    if oriented.mode in ("RGBA", "LA") or "transparency" in oriented.info:
        rgba = oriented.convert("RGBA")
        rgb = Image.new("RGBA", rgba.size, "white")
        rgb.alpha_composite(rgba)
        rgb = rgb.convert("RGB")
    else:
        rgb = oriented.convert("RGB")
    if max(rgb.size) > max_size:
        scale = max_size / max(rgb.size)
        size = tuple(max(1, round(side * scale)) for side in rgb.size)
        rgb = rgb.resize(size, Image.Resampling.LANCZOS)
    return rgb


def _fit_box(
    box: tuple[float, float, float, float],
    width: int,
    height: int,
    min_area: float,
    max_area: float,
) -> Box:
    """Fit around the candidate center, with area and aspect constraints.

    On extremely narrow or tiny images, integer pixels can make the area and
    aspect constraints incompatible. In that case keep a valid in-bounds box.
    """
    x1, y1, x2, y2 = box
    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
    ratio = float(np.clip(max(x2 - x1, 1) / max(y2 - y1, 1), 1 / 3.5, 3.5))
    area = float(np.clip(max(x2 - x1, 1) * max(y2 - y1, 1),
                         min_area * width * height, max_area * width * height))
    box_width, box_height = math.sqrt(area * ratio), math.sqrt(area / ratio)
    # If one side hits the frame, expand the other side to retain enough area.
    if box_width > width:
        box_width, box_height = width, area / width
    if box_height > height:
        box_height, box_width = height, area / height
    if box_width > 3.5 * box_height:
        box_width = 3.5 * box_height
    elif box_height > 3.5 * box_width:
        box_height = 3.5 * box_width
    # Round outward so an 8% minimum does not become 7–8% on small inputs.
    box_width = max(1, min(width, math.ceil(box_width)))
    box_height = max(1, min(height, math.ceil(box_height)))

    # Rounding should not push a normal-size main box beyond the 80% limit.
    while box_width * box_height > max_area * width * height:
        if box_width == 1 and box_height == 1:
            break
        if box_width >= box_height and box_width > 1:
            box_width -= 1
        else:
            box_height -= 1
    left = max(0, min(width - box_width, round(center_x - box_width / 2)))
    top = max(0, min(height - box_height, round(center_y - box_height / 2)))
    return left, top, left + box_width, top + box_height


def _coerce_focus(focus: Focus | None, width: int, height: int) -> Focus | None:
    """Validate and clamp a pixel focus; malformed/nonfinite points mean auto."""
    if focus is None:
        return None
    try:
        x, y = map(float, focus)
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        return max(0.0, min(width - 1.0, x)), max(0.0, min(height - 1.0, y))
    except (TypeError, ValueError):
        return None


def _fallback_boxes(width: int, height: int, focus: Focus | None = None) -> list[Box]:
    """A stable local layout, centered on the requested point when supplied."""
    if focus is None:
        bounds = (0.22 * width, 0.22 * height, 0.78 * width, 0.78 * height)
    else:
        x, y = focus
        bounds = (x - 0.18 * width, y - 0.18 * height,
                  x + 0.18 * width, y + 0.18 * height)
    main = _fit_box(bounds, width, height, 0.08, 0.80)
    return [main, *_detail_fallback(main, width, height)[:2]]


def _detail_fallback(main: Box, width: int, height: int) -> list[Box]:
    """Supply deterministic local windows, never unrelated frame corners."""
    left, top, right, bottom = main
    mw, mh = right - left, bottom - top
    layouts = [(0.08, 0.10, 0.52, 0.54), (0.47, 0.46, 0.92, 0.91),
               (0.48, 0.08, 0.91, 0.51), (0.09, 0.48, 0.52, 0.91)]
    return [
        tuple(value + (left if index % 2 == 0 else top)
              for index, value in enumerate(_fit_box(
                  (a * mw, b * mh, c * mw, d * mh), mw, mh,
                  min(0.008 * width * height / max(mw * mh, 1), 0.4), 0.65)))
        for a, b, c, d in layouts
    ]


def _normalized(values: np.ndarray) -> np.ndarray:
    limit = float(np.percentile(values, 98))
    if limit <= 1e-6:
        limit = float(values.max())
    if limit <= 1e-6:
        return np.zeros_like(values, dtype=np.float32)
    return np.clip(values / limit, 0, 1).astype(np.float32)


def _information_map(rgb: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    smooth = cv2.GaussianBlur(gray, (0, 0), 0.8)
    dx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0)
    dy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1)
    edges = _normalized(cv2.magnitude(dx, dy))
    contrast = _normalized(np.abs(gray - cv2.GaussianBlur(gray, (0, 0), 5)))

    # Lab center-surround contrast also sees strong color changes with similar
    # brightness, which grayscale edges alone can miss.
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    surround = cv2.GaussianBlur(lab, (0, 0), 9)
    color_contrast = _normalized(np.linalg.norm(lab - surround, axis=2))
    information = 0.50 * edges + 0.30 * contrast + 0.20 * color_contrast
    return cv2.GaussianBlur(information, (0, 0), 2)


def _box_blur(values: np.ndarray, radius: int) -> np.ndarray:
    return cv2.blur(values, (2 * radius + 1, 2 * radius + 1),
                    borderType=cv2.BORDER_REPLICATE)


def _subject_map(rgb: np.ndarray) -> np.ndarray:
    """Coherent color novelty, with texture and almost-black background gates.

    Compare color populations inside the image with those on its border. This
    is a background prior, not a skin/color classifier, and follows off-center
    subjects. Coarse contrast preserves subjects whose colors also touch an edge.
    """
    height, width = rgb.shape[:2]
    side = min(width, height)
    colors = rgb.astype(np.float32) / 255
    small = _box_blur(colors, max(1, round(side * 0.015)))
    broad = _box_blur(colors, max(2, round(side * 0.12)))
    gray = colors @ np.array([0.299, 0.587, 0.114], np.float32)
    small_gray = small @ np.array([0.299, 0.587, 0.114], np.float32)

    # Smooth the tiny RGB histogram in color space to avoid bin-edge jumps.
    indices = np.minimum((small * 8).astype(np.int32), 7)
    encoded = indices[:, :, 0] * 64 + indices[:, :, 1] * 8 + indices[:, :, 2]
    border = max(1, round(side * 0.06))
    border_mask = np.zeros((height, width), bool)
    border_mask[:border] = border_mask[-border:] = True
    border_mask[:, :border] = border_mask[:, -border:] = True

    def histogram(values: np.ndarray) -> np.ndarray:
        hist = np.bincount(values.ravel(), minlength=512).reshape(8, 8, 8).astype(np.float32)
        hist /= max(values.size, 1)
        for axis in range(3):
            padded = np.pad(hist, [(1, 1) if a == axis else (0, 0) for a in range(3)], mode="edge")
            slices = [slice(None)] * 3
            parts = []
            for offset in range(3):
                slices[axis] = slice(offset, offset + 8)
                parts.append(padded[tuple(slices)])
            hist = (parts[0] + 2 * parts[1] + parts[2]) * 0.25
        return hist.ravel()

    all_density = histogram(encoded)[encoded]
    border_density = histogram(encoded[border_mask])[encoded]
    novelty = np.clip((all_density - 1.15 * border_density) / (all_density + 0.002), 0, 1)
    coarse = np.linalg.norm(small - broad, axis=2) / math.sqrt(3)
    global_contrast = np.linalg.norm(small - small.mean(axis=(0, 1)), axis=2) / math.sqrt(3)
    fine = _box_blur(np.abs(gray - small_gray), max(1, round(side * 0.012)))
    texture_gate = 1 / (1 + 1.8 * fine / (0.025 + coarse))
    dark_gate = 0.08 + 0.92 * np.clip((small_gray - 0.025) / 0.14, 0, 1)
    confidence = (0.60 * novelty + 0.25 * _normalized(coarse)
                  + 0.15 * _normalized(global_contrast)) * texture_gate * dark_gate
    confidence = _box_blur(confidence, max(1, round(side * 0.018)))
    return _normalized(confidence)


def _intersection_over_union(a: Box, b: Box) -> float:
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1]))
    union = ((a[2] - a[0]) * (a[3] - a[1])
             + (b[2] - b[0]) * (b[3] - b[1]) - intersection)
    return intersection / max(union, 1)


def _analyze_boxes(rgb: np.ndarray, focus: Focus | None = None) -> list[Box]:
    height, width = rgb.shape[:2]
    if width < 3 or height < 3 or float(np.std(rgb.astype(np.float32), axis=(0, 1)).max()) < 0.05:
        return _fallback_boxes(width, height, focus)
    subject = _subject_map(rgb)
    # Fine structure can support a coherent region, but cannot win by density.
    information = 0.97 * subject + 0.03 * _information_map(rgb) * subject
    if focus is not None:
        # A click is a visual preference, not an object/skin class. Local edges
        # may compete even when the automatic background prior rejects them.
        yy, xx = np.mgrid[:height, :width]
        distance = ((xx - focus[0]) / max(width * 0.17, 1)) ** 2 + ((yy - focus[1]) / max(height * 0.17, 1)) ** 2
        proximity = np.exp(-0.5 * distance)
        information = (0.60 * subject + 0.40 * _information_map(rgb)) * (0.015 + 0.985 * proximity)
    if float(information.max()) < 1e-5 or float(information.sum()) < 1e-4:
        return _fallback_boxes(width, height, focus)
    candidates: list[tuple[float, float, float, float]] = []
    kernel = np.ones((max(3, round(min(width, height) * 0.016)) | 1,) * 2, np.uint8)
    support = None
    labels = None
    for threshold in (0.28, 0.46, 0.66):
        mask = (subject >= threshold).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        count, current_labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if support is None:
            support, labels = mask, current_labels
        for index in sorted(range(1, count), key=lambda i: -int(stats[i, cv2.CC_STAT_AREA]))[:32]:
            x, y, w, h, pixels = stats[index]
            if pixels < max(4, width * height * 0.0015):
                continue
            padding = max(2, round(min(w, h) * 0.06))
            candidates.append((x - padding, y - padding, x + w + padding, y + h + padding))

    # Windows follow actual coarse-confidence peaks, never fixed subject positions.
    peaks = subject.copy()
    for _ in range(12):
        _, peak, _, (x, y) = cv2.minMaxLoc(peaks)
        if peak < 0.10:
            break
        for fraction in (0.28, 0.42, 0.56, 0.68):
            half_width, half_height = width * fraction / 2, height * fraction / 2
            candidates.append((x - half_width, y - half_height,
                               x + half_width, y + half_height))
        radius_x, radius_y = max(1, round(width * 0.14)), max(1, round(height * 0.14))
        peaks[max(0, y - radius_y):min(height, y + radius_y + 1),
              max(0, x - radius_x):min(width, x + radius_x + 1)] = 0

    if focus is not None:
        # Explicit local windows guarantee a candidate containing the click,
        # including a smooth/dark click with no segmented component nearby.
        fx, fy = focus
        for fraction in (0.28, 0.36, 0.46, 0.56):
            for dx, dy in ((0, 0), (-0.06, 0), (0.06, 0), (0, -0.06), (0, 0.06)):
                cx, cy = fx + dx * width, fy + dy * height
                candidates.append((cx - width * fraction / 2, cy - height * fraction / 2,
                                   cx + width * fraction / 2, cy + height * fraction / 2))

    integral = cv2.integral(information)
    total = float(information.sum())

    def mass(box: Box) -> float:
        x1, y1, x2, y2 = box
        return float(integral[y2, x2] - integral[y1, x2] - integral[y2, x1] + integral[y1, x1])

    def score(box: Box) -> float:
        x1, y1, x2, y2 = box
        box_area = (x2 - x1) * (y2 - y1)
        area_fraction = box_area / (width * height)
        inside_mass = mass(box)
        active = labels[y1:y2, x1:x2].ravel()
        populations = np.bincount(active)
        occupied = int(populations[1:].sum())
        fill = occupied / max(box_area, 1)
        connectivity = float(populations[1:].max(initial=0)) / max(occupied, 1)
        pad_x, pad_y = max(1, round((x2 - x1) * 0.18)), max(1, round((y2 - y1) * 0.18))
        outer = (max(0, x1 - pad_x), max(0, y1 - pad_y), min(width, x2 + pad_x), min(height, y2 + pad_y))
        ring_area = (outer[2] - outer[0]) * (outer[3] - outer[1]) - box_area
        ring_mean = (mass(outer) - inside_mass) / max(ring_area, 1)
        contrast = max(0, inside_mass / box_area - ring_mean) / max(total / (width * height), 1e-6)
        touch = sum((x1 == 0, y1 == 0, x2 == width, y2 == height))
        aspect = (x2 - x1) / max(y2 - y1, 1)
        penalty = (1 + 6 * max(0, area_fraction - 0.48) ** 1.3
                   + 0.10 * touch + 0.15 * math.log(aspect) ** 2)
        if focus is not None:
            center_distance = (((x1 + x2) / 2 - focus[0]) / max(width * 0.18, 1)) ** 2 + (((y1 + y2) / 2 - focus[1]) / max(height * 0.18, 1)) ** 2
            penalty *= (1 + 1.8 * center_distance + 9 * max(0, area_fraction - 0.28))
        return (inside_mass / total / max(area_fraction, 1e-9) ** 0.65
                * (0.5 + 0.5 * fill) * (0.65 + 0.35 * connectivity)
                * (1 + 0.35 * min(contrast, 2)) / penalty)

    main_candidates = {_fit_box(box, width, height, 0.08, 0.80) for box in candidates}
    if focus is not None:
        main_candidates = {b for b in main_candidates
                           if b[0] <= focus[0] < b[2] and b[1] <= focus[1] < b[3]
                           and abs((b[0] + b[2]) / 2 - focus[0]) <= max(width * 0.18, 1)
                           and abs((b[1] + b[3]) / 2 - focus[1]) <= max(height * 0.18, 1)}
    if not main_candidates:
        return _fallback_boxes(width, height, focus)
    main = max(sorted(main_candidates), key=score)
    mx1, my1, mx2, my2 = main
    mw, mh = mx2 - mx1, my2 - my1
    expanded = (max(0, mx1 - mw * 0.10), max(0, my1 - mh * 0.10),
                min(width, mx2 + mw * 0.10), min(height, my2 + mh * 0.10))
    auxiliaries = {_fit_box(box, width, height, 0.008, 0.14) for box in candidates}
    # Sample subject-local subwindows so sparse, smooth regions still yield details.
    for fraction in (0.32, 0.45, 0.60):
        aw, ah = max(1, mw * fraction), max(1, mh * fraction)
        for gy in range(4):
            for gx in range(4):
                x, y = mx1 + (mw - aw) * gx / 3, my1 + (mh - ah) * gy / 3
                auxiliaries.add(_fit_box((x, y, x + aw, y + ah), width, height, 0.008, 0.14))

    def near_main(box: Box) -> bool:
        x1, y1, x2, y2 = box
        overlap = max(0, min(x2, expanded[2]) - max(x1, expanded[0])) * max(0, min(y2, expanded[3]) - max(y1, expanded[1]))
        return (mx1 <= (x1 + x2) / 2 <= mx2 and my1 <= (y1 + y2) / 2 <= my2
                and overlap >= 0.8 * (x2 - x1) * (y2 - y1)
                and (x2 - x1) * (y2 - y1) <= 0.65 * mw * mh)

    selected: list[Box] = []
    for box in sorted((b for b in auxiliaries if near_main(b)), key=lambda item: (-score(item), item)):
        if _intersection_over_union(main, box) > 0.65:
            continue
        if all(_intersection_over_union(box, previous) < 0.35 for previous in selected):
            selected.append(box)
        if len(selected) == 4:
            break

    # Missing details come from this main rectangle, not frame-wide fallback sites.
    for box in _detail_fallback(main, width, height):
        if len(selected) >= 2:
            break
        if box not in selected:
            selected.append(box)
    while len(selected) < 2:  # Degenerate 1-pixel canvases cannot have distinct boxes.
        selected.append(_detail_fallback(main, width, height)[0])
    return [main, *selected]


def detect_boxes(image: Image.Image, focus: Focus | None = None) -> list[Box]:
    """Return one main box followed by 2–4 auxiliary boxes (exclusive right/bottom).

    Analysis runs at up to 512 pixels; boxes are returned in the input image's
    oriented coordinates, as is optional focus. Unusable analysis gets a stable layout.
    """
    if not isinstance(image, Image.Image):
        raise TypeError("Expected a Pillow image.")
    image = resize_image(image, max(image.size))
    width, height = image.size
    focus = _coerce_focus(focus, width, height)
    try:
        small = resize_image(image, ANALYSIS_SIZE)
        small_focus = None if focus is None else (focus[0] * small.width / width,
                                                 focus[1] * small.height / height)
        boxes = _analyze_boxes(np.asarray(small), small_focus)
        scale_x, scale_y = width / small.width, height / small.height
        mapped = [
            _fit_box((x1 * scale_x, y1 * scale_y, x2 * scale_x, y2 * scale_y),
                     width, height, 0.08 if index == 0 else 0.008,
                     0.80 if index == 0 else 0.14)
            for index, (x1, y1, x2, y2) in enumerate(boxes)
        ]
        if focus is not None:
            # Integer fitting can shift a 1-pixel-wide extreme-aspect candidate
            # away from the point. Translate it without changing its dimensions.
            x1, y1, x2, y2 = mapped[0]
            bw, bh = x2 - x1, y2 - y1
            if focus[0] < x1:
                x1 = math.floor(focus[0])
            elif focus[0] >= x2:
                x1 = math.floor(focus[0]) - bw + 1
            if focus[1] < y1:
                y1 = math.floor(focus[1])
            elif focus[1] >= y2:
                y1 = math.floor(focus[1]) - bh + 1
            x1, y1 = max(0, min(width - bw, x1)), max(0, min(height - bh, y1))
            mapped[0] = (x1, y1, x1 + bw, y1 + bh)
        return mapped
    except Exception:
        _LOGGER.warning("Image analysis failed; using the stable fallback layout.", exc_info=True)
        return _fallback_boxes(width, height, focus)


def _near_duplicate(a: Box, b: Box) -> bool:
    """Reject overlapping, nested, or almost co-centered detail rectangles."""
    aw, ah, bw, bh = a[2] - a[0], a[3] - a[1], b[2] - b[0], b[3] - b[1]
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1]))
    center_distance = math.hypot(
        ((a[0] + a[2] - b[0] - b[2]) / 2) / max((aw + bw) / 2, 1),
        ((a[1] + a[3] - b[1] - b[3]) / 2) / max((ah + bh) / 2, 1))
    return (_intersection_over_union(a, b) >= 0.32
            or intersection / max(min(aw * ah, bw * bh), 1) >= 0.68
            or center_distance < 0.65)


def _medium_pool(boxes: list[Box], width: int, height: int) -> list[Box]:
    """Keep a fixed, distinct three-box sequence for every Structure value."""
    candidates = list(dict.fromkeys([*boxes[1:], *_detail_fallback(boxes[0], width, height)]))
    # A large first auxiliary may contain all later ones. Choose the earliest
    # compatible group instead of allowing that one box to block the whole pool.
    for count in (3, 2, 1):
        for group in combinations(candidates, count):
            if all(not _near_duplicate(a, b) for a, b in combinations(group, 2)):
                return list(group)
    return []


def _micro_boxes(image: Image.Image, main: Box, medium: list[Box], seed: int,
                 focus: Focus | None = None) -> list[Box]:
    """Build a shared, seeded detail sequence, independent of Structure.

    Five information peaks become small clusters. Weighted sampling stays local
    to those peaks and is gated by subject confidence, rather than spreading
    random rectangles over the whole frame.
    """
    mx1, my1, mx2, my2 = main
    mw, mh = mx2 - mx1, my2 - my1
    if min(image.size) < 32 or min(mw, mh) < 20 or not medium:
        return []
    small = resize_image(image, ANALYSIS_SIZE)
    rgb = np.asarray(small)
    if int(np.ptp(rgb, axis=(0, 1)).max()) == 0:
        return []
    information, subject = _information_map(rgb), _subject_map(rgb)
    weights = information ** 1.3 * (0.05 + 0.95 * subject ** 1.4)
    if focus is not None:
        # Keep the existing peak/cluster algorithm; change only its search weight.
        yy, xx = np.mgrid[:small.height, :small.width]
        fx, fy = focus[0] * small.width / image.width, focus[1] * small.height / image.height
        proximity = np.exp(-0.5 * (((xx - fx) / max(small.width * 0.14, 1)) ** 2
                                  + ((yy - fy) / max(small.height * 0.14, 1)) ** 2))
        weights = information ** 1.3 * (0.25 + 0.75 * subject) * (0.015 + 0.985 * proximity)
    if float(weights.max()) < 1e-6:
        return []

    # Keep complete micro rectangles inside this subject-local expanded region.
    roi = (max(0, math.floor(mx1 - 0.15 * mw)), max(0, math.floor(my1 - 0.15 * mh)),
           min(image.width, math.ceil(mx2 + 0.15 * mw)),
           min(image.height, math.ceil(my2 + 0.15 * mh)))
    sx, sy = image.width / small.width, image.height / small.height
    ax1, ay1 = max(0, math.floor(roi[0] / sx)), max(0, math.floor(roi[1] / sy))
    ax2, ay2 = min(small.width, math.ceil(roi[2] / sx)), min(small.height, math.ceil(roi[3] / sy))
    # Nearby features may extend past a main edge. Features outside both axes
    # receive less weight, which avoids pulling a whole cluster into a corner of
    # the expanded background while retaining adjoining horns, hands, or edges.
    xs, ys = (np.arange(small.width) + 0.5) * sx, (np.arange(small.height) + 0.5) * sy
    weights *= np.where((xs >= mx1) & (xs <= mx2), 1.0, 0.35)[None, :]
    weights *= np.where((ys >= my1) & (ys <= my2), 1.0, 0.35)[:, None]
    local = np.zeros_like(weights)
    local[ay1:ay2, ax1:ax2] = weights[ay1:ay2, ax1:ax2]
    peak_limit = float(local.max())
    if peak_limit < 1e-6:
        return []

    # A local LCG makes repeatability explicit and easy to reproduce in the
    # offline browser preview. It never changes NumPy/Python global RNG state.
    state = int(seed) & 0xFFFFFFFF

    def random_value() -> float:
        nonlocal state
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        return state / 4294967296

    radius_x = max(1, round(0.13 * mw / sx))
    radius_y = max(1, round(0.13 * mh / sy))
    sample_x = max(1, round(0.065 * mw / sx))
    sample_y = max(1, round(0.065 * mh / sy))
    peaks = local.copy()
    clusters = []
    for _ in range(5):
        _, value, _, (x, y) = cv2.minMaxLoc(peaks)
        if value < peak_limit * 0.08:
            break
        left, top = max(ax1, x - sample_x), max(ay1, y - sample_y)
        right, bottom = min(ax2, x + sample_x + 1), min(ay2, y + sample_y + 1)
        distribution = np.cumsum(local[top:bottom, left:right].ravel(), dtype=np.float64)
        if distribution.size and distribution[-1] > 0:
            clusters.append((left, top, right - left, distribution))
        peaks[max(ay1, y - radius_y):min(ay2, y + radius_y + 1),
              max(ax1, x - radius_x):min(ax2, x + radius_x + 1)] = 0
    if not clusters:
        return []

    area_limit = min((box[2] - box[0]) * (box[3] - box[1]) for box in medium) * 0.25
    if area_limit < 4:
        return []
    selected: list[Box] = []
    # Rejected duplicates do not change the Structure relationship: all values
    # still take a prefix of exactly this same seed-conditioned sequence.
    for attempt in range(180):
        left, top, span, distribution = clusters[attempt % len(clusters)]
        index = min(int(np.searchsorted(distribution, random_value() * distribution[-1], side="right")),
                    len(distribution) - 1)
        center_x = (left + index % span + 0.5) * sx
        center_y = (top + index // span + 0.5) * sy
        area = min(mw * mh * (0.0025 + 0.0095 * random_value()), area_limit)
        aspect = math.exp(math.log(0.55) + random_value() * math.log(2.3 / 0.55))
        bw = max(2, min(roi[2] - roi[0], round(math.sqrt(area * aspect))))
        bh = max(2, min(roi[3] - roi[1], round(math.sqrt(area / aspect))))
        while bw * bh > area_limit and (bw > 2 or bh > 2):
            if bw >= bh and bw > 2:
                bw -= 1
            else:
                bh -= 1
        x1 = max(roi[0], min(roi[2] - bw, round(center_x - bw / 2)))
        y1 = max(roi[1], min(roi[3] - bh, round(center_y - bh / 2)))
        box = (x1, y1, x1 + bw, y1 + bh)
        if all(not _near_duplicate(box, previous) for previous in selected):
            selected.append(box)
        if len(selected) == 9:
            break
    return selected


def detect_layers(image: Image.Image, structure: float = 45, seed: int = 0,
                  focus: Focus | None = None) -> dict[str, list[Box]]:
    """Return 1 main, 1–3 medium and 0–9 micro boxes in oriented image pixels.

    Optional focus uses those same pixels. Structure changes density, seed
    changes detail variations; neither moves the chosen main box.
    """
    image = resize_image(image, max(image.size))
    focus = _coerce_focus(focus, image.width, image.height)
    boxes = detect_boxes(image, focus)
    value = float(structure)
    value = min(100.0, max(0.0, value)) if math.isfinite(value) else 45.0
    t = value / 100
    medium_count = 1 + math.floor(2 * t + 0.5)
    pool = _medium_pool(boxes, image.width, image.height)
    medium = pool[:medium_count]
    micro_count = math.floor(8 * t + 2 * max(0.0, t - 0.5) + 0.5)
    micro: list[Box] = []
    if micro_count:
        try:
            micro = _micro_boxes(image, boxes[0], pool, seed, focus)[:micro_count]
        except Exception:
            _LOGGER.warning("Detail analysis failed; retaining main and medium layers.", exc_info=True)
    return {"main": [boxes[0]], "medium": medium, "micro": micro}


def process_image(image: Image.Image, structure: float = 45, seed: int = 0,
                  focus: Focus | None = None, *, stroke_width: str | int = "Medium",
                  label_mode: str = "Emotion Pool", word: str | None = None,
                  custom_text: str = "") -> Image.Image:
    """Analyze once and overlay blue boxes/labels without crop/pad/upscale.

    Focus is in EXIF-oriented source-image pixels. It is mapped to the output
    only here when the longest edge is reduced to 1600 pixels.
    """
    oriented_size = ImageOps.exif_transpose(image).size
    focus = _coerce_focus(focus, *oriented_size)
    result = resize_image(image)
    if focus is not None:
        focus = (focus[0] * result.width / oriented_size[0],
                 focus[1] * result.height / oriented_size[1])
    layers = detect_layers(result, structure, seed, focus)
    return render_overlay(result, layers, stroke_width, label_mode, word, custom_text)
