#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Başlıksız pencere regresyon testi (gerçek pencere açar).

Arka plan: başlık çubuğu arayüzün içine alındıktan sonra her büyüt → geri al'da pencere
31 px uzuyordu. WinForms normal boyutu istemci alanı olarak saklayıp geri alırken başlıklı
çerçeve payını ekliyordu. Test bu uzamanın geri gelmesini engelliyor.

Ekranda kısa süre pencere açtığı için yalnız ORTAM_GUI_TESTS=1 ile çalışır.
"""
import json
import os
import subprocess
import sys
import textwrap

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != 'win32' or os.environ.get('ORTAM_GUI_TESTS') != '1',
    reason='gerçek pencere açar; ORTAM_GUI_TESTS=1 ile çalıştır',
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_TIMEOUT_S = 90

SCRIPT = textwrap.dedent('''
    import ctypes, json, sys, time
    from ctypes import wintypes
    import webview
    from src.web import app as webapp, window_frame

    u = ctypes.windll.user32
    window = webview.create_window('frame-test', html='<body style="background:#151719"></body>',
                                   width=900, height=640)
    memo = {}
    heights = {}

    def rect_height(h):
        r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r)); return r.bottom - r.top

    def drive():
        time.sleep(1.5)
        h = window.native.Handle.ToInt64()
        frame = window_frame.CaptionlessFrame(h, on_left_normal=lambda: webapp._fix_restore_bounds(window.native, h, memo))
        time.sleep(0.5)
        heights['start'] = rect_height(h)
        for i in range(2):
            window_frame.system_command(h, window_frame.SC_MAXIMIZE); time.sleep(1.0)
            window_frame.system_command(h, window_frame.SC_RESTORE); time.sleep(1.0)
            heights[f'restore_{i}'] = rect_height(h)
        window_frame.system_command(h, window_frame.SC_MINIMIZE); time.sleep(1.0)
        window_frame.system_command(h, window_frame.SC_RESTORE); time.sleep(1.0)
        heights['unminimize'] = rect_height(h)
        print(json.dumps(heights), flush=True)
        del frame
        window.destroy()

    webview.start(drive, gui='edgechromium')
''')


def test_maximize_and_minimize_cycles_keep_window_height():
    result = subprocess.run([sys.executable, '-c', SCRIPT], cwd=ROOT, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=RUN_TIMEOUT_S)
    lines = [l for l in result.stdout.splitlines() if l.startswith('{')]
    assert lines, f'test penceresi sonuç vermedi:\n{result.stdout}\n{result.stderr}'
    heights = json.loads(lines[-1])
    start = heights.pop('start')
    assert heights == {k: start for k in heights}, f'başlangıç {start}, sonra {heights}'
