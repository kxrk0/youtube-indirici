#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
from unittest.mock import MagicMock, patch


# ─── Updater ────────────────────────────────────────────────────────────────

from src.utils.updater import _compare_versions, get_current_version


def test_compare_versions_newer():
    assert _compare_versions("2.0.0", "2.1.0") is True


def test_compare_versions_older():
    assert _compare_versions("2.1.0", "2.0.0") is False


def test_compare_versions_equal():
    assert _compare_versions("2.2.0", "2.2.0") is False


def test_compare_versions_with_v_prefix():
    assert _compare_versions("2.0.0", "v2.1.0") is True


def test_get_current_version():
    v = get_current_version()
    assert isinstance(v, str)
    parts = v.split(".")
    assert len(parts) == 3


# ─── Helpers ────────────────────────────────────────────────────────────────

from src.utils.helpers import (
    is_valid_url,
    detect_platform,
    format_size,
    format_duration,
)


@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
    ("https://youtu.be/dQw4w9WgXcQ", True),
    ("https://www.youtube.com/shorts/abc123", True),
    ("https://vimeo.com/123456789", True),
    ("https://twitter.com/user/status/1", True),
    ("https://x.com/user/status/1", True),
    ("https://www.dailymotion.com/video/x7tgd0", True),
    ("https://www.reddit.com/r/videos/", False),
    ("not_a_url", False),
    ("", False),
    ("   ", False),
    ("http://youtube.com/watch?v=abc", True),
])
def test_is_valid_url(url, expected):
    assert is_valid_url(url) == expected


@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/shorts/abc", "youtube_shorts"),
    ("https://www.youtube.com/watch?v=abc", "youtube"),
    ("https://youtu.be/abc", "youtube"),
    ("https://vimeo.com/123", "vimeo"),
    ("https://twitter.com/user/status/1", "twitter"),
    ("https://x.com/user/status/1", "twitter"),
    ("https://www.dailymotion.com/video/x7tgd0", "dailymotion"),
    ("https://unknown.site/video", "unknown"),
    ("", "unknown"),
])
def test_detect_platform(url, expected):
    assert detect_platform(url) == expected


@pytest.mark.parametrize("size,expected_contains", [
    (0, "0.00 B"),
    (1023, "B"),
    (1024, "1.00 KB"),
    (1048576, "1.00 MB"),
    (1073741824, "1.00 GB"),
    (-1, "Bilinmiyor"),
])
def test_format_size(size, expected_contains):
    result = format_size(size)
    assert expected_contains in result


@pytest.mark.parametrize("secs,expected", [
    (0, "00:00"),
    (59, "00:59"),
    (60, "01:00"),
    (3661, "1:01:01"),
    (-1, "Bilinmiyor"),
])
def test_format_duration(secs, expected):
    assert format_duration(secs) == expected


# ─── Config ─────────────────────────────────────────────────────────────────

def test_config_get_defaults(tmp_path, monkeypatch):
    import src.utils.config as cfg
    monkeypatch.setattr(cfg, '_CONFIG_PATH', str(tmp_path / 'config.json'))
    monkeypatch.setattr(cfg, '_CONFIG_DIR', str(tmp_path))
    monkeypatch.setattr(cfg, '_cache', {})
    monkeypatch.setattr(cfg, '_loaded', False)

    assert cfg.get('theme') == 'dark'
    assert cfg.get('speed_limit') == 0


def test_config_set_and_get(tmp_path, monkeypatch):
    import src.utils.config as cfg
    monkeypatch.setattr(cfg, '_CONFIG_PATH', str(tmp_path / 'config.json'))
    monkeypatch.setattr(cfg, '_CONFIG_DIR', str(tmp_path))
    monkeypatch.setattr(cfg, '_cache', {})
    monkeypatch.setattr(cfg, '_loaded', False)

    cfg.set_value('proxy', 'http://proxy:8080')
    monkeypatch.setattr(cfg, '_cache', {})
    monkeypatch.setattr(cfg, '_loaded', False)
    assert cfg.get('proxy') == 'http://proxy:8080'


# ─── Downloader (unit, no network) ──────────────────────────────────────────

from src.core.downloader import Downloader, DownloadTask, DOWNLOAD_STATUS_CANCELLED


def test_download_task_cancel():
    task = DownloadTask("https://youtube.com/watch?v=test", "/tmp")
    assert not task.is_cancelled()
    task.cancel()
    assert task.is_cancelled()
    assert task.status == DOWNLOAD_STATUS_CANCELLED


def test_downloader_cancel_all():
    d = Downloader()
    task1 = DownloadTask("url1", "/tmp", "t1")
    task2 = DownloadTask("url2", "/tmp", "t2")
    d.active_tasks = {"t1": task1, "t2": task2}
    d.cancel_all_downloads()
    assert task1.is_cancelled()
    assert task2.is_cancelled()


def test_downloader_get_video_info_network_error():
    d = Downloader()
    with patch('yt_dlp.YoutubeDL') as mock_ydl:
        mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = Exception("Network error")
        result = d.get_video_info("https://youtube.com/watch?v=test")
    assert result is None
