# 領収書 → Excel 集計アプリ

Google Drive のフォルダに溜めた領収書（画像 / PDF）を、Webアプリの「更新」ボタン1つで
Excel ひな形に追記していく Streamlit アプリ。スマホ・iPad・PC どこからでも使えます。

- **抽出**: Claude API (Vision) で構造化JSONとして読み取り
- **保存先**: 同じ Drive フォルダ内の `receipt_tracker_template.xlsx` に追記
- **アクセス制御**: Google OAuth で本人のメアドのみ許可
- **デプロイ**: Streamlit Community Cloud（無料）

## ディレクトリ構成

```
receipt-tracker/
  streamlit_app.py        # エントリ
  auth.py                 # Google OAuth + メアド whitelist
  bootstrap.py            # 起動時にテンプレ.xlsx と state.json を自動生成
  config.py               # secrets 読み込み
  drive_client.py         # Drive REST API ラッパ
  extractor.py            # Claude Vision で領収書 → JSON
  excel_writer.py         # ひな形 .xlsx に追記
  state.py                # 処理済みファイル管理（Drive上のJSONに保存）
  template_builder.py     # ひな形 .xlsx を生成
  requirements.txt
  template/
    receipts_template.xlsx  # 参考ひな形（実運用ではDrive上のものを使用）
  .streamlit/
    config.toml
    secrets.toml.example  # secrets.toml にコピーして埋める
```

## セットアップ手順

### 1. Anthropic API キー
[console.anthropic.com](https://console.anthropic.com/) でAPIキーを発行。

### 2. Google Cloud Console
1. プロジェクトを作成
2. **APIとサービス → ライブラリ** で `Google Drive API` を有効化
3. **OAuth 同意画面**:
   - User Type: 外部
   - スコープ: `openid`, `email`, `profile`, `.../auth/drive`
   - テストユーザー: 自分のGoogleアカウントを追加
4. **認証情報 → OAuth クライアントID 作成**:
   - 種類: ウェブアプリケーション
   - 承認済みリダイレクトURI:
     - ローカル: `http://localhost:8501/`
     - デプロイ後: `https://<your-app>.streamlit.app/` （確定したら追加）
   - 出来上がった `クライアントID` と `クライアントシークレット` をメモ

### 3. ローカルで動作確認

```bash
# Python 3.10+
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# secrets を作る
cp .streamlit\secrets.toml.example .streamlit\secrets.toml
# 中身を編集して値を埋める

streamlit run streamlit_app.py
```

ブラウザで http://localhost:8501 が開く → Googleログイン → 初回起動時に
Drive フォルダ内に `receipt_tracker_template.xlsx` と `receipt_tracker_state.json` が
自動生成される。あとは **「Driveから更新」** ボタン。

### 4. Streamlit Community Cloud にデプロイ

1. このコードを GitHub の **private リポジトリ** に push
2. [share.streamlit.io](https://share.streamlit.io) → **New app** → リポジトリと `streamlit_app.py` を選択 → Deploy
3. 初回デプロイで確定したURL（例: `https://receipt-tracker-xxxx.streamlit.app/`）を
   Google Cloud Console の OAuthクライアントの **承認済みリダイレクトURI** に追加
4. Streamlit Cloud の **Settings → Secrets** に下記を貼り付け:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
ALLOWED_EMAIL = "hopebanerawa@gmail.com"

[google_oauth]
client_id = "xxxxxx.apps.googleusercontent.com"
client_secret = "GOCSPX-xxxxxxxxxxxx"
redirect_uri = "https://receipt-tracker-xxxx.streamlit.app/"

[drive]
folder_id = "15HBWtRSh4PNo3LuBEMNvinupQVwLY_nC"
```

5. 完了。スマホでURLを開き、ホーム画面に追加すると専用アプリのように使えます。

## 使い方

1. 領収書（JPG/PNG/PDF）を Drive のフォルダにそのまま放り込む（PCでもスマホDriveアプリでもOK）
2. アプリを開いて「📥 Driveから更新」ボタンを押す
3. 新しいファイルだけ Claude が読み取り、Excelに追記される
4. サイドバーの「📊 集計Excelを開く」リンクから Excel を確認

何度押しても同じファイルを二重に取り込むことはありません（ファイルIDで管理）。

## 抽出される項目

| 列 | 内容 |
|----|------|
| A | 取引日 |
| B | 店舗・サイト |
| C | 注文ID |
| D | 商品名 |
| E | 数量 |
| F | 単価（税込） |
| G | 商品小計 |
| H | 送料 |
| I | 手数料 |
| J | 合計金額（税込） |
| K | 決済方法 |
| L | 元ファイル名 |
| M | Driveリンク |
| N | 処理日時 |
| O | 備考 |

`集計` シートには、店舗別合計・月別合計（A列・D列に値を入れると自動集計される）と
全体件数・全体合計が用意されています。

## トラブルシューティング

- **「アクセス権がありません」と表示される** → Secrets の `ALLOWED_EMAIL` がログインしたGoogleメアドと一致しているか確認
- **OAuthのstateエラー** → クッキー削除して再ログイン
- **抽出結果がおかしい** → 該当ファイルを Drive から削除し、`receipt_tracker_state.json` も該当の file_id だけ手で消すと、次の更新で再抽出される
- **複数行の領収書なのに1行しか入らない** → Claude のJSONが items 空配列だった可能性。テンプレ末尾に `(明細抽出失敗)` で記録される

## 制約

- 領収書1点あたり Claude Sonnet で約 1〜2円程度のAPIコスト想定（画像サイズによる）
- Streamlit Community Cloud は1セッションあたり1GBメモリ。極端に大きいPDFは避ける
- OAuthアプリを「公開」しない場合、Google同意画面でテストユーザーに登録した Google アカウントしかログインできない（個人運用の場合むしろ望ましい）
