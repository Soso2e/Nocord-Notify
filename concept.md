# Notion複数ワークスペース対応・中央サーバー通知システム設計書

## 1. 概要

本システムは、複数のNotionワークスペースに存在するデータベースを横断的に監視し、期限が迫っているタスクを抽出し、Discordへ通知する中央集約型の通知システムである。

---

## 2. システムコンセプト

### 2.1 基本思想

3層構造：

* Data Source Layer（Notion複数WS）
* Logic Layer（中央サーバー）
* Output Layer（Discord等）

### 2.2 目的

* ワークスペース差異の吸収
* 通知ロジックの一元化
* 拡張性の確保

---

## 3. システム構成

* Scheduler（cron）
* Central Server

  * Config Loader
  * Notion Client
  * Normalizer
  * Filter Engine
  * Notifier
  * Storage
* Discord Webhook

---

## 4. データフロー

1. Scheduler起動
2. Config読み込み
3. Notionからデータ取得
4. 正規化
5. フィルタ
6. 通知生成
7. Discord送信
8. 履歴保存

---

## 5. 設定設計

config.json例：

```json
[
  {
    "name": "workspace_a",
    "notion_token": "secret_xxx",
    "database_id": "xxx",
    "date_property": "End date",
    "status_property": "Status",
    "done_values": ["完了", "Done"],
    "discord_webhook_url": "https://..."
  }
]
```

---

## 6. データモデル

```python
Task = {
    "workspace": str,
    "page_id": str,
    "title": str,
    "due_date": datetime,
    "status": str,
    "url": str,
    "assignee": Optional[str]
}
```

---

## 7. フィルタ条件

* 期限 >= 今日
* 期限 <= 今日 + N日
* ステータス != 完了

---

## 8. 通知設計

* タスク名
* 締切
* 担当
* URL

---

## 9. 重複通知防止

SQLiteで管理

---

## 10. ストレージ

```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY,
    workspace TEXT,
    page_id TEXT,
    notified_date TEXT
);
```

---

## 11. 技術スタック

* Python
* requests
* sqlite3
* dotenv

---

## 12. ディレクトリ構成

```
project/
  main.py
  config.json
  notion_client.py
  filter.py
  notifier.py
  storage.py
```

---

## 13. 拡張性

* Slack対応
* Web UI
* OAuth

---

## 14. MVP

* 複数WS対応
* 期限通知
* Discord送信
* 重複防止

---

## 15. 設計方針

* 単一責任
* 設定駆動
* スケーラブル
