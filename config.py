"""Streamlit secrets を読みやすい形にまとめる。

Secrets に必須なのは:
  ANTHROPIC_API_KEY
  ALLOWED_EMAIL
  google_oauth.client_id / client_secret / redirect_uri
  drive.folder_id

テンプレ.xlsxとstate.jsonのIDは「フォルダ内に決まった名前で保存する」運用にして、
Secrets には不要にする。
"""
from __future__ import annotations

import streamlit as st

TEMPLATE_FILENAME = "receipt_tracker_template.xlsx"
STATE_FILENAME = "receipt_tracker_state.json"


def anthropic_api_key() -> str:
    return st.secrets["ANTHROPIC_API_KEY"]


def allowed_email() -> str:
    return st.secrets["ALLOWED_EMAIL"].strip().lower()


def google_oauth() -> dict:
    return dict(st.secrets["google_oauth"])


def drive_folder_id() -> str:
    return st.secrets["drive"]["folder_id"]


SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive",
]
