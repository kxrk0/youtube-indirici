#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yt-dlp format listesinden kalite seçenekleri.

Arayüzden bağımsız: hem web arayüzü hem testler bunu kullanır. Her seçenek
{label, data, short, size, preset} sözlüğüdür:
  label  — tam etiket (araç ipucu, "Diğer" menüsü)
  data   — yt-dlp'ye giden format değeri ("best", "edit_h264", "137+bestaudio/best" ...)
  short  — segmentli kontrolde görünen kısa ad
  size   — tahmini bayt (bilinmiyorsa None)
  preset — True ise segmentli kontrolde doğrudan görünür, değilse "Diğer" menüsünde
"""
import re

# Listede gösterilen en düşük kalite basamağı.
MIN_LISTED_QUALITY = 720

# Satır sırası: önce düzenlemede işe yarayan H.264, sonra verimli AV1.
CODEC_RANK = {'avc1': 0, 'av01': 1, 'vp9': 2}


def format_size(bytes_size) -> str:
    if not bytes_size or bytes_size < 0:
        return "?"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f}{unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f}GB"


def quality_of(fmt) -> int:
    """
    Kalite basamağı (720, 1080, 1440, 2160...).

    Ham `height` yanıltıcı: 3840x1920 sinema oranlı video YouTube'da 2160p
    diye geçiyor ama height 1920 — liste "1920p" gösterip 4K'yı yok
    sayıyordu. Asıl kaynak `format_note`; YouTube'un kendi merdivenini
    veriyor ve her zaman doğru.

    Geometrik hesap yalnızca not yokken (YouTube dışı siteler) devreye
    giriyor. Tek formül yetmiyor, gerçek veriyle ölçüldü:
    yatayda 16:9 karşılığı doğru (3840x1920 → 2160), dikeyde ise
    kısa kenar doğru (1080x1920 → 1080, 16:9 karşılığı 607 verirdi).
    """
    note = (fmt.get('format_note') or '').strip()
    match = re.match(r'^(\d{3,4})p', note)
    if match:
        return int(match.group(1))

    height = fmt.get('height') or 0
    width = fmt.get('width') or 0
    if not height and not width:
        resolution = fmt.get('resolution') or ''
        if 'x' in resolution:
            try:
                width, height = (int(v) for v in resolution.split('x')[:2])
            except ValueError:
                return 0
    if not width:
        return height
    if height > width:
        return width
    return max(height, round(width * 9 / 16))


def codec_family(vcodec: str) -> str:
    v = (vcodec or '').lower()
    if v.startswith(('avc1', 'avc3', 'h264')):
        return 'avc1'
    if v.startswith(('vp09', 'vp9')):
        return 'vp9'
    if v.startswith(('av01', 'av1')):
        return 'av01'
    return v[:4]


def auto_codec_family(formats) -> str:
    """
    'bestvideo' seçiminin hangi codec'e düşeceğini tahmin eder.
    yt-dlp önce çözünürlüğe, eşitlikte codec tercihine bakıyor:
    av01 > vp9 > h264.
    """
    preference = ('av01', 'vp9', 'avc1')
    best_q = 0
    families = set()
    for fmt in formats:
        if (fmt.get('vcodec') or 'none') == 'none':
            continue
        quality = quality_of(fmt)
        family = codec_family(fmt.get('vcodec'))
        if quality > best_q:
            best_q, families = quality, {family}
        elif quality == best_q:
            families.add(family)
    for family in preference:
        if family in families:
            return family
    return next(iter(families), '')


def best_h264_summary(formats):
    """
    En yüksek kaliteli avc1 video + m4a ses için (kalite basamağı, toplam byte).
    Boyut belirlenemezse ikinci değer None döner.
    """
    best_q = 0
    best_size = None
    audio = 0
    for fmt in formats:
        vcodec = (fmt.get('vcodec') or '')
        acodec = (fmt.get('acodec') or '')
        size = fmt.get('filesize') or fmt.get('filesize_approx')
        if vcodec.lower().startswith(('avc1', 'avc3', 'h264')):
            quality = quality_of(fmt)
            # Aynı basamakta boyutu bilinen kaydı tercih et. m3u8 varyantları
            # filesize taşımıyor; listede önce gelirlerse boyut 0 kalıyor ve
            # etiket sadece ses boyutunu gösteriyordu.
            if quality > best_q or (quality == best_q and best_size is None and size):
                best_q, best_size = quality, size
        elif vcodec in ('none', '') and acodec not in ('none', '') and fmt.get('ext') == 'm4a':
            if size and size > audio:
                audio = size
    if not best_q:
        return None, None
    return best_q, (best_size + audio) if best_size else None


def best_quality(formats):
    """Videodaki en yüksek kalite basamağı."""
    best = 0
    for fmt in formats:
        if (fmt.get('vcodec') or 'none') == 'none':
            continue
        best = max(best, quality_of(fmt))
    return best or None


def best_webm_size(formats):
    """Saf WebM seçeneği için en iyi webm video + webm ses toplam boyutu (byte)."""
    video = None
    audio = None
    for fmt in formats:
        if fmt.get('ext') != 'webm':
            continue
        vcodec = fmt.get('vcodec') or ''
        acodec = fmt.get('acodec') or ''
        size = fmt.get('filesize') or fmt.get('filesize_approx')
        is_video = vcodec not in ('', 'none')
        is_audio = acodec not in ('', 'none')
        if is_video and not is_audio:
            key = (fmt.get('height') or 0, fmt.get('fps') or 0)
            if video is None or key > (video[0], video[1]):
                video = (key[0], key[1], size)
        elif is_audio and not is_video:
            abr = fmt.get('abr') or 0
            if audio is None or abr > audio[0]:
                audio = (abr, size)
    if video and audio and video[2] and audio[1]:
        return video[2] + audio[1]
    return None


def format_codec(vcodec: str) -> str:
    if not vcodec or vcodec == 'none':
        return ""
    v = vcodec.lower()
    if 'av01' in v or 'av1' in v:
        return "AV1"
    if 'vp9' in v or 'vp09' in v:
        return "VP9"
    if 'hvc1' in v or 'hev1' in v or 'hevc' in v or 'h265' in v:
        return "H.265"
    if 'avc1' in v or 'avc' in v or 'h264' in v:
        return "H.264"
    if 'vp8' in v:
        return "VP8"
    return vcodec[:8] if len(vcodec) > 8 else vcodec


def _option(label: str, data: str, short: str, size=None, preset: bool = False) -> dict:
    return {'label': label, 'data': data, 'short': short, 'size': size, 'preset': preset}


def build_quality_options(formats) -> list[dict]:
    options = []

    # After Effects / Premiere AV1 ve VP9 çözemiyor: dosya açılıyor, ses
    # geliyor, görüntü siyah kalıyor. YouTube'da en yüksek kalite neredeyse
    # her zaman AV1 olduğu için "En İyi Kalite" düzenleme için tuzak —
    # etiketin bunu söylemesi ve alternatiflerin yanında durması gerekiyor.
    auto_family = auto_codec_family(formats)
    auto_label = "En İyi Kalite (Otomatik)"
    if auto_family in ('av01', 'vp9'):
        auto_label += f" — {'AV1' if auto_family == 'av01' else 'VP9'}, AE açmaz"
    options.append(_option(auto_label, "best", "En iyi", preset=True))

    # avc1 akışı olmayan videoda bu seçeneğin sunacağı bir şey yok —
    # dönüştürme gerektiği için "Maks" satırı zaten o işi yapıyor.
    h264_q, h264_size = best_h264_summary(formats)
    if h264_q:
        h264_label = f"AE/Premiere — H.264 · {h264_q}p"
        h264_label += f" · {format_size(h264_size) if h264_size else '?'}"
        options.append(_option(h264_label, "edit_h264", f"AE {h264_q}p", h264_size, preset=True))

    best_q = best_quality(formats)
    max_label = "AE/Premiere — Maks"
    if best_q:
        max_label += f" · {best_q}p"
    max_label += " · dönüştürür"
    options.append(_option(max_label, "edit_h264_max", "AE maks", preset=True))

    webm_size = best_webm_size(formats)
    size_str = format_size(webm_size) if webm_size else "?"
    options.append(_option(f"Saf WebM · VP9/Opus · {size_str}", "webm", "WebM", webm_size, preset=True))

    # Aynı çözünürlük+codec için hem https hem m3u8 varyantı geliyor. m3u8
    # olanlar filesize taşımadığı için listede "(?)" boyutlu kopyalar
    # oluşturuyordu; https karşılığı varken onları gösterme.
    https_variants = {
        (quality_of(f), codec_family(f.get('vcodec')))
        for f in formats
        if not (f.get('protocol') or '').startswith('m3u8')
        and (f.get('vcodec') or 'none') != 'none'
    }

    available = []
    for fmt in formats:
        vcodec = fmt.get('vcodec', '')
        if vcodec == 'none' or not vcodec:
            continue
        family = codec_family(vcodec)
        quality = quality_of(fmt)
        if (fmt.get('protocol') or '').startswith('m3u8') and (quality, family) in https_variants:
            continue
        filesize = fmt.get('filesize') or fmt.get('filesize_approx')
        fps = fmt.get('fps') or 0
        dynamic_range = fmt.get('dynamic_range')

        # Codec adı zaten uyumluluğu söylüyor (H.264 açılır, AV1/VP9
        # açılmaz) ve konteyner birleştirmeden sonra her zaman MP4 —
        # ikisini de satıra yazmak listeyi gereksiz genişletiyordu.
        parts = [f"{quality}p" if quality else "Bilinmeyen", format_codec(vcodec)]
        if fps > 30:
            parts.append(f"{int(fps)}fps")
        if dynamic_range and dynamic_range != 'SDR':
            parts.append("HDR")
        parts.append(format_size(filesize) if filesize else "?")
        available.append({
            'id': fmt.get('format_id'),
            'label': " · ".join(p for p in parts if p),
            'short': " ".join(p for p in parts[:2] if p),
            'size': filesize,
            'quality': quality,
            'rank': CODEC_RANK.get(family, 9),
            'fps': fps,
        })

    # 720p altı satırlar listeyi şişiriyor ve pratikte seçilmiyor. Hiç
    # yüksek çözünürlük yoksa (eski/düşük kaliteli video) hepsini göster.
    qualified = [row for row in available if row['quality'] >= MIN_LISTED_QUALITY] or available

    seen = set()
    for row in sorted(qualified, key=lambda r: (-r['quality'], r['rank'], -r['fps'])):
        if row['label'] in seen:
            continue
        options.append(_option(row['label'], f"{row['id']}+bestaudio/best", row['short'], row['size']))
        seen.add(row['label'])
    return options
