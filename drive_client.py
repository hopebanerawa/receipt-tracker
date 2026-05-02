"""Google Drive REST API ラッパ。

OAuthアクセストークンを使い、フォルダ内ファイル一覧・バイナリDL・
既存ファイル上書き・新規ファイル作成を提供する。
"""
from __future__ import annotations

import io
import json
import mimetypes
from typing import Iterable

import requests

API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"


class DriveClient:
    def __init__(self, access_token: str):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {access_token}"})

    def find_by_name(self, folder_id: str, name: str) -> dict | None:
        """フォルダ内に同名ファイルがあれば最初の1件を返す。"""
        # name に ' を含む場合はエスケープ
        safe = name.replace("\\", "\\\\").replace("'", "\\'")
        params = {
            "q": (
                f"'{folder_id}' in parents and name = '{safe}' "
                "and trashed = false"
            ),
            "fields": "files(id, name, mimeType, modifiedTime, size)",
            "pageSize": 5,
        }
        r = self.session.get(f"{API}/files", params=params, timeout=30)
        r.raise_for_status()
        files = r.json().get("files", [])
        return files[0] if files else None

    def list_folder(self, folder_id: str) -> list[dict]:
        files: list[dict] = []
        page_token: str | None = None
        while True:
            params = {
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                "pageSize": 200,
            }
            if page_token:
                params["pageToken"] = page_token
            r = self.session.get(f"{API}/files", params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            files.extend(data.get("files", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return files

    def download_bytes(self, file_id: str) -> bytes:
        r = self.session.get(
            f"{API}/files/{file_id}",
            params={"alt": "media"},
            timeout=60,
        )
        r.raise_for_status()
        return r.content

    def download_text(self, file_id: str) -> str:
        return self.download_bytes(file_id).decode("utf-8")

    def update_file_content(
        self, file_id: str, data: bytes, mime_type: str
    ) -> dict:
        r = self.session.patch(
            f"{UPLOAD_API}/files/{file_id}",
            params={"uploadType": "media"},
            headers={"Content-Type": mime_type},
            data=data,
            timeout=120,
        )
        r.raise_for_status()
        return r.json()

    def create_file(
        self,
        name: str,
        data: bytes,
        mime_type: str,
        parent_folder_id: str,
    ) -> dict:
        """multipart upload で新規作成。"""
        boundary = "----receipt-tracker-boundary"
        metadata = {
            "name": name,
            "parents": [parent_folder_id],
            "mimeType": mime_type,
        }
        body = (
            f"--{boundary}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8")
        body += data
        body += f"\r\n--{boundary}--\r\n".encode("utf-8")
        r = self.session.post(
            f"{UPLOAD_API}/files",
            params={"uploadType": "multipart"},
            headers={"Content-Type": f"multipart/related; boundary={boundary}"},
            data=body,
            timeout=120,
        )
        r.raise_for_status()
        return r.json()

    @staticmethod
    def view_url(file_id: str) -> str:
        return f"https://drive.google.com/file/d/{file_id}/view"
