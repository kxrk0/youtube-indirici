#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
İçerik otomatik kategorizasyon kuralları.
Kural formatı (JSON listesi, cache/auto_rules.json):
  [
    {
      "name": "Müzik",
      "match_field": "title|url|channel",
      "pattern": "regex or substring (case-insensitive)",
      "output_subdir": "Müzik",
      "type_override": "audio|video|"  (boş = değiştirme)
    }, ...
  ]
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from src.utils.helpers import get_data_dir

_RULES_FILE = os.path.join(get_data_dir(), 'auto_rules.json')

# Built-in default rules
_DEFAULT_RULES: list[dict] = [
    {
        'name': 'Müzik',
        'match_field': 'title',
        'pattern': r'music|müzik|remix|lyric|official audio|nightcore|lofi|lo-fi',
        'output_subdir': 'Müzik',
        'type_override': '',
    },
    {
        'name': 'Podcast',
        'match_field': 'title',
        'pattern': r'podcast|episode|ep\.\s*\d+|bölüm',
        'output_subdir': 'Podcast',
        'type_override': '',
    },
    {
        'name': 'Kısa Video',
        'match_field': 'url',
        'pattern': r'shorts|tiktok\.com|instagram\.com/reels',
        'output_subdir': 'Kısa Videolar',
        'type_override': '',
    },
    {
        'name': 'Eğitim',
        'match_field': 'title',
        'pattern': r'tutorial|course|ders|öğren|eğitim|how to|nasıl',
        'output_subdir': 'Eğitim',
        'type_override': '',
    },
]


def _rules_path() -> str:
    os.makedirs(os.path.dirname(_RULES_FILE), exist_ok=True)
    return _RULES_FILE


def load_rules() -> list[dict]:
    path = _rules_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return list(_DEFAULT_RULES)


def save_rules(rules: list[dict]):
    with open(_rules_path(), 'w', encoding='utf-8') as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


def _ends_with_folder(base: str, subdir: str) -> bool:
    """base zaten subdir ile bitiyor mu (harf duyarsız, / ve \\ eşit, sondaki ayraç yok sayılır).
    İndirme klasörü İndirilenler\\Müzik iken "Müzik" kuralı İndirilenler\\Müzik\\Müzik açıyordu."""
    base_parts = os.path.normcase(os.path.normpath(base)).split(os.sep)
    sub_parts = os.path.normcase(os.path.normpath(subdir)).split(os.sep)
    return base_parts[-len(sub_parts):] == sub_parts


def apply_rules(
    url: str,
    title: str = '',
    channel: str = '',
    base_output_dir: str = '',
) -> dict:
    """
    Match URL/title/channel against saved rules.
    Returns dict with optional keys:
      - output_dir: str — modified output path
      - type_override: str — 'audio'|'video'|''
      - matched_rule: str — name of matched rule
    """
    rules = load_rules()
    fields = {'url': url, 'title': title, 'channel': channel}
    for rule in rules:
        field = rule.get('match_field', 'title')
        pattern = rule.get('pattern', '')
        text = fields.get(field, '') or ''
        try:
            if re.search(pattern, text, re.IGNORECASE):
                result: dict = {'matched_rule': rule.get('name', '')}
                subdir = rule.get('output_subdir', '')
                if subdir and base_output_dir:
                    result['output_dir'] = (base_output_dir if _ends_with_folder(base_output_dir, subdir)
                                            else os.path.join(base_output_dir, subdir))
                elif subdir:
                    result['output_dir'] = subdir
                if rule.get('type_override'):
                    result['type_override'] = rule['type_override']
                return result
        except re.error:
            continue
    return {}


def add_rule(rule: dict):
    rules = load_rules()
    rules.append(rule)
    save_rules(rules)


def delete_rule(name: str):
    rules = load_rules()
    rules = [r for r in rules if r.get('name') != name]
    save_rules(rules)


def reset_to_defaults():
    save_rules(list(_DEFAULT_RULES))
