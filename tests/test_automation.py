#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zamanlayıcı kararı ve ayar doğrulaması."""
import datetime
from unittest.mock import patch

import pytest

from src.core import automation, settings_schema

NOW = datetime.datetime(2026, 9, 25, 21, 30)


def test_gunluk_gorev_dakikasinda_bir_kez_tetiklenir():
    task = {'id': 1, 'schedule_time': '21:30', 'repeat_daily': 1}
    fired = set()
    assert automation.due_tasks([task], NOW, fired) == [task]
    fired.add(automation.firing_key(task, NOW))
    # aynı dakikada ikinci kontrol (döngü 30 sn'de bir) yeniden başlatmamalı
    assert automation.due_tasks([task], NOW + datetime.timedelta(seconds=30), fired) == []
    # ertesi gün yine tetiklenir
    assert automation.due_tasks([task], NOW + datetime.timedelta(days=1), fired) == [task]


def test_tek_seferlik_gecmis_gorev_acilista_yakalanir():
    task = {'id': 2, 'schedule_time': '2026-09-25 08:00'}
    assert automation.due_tasks([task], NOW, set()) == [task]
    assert automation.is_one_shot(task)


def test_gelecekteki_gorev_ve_bozuk_zaman_tetiklenmez():
    tasks = [{'id': 3, 'schedule_time': '2026-09-26 08:00'}, {'id': 4, 'schedule_time': 'yarın sabah'}]
    assert automation.due_tasks(tasks, NOW, set()) == []


def test_bozuk_zaman_aciklayici_hata():
    with pytest.raises(ValueError, match='SS:DD'):
        automation.parse_schedule('25:99')


@pytest.mark.parametrize('key,value,error', [
    ('max_concurrent', 9, ValueError),
    ('max_concurrent', '3', TypeError),
    ('auto_organize', 1, TypeError),
    ('audio_quality', '999', ValueError),
    ('bilinmeyen', 'x', KeyError),
])
def test_ayar_dogrulamasi_gecersizi_reddeder(key, value, error):
    with pytest.raises(error):
        settings_schema.validate(key, value)


def test_gecerli_ayar_yazilir():
    with patch('src.core.settings_schema.cfg.set_value') as setter:
        settings_schema.write('speed_limit', 10)
        settings_schema.write('proxy', '  http://h:1  ')
    assert setter.call_args_list[0].args == ('speed_limit', 10)
    assert setter.call_args_list[1].args == ('proxy', 'http://h:1')


def test_esz_zamanli_sinir_calisirken_buyutulebilir():
    import threading
    import time
    from src.core.download_job import ConcurrencyLimiter
    lim = ConcurrencyLimiter(1)
    lim.acquire()
    entered = threading.Event()
    t = threading.Thread(target=lambda: (lim.acquire(), entered.set()), daemon=True)
    t.start()
    time.sleep(0.05)
    assert not entered.is_set(), 'sınır 1 iken ikinci iş beklemeli'
    lim.set_limit(2)
    assert entered.wait(1), 'sınır 2 olunca bekleyen iş başlamalı'
