"""SQLite による通知履歴管理モジュール。

重複通知を防ぐため、送信済みの通知レコードを永続化する。
"""

import sqlite3
from pathlib import Path
from typing import Optional


_DEFAULT_DB_PATH = Path(__file__).parent / "notifications.db"


def _get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """SQLite 接続を取得する。

    Args:
        db_path: データベースファイルのパス。省略時はデフォルトパスを使用。

    Returns:
        sqlite3.Connection オブジェクト。
    """
    path = db_path or _DEFAULT_DB_PATH
    return sqlite3.connect(path)


def initialize_db(db_path: Optional[Path] = None) -> None:
    """通知履歴テーブルを作成する（既存の場合はスキップ）。

    Args:
        db_path: データベースファイルのパス。省略時はデフォルトパスを使用。
    """
    with _get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id           INTEGER PRIMARY KEY,
                workspace    TEXT    NOT NULL,
                page_id      TEXT    NOT NULL,
                notified_date TEXT   NOT NULL
            )
            """
        )
        conn.commit()


def is_notified(
    workspace: str,
    page_id: str,
    notified_date: str,
    db_path: Optional[Path] = None,
) -> bool:
    """指定のタスクが当日すでに通知済みかを確認する。

    Args:
        workspace: ワークスペース名。
        page_id: Notion のページ ID。
        notified_date: 通知日（ISO 形式の日付文字列 例: "2026-04-05"）。
        db_path: データベースファイルのパス。省略時はデフォルトパスを使用。

    Returns:
        通知済みの場合 True、未通知の場合 False。
    """
    with _get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT 1
            FROM notifications
            WHERE workspace = ?
              AND page_id = ?
              AND notified_date = ?
            LIMIT 1
            """,
            (workspace, page_id, notified_date),
        )
        return cursor.fetchone() is not None


def mark_notified(
    workspace: str,
    page_id: str,
    notified_date: str,
    db_path: Optional[Path] = None,
) -> None:
    """指定のタスクを通知済みとして記録する。

    Args:
        workspace: ワークスペース名。
        page_id: Notion のページ ID。
        notified_date: 通知日（ISO 形式の日付文字列 例: "2026-04-05"）。
        db_path: データベースファイルのパス。省略時はデフォルトパスを使用。
    """
    with _get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO notifications (workspace, page_id, notified_date)
            VALUES (?, ?, ?)
            """,
            (workspace, page_id, notified_date),
        )
        conn.commit()
