#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Otomatik kategori kuralları. Arka plan: indirme klasörü zaten İndirilenler\\Müzik seçiliyken
"Müzik" kuralı bir Müzik daha ekliyordu; dosya İndirilenler\\Müzik\\Müzik'e düştü (2.7.3'te görüldü).
"""
import os

import pytest

from src.core import auto_categorize

MUSIC_TITLE = 'Uzi - Umrumda Değil (Official Music Video)'


@pytest.fixture(autouse=True)
def default_rules(monkeypatch):
    # Kullanıcının kayıtlı kuralları (cache\auto_rules.json) testi etkilemesin.
    monkeypatch.setattr(auto_categorize, 'load_rules', lambda: list(auto_categorize._DEFAULT_RULES))


def test_rule_adds_its_folder_under_the_download_dir(tmp_path):
    rule = auto_categorize.apply_rules(url='https://youtu.be/x', title=MUSIC_TITLE, base_output_dir=str(tmp_path))
    assert rule['output_dir'] == os.path.join(str(tmp_path), 'Müzik')


@pytest.mark.parametrize('suffix', ['Müzik', 'müzik', 'Müzik' + os.sep])
def test_rule_does_not_nest_its_folder_again(tmp_path, suffix):
    base = str(tmp_path) + os.sep + suffix
    rule = auto_categorize.apply_rules(url='https://youtu.be/x', title=MUSIC_TITLE, base_output_dir=base)
    assert os.path.normcase(os.path.normpath(rule['output_dir'])) == os.path.normcase(os.path.join(str(tmp_path), 'Müzik'))


def test_nested_rule_folder_is_not_repeated(tmp_path, monkeypatch):
    monkeypatch.setattr(auto_categorize, 'load_rules', lambda: [
        {'name': 'Rap', 'match_field': 'title', 'pattern': 'uzi', 'output_subdir': 'Müzik/Rap'}])
    base = os.path.join(str(tmp_path), 'Müzik', 'Rap')
    rule = auto_categorize.apply_rules(url='https://youtu.be/x', title=MUSIC_TITLE, base_output_dir=base)
    assert rule['output_dir'] == base


def test_folder_that_only_shares_a_prefix_still_gets_the_rule_folder(tmp_path):
    base = os.path.join(str(tmp_path), 'Müzikler')
    rule = auto_categorize.apply_rules(url='https://youtu.be/x', title=MUSIC_TITLE, base_output_dir=base)
    assert rule['output_dir'] == os.path.join(base, 'Müzik')
