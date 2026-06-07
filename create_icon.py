#!/usr/bin/env python3
"""Uygulama ICO ikonu oluşturur (Pillow gerekli)"""
import os
from PIL import Image, ImageDraw

def create_app_icon():
    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        m = max(1, size // 10)
        draw.ellipse([m, m, size - m - 1, size - m - 1], fill=(0, 120, 212, 255))

        cx = size // 2
        sw = max(2, size // 7)
        top = size // 4
        mid = size // 2
        draw.rectangle([cx - sw // 2, top, cx + sw // 2, mid], fill='white')

        hw = size // 3
        hh = size // 4
        arrow = [
            (cx - hw // 2, mid),
            (cx + hw // 2, mid),
            (cx, mid + hh),
        ]
        draw.polygon(arrow, fill='white')

        images.append(img)

    out = os.path.join('extension', 'icons', 'app.ico')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    images[0].save(out, format='ICO', sizes=[(s, s) for s in sizes], append_images=images[1:])
    print(f"Icon olusturuldu: {out}")

def create_extension_icons():
    """Tarayıcı eklentisi için PNG ikonları oluşturur"""
    for size in [16, 48, 128]:
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        m = max(1, size // 10)
        draw.ellipse([m, m, size - m - 1, size - m - 1], fill=(0, 120, 212, 255))
        cx = size // 2
        sw = max(1, size // 7)
        top = size // 4
        mid = size // 2
        draw.rectangle([cx - sw // 2, top, cx + sw // 2, mid], fill='white')
        hw = size // 3
        hh = size // 4
        arrow = [(cx - hw // 2, mid), (cx + hw // 2, mid), (cx, mid + hh)]
        draw.polygon(arrow, fill='white')
        out = os.path.join('extension', 'icons', f'icon{size}.png')
        img.save(out, format='PNG')
        print(f"Icon olusturuldu: {out}")


if __name__ == '__main__':
    create_app_icon()
    create_extension_icons()
