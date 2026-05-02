"""Google OAuth2 ログイン。許可メアドのみ通す。

Streamlit のクエリパラメータ経由でリダイレクトコールバックを受け取り、
取得したアクセストークンを session_state に保存する。
"""
from __future__ import annotations

import secrets as _secrets
import time

import requests
import streamlit as st

import config

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _build_auth_url(state: str) -> str:
    oauth = config.google_oauth()
    from urllib.parse import urlencode

    params = {
        "client_id": oauth["client_id"],
        "redirect_uri": oauth["redirect_uri"],
        "response_type": "code",
        "scope": " ".join(config.SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def _exchange_code(code: str) -> dict:
    oauth = config.google_oauth()
    resp = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": oauth["client_id"],
            "client_secret": oauth["client_secret"],
            "redirect_uri": oauth["redirect_uri"],
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _refresh_access_token(refresh_token: str) -> dict:
    oauth = config.google_oauth()
    resp = requests.post(
        TOKEN_URL,
        data={
            "refresh_token": refresh_token,
            "client_id": oauth["client_id"],
            "client_secret": oauth["client_secret"],
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_userinfo(access_token: str) -> dict:
    resp = requests.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_access_token() -> str | None:
    tok = st.session_state.get("oauth_token")
    if not tok:
        return None
    if tok.get("expires_at", 0) - 60 < time.time():
        rt = tok.get("refresh_token")
        if not rt:
            return None
        new = _refresh_access_token(rt)
        tok = {
            **tok,
            "access_token": new["access_token"],
            "expires_at": time.time() + new.get("expires_in", 3600),
        }
        st.session_state["oauth_token"] = tok
    return tok["access_token"]


def logout():
    for k in ("oauth_token", "user_email"):
        st.session_state.pop(k, None)
    st.query_params.clear()


def ensure_authenticated() -> str:
    """ログインしていなければログインフローを表示し st.stop()。
    成功すれば許可メアドを返す。"""

    # コールバック処理
    qp = st.query_params
    if "code" in qp:
        try:
            tok = _exchange_code(qp["code"])
        except requests.HTTPError as e:
            st.error(f"トークン取得に失敗しました: {e.response.text}")
            st.stop()
        st.session_state["oauth_token"] = {
            **tok,
            "expires_at": time.time() + tok.get("expires_in", 3600),
        }
        userinfo = _fetch_userinfo(tok["access_token"])
        st.session_state["user_email"] = (userinfo.get("email") or "").strip().lower()
        st.query_params.clear()
        st.rerun()

    email = st.session_state.get("user_email")
    if email and st.session_state.get("oauth_token"):
        if email != config.allowed_email():
            st.error(
                f"このアカウント ({email}) はアクセスを許可されていません。"
                "正しいGoogleアカウントでログインし直してください。"
            )
            if st.button("ログアウト"):
                logout()
                st.rerun()
            st.stop()
        return email

    # 未ログイン: ボタン表示
    st.title("領収書 → Excel 集計アプリ")
    st.markdown(
        "ログインが必要です。許可されたGoogleアカウントでログインしてください。"
    )
    state = _secrets.token_urlsafe(16)
    auth_url = _build_auth_url(state)
    st.link_button("Googleでログイン", auth_url, type="primary")
    st.stop()
