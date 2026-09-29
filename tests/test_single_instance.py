#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tek kopya. Arka plan: tepsideki kopya dururken masaüstünden açılan ikinci kopya güncellemeyi
başlattı; öteki EXE'yi kilitli tuttuğu için sessiz kurulum iptal oldu (2.7.0 -> 2.7.1).
"""
import os
import subprocess
import sys
import time
import uuid

import pytest

from src.web.single_instance import SingleInstance

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows adlandırılmış nesneleri')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAIT_S = 10

# İlk kopya: kilidi alır, hazır olduğunu yazar, "öne gel" isteğinde işaret dosyası yazar; stdin
# kapanınca çıkar. kill() yetmez: venv'in python.exe'si asıl Python'u alt süreç olarak başlatıyor,
# başlatıcıyı öldürmek kilidi tutan alt süreci bırakıyor.
FIRST_INSTANCE = '''
import sys
sys.path.insert(0, {root!r})
from src.web.single_instance import SingleInstance
inst = SingleInstance({key!r})
assert inst.acquire()
inst.listen(lambda: open({shown!r}, 'a').write('x'))
print('hazir', flush=True)
sys.stdin.read()
'''


def _wait_for(check, timeout_s=WAIT_S):
    end = time.time() + timeout_s
    while time.time() < end:
        if check():
            return True
        time.sleep(0.05)
    return False


def test_second_launch_signals_the_running_copy(tmp_path):
    key = f'test-{uuid.uuid4()}'
    shown = tmp_path / 'shown.txt'
    first = subprocess.Popen([sys.executable, '-c', FIRST_INSTANCE.format(root=ROOT, key=key, shown=str(shown))],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert first.stdout.readline().strip() == 'hazir'
        second = SingleInstance(key)
        assert second.acquire() is False, 'ikinci kopya kilidi alamamalı'
        second.signal_existing()
        assert _wait_for(lambda: shown.exists() and shown.read_text() == 'x'), 'çalışan kopya öne gelme isteğini almadı'
        SingleInstance(key).signal_existing()
        assert _wait_for(lambda: shown.read_text() == 'xx'), 'her açılış ayrı bir istek olmalı'
    finally:
        first.stdin.close()
        first.wait(timeout=WAIT_S)


def test_lock_is_released_when_the_copy_exits(tmp_path):
    key = f'test-{uuid.uuid4()}'
    first = subprocess.Popen([sys.executable, '-c', FIRST_INSTANCE.format(root=ROOT, key=key, shown=str(tmp_path / 's'))],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert first.stdout.readline().strip() == 'hazir'
    first.stdin.close()
    first.wait(timeout=WAIT_S)
    assert SingleInstance(key).acquire() is True


def test_different_data_dirs_do_not_block_each_other():
    a, b = SingleInstance(f'a-{uuid.uuid4()}'), SingleInstance(f'b-{uuid.uuid4()}')
    assert a.acquire() is True
    assert b.acquire() is True


def test_signal_without_running_copy_fails_loudly(monkeypatch):
    monkeypatch.setattr('src.web.single_instance.SIGNAL_RETRIES', 2)
    with pytest.raises(OSError, match='ulaşılamadı'):
        SingleInstance(f'yok-{uuid.uuid4()}').signal_existing()
