"""Owner artwork derivatives and build inputs; no dependency on desktop caches."""
import importlib.util
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('generate_icons', ROOT / 'scripts/generate-icons.py')
icons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(icons)


def test_exterior_removal_preserves_enclosed_black_and_colour():
    image = Image.new('RGBA', (9, 9), (0, 0, 0, 255))
    for x in range(2, 7):
        for y in range(2, 7): image.putpixel((x, y), (70, 230, 120, 255))
    image.putpixel((4, 4), (0, 0, 0, 255))
    cleaned = icons.transparent_artwork(image)
    assert cleaned.getpixel((0, 0))[3] == 0
    assert cleaned.getpixel((2, 2)) == image.getpixel((2, 2))
    assert cleaned.getpixel((4, 4)) == (0, 0, 0, 255)
    assert image.getpixel((0, 0))[3] == 255  # Never overwrite the supplied original.


def test_all_consumers_use_transparent_derivatives_of_owner_artwork():
    source = Image.open(icons.SOURCE).convert('RGBA')
    assert source.getpixel((0, 0))[3] == 255
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        image = Image.open(ROOT / f'data/icons/{size}x{size}.png').convert('RGBA')
        assert image.size == (size, size)
        assert image.getpixel((0, 0))[3] == 0
        assert image.getchannel('A').getextrema() == (0, 255)
    assert Image.open(ROOT / 'src-tauri/icons/icon.png').tobytes() == Image.open(ROOT / 'data/icons/512x512.png').tobytes()
    build = (ROOT / 'src-tauri/build.rs').read_text()
    assert 'cargo:rerun-if-changed=icons' in build
    assert 'cargo:rerun-if-changed=tauri.conf.json' in build