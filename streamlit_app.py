"""領収書 → Excel 集計アプリ Streamlit エントリ。"""
from __future__ import annotations

import streamlit as st

import auth
import bootstrap
import config
import excel_writer
import extractor
import state
from drive_client import DriveClient

SUPPORTED_MIMES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}

st.set_page_config(page_title="領収書 → Excel 集計", page_icon="📄", layout="centered")

email = auth.ensure_authenticated()
access_token = auth.get_access_token()
if not access_token:
    st.warning("セッションが切れました。再ログインしてください。")
    auth.logout()
    st.stop()

drive = DriveClient(access_token)
folder_id = config.drive_folder_id()

# ---- 初回 / 起動時 bootstrap ----
try:
    template_id, state_id, boot_log = bootstrap.ensure(drive, folder_id)
except Exception as e:
    st.error(f"テンプレート・state準備でエラー: {e}")
    st.stop()

# ---- サイドバー ----
with st.sidebar:
    st.markdown(f"**ログイン中:** {email}")
    if st.button("ログアウト"):
        auth.logout()
        st.rerun()
    st.divider()
    st.markdown(f"[📊 集計Excelを開く]({DriveClient.view_url(template_id)})")
    st.markdown(
        f"[📁 領収書フォルダを開く](https://drive.google.com/drive/folders/{folder_id})"
    )
    st.caption("領収書はこのフォルダに直接アップロードしてください。")
    with st.expander("初期化ログ", expanded=False):
        for m in boot_log:
            st.write("•", m)

# ---- メイン ----
st.title("領収書 → Excel 集計")

# 累計サマリ
try:
    template_bytes = drive.download_bytes(template_id)
    summary = excel_writer.read_summary(template_bytes)
    col1, col2, col3 = st.columns(3)
    col1.metric("記録済み件数", summary["receipts"])
    col2.metric("累計合計（円）", f"{summary['total_amount']:,}")
    col3.metric("明細行数", summary["rows"])
except Exception as e:
    st.error(f"テンプレートの読み込みに失敗: {e}")
    st.stop()

st.divider()
st.markdown("### Driveから新しい領収書を取り込む")
st.write(
    "Driveの領収書フォルダを見て、まだ取り込んでいないファイルを抽出し、"
    "Claude Visionで内容を読み取ってExcelに追記します。"
)

if st.button("📥 Driveから更新", type="primary", use_container_width=True):
    progress = st.progress(0.0)
    status = st.empty()

    status.write("Driveからファイル一覧を取得中…")
    try:
        files = drive.list_folder(folder_id)
    except Exception as e:
        st.error(f"フォルダの一覧取得に失敗: {e}")
        st.stop()

    # bootstrap で作ったテンプレ自身・state自身は除外
    targets = [
        f for f in files
        if f.get("mimeType") in SUPPORTED_MIMES
        and f["id"] not in (template_id, state_id)
    ]
    status.write(f"対象ファイル {len(targets)} 件を確認中…")

    current_state = state.load(drive, state_id)
    new_files = [f for f in targets if not state.is_processed(current_state, f["id"])]

    if not new_files:
        progress.progress(1.0)
        status.success("新しいファイルはありません。すべて取り込み済みです。")
        st.stop()

    api_key = config.anthropic_api_key()
    wb_bytes = template_bytes
    appended_all = []
    errors = []

    for i, f in enumerate(new_files, start=1):
        status.write(f"[{i}/{len(new_files)}] {f['name']} を解析中…")
        progress.progress((i - 1) / len(new_files))
        try:
            data = drive.download_bytes(f["id"])
            mt = f["mimeType"]
            if mt == "image/jpg":
                mt = "image/jpeg"
            receipt = extractor.extract(data, mt, api_key)
            wb_bytes, appended = excel_writer.append_receipt(
                wb_bytes,
                receipt=receipt,
                file_name=f["name"],
                drive_link=DriveClient.view_url(f["id"]),
            )
            appended_all.extend(appended)
            state.mark_processed(
                current_state,
                f["id"],
                vendor=receipt.get("vendor", ""),
                total=receipt.get("total", 0),
                rows=len(appended),
            )
        except Exception as e:
            errors.append({"file": f["name"], "error": str(e)})
            continue

    status.write("Excelをアップロード中…")
    try:
        drive.update_file_content(template_id, wb_bytes, excel_writer.TEMPLATE_MIME)
        state.save(drive, state_id, current_state)
    except Exception as e:
        st.error(f"アップロードに失敗: {e}")
        st.stop()

    progress.progress(1.0)
    status.success(f"完了: 新規 {len(new_files) - len(errors)} 件 / エラー {len(errors)} 件")

    if appended_all:
        st.markdown("### 今回追加された行")
        st.dataframe(appended_all, use_container_width=True)

    if errors:
        st.markdown("### スキップしたファイル")
        st.dataframe(errors, use_container_width=True)
