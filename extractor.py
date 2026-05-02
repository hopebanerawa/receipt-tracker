"""Claude Vision で領収書/請求書から構造化JSONを抽出。

`tool_use` を強制することで、必ずスキーマに沿ったオブジェクトが返る。
プロンプトキャッシュ (ephemeral) を効かせて反復処理時のコストを抑える。
"""
from __future__ import annotations

import base64
from typing import TypedDict

import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
あなたは日本語の領収書・請求書・注文確認画面からデータを正確に抽出するアシスタントです。
画像またはPDFが渡されるので、`save_receipt` ツールを必ず呼び出して構造化データを返してください。

ルール:
- 金額は税込・整数（円）。コンマや「¥」は除く。
- 取引日: 注文日 > 印刷日 > 受取日 の優先順。読めなければ null。
- 商品名は型番までは含むがパッケージ説明文は含めない。簡潔に。
- 数量・単価・小計が読めない明細行は items に入れず、合計だけ total に入れる。
- 合計金額 (total) は送料・手数料込みの最終金額。
- 店舗名 (vendor) は会社名やECサイト名（例: 「秋月電子通商」「BASE」「Amazon」）。
"""

RECEIPT_SCHEMA = {
    "type": "object",
    "required": ["vendor", "total", "items"],
    "properties": {
        "transaction_date": {
            "type": ["string", "null"],
            "description": "YYYY-MM-DD 形式。不明なら null。",
        },
        "vendor": {"type": "string", "description": "店舗・サイト名"},
        "order_id": {"type": ["string", "null"]},
        "payment_method": {
            "type": ["string", "null"],
            "description": "クレジットカード、銀行振込、代引き等",
        },
        "shipping": {"type": "integer", "description": "送料（税込・円）。なければ0"},
        "fee": {"type": "integer", "description": "手数料（税込・円）。なければ0"},
        "total": {"type": "integer", "description": "合計金額（税込・円）"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "qty", "subtotal"],
                "properties": {
                    "name": {"type": "string"},
                    "qty": {"type": "integer"},
                    "unit_price": {"type": ["integer", "null"]},
                    "subtotal": {"type": "integer"},
                },
            },
        },
    },
}

TOOL = {
    "name": "save_receipt",
    "description": "領収書から抽出した構造化データを保存する。",
    "input_schema": RECEIPT_SCHEMA,
}


class ReceiptItem(TypedDict, total=False):
    name: str
    qty: int
    unit_price: int | None
    subtotal: int


class Receipt(TypedDict, total=False):
    transaction_date: str | None
    vendor: str
    order_id: str | None
    payment_method: str | None
    shipping: int
    fee: int
    total: int
    items: list[ReceiptItem]


def _build_content_block(data: bytes, mime_type: str) -> dict:
    b64 = base64.standard_b64encode(data).decode("ascii")
    if mime_type == "application/pdf":
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
        }
    if mime_type in ("image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"):
        if mime_type == "image/jpg":
            mime_type = "image/jpeg"
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": mime_type, "data": b64},
        }
    raise ValueError(f"未対応のMIMEタイプ: {mime_type}")


def extract(data: bytes, mime_type: str, api_key: str) -> Receipt:
    client = anthropic.Anthropic(api_key=api_key)
    content = [
        _build_content_block(data, mime_type),
        {
            "type": "text",
            "text": "この領収書の内容を save_receipt ツールで保存してください。",
        },
    ]
    msg = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "save_receipt"},
        messages=[{"role": "user", "content": content}],
    )
    for block in msg.content:
        if block.type == "tool_use" and block.name == "save_receipt":
            return _normalize(block.input)
    raise RuntimeError("Claude が tool_use を返しませんでした")


def _normalize(raw: dict) -> Receipt:
    out: Receipt = {
        "transaction_date": raw.get("transaction_date"),
        "vendor": (raw.get("vendor") or "").strip(),
        "order_id": raw.get("order_id"),
        "payment_method": raw.get("payment_method"),
        "shipping": int(raw.get("shipping") or 0),
        "fee": int(raw.get("fee") or 0),
        "total": int(raw.get("total") or 0),
        "items": [],
    }
    for it in raw.get("items") or []:
        out["items"].append(
            {
                "name": (it.get("name") or "").strip(),
                "qty": int(it.get("qty") or 1),
                "unit_price": (
                    int(it["unit_price"]) if it.get("unit_price") is not None else None
                ),
                "subtotal": int(it.get("subtotal") or 0),
            }
        )
    return out


# CLI 単体テスト用
if __name__ == "__main__":
    import os
    import sys
    import json

    if len(sys.argv) < 2:
        print("usage: python extractor.py <file>")
        sys.exit(1)
    path = sys.argv[1]
    mt = (
        "application/pdf"
        if path.lower().endswith(".pdf")
        else "image/jpeg"
        if path.lower().endswith((".jpg", ".jpeg"))
        else "image/png"
    )
    with open(path, "rb") as f:
        data = f.read()
    key = os.environ["ANTHROPIC_API_KEY"]
    print(json.dumps(extract(data, mt, key), ensure_ascii=False, indent=2))
