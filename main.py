#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

# Windows konsolu varsayılan cp1254'te emoji/Unicode print'i UnicodeEncodeError verir.
# stdout/stderr'i UTF-8'e sabitle; desteklenmeyen konsollarda çökme yerine sessizce geç.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from src.core.downloader import Downloader

# Tarayıcı eklentisi katmanı kaldırıldı: arayüz yalnızca masaüstü penceresidir (src/web),
# --url / --no-gui ile komut satırından da indirilebilir.


def _run_cli(args):
    """--no-gui CLI modu — indirmeyi doğrudan çalıştırır."""
    from src.utils.helpers import setup_ffmpeg_path, get_os_download_dir
    setup_ffmpeg_path()

    dl = Downloader()
    output = args.output or get_os_download_dir()
    fmt_type = args.type or 'video'

    print(f"[CLI] İndirme başlatılıyor: {args.url}")
    print(f"[CLI] Çıktı: {output}  Format: {args.format or 'best'}  Tür: {fmt_type}")

    result = dl.process_extension_request(
        video_url=args.url,
        format_quality=args.format or 'best',
        format_type=fmt_type,
        output_path=output,
    )
    if result.get('status') == 'error':
        print(f"[CLI] HATA: {result.get('message', 'Bilinmeyen hata')}")
        return 1
    print("[CLI] Tamamlandı!")
    return 0


def main():
    import argparse
    parser = argparse.ArgumentParser(
        prog='ydl',
        description='YDL İndirici — GUI veya CLI modunda çalışır'
    )
    parser.add_argument('--url',     help='İndirilecek URL', default=None)
    parser.add_argument('--format',  help='Format (best/audio/1080p/720p/...)', default='best')
    parser.add_argument('--type',    help='Tür (video/audio)', default='video')
    parser.add_argument('--output',  help='Çıktı klasörü', default=None)
    parser.add_argument('--no-gui',  action='store_true', help='GUI olmadan çalıştır')
    args, _ = parser.parse_known_args()

    if args.url or args.no_gui:
        sys.exit(_run_cli(args))

    from src.web.app import main as run_app
    run_app()


if __name__ == "__main__":
    main()
