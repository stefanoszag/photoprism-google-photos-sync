"""Tests for the image resizer module."""

import pytest

pytest.importorskip("PIL")

from pathlib import Path  # noqa: E402
from unittest.mock import patch  # noqa: E402

from PIL import Image  # noqa: E402

from resizer.main import _is_image, _list_image_paths, _resize_one, resize_images  # noqa: E402


class TestIsImage:
    """Tests for _is_image."""

    def test_recognizes_common_image_extensions(self):
        assert _is_image(Path("photo.jpg")) is True
        assert _is_image(Path("photo.jpeg")) is True
        assert _is_image(Path("photo.png")) is True
        assert _is_image(Path("photo.gif")) is True
        assert _is_image(Path("photo.webp")) is True

    def test_rejects_non_image_extensions(self):
        assert _is_image(Path("document.pdf")) is False
        assert _is_image(Path("readme.txt")) is False
        assert _is_image(Path("data.csv")) is False
        assert _is_image(Path("file")) is False


class TestListImagePaths:
    """Tests for _list_image_paths."""

    def test_empty_directory_returns_empty_list(self, temp_shared_dir):
        result = _list_image_paths(str(temp_shared_dir))
        assert result == []

    def test_returns_only_image_files(self, temp_shared_dir):
        (temp_shared_dir / "a.jpg").touch()
        (temp_shared_dir / "b.png").touch()
        (temp_shared_dir / "c.txt").touch()
        (temp_shared_dir / "d.pdf").touch()
        result = _list_image_paths(str(temp_shared_dir))
        assert len(result) == 2
        names = {p.name for p in result}
        assert names == {"a.jpg", "b.png"}

    def test_non_directory_returns_empty_list(self, tmp_path):
        file_path = tmp_path / "not_a_dir"
        file_path.touch()
        result = _list_image_paths(str(file_path))
        assert result == []


class TestResizeOne:
    """Tests for _resize_one."""

    def test_resizes_image_and_preserves_aspect_ratio(self, temp_shared_dir):
        path = temp_shared_dir / "test.jpg"
        img = Image.new("RGB", (200, 100), color="red")
        img.save(str(path), format="JPEG", quality=95)

        result = _resize_one(path, 50)

        assert result is True
        with Image.open(path) as out:
            assert out.size == (100, 50)

    def test_returns_true_when_dimensions_unchanged(self, temp_shared_dir):
        path = temp_shared_dir / "small.jpg"
        img = Image.new("RGB", (2, 2), color="blue")
        img.save(str(path), format="JPEG")

        result = _resize_one(path, 100)

        assert result is True
        with Image.open(path) as out:
            assert out.size == (2, 2)

    def test_returns_false_for_invalid_image(self, temp_shared_dir):
        path = temp_shared_dir / "not_an_image.jpg"
        path.write_text("not image data")

        result = _resize_one(path, 50)

        assert result is False

    def test_resizes_png_and_preserves_format(self, temp_shared_dir):
        path = temp_shared_dir / "test.png"
        img = Image.new("RGB", (100, 80), color="green")
        img.save(str(path), format="PNG")

        result = _resize_one(path, 50)

        assert result is True
        with Image.open(path) as out:
            assert out.size == (50, 40)
            assert out.format == "PNG"


class TestResizeImages:
    """Tests for resize_images (integration with config)."""

    @patch("resizer.main.config.RESIZE_ENABLED", False)
    def test_returns_empty_dict_when_disabled(self):
        result = resize_images()
        assert result == {}

    @patch("resizer.main.config.RESIZE_ENABLED", True)
    @patch("resizer.main.config.RESIZE_PERCENTAGE", 100)
    def test_returns_empty_dict_when_percentage_100(self):
        result = resize_images()
        assert result == {}

    @patch("resizer.main.config.RESIZE_ENABLED", True)
    @patch("resizer.main.config.RESIZE_PERCENTAGE", 50)
    @patch("resizer.main.config.SHARED_FOLDER", "/nonexistent/path/12345")
    def test_returns_zero_stats_when_folder_missing(self):
        result = resize_images()
        assert result == {"processed": 0, "skipped": 0, "errors": 0}

    @patch("resizer.main.config.RESIZE_ENABLED", True)
    @patch("resizer.main.config.RESIZE_PERCENTAGE", 50)
    def test_returns_zero_stats_when_folder_empty(self, temp_shared_dir):
        with patch("resizer.main.config.SHARED_FOLDER", str(temp_shared_dir)):
            result = resize_images()
        assert result == {"processed": 0, "skipped": 0, "errors": 0}

    @patch("resizer.main.config.RESIZE_ENABLED", True)
    @patch("resizer.main.config.RESIZE_PERCENTAGE", 50)
    def test_resizes_images_in_folder_and_returns_stats(self, temp_shared_dir):
        (temp_shared_dir / "one.jpg").parent.mkdir(parents=True, exist_ok=True)
        for name in ["one.jpg", "two.png"]:
            img = Image.new("RGB", (60, 40), color="red")
            img.save(str(temp_shared_dir / name), format="JPEG" if name.endswith("jpg") else "PNG")

        with patch("resizer.main.config.SHARED_FOLDER", str(temp_shared_dir)):
            result = resize_images()

        assert result["processed"] == 2
        assert result["errors"] == 0
        assert result["skipped"] == 0
        with Image.open(temp_shared_dir / "one.jpg") as img:
            assert img.size == (30, 20)
        with Image.open(temp_shared_dir / "two.png") as img:
            assert img.size == (30, 20)

    @patch("resizer.main.config.RESIZE_ENABLED", True)
    @patch("resizer.main.config.RESIZE_PERCENTAGE", 50)
    def test_counts_errors_for_invalid_files(self, temp_shared_dir):
        (temp_shared_dir / "good.jpg").parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), color="red").save(str(temp_shared_dir / "good.jpg"), format="JPEG")
        (temp_shared_dir / "bad.jpg").write_text("not an image")

        with patch("resizer.main.config.SHARED_FOLDER", str(temp_shared_dir)):
            result = resize_images()

        assert result["processed"] == 1
        assert result["errors"] == 1
        assert result["skipped"] == 0
