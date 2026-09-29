#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veri klasörü testleri. 2.7.0'dan önce ayar ve geçmiş EXE'nin yanındaki cache\\ klasöründeydi;
Program Files'a kurulan EXE oraya yazamaz, veri %LOCALAPPDATA%\\YouTubeIndirici'ye taşındı.
"""
import os
import sys

import pytest

from src.utils import helpers


@pytest.fixture
def frozen_app(tmp_path, monkeypatch):
    """Kurulu EXE gibi davranır: EXE tmp/app içinde, LOCALAPPDATA tmp/local."""
    app_dir = tmp_path / 'app'
    app_dir.mkdir()
    local = tmp_path / 'local'
    local.mkdir()
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(app_dir / 'YouTubeIndirici.exe'))
    monkeypatch.setenv('LOCALAPPDATA', str(local))
    return app_dir, local


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def test_frozen_data_lives_in_local_appdata_not_next_to_exe(frozen_app):
    app_dir, local = frozen_app
    assert helpers.get_data_dir() == str(local / 'YouTubeIndirici')
    assert helpers.get_plugins_dir() == str(local / 'YouTubeIndirici' / 'plugins')
    assert not helpers.get_data_dir().startswith(str(app_dir))


def test_migrates_cache_and_plugins_from_next_to_exe(frozen_app):
    app_dir, local = frozen_app
    _write(app_dir / 'cache' / 'config.json', '{"theme": "light"}')
    _write(app_dir / 'cache' / 'thumbnails' / 'a.jpg', 'jpg')
    _write(app_dir / 'plugins' / 'benim.py', 'PLUGIN_NAME = "x"')
    assert helpers.migrate_legacy_data() == str(app_dir)
    data = local / 'YouTubeIndirici'
    assert (data / 'config.json').read_text(encoding='utf-8') == '{"theme": "light"}'
    assert (data / 'thumbnails' / 'a.jpg').exists()
    assert (data / 'plugins' / 'benim.py').exists()
    assert (app_dir / 'cache' / 'config.json').exists(), 'eski veri yedek olarak kalmalı'


def test_migrates_from_the_old_per_user_install(frozen_app):
    _, local = frozen_app
    _write(local / 'Programs' / 'YouTubeIndirici' / 'cache' / 'history.db', 'db')
    assert helpers.migrate_legacy_data() == str(local / 'Programs' / 'YouTubeIndirici')
    assert (local / 'YouTubeIndirici' / 'history.db').read_text(encoding='utf-8') == 'db'


def test_does_not_overwrite_existing_data(frozen_app):
    app_dir, local = frozen_app
    _write(app_dir / 'cache' / 'config.json', 'eski')
    _write(local / 'YouTubeIndirici' / 'config.json', 'yeni')
    assert helpers.migrate_legacy_data() is None
    assert (local / 'YouTubeIndirici' / 'config.json').read_text(encoding='utf-8') == 'yeni'


def test_no_legacy_data_creates_nothing(frozen_app):
    _, local = frozen_app
    assert helpers.migrate_legacy_data() is None
    assert not (local / 'YouTubeIndirici').exists()


def test_source_mode_keeps_project_cache(monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)
    assert helpers.get_data_dir() == os.path.join(helpers.get_app_dir(), 'cache')
    assert helpers.migrate_legacy_data() is None


def test_finds_ffmpeg_where_the_installer_puts_it(frozen_app, tmp_path, monkeypatch):
    program_files = tmp_path / 'Program Files'
    ffmpeg_bin = program_files / 'FFmpeg' / 'bin'
    _write(ffmpeg_bin / 'ffmpeg.exe', 'exe')
    monkeypatch.setenv('ProgramFiles', str(program_files))
    assert helpers.get_ffmpeg_path() == str(ffmpeg_bin)
