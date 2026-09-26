#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zamanlanmış görevler ve kanal abonelikleri: ne zaman ne indirileceğine karar veren saf mantık.
Döngüleri ve indirmeyi başlatmayı çağıran taraf (web köprüsü) yapar.

Zaman biçimleri (scheduled_tasks.schedule_time):
  "HH:MM"             her gün o dakikada (repeat_daily) ya da ilk gelen o dakikada bir kez
  "YYYY-MM-DD HH:MM"  o anda bir kez; uygulama kapalıyken geçtiyse açılışta yakalanır
"""
import datetime
from typing import Iterable

DAILY_FORMAT = '%H:%M'
ONCE_FORMAT = '%Y-%m-%d %H:%M'


def parse_schedule(text: str) -> tuple[str, object]:
    """('daily', 'HH:MM') ya da ('once', datetime). Geçersizse ValueError."""
    text = (text or '').strip()
    try:
        datetime.datetime.strptime(text, DAILY_FORMAT)
        return 'daily', text
    except ValueError:
        pass
    try:
        return 'once', datetime.datetime.strptime(text, ONCE_FORMAT)
    except ValueError:
        raise ValueError(f"Zaman 'SS:DD' ya da 'YYYY-AA-GG SS:DD' olmalı, gelen: {text!r}") from None


def firing_key(task: dict, now: datetime.datetime) -> tuple:
    """Aynı görevin aynı gün (günlük) ya da hiç (tek seferlik) ikinci kez tetiklenmemesi için anahtar."""
    kind, _ = parse_schedule(task.get('schedule_time', ''))
    return (task['id'], now.date()) if kind == 'daily' else (task['id'], 'once')


def due_tasks(tasks: Iterable[dict], now: datetime.datetime, fired: set) -> list[dict]:
    """
    Şu an çalışması gereken görevler. `fired` bu süreçte tetiklenenlerin anahtarları.
    Veritabanındaki last_run UTC yazılıyor, yerel saatle karşılaştırılamaz; tekrarı bu küme önler.
    """
    out = []
    for task in tasks:
        try:
            kind, when = parse_schedule(task.get('schedule_time', ''))
        except ValueError as e:
            print(f"[Zamanlayıcı] Görev {task.get('id')} atlandı: {e}")
            continue
        if firing_key(task, now) in fired:
            continue
        if kind == 'daily' and now.strftime(DAILY_FORMAT) == when:
            out.append(task)
        elif kind == 'once' and when <= now:
            out.append(task)
    return out


def is_one_shot(task: dict) -> bool:
    kind, _ = parse_schedule(task.get('schedule_time', ''))
    return kind == 'once' or not task.get('repeat_daily')
