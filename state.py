"""processed_files.json を Drive 上で読み書きする。

ファイル形式:
{
  "<drive_file_id>": {
    "processed_at": "2026-05-02T12:34:56+09:00",
    "rows_added": 3,
    "vendor": "...",
    "total": 9910
  },
  ...
}
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from drive_client import DriveClient

STATE_FILENAME = "receipt_tracker_state.json"
STATE_MIME = "application/json"


def load(drive: DriveClient, state_file_id: str) -> dict:
    if not state_file_id:
        return {}
    try:
        return json.loads(drive.download_text(state_file_id))
    except Exception:
        return {}


def save(drive: DriveClient, state_file_id: str, state: dict) -> None:
    body = json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8")
    drive.update_file_content(state_file_id, body, STATE_MIME)


def mark_processed(state: dict, file_id: str, *, vendor: str, total: int, rows: int) -> None:
    state[file_id] = {
        "processed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "rows_added": rows,
        "vendor": vendor,
        "total": total,
    }


def is_processed(state: dict, file_id: str) -> bool:
    return file_id in state
