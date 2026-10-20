"""Build 02.2 regression checks: run `python -m unittest -v test_build_02_2`.

Uses only the standard test runner and the application's existing dependencies.
Synthetic images keep these checks independent of the two sample photographs.
"""

import unittest

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from processor import BOX_COLOR, detect_layers, process_image, resize_image


def structured_image(size):
    """Distinct corners and two coherent regions expose crop/warp mistakes."""
    width, height = size
    image = Image.new("RGB", size, (30, 47, 71))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width // 2, height // 2), fill=(211, 169, 85))
    draw.ellipse((width // 2, height // 3, width - 1, height - 1),
                 fill=(155, 86, 102), outline=(235, 211, 180), width=3)
    draw.line((0, height - 1, width - 1, 0), fill=(191, 231, 210), width=2)
    return image


class CanvasGeometryTests(unittest.TestCase):
    def test_landscape_portrait_square_and_no_upscale(self):
        cases = ((321, 179), (179, 321), (257, 257),
                 (1600, 901), (901, 1600),
                 (3001, 1999), (1999, 3001), (2049, 2049))
        for size in cases:
            with self.subTest(size=size):
                image = structured_image(size)
                scale = min(1, 1600 / max(size))
                expected = tuple(max(1, round(side * scale)) for side in size)
                output = resize_image(image)
                self.assertEqual(output.size, expected)
                self.assertLessEqual(max(output.size), 1600)
                for actual, source in zip(output.size, size):
                    self.assertLessEqual(actual, source)
                    self.assertLessEqual(abs(actual - source * scale), .5)
                reference = (image if expected == size else
                             image.resize(expected, Image.Resampling.LANCZOS))
                self.assertEqual(output.tobytes(), reference.tobytes())

    def test_exif_orientation_is_applied_once(self):
        for orientation, transpose in ((6, Image.Transpose.ROTATE_270),
                                       (8, Image.Transpose.ROTATE_90)):
            with self.subTest(orientation=orientation):
                image = structured_image((241, 383))
                exif = image.getexif()
                exif[274] = orientation
                image.info["exif"] = exif.tobytes()
                output = resize_image(image)
                self.assertEqual(output.size, (383, 241))
                self.assertEqual(output.tobytes(), image.transpose(transpose).tobytes())
                self.assertIsNone(output.getexif().get(274))
                self.assertEqual(resize_image(output).tobytes(), output.tobytes())

    def test_processing_changes_only_blue_overlay_pixels(self):
        for size in ((2101, 1307), (179, 321), (257, 257)):
            with self.subTest(size=size):
                image = structured_image(size)
                source = np.asarray(resize_image(image))
                result = process_image(image, structure=50, seed=0)
                output = np.asarray(result)
                self.assertEqual(output.shape, source.shape)
                changed = np.any(output != source, axis=2)
                self.assertTrue(changed.any())
                self.assertTrue(np.all(output[changed] == BOX_COLOR))
                self.assertTrue(np.array_equal(np.asarray(image),
                                               np.asarray(structured_image(size))))


class FocusTests(unittest.TestCase):
    def assert_valid_layers(self, layers, size):
        width, height = size
        self.assertEqual(len(layers["main"]), 1)
        self.assertGreaterEqual(len(layers["medium"]), 1)
        self.assertLessEqual(len(layers["medium"]), 3)
        self.assertLessEqual(len(layers["micro"]), 9)
        self.assertLessEqual(sum(map(len, layers.values())), 13)
        for boxes in layers.values():
            for left, top, right, bottom in boxes:
                self.assertTrue(0 <= left < right <= width)
                self.assertTrue(0 <= top < bottom <= height)

    def test_automatic_none_and_repeatability(self):
        image = structured_image((240, 180))
        self.assertEqual(detect_layers(image, 50, 0),
                         detect_layers(image, 50, 0, focus=None))
        automatic = process_image(image, 50, 0).tobytes()
        self.assertEqual(automatic, process_image(image, 50, 0, focus=None).tobytes())
        for point in ((0, 0), (239, 179), (100, 85)):
            main = None
            for structure in (0, 50, 100):
                with self.subTest(point=point, structure=structure):
                    layers = detect_layers(image, structure, seed=0, focus=point)
                    self.assertEqual(layers, detect_layers(image, structure, seed=0,
                                                          focus=point))
                    self.assert_valid_layers(layers, image.size)
                    left, top, right, bottom = layers["main"][0]
                    self.assertTrue(left <= point[0] < right)
                    self.assertTrue(top <= point[1] < bottom)
                    if main is not None:
                        self.assertEqual(layers["main"], main)
                    main = layers["main"]
            # PNG-producing rendering is deterministic too, not only its boxes.
            self.assertEqual(process_image(image, 50, 0, point).tobytes(),
                             process_image(image, 50, 0, point).tobytes())
        self.assertNotEqual(detect_layers(image, 50, focus=(0, 0))["main"],
                            detect_layers(image, 50, focus=(239, 179))["main"])

    def test_large_input_focus_maps_to_actual_output_pixels(self):
        image = structured_image((2101, 1307))
        original_size = ImageOps.exif_transpose(image).size
        resized = resize_image(image)
        point = (1750, 1050)
        mapped = (point[0] * resized.width / original_size[0],
                  point[1] * resized.height / original_size[1])
        direct = process_image(image, 50, seed=0, focus=point)
        explicit = process_image(resized, 50, seed=0, focus=mapped)
        self.assertEqual(direct.size, resized.size)
        self.assertEqual(direct.tobytes(), explicit.tobytes())

    def test_blank_tiny_and_edge_fallback_remain_valid(self):
        for size in ((1, 1), (2, 7), (1, 1600), (128, 96)):
            image = Image.new("RGB", size, "black")
            for point in ((0, 0), (size[0] - 1, size[1] - 1)):
                for structure in (0, 100):
                    with self.subTest(size=size, point=point, structure=structure):
                        layers = detect_layers(image, structure, seed=0, focus=point)
                        self.assert_valid_layers(layers, size)
                        left, top, right, bottom = layers["main"][0]
                        self.assertTrue(left <= point[0] < right)
                        self.assertTrue(top <= point[1] < bottom)
                        result = process_image(image, structure, seed=0, focus=point)
                        self.assertEqual(result.size, size)


if __name__ == "__main__":
    unittest.main()
