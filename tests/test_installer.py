#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kurucu parçalarının testleri: PATH betiği, FFmpeg zip'inden dosya seçimi, .nsi derlemesi.

PATH betiği gerçek sistem PATH'ine değil, HKCU altında geçici bir anahtara yazar.
Arka plan: Vellum kurucusu her güncellemede PATH'e bir kopya ekledi (47 kopya); PATH uzayınca
Explorer kullanıcı PATH'ini tümden düşürdü ve Python "bulunamadı". Betik bu yüzden eklemeden
önce bütün kopyaları çıkarıyor.
"""
import os
import shutil
import subprocess
import sys
import winreg
import zipfile

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='kurucu Windows için')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'installer'))
import build_release  # noqa: E402  (installer/ yola eklendikten sonra)

PATH_SCRIPT = os.path.join(ROOT, 'installer', 'path_entry.ps1')
NSI_SCRIPT = os.path.join(ROOT, 'installer', 'youtube_indirici.nsi')
TEST_KEY = r'Software\YouTubeIndiriciPathTest'
FFMPEG_BIN = r'C:\Program Files\FFmpeg\bin'
SCRIPT_TIMEOUT_S = 60
BUILD_TIMEOUT_S = 120
# Stok NSIS dizelerinin sınırı; betik bundan uzun PATH'i de bozmamalı.
NSIS_MAX_STRLEN = 1024


@pytest.fixture
def path_key():
    winreg.CreateKey(winreg.HKEY_CURRENT_USER, TEST_KEY)
    yield
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, TEST_KEY)


def _set_path(value, kind=winreg.REG_EXPAND_SZ):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, TEST_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, 'Path', 0, kind, value)


def _get_path():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, TEST_KEY) as k:
        try:
            value, kind = winreg.QueryValueEx(k, 'Path')
        except FileNotFoundError:
            return None, None
    return value, kind


def _run_path_script(action, directory=FFMPEG_BIN):
    return subprocess.run(
        ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', PATH_SCRIPT,
         '-Action', action, '-Dir', directory, '-RegistryKey', f'HKCU:\\{TEST_KEY}'],
        capture_output=True, text=True, timeout=SCRIPT_TIMEOUT_S)


def test_add_collapses_existing_copies_to_one_at_the_end(path_key):
    _set_path(f'a;{FFMPEG_BIN};b;{FFMPEG_BIN}\\;{FFMPEG_BIN.lower()};c')
    assert _run_path_script('Add').returncode == 0
    assert _get_path() == (f'a;b;c;{FFMPEG_BIN}', winreg.REG_EXPAND_SZ)


def test_add_is_idempotent_and_keeps_unexpanded_variables(path_key):
    _set_path(r'%SystemRoot%\system32;' + FFMPEG_BIN)
    assert _run_path_script('Add').returncode == 0
    assert _get_path() == (r'%SystemRoot%\system32;' + FFMPEG_BIN, winreg.REG_EXPAND_SZ)


def test_add_after_trailing_separator_does_not_double_it(path_key):
    _set_path('a;b;')
    assert _run_path_script('Add').returncode == 0
    assert _get_path()[0] == f'a;b;{FFMPEG_BIN}'


def test_add_keeps_entries_that_only_share_a_prefix(path_key):
    _set_path(f'{FFMPEG_BIN}2;a')
    assert _run_path_script('Add').returncode == 0
    assert _get_path()[0] == f'{FFMPEG_BIN}2;a;{FFMPEG_BIN}'


def test_add_creates_missing_value(path_key):
    assert _run_path_script('Add').returncode == 0
    assert _get_path() == (FFMPEG_BIN, winreg.REG_EXPAND_SZ)


def test_long_path_survives(path_key):
    entries = [rf'C:\uzun\klasor{i}' for i in range(200)]
    assert len(';'.join(entries)) > NSIS_MAX_STRLEN
    _set_path(';'.join(entries))
    assert _run_path_script('Add').returncode == 0
    assert _get_path()[0] == ';'.join(entries + [FFMPEG_BIN])


def test_remove_strips_every_copy(path_key):
    _set_path(f'a;{FFMPEG_BIN};b;{FFMPEG_BIN}')
    assert _run_path_script('Remove').returncode == 0
    assert _get_path()[0] == 'a;b'


def test_remove_keeps_plain_string_kind(path_key):
    _set_path(f'a;{FFMPEG_BIN}', winreg.REG_SZ)
    assert _run_path_script('Remove').returncode == 0
    assert _get_path() == ('a', winreg.REG_SZ)


def test_missing_key_fails_loudly():
    result = subprocess.run(
        ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', PATH_SCRIPT,
         '-Action', 'Add', '-Dir', FFMPEG_BIN, '-RegistryKey', r'HKCU:\Software\YokBoyleBirAnahtar'],
        capture_output=True, text=True, timeout=SCRIPT_TIMEOUT_S)
    assert result.returncode == 1
    assert 'YokBoyleBirAnahtar' in result.stderr


def _fake_ffmpeg_zip(path, members):
    with zipfile.ZipFile(path, 'w') as z:
        for name in members:
            z.writestr(f'ffmpeg-8.0-essentials_build/{name}', name)


def test_extract_ffmpeg_flattens_the_needed_files(tmp_path):
    archive = tmp_path / 'ffmpeg.zip'
    _fake_ffmpeg_zip(archive, ['bin/ffmpeg.exe', 'bin/ffprobe.exe', 'bin/ffplay.exe', 'LICENSE', 'doc/ffmpeg.html'])
    build_release.extract_ffmpeg(str(archive), str(tmp_path / 'out'))
    assert sorted(os.listdir(tmp_path / 'out')) == ['LICENSE', 'ffmpeg.exe', 'ffprobe.exe']
    assert (tmp_path / 'out' / 'ffprobe.exe').read_text() == 'bin/ffprobe.exe'


def test_extract_ffmpeg_names_missing_files(tmp_path):
    archive = tmp_path / 'ffmpeg.zip'
    _fake_ffmpeg_zip(archive, ['bin/ffmpeg.exe'])
    with pytest.raises(SystemExit, match='ffprobe.exe'):
        build_release.extract_ffmpeg(str(archive), str(tmp_path / 'out'))


MAKENSIS = shutil.which('makensis') or next((p for p in build_release.MAKENSIS_CANDIDATES if os.path.isfile(p)), None)


@pytest.mark.skipif(MAKENSIS is None, reason='NSIS (makensis) kurulu değil')
def test_real_installer_script_compiles(tmp_path):
    """Kurulum yönetici izni istediği için burada çalıştırılamıyor; en azından derlendiği sınanır."""
    dist = tmp_path / 'dist'
    (dist / '_internal').mkdir(parents=True)
    (dist / 'YouTubeIndirici.exe').write_bytes(b'MZ')
    ffmpeg = tmp_path / 'ffmpeg'
    ffmpeg.mkdir()
    for name in ('ffmpeg.exe', 'ffprobe.exe', 'LICENSE'):
        (ffmpeg / name).write_bytes(b'x')
    out = tmp_path / 'Kurulum.exe'
    result = subprocess.run(
        [MAKENSIS, '/V2', '/WX', '/DVERSION=9.9.9', f'/DDIST={dist}', f'/DFFMPEG_DIR={ffmpeg}', f'/DOUTFILE={out}',
         NSI_SCRIPT],
        cwd=os.path.dirname(NSI_SCRIPT), capture_output=True, text=True, timeout=BUILD_TIMEOUT_S)
    assert result.returncode == 0, result.stdout + result.stderr
    assert out.is_file()
