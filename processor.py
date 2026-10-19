"""Deterministic, CPU-only pseudo detection for image-observer-v1 Build 01.

The rectangles describe visual information, not recognized objects. No model,
network access, or random sampling is used.
"""

import logging
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps


MAX_IMAGE_SIZE = 1600
ANALYSIS_SIZE = 512
BOX_COLOR = (0, 80, 255)
Box = tuple[int, int, int, int]
_LOGGER = logging.getLogger(__name__)


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


def _fallback_boxes(width: int, height: int) -> list[Box]:
    """A balanced layout for flat images, tiny images, and analysis failures."""
    layouts = [
        (0.22, 0.22, 0.78, 0.78),
        (0.08, 0.12, 0.31, 0.36),
        (0.69, 0.64, 0.92, 0.88),
    ]
    return [
        _fit_box((a * width, b * height, c * width, d * height),
                 width, height, 0.08 if index == 0 else 0.008,
                 0.80 if index == 0 else 0.14)
        for index, (a, b, c, d) in enumerate(layouts)
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


def _intersection_over_union(a: Box, b: Box) -> float:
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1]))
    union = ((a[2] - a[0]) * (a[3] - a[1])
             + (b[2] - b[0]) * (b[3] - b[1]) - intersection)
    return intersection / max(union, 1)


def _analyze_boxes(rgb: np.ndarray) -> list[Box]:
    height, width = rgb.shape[:2]
    information = _information_map(rgb)
    if float(information.max()) < 1e-5 or float(information.sum()) < 1e-4:
        return _fallback_boxes(width, height)

    candidates: list[tuple[float, float, float, float]] = []
    # Multiple thresholds retain both larger groups of features and finer parts.
    positive = information[information > float(information.max()) * 0.05]
    for percentile in (55, 80):
        threshold = float(np.percentile(positive, percentile))
        mask = (information >= threshold).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:32]
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w * h >= max(4, width * height * 0.001):
                padding = max(2, round(min(w, h) * 0.12))
                candidates.append((x - padding, y - padding,
                                   x + w + padding, y + h + padding))

    # Find spatially separated information peaks. Candidate windows are centered
    # on actual image structure; suppression keeps one edge from taking all slots.
    peaks = information.copy()
    for _ in range(12):
        _, peak, _, (x, y) = cv2.minMaxLoc(peaks)
        if peak < float(information.max()) * 0.08:
            break
        for fraction in (0.20, 0.42, 0.64):
            half_width, half_height = width * fraction / 2, height * fraction / 2
            candidates.append((x - half_width, y - half_height,
                               x + half_width, y + half_height))
        radius_x, radius_y = max(1, round(width * 0.14)), max(1, round(height * 0.14))
        peaks[max(0, y - radius_y):min(height, y + radius_y + 1),
              max(0, x - radius_x):min(width, x + radius_x + 1)] = 0

    integral = cv2.integral(information)
    total = float(information.sum())

    def score(box: Box) -> float:
        x1, y1, x2, y2 = box
        mass = integral[y2, x2] - integral[y1, x2] - integral[y2, x1] + integral[y1, x1]
        area_fraction = (x2 - x1) * (y2 - y1) / (width * height)
        # Balance captured information against size; tiny high-contrast patches
        # should not automatically beat a coherent group of features.
        return float(mass / total / math.sqrt(area_fraction))

    main_candidates = {_fit_box(box, width, height, 0.08, 0.80) for box in candidates}
    main = max(sorted(main_candidates), key=score)
    auxiliaries = {_fit_box(box, width, height, 0.008, 0.14) for box in candidates}
    selected: list[Box] = []
    for box in sorted(auxiliaries, key=lambda item: (-score(item), item)):
        if _intersection_over_union(main, box) > 0.70:
            continue
        if all(_intersection_over_union(box, previous) < 0.35 for previous in selected):
            selected.append(box)
        if len(selected) == 4:
            break

    # Sparse scenes can yield just one contour. Supplement only the missing
    # rectangles, preserving the structure-driven choices already found.
    for box in _fallback_boxes(width, height)[1:]:
        if len(selected) >= 2:
            break
        if box not in selected:
            selected.append(box)
    while len(selected) < 2:  # Degenerate 1-pixel canvases cannot have distinct boxes.
        selected.append(_fallback_boxes(width, height)[1])
    return [main, *selected]


def detect_boxes(image: Image.Image) -> list[Box]:
    """Return one main box followed by 2–4 auxiliary boxes (exclusive right/bottom).

    Analysis runs at up to 512 pixels; boxes are returned in the input image's
    coordinates. Flat or otherwise unusable analysis always gets a stable layout.
    """
    if not isinstance(image, Image.Image):
        raise TypeError("Expected a Pillow image.")
    width, height = image.size
    try:
        small = resize_image(image, ANALYSIS_SIZE)
        boxes = _analyze_boxes(np.asarray(small))
        scale_x, scale_y = width / small.width, height / small.height
        return [
            _fit_box((x1 * scale_x, y1 * scale_y, x2 * scale_x, y2 * scale_y),
                     width, height, 0.08 if index == 0 else 0.008,
                     0.80 if index == 0 else 0.14)
            for index, (x1, y1, x2, y2) in enumerate(boxes)
        ]
    except Exception:
        _LOGGER.warning("Image analysis failed; using the stable fallback layout.", exc_info=True)
        return _fallback_boxes(width, height)


def process_image(image: Image.Image) -> Image.Image:
    """Resize, analyze, and draw the Build 01 blue outlines on a copy of the image."""
    result = resize_image(image)
    boxes = detect_boxes(result)
    draw = ImageDraw.Draw(result)
    line_width = 2 if min(result.size) >= 120 else 1
    for x1, y1, x2, y2 in boxes:
        draw.rectangle((x1, y1, x2 - 1, y2 - 1), outline=BOX_COLOR, width=line_width)
    return result
