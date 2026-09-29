#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Geçmiş veritabanının ilk açılışı. Arka plan: yeni kurulumun ilk açılışında arayüzün açılış
çağrısı ve zamanlayıcı iş parçacığı veritabanını aynı anda oluşturdu; ikisi de WAL'a geçmeye
çalışınca biri "database is locked" aldı ve açılış verisi yüklenemedi (2.7.4 duman testinde,
yedi açılışta bir; uygulama günlüğü sayesinde görüldü).
"""
import threading

import pytest

from src.core import database

THREADS = 16
ROUNDS = 5
JOIN_TIMEOUT_S = 30


@pytest.fixture
def fresh_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(database, '_history_instance', None)
    return tmp_path


def _race(data_dir, monkeypatch):
    monkeypatch.setattr(database, 'get_data_dir', lambda: str(data_dir))
    monkeypatch.setattr(database, '_history_instance', None)
    start = threading.Barrier(THREADS)
    instances, errors = [], []

    def worker():
        start.wait()
        try:
            history = database.get_download_history()
            history.get_all_downloads(limit=1)
            instances.append(history)
        except Exception as e:  # noqa: BLE001  (testte her hata toplanıp gösterilir)
            errors.append(repr(e))

    threads = [threading.Thread(target=worker) for _ in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(JOIN_TIMEOUT_S)
    return instances, errors


def test_concurrent_first_use_creates_one_database(fresh_data_dir, monkeypatch):
    for n in range(ROUNDS):
        data_dir = fresh_data_dir / f'tur{n}'
        data_dir.mkdir()
        instances, errors = _race(data_dir, monkeypatch)
        assert errors == [], f'tur {n}: {errors[:3]}'
        assert len(instances) == THREADS
        assert len({id(i) for i in instances}) == 1, 'tek bir DownloadHistory olmalı'
