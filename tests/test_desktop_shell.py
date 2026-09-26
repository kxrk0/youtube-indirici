#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Masaüstü kabuğu: kapatınca tepsiye gizlenme ve mini pencerenin kendiliğinden açılıp kapanması.
Gerçek pencere açılmaz; pywebview ve tepsi sahte nesnelerle değiştirilir.
"""
import pytest

from src.web import app as webapp


class FakeEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


class FakeEvents:
    def __init__(self):
        self.shown = FakeEvent()


class FakeWindow:
    def __init__(self):
        self.kwargs = {}
        self.calls = []
        self.events = FakeEvents()
        self.native = None
        self.width, self.height = 1100, 720
        self.title = 'fake'

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append(name)
            return 'http://127.0.0.1:1/index.html' if name == 'get_current_url' else True
        return record


class FakeTray:
    def __init__(self, *args, **kwargs):
        self.notified = []
        self.stopped = False

    def start(self):
        pass

    def notify(self, title, message):
        self.notified.append(message)

    def stop(self):
        self.stopped = True


class FakeApi:
    def __init__(self):
        self.windows = []
        self.cancelled = False
        self.active = False

    def _add_window(self, window):
        self.windows.append(window)

    def _has_active_jobs(self):
        return self.active

    def _cancel_all(self):
        self.cancelled = True

    def _emit(self, event):
        pass


@pytest.fixture
def shell(monkeypatch):
    created = []

    def create_window(*args, **kwargs):
        window = FakeWindow()
        window.kwargs = kwargs
        created.append(window)
        return window

    monkeypatch.setattr(webapp, 'TrayIcon', FakeTray)
    monkeypatch.setattr(webapp, '_icon_path', lambda: 'app.ico')
    monkeypatch.setattr(webapp, '_work_area_logical', lambda: (1920, 1040))
    monkeypatch.setattr(webapp.webview, 'create_window', create_window)
    monkeypatch.setattr(webapp.cfg, 'set_value', lambda key, value: None)
    monkeypatch.setattr(webapp, 'MINI_AUTO_HIDE_S', 0.0)
    main = FakeWindow()
    s = webapp.DesktopShell(FakeApi(), main, None)
    s.created = created
    return s


def test_close_hides_to_tray_and_notifies_once(shell):
    assert shell.on_closing() is False
    assert shell.on_closing() is False
    assert shell._main_hidden
    assert len(shell._tray.notified) == 1


def test_close_after_quit_really_closes(shell):
    shell.quit_now()
    assert shell.on_closing() is True
    assert shell._api.cancelled
    assert shell._tray.stopped


def test_download_while_hidden_opens_mini_then_hides_when_done(shell):
    shell.on_closing()
    shell.jobs_changed(1)
    assert len(shell.created) == 1
    mini = shell.created[0]
    # Kendiliğinden açılan mini pencere odağı çalmamalı (kullanıcı başka işteyken).
    assert mini.kwargs['focus'] is False
    assert shell._mini_visible and shell._mini_auto

    shell.jobs_changed(0)
    timer = shell._auto_hide  # süre 0: zamanlayıcı çoktan bitmiş (None) olabilir
    if timer is not None:
        timer.join(timeout=2)
    assert not shell._mini_visible
    assert 'hide' in mini.calls


def test_download_with_main_visible_does_not_open_mini(shell):
    shell.jobs_changed(1)
    assert shell.created == []


def test_mini_opened_by_user_stays_after_downloads_finish(shell):
    shell.toggle_mini()
    shell.jobs_changed(1)
    shell.jobs_changed(0)
    assert shell._auto_hide is None
    assert shell._mini_visible


def test_mini_url_uses_main_window_address(shell):
    shell.toggle_mini()
    assert shell.created[0].kwargs['focus'] is True
    assert shell._mini_url() == 'http://127.0.0.1:1/index.html#mini'
