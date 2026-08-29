"""Corpus cache + audit artifacts (§7.1).

Layout: data/cache/{app}/{date}/{reviews_raw.json, reviews_normalized.json, manifest.json}

The cache is AUTHORITATIVE: retries read it, they never re-scrape. It is also the
"exactly what was analyzed" audit artifact the deck points at.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config


def cache_dir(app: str, date: str) -> Path:
    d = config.CACHE_DIR / app / date
    d.mkdir(parents=True, exist_ok=True)
    return d


def _raw_path(app: str, date: str) -> Path:
    return cache_dir(app, date) / "reviews_raw.json"


def _normalized_path(app: str, date: str) -> Path:
    return cache_dir(app, date) / "reviews_normalized.json"


def _manifest_path(app: str, date: str) -> Path:
    return cache_dir(app, date) / "manifest.json"


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def has_raw(app: str, date: str) -> bool:
    return _raw_path(app, date).exists()


def save_raw(app: str, date: str, records: list[dict]) -> None:
    _write_json(_raw_path(app, date), records)


def load_raw(app: str, date: str) -> list[dict]:
    return _read_json(_raw_path(app, date))


def load_raw_safe(app: str, date: str) -> list[dict] | None:
    """Load raw, or return None if missing/corrupt (edge-cases §1.7).

    The cache is regenerable, so a corrupt file is a re-scrape signal, not a
    crash — the caller falls back to scraping rather than analyzing garbage.
    """
    if not has_raw(app, date):
        return None
    try:
        data = _read_json(_raw_path(app, date))
    except (ValueError, OSError):
        return None
    return data if isinstance(data, list) else None


def raw_stores(app: str, date: str) -> set[str]:
    """Which stores are already in the cached raw pull (store-aware reuse, §7.1).

    Corrupt/missing cache -> empty set, so the planner treats it as needing a pull.
    """
    data = load_raw_safe(app, date)
    if not data:
        return set()
    return {rec.get("store") for rec in data}


def save_normalized(app: str, date: str, reviews: list[dict]) -> None:
    _write_json(_normalized_path(app, date), reviews)


def load_normalized(app: str, date: str) -> list[dict]:
    return _read_json(_normalized_path(app, date))


def save_manifest(app: str, date: str, manifest: dict) -> None:
    _write_json(_manifest_path(app, date), manifest)


def load_manifest(app: str, date: str) -> dict:
    return _read_json(_manifest_path(app, date))
