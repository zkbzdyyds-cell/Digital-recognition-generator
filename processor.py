"""Deterministic, CPU-only pseudo detection for image-observer-v1 Build 02.1.

The rectangles describe visual information, not recognized objects. No model,
network access, or global random state is used.
"""

import logging
import math
from itertools import combinations

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
    """A stable layout whose fallback details stay inside its main rectangle."""
    main = _fit_box((0.22 * width, 0.22 * height, 0.78 * width, 0.78 * height),
                    width, height, 0.08, 0.80)
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


def _analyze_boxes(rgb: np.ndarray) -> list[Box]:
    height, width = rgb.shape[:2]
    if width < 3 or height < 3 or float(np.std(rgb.astype(np.float32), axis=(0, 1)).max()) < 0.05:
        return _fallback_boxes(width, height)
    subject = _subject_map(rgb)
    # Fine structure can support a coherent region, but cannot win by density.
    information = 0.97 * subject + 0.03 * _information_map(rgb) * subject
    if float(information.max()) < 1e-5 or float(information.sum()) < 1e-4:
        return _fallback_boxes(width, height)
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
        return (inside_mass / total / max(area_fraction, 1e-9) ** 0.65
                * (0.5 + 0.5 * fill) * (0.65 + 0.35 * connectivity)
                * (1 + 0.35 * min(contrast, 2)) / penalty)

    main_candidates = {_fit_box(box, width, height, 0.08, 0.80) for box in candidates}
    if not main_candidates:
        return _fallback_boxes(width, height)
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


def _micro_boxes(image: Image.Image, main: Box, medium: list[Box], seed: int) -> list[Box]:
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


def detect_layers(image: Image.Image, structure: float = 45, seed: int = 0) -> dict[str, list[Box]]:
    """Return the unchanged main, 1–3 medium boxes, and 0–9 local micro boxes.

    Structure controls layer density only. Seed controls micro variations only;
    both leave the Build 01.1 main-box algorithm and its location untouched.
    """
    boxes = detect_boxes(image)
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
            micro = _micro_boxes(image, boxes[0], pool, seed)[:micro_count]
        except Exception:
            _LOGGER.warning("Detail analysis failed; retaining main and medium layers.", exc_info=True)
    return {"main": [boxes[0]], "medium": medium, "micro": micro}


def process_image(image: Image.Image, structure: float = 45, seed: int = 0) -> Image.Image:
    """Draw the fixed-blue main, medium, and micro layers on a resized copy."""
    result = resize_image(image)
    layers = detect_layers(result, structure, seed)
    draw = ImageDraw.Draw(result)
    line_width = 2 if min(result.size) >= 120 else 1
    for name, boxes in layers.items():
        for x1, y1, x2, y2 in boxes:
            draw.rectangle((x1, y1, x2 - 1, y2 - 1), outline=BOX_COLOR,
                           width=line_width if name == "main" else 1)
    return result
