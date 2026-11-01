#!/usr/bin/env python3
"""Generate application and desktop icons from the source artwork."""
from pathlib import Path
from collections import deque
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/io.github.DevVoidPL.NarratorVerse.png'


def transparent_artwork(source):
    """Remove only near-black exterior connected to the edges, never interior ink."""
    image = source.convert('RGBA').copy()
    width, height = image.size
    pixels = image.load()
    visited = set()
    pending = deque([(x, y) for x in range(width) for y in (0, height - 1)] +
                    [(x, y) for y in range(height) for x in (0, width - 1)])
    while pending:
        x, y = pending.popleft()
        if (x, y) in visited or not (0 <= x < width and 0 <= y < height): continue
        visited.add((x, y))
        red, green, blue, alpha = pixels[x, y]
        if alpha and max(red, green, blue) > 60: continue
        pixels[x, y] = (0, 0, 0, 0)
        pending.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    return image


def generate():
    image = transparent_artwork(Image.open(SOURCE))
    image = image.crop(image.getbbox())
    side = max(image.size)
    canvas = Image.new('RGBA', (side, side))
    canvas.paste(image, ((side-image.width)//2, (side-image.height)//2))
    canvas.save(ROOT / 'data/icons/artwork.png')
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        destination = ROOT / 'data/icons' / f'{size}x{size}.png'
        destination.parent.mkdir(parents=True, exist_ok=True)
        canvas.resize((size, size), Image.Resampling.NEAREST).save(destination)
    for name, size in (('32x32.png', 32), ('128x128.png', 128), ('128x128@2x.png', 256), ('icon.png', 512)):
        canvas.resize((size, size), Image.Resampling.NEAREST).save(ROOT / 'src-tauri/icons' / name)


if __name__ == '__main__': generate()