"""フォルダ内に必要ファイル (テンプレ.xlsx, state.json) がなければ作成する。

戻り値はそれぞれの fileId。
"""
from __future__ import annotations

import config
import excel_writer
import template_builder
from drive_client import DriveClient

STATE_MIME = "application/json"


def ensure(drive: DriveClient, folder_id: str) -> tuple[str, str, list[str]]:
    """(template_file_id, state_file_id, log_messages) を返す。"""
    log: list[str] = []

    tmpl = drive.find_by_name(folder_id, config.TEMPLATE_FILENAME)
    if tmpl:
        template_id = tmpl["id"]
        log.append(f"既存テンプレートを使用: {config.TEMPLATE_FILENAME}")
    else:
        log.append(f"テンプレートを新規作成: {config.TEMPLATE_FILENAME}")
        body = template_builder.build()
        created = drive.create_file(
            name=config.TEMPLATE_FILENAME,
            data=body,
            mime_type=excel_writer.TEMPLATE_MIME,
            parent_folder_id=folder_id,
        )
        template_id = created["id"]

    st = drive.find_by_name(folder_id, config.STATE_FILENAME)
    if st:
        state_id = st["id"]
        log.append(f"既存stateを使用: {config.STATE_FILENAME}")
    else:
        log.append(f"stateを新規作成: {config.STATE_FILENAME}")
        created = drive.create_file(
            name=config.STATE_FILENAME,
            data=b"{}",
            mime_type=STATE_MIME,
            parent_folder_id=folder_id,
        )
        state_id = created["id"]

    return template_id, state_id, log
