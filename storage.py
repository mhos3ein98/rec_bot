# =============================================================================
# storage.py
# Local file-system storage layer.
#
# Layout:
#   data/
#     sessions.json              ← per-user language + active-folder cache
#     <user_id>/
#       <folder_name>/
#         metadata.json          ← list of receipt records
#         images/
#           receipt_<n>.jpg
#         logs.json              ← append-only activity log
# =============================================================================

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BASE = Path("data")
_SESSIONS_FILE = BASE / "sessions.json"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _user_dir(uid: int) -> Path:
    return BASE / str(uid)


def _folder_dir(uid: int, folder: str) -> Path:
    return _user_dir(uid) / folder


def _meta_path(uid: int, folder: str) -> Path:
    return _folder_dir(uid, folder) / "metadata.json"


def _log_path(uid: int, folder: str) -> Path:
    return _folder_dir(uid, folder) / "logs.json"


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to read %s: %s", path, exc)
        return default if default is not None else {}


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Session store  (language + active folder per user)
# ---------------------------------------------------------------------------

def _load_sessions() -> dict:
    return _read_json(_SESSIONS_FILE, {})


def _save_sessions(s: dict) -> None:
    _write_json(_SESSIONS_FILE, s)


def get_user_lang(uid: int) -> str | None:
    """Return stored language for user, or None if never set."""
    return _load_sessions().get(str(uid), {}).get("lang")


def set_user_lang(uid: int, lang: str) -> None:
    s = _load_sessions()
    s.setdefault(str(uid), {})["lang"] = lang
    _save_sessions(s)


def get_active_folder(uid: int) -> str | None:
    return _load_sessions().get(str(uid), {}).get("active_folder")


def set_active_folder(uid: int, folder: str) -> None:
    s = _load_sessions()
    s.setdefault(str(uid), {})["active_folder"] = folder
    _save_sessions(s)


def clear_active_folder(uid: int) -> None:
    s = _load_sessions()
    if str(uid) in s:
        s[str(uid)].pop("active_folder", None)
    _save_sessions(s)


# ---------------------------------------------------------------------------
# Folder operations
# ---------------------------------------------------------------------------

def list_folders(uid: int) -> list[str]:
    d = _user_dir(uid)
    if not d.exists():
        return []
    return sorted(
        p.name for p in d.iterdir()
        if p.is_dir() and (p / "metadata.json").exists()
    )


def folder_exists(uid: int, folder: str) -> bool:
    return _meta_path(uid, folder).exists()


def create_folder(uid: int, folder: str) -> bool:
    """Returns False if folder already exists."""
    if folder_exists(uid, folder):
        return False
    _write_json(_meta_path(uid, folder), {"folder": folder, "receipts": []})
    _write_json(_log_path(uid, folder), [])
    return True


# ---------------------------------------------------------------------------
# Receipt operations
# ---------------------------------------------------------------------------

def load_receipts(uid: int, folder: str) -> list[dict]:
    meta = _read_json(_meta_path(uid, folder), {"receipts": []})
    return meta.get("receipts", [])


def save_receipt(
    uid: int,
    folder: str,
    data: dict,
    image_bytes: bytes | None = None,
) -> int:
    """
    Append a receipt to metadata.json.
    Returns the 1-based receipt index.
    """
    meta = _read_json(_meta_path(uid, folder), {"folder": folder, "receipts": []})
    receipts: list = meta.setdefault("receipts", [])
    idx = len(receipts) + 1

    record: dict[str, Any] = {
        "index":        idx,
        "customer":     data.get("customer", ""),
        "amount":       data.get("amount", ""),
        "volume":       data.get("volume", ""),
        "time":         data.get("time", ""),
        "admin":        data.get("admin", ""),
        "receipt_type": "image" if image_bytes else "text",
        "receipt_text": data.get("receipt_text", "") if not image_bytes else "",
        "receipt_file": "",
        "saved_at":     time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    if image_bytes:
        img_dir = _folder_dir(uid, folder) / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        img_path = img_dir / f"receipt_{idx}.jpg"
        img_path.write_bytes(image_bytes)
        record["receipt_file"] = str(img_path)

    receipts.append(record)
    _write_json(_meta_path(uid, folder), meta)

    # Append to log
    logs = _read_json(_log_path(uid, folder), [])
    logs.append({"action": "receipt_saved", "index": idx, "at": record["saved_at"]})
    _write_json(_log_path(uid, folder), logs)

    return idx


def get_receipt_image(uid: int, folder: str, idx: int) -> Path | None:
    p = _folder_dir(uid, folder) / "images" / f"receipt_{idx}.jpg"
    return p if p.exists() else None


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------

def total_volume(uid: int, folder: str) -> float:
    total = 0.0
    for r in load_receipts(uid, folder):
        try:
            total += float(r.get("volume", 0))
        except (ValueError, TypeError):
            pass
    return total


def total_amount(uid: int, folder: str) -> float:
    total = 0.0
    for r in load_receipts(uid, folder):
        try:
            raw = str(r.get("amount", "0")).replace(".", "").replace(",", "")
            total += float(raw)
        except (ValueError, TypeError):
            pass
    return total


def volume_by_admin(uid: int, folder: str, admin_name: str) -> tuple[float, int]:
    """Return (total_gb, receipt_count) for a specific admin in a folder."""
    vol = 0.0
    count = 0
    for r in load_receipts(uid, folder):
        if r.get("admin") == admin_name:
            try:
                vol += float(r.get("volume", 0))
            except (ValueError, TypeError):
                pass
            count += 1
    return vol, count
