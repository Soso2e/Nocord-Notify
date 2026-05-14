# Nocord — Notion × Discord タスク通知システム

複数の Notion ワークスペースを横断的に監視し、期限が迫ったタスクを Discord へ通知する中央集約型の通知サーバーです。

---

## 概要

- **複数ワークスペース対応**: ワークスペースごとに異なるプロパティ名・ステータス定義・Webhook URL を設定可能
- **期限フィルタ**: 今日から N 日以内（デフォルト 7 日）のタスクと、期限超過タスクを抽出
- **重複通知防止**: SQLite で送信履歴を管理し、1日に同じタスクを2回送信しない
- **並列処理**: 複数ワークスペースを `ThreadPoolExecutor` で同時取得
- **メッセージ分割**: Discord の 2000 文字制限を超える場合は自動で分割送信

---

## 動作イメージ

```
【残り3日】 レポート提出
締切: 2026-05-17  |  担当: Alice
[ページへ](https://notion.so/...)

【本日締切】 週次レビュー資料
締切: 2026-05-14
[ページへ](https://notion.so/...)

【2日超過: 更新して下さい】
締切: 2026-05-12
[ページへ](https://notion.so/...)
```

---

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. 設定ファイルの作成

```bash
cp config.example.json config.json
```

`config.json` を編集してください（後述）。

### 3. 実行

```bash
python main.py
```

毎朝 9 時に自動実行したい場合は cron に登録します。

```cron
0 9 * * * cd /path/to/Server_Nocord && python main.py
```

---

## 設定ファイル (`config.json`)

ワークスペースの設定を配列で記述します。複数ワークスペースに対応しています。

```json
[
  {
    "name": "workspace_a",
    "notion_token": "secret_xxx",
    "database_id": "xxx",
    "date_property": "End date",
    "status_property": "Status",
    "done_values": ["完了", "Done"],
    "notify_within_days": 7,
    "discord_webhook_url": "https://discord.com/api/webhooks/...",
    "discord_mention_id": "123456789012345678",
    "additional_property": "担当者"
  }
]
```

| キー | 必須 | 説明 |
|------|------|------|
| `name` | ✅ | ワークスペースの識別名（ログ・DB 管理に使用） |
| `notion_token` | ✅ | Notion の内部インテグレーショントークン（`secret_` から始まる） |
| `database_id` | ✅ | 対象の Notion データベース ID |
| `date_property` | ✅ | 期限が格納されているプロパティ名 |
| `status_property` | ✅ | ステータスが格納されているプロパティ名 |
| `done_values` | ✅ | 完了扱いとするステータス値のリスト |
| `notify_within_days` | - | 通知する期限の範囲（日数）。デフォルト: `7` |
| `discord_webhook_url` | ✅ | 送信先の Discord Webhook URL |
| `discord_mention_id` | - | メンションする Discord ユーザー ID（省略可） |
| `additional_property` | - | タスク通知に追加表示するプロパティ名（省略可） |

### `additional_property` について

担当者・カテゴリ・プロジェクト名など、任意のプロパティを通知メッセージに追加できます。
対応プロパティ型: `select`, `multi_select`, `rich_text`, `status`, `title`, `relation`, `formula`

---

## ディレクトリ構成

```
Server_Nocord/
├── main.py            # エントリポイント。全ワークスペースの処理を統括
├── notion_client.py   # Notion API クライアント／データ取得・正規化
├── filter.py          # 期限・ステータスによるタスクフィルタリング
├── notifier.py        # Discord Webhook へのメッセージ生成・送信
├── storage.py         # SQLite による通知履歴の永続化
├── config.json        # 設定ファイル（gitignore 対象）
├── config.example.json
├── notifications.db   # 送信履歴 DB（自動生成）
└── requirements.txt
```

---

## データフロー

```
[cron / 手動実行]
      ↓
  config.json 読み込み
      ↓
  SQLite 初期化
      ↓ (ワークスペースごとに並列)
  Notion API → タスク一覧取得・正規化
      ↓
  フィルタ（期限 / ステータス / 通知済みチェック）
      ↓
  Discord Webhook 送信
      ↓
  送信履歴を SQLite に記録
```

---

## フィルタ条件

以下の**すべて**を満たすタスクが通知対象になります。

1. 期限プロパティが設定されている
2. ステータスが `done_values` に含まれない（未完了）
3. 期限が `今日〜今日 + notify_within_days` の範囲内

> 期限が過去のタスク（超過タスク）も通知対象に含まれます。

---

## 技術スタック

| 用途 | ライブラリ |
|------|------------|
| HTTP クライアント | `requests` |
| 通知履歴管理 | `sqlite3`（標準ライブラリ） |
| 並列処理 | `concurrent.futures`（標準ライブラリ） |
| 環境変数管理 | `python-dotenv` |

---

## Notion インテグレーションの設定

1. [Notion Integrations](https://www.notion.so/my-integrations) でインテグレーションを作成
2. 発行された `secret_` トークンを `notion_token` に設定
3. 対象データベースのページを開き、「接続」からインテグレーションを追加
