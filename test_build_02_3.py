"""Build 02.3 overlay/state regressions; run with the standard unittest runner."""

from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from processor import (
    BOX_COLOR, CUSTOM_TEXT_MAX_LENGTH, EMOTION_POOL, LABEL_MODES, STROKE_WIDTHS,
    clean_custom_text, create_word_state, detect_layers, layout_labels,
    render_overlay, resize_image, shuffle_word,
)


EXPECTED_WORDS = (
    "MELANCHOLY HESITATION SORROW UNEASE ANXIETY GRIEF REGRET SHAME GUILT "
    "JEALOUSY ENVY LONELINESS FEAR DREAD ANGER FRUSTRATION SADNESS JOY "
    "DELIGHT RELIEF HOPE GRATITUDE AFFECTION TENDERNESS NOSTALGIA AWE "
    "SERENITY CALM AMBIVALENCE DETACHMENT"
).split()


class WordStateTests(unittest.TestCase):
    def test_exact_pool_presets_and_bounded_custom_text(self):
        self.assertEqual(list(EMOTION_POOL), EXPECTED_WORDS)
        self.assertEqual(len(set(EMOTION_POOL)), 30)
        self.assertEqual(STROKE_WIDTHS, {"Thin": 1, "Medium": 2, "Thick": 4})
        self.assertEqual(tuple(LABEL_MODES), ("Off", "Emotion Pool", "Custom Text"))
        self.assertEqual(clean_custom_text("  melancholy   and hope  "),
                         "MELANCHOLY AND HOPE")
        self.assertEqual(CUSTOM_TEXT_MAX_LENGTH, 32)
        cleaned = clean_custom_text("a" * 100 + "<script>中文")
        self.assertLessEqual(len(cleaned), 32)
        self.assertTrue(all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ '-" for c in cleaned))

    def test_shuffle_changes_word_without_mutation_and_repeats_sequence(self):
        first = create_word_state(seed=0)
        second = create_word_state(seed=0)
        for _ in range(12):
            self.assertEqual(first, second)
            self.assertIn(first["word"], EMOTION_POOL)
            previous = deepcopy(first)
            following = shuffle_word(first)
            self.assertEqual(first, previous)
            self.assertNotEqual(following["word"], first["word"])
            first, second = following, shuffle_word(second)


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.image = Image.new("RGB", (512, 384), (29, 31, 37))
        self.layers = {
            "main": [(20, 60, 490, 350)],
            "medium": [(40, 130, 180, 240), (300, 130, 450, 250)],
            "micro": [(220, 270, 245, 293)],
        }

    def test_stroke_is_inward_exact_and_applies_to_every_tier(self):
        source = np.asarray(self.image)
        for preset, width in STROKE_WIDTHS.items():
            with self.subTest(preset=preset):
                result = np.asarray(render_overlay(self.image, self.layers,
                                                   stroke_width=preset, label_mode="Off"))
                changed = np.any(result != source, axis=2)
                self.assertTrue(np.all(result[changed] == BOX_COLOR))
                allowed = np.zeros(source.shape[:2], dtype=bool)
                for boxes in self.layers.values():
                    for x1, y1, x2, y2 in boxes:
                        allowed[y1:y2, x1:x2] = True
                        middle = (x1 + x2) // 2
                        self.assertTrue(np.all(result[y1:y1 + width, middle] == BOX_COLOR))
                        self.assertTrue(np.array_equal(result[y1 + width, middle],
                                                       source[y1 + width, middle]))
                        self.assertTrue(np.array_equal(result[y1 - 1, middle],
                                                       source[y1 - 1, middle]))
                self.assertFalse(changed[~allowed].any())

    def test_overlay_keeps_source_boxes_and_word_state_and_never_detects(self):
        original_pixels = self.image.tobytes()
        original_layers = deepcopy(self.layers)
        state = create_word_state(seed=0)
        original_state = deepcopy(state)
        with patch("processor.detect_layers", side_effect=AssertionError("Detection reran")):
            first = render_overlay(self.image, self.layers, word=state["word"])
            for preset in STROKE_WIDTHS:
                for mode in LABEL_MODES:
                    render_overlay(self.image, self.layers, stroke_width=preset,
                                   label_mode=mode, word=state["word"],
                                   custom_text="melancholy")
            for _ in range(3):
                state = shuffle_word(state)
                render_overlay(self.image, self.layers, word=state["word"])
            restored = render_overlay(self.image, self.layers, word=original_state["word"])
        self.assertEqual(first.tobytes(), restored.tobytes())
        self.assertEqual(self.image.tobytes(), original_pixels)
        self.assertEqual(self.layers, original_layers)

    def test_labels_are_one_word_main_medium_only_and_never_overlap(self):
        crowded = {"main": [(0, 0, 220, 120)],
                   "medium": [(0, 0, 90, 70), (2, 1, 100, 80), (5, 2, 120, 90)],
                   "micro": [(0, 0, 10, 10), (100, 60, 120, 80)]}
        for text in ("MELANCHOLY", "A SHORT ENGLISH PHRASE", "A" * 32):
            size = (512, 384) if len(text) == 32 else (240, 150)
            records = layout_labels(size, crowded, text, "Thick")
            self.assertGreaterEqual(len(records), 1)
            self.assertEqual(records[0]["tier"], "main")
            self.assertLessEqual(len(records), 4)
            for record in records:
                self.assertIn(record["tier"], ("main", "medium"))
                self.assertEqual(record["text"], text)
                x1, y1, x2, y2 = record["bounds"]
                self.assertTrue(0 <= x1 < x2 <= size[0] and 0 <= y1 < y2 <= size[1])
                for previous in records[:records.index(record)]:
                    a, b, c, d = previous["bounds"]
                    self.assertFalse(min(c, x2) > max(a, x1)
                                     and min(d, y2) > max(b, y1))
        tiny = {"main": [(0, 0, 1, 1)], "medium": [], "micro": []}
        self.assertEqual(layout_labels((1, 1), tiny, "MELANCHOLY"), [])

    def test_both_photos_keep_focus_geometry_across_a_b_c_and_three_shuffles(self):
        root = Path(__file__).resolve().parent
        for name, point in (("detection_01", (430, 520)),
                            ("detection_02", (750, 510))):
            with self.subTest(image=name):
                with Image.open(root / "test_images" / (name + ".jpg")) as source:
                    image = resize_image(source)
                layers = detect_layers(image, structure=50, seed=0, focus=point)
                frozen = deepcopy(layers)
                self.assertEqual(list(map(len, layers.values())), [1, 2, 4])
                state = create_word_state(seed=0)
                with patch("processor.detect_layers", side_effect=AssertionError("Detection reran")):
                    for stroke, mode in (("Thin", "Off"), ("Medium", "Emotion Pool"),
                                         ("Thick", "Custom Text")):
                        result = render_overlay(image, layers, stroke, mode,
                                                word=state["word"], custom_text="MELANCHOLY")
                        self.assertEqual(result.size, image.size)
                        self.assertEqual(layers, frozen)
                    for _ in range(3):
                        state = shuffle_word(state)
                        render_overlay(image, layers, word=state["word"])
                        self.assertEqual(layers, frozen)


class AppOverlayCallbackTests(unittest.TestCase):
    def test_cached_callbacks_render_full_text_and_keep_session_state(self):
        import app

        image = Image.new("RGB", (512, 384), (29, 31, 37))
        layers = {"main": [(20, 60, 490, 350)],
                  "medium": [(40, 130, 180, 240), (300, 130, 450, 250)],
                  "micro": [(220, 270, 245, 293)]}
        pixels, boxes = image.tobytes(), deepcopy(layers)
        words = create_word_state(seed=0)
        initial_words = deepcopy(words)
        other_session_words = deepcopy(words)
        expected_custom = render_overlay(image, layers, "Thick", "Custom Text",
                                         word=words["word"], custom_text="MELANCHOLY")
        drawn_text = []
        original_text = ImageDraw.ImageDraw.text

        def record_text(draw, position, text, *args, **kwargs):
            drawn_text.append(text)
            return original_text(draw, position, text, *args, **kwargs)

        with patch("app.detect_layers", side_effect=AssertionError("Detection reran")):
            pool = app.redraw_overlay(image, layers, "Medium", "Emotion Pool", "", words)
            app.redraw_overlay(image, layers, "Thin", "Off", "", words)
            custom_visibility, shuffle_visibility, _ = app.change_label_mode(
                image, layers, "Thick", "Custom Text", "", words)
            self.assertTrue(custom_visibility["visible"])
            self.assertFalse(shuffle_visibility["visible"])
            with patch.object(ImageDraw.ImageDraw, "text", new=record_text):
                custom = app.change_custom_text(image, layers, "Thick", "Custom Text",
                                                "mElAnChOlY", words)
            # Returning an image alone prevents stale server-side text prefixes
            # from replacing characters that a user has since typed in the UI.
            self.assertIsInstance(custom, Image.Image)
            self.assertEqual(custom.tobytes(), expected_custom.tobytes())
            self.assertTrue(drawn_text)
            self.assertTrue(all(text == "MELANCHOLY" for text in drawn_text))
            self.assertLessEqual(len(drawn_text), 1 + len(layers["medium"]))
            _, _, restored_pool = app.change_label_mode(
                image, layers, "Medium", "Emotion Pool", "MELANCHOLY", words)
            self.assertEqual(restored_pool.tobytes(), pool.tobytes())
            self.assertEqual(words, initial_words)
            for _ in range(3):
                previous = deepcopy(words)
                following, rendered = app.change_word(
                    image, layers, "Medium", "Emotion Pool", "MELANCHOLY", words)
                self.assertIsNot(following, words)
                self.assertEqual(words, previous)
                self.assertNotEqual(following["word"], words["word"])
                self.assertEqual(rendered.size, image.size)
                words = following
        self.assertEqual(other_session_words, initial_words)
        self.assertEqual(image.tobytes(), pixels)
        self.assertEqual(layers, boxes)

    def test_custom_change_event_cannot_echo_stale_prefix_into_textbox(self):
        import app

        demo = app.create_app()
        components = {getattr(block, "elem_id", None): block
                      for block in demo.blocks.values() if getattr(block, "elem_id", None)}
        custom = components["custom-text"]
        detection = components["detection"]
        event = next(event for event in demo.config["dependencies"]
                     if (custom._id, "change") in event["targets"])
        self.assertEqual(event["outputs"], [detection._id])
        blur = next(event for event in demo.config["dependencies"]
                    if (custom._id, "blur") in event["targets"])
        self.assertFalse(blur["backend_fn"])
        self.assertFalse(blur["queue"])
        self.assertEqual(blur["outputs"], [custom._id])


if __name__ == "__main__":
    unittest.main()
