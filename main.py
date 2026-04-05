"""Nocord CenterServer — エントリポイント。

concept.md §4 のデータフローを統括する。

使用方法:
    python main.py

事前準備:
    1. config.example.json をコピーして config.json を作成し、各設定を埋める
    2. pip install -r requirements.txt
"""

from __future__ import annotations

import json
import logging
import sys
import concurrent.futures
from datetime import datetime, timezone
from pathlib import Path

from filter import filter_tasks
from notion_client import fetch_tasks
from notifier import send_notifications
from storage import initialize_db, is_notified, mark_notified


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "config.json"


def _load_config(config_path: Path) -> list[dict]:
    """config.json を読み込む。

    Args:
        config_path: 設定ファイルのパス。

    Returns:
        ワークスペース設定のリスト。

    Raises:
        SystemExit: ファイルが存在しない場合。
    """
    if not config_path.exists():
        logger.error(
            "config.json が見つかりません。"
            "config.example.json をコピーして設定を作成してください。"
        )
        sys.exit(1)
    with config_path.open(encoding="utf-8") as f:
        return json.load(f)


def _process_workspace(workspace_config: dict, today_str: str) -> None:
    """1ワークスペースの通知処理を実行する。

    concept.md §4 のステップ 3〜8 に対応:
        3. Notion からデータ取得
        4. 正規化（notion_client 内で実施）
        5. フィルタ
        6. 通知生成（重複チェック含む）
        7. Discord 送信
        8. 履歴保存

    Args:
        workspace_config: ワークスペースの設定辞書。
        today_str: 本日の日付文字列（ISO 形式 例: "2026-04-05"）。
    """
    name: str = workspace_config["name"]
    done_values: list[str] = workspace_config.get("done_values", [])
    notify_within_days: int = workspace_config.get("notify_within_days", 7)
    webhook_url: str = workspace_config["discord_webhook_url"]
    mention_id: Optional[str] = workspace_config.get("discord_mention_id")

    logger.info("[%s] タスク取得開始", name)
    try:
        all_tasks = fetch_tasks(workspace_config)
    except Exception as exc:
        logger.error("[%s] Notion API エラー: %s", name, exc)
        return

    logger.info("[%s] 取得タスク数: %d", name, len(all_tasks))

    filtered = filter_tasks(all_tasks, done_values, notify_within_days)
    logger.info("[%s] フィルタ後タスク数: %d", name, len(filtered))

    # 重複チェック: 本日まだ通知していないタスクのみ対象にする
    new_tasks = [
        task for task in filtered
        if not is_notified(name, task.page_id, today_str)
    ]
    logger.info("[%s] 未通知タスク数: %d", name, len(new_tasks))

    if not new_tasks:
        logger.info("[%s] 通知対象なし。スキップ。", name)
        return

    try:
        send_notifications(new_tasks, webhook_url, name, mention_id=mention_id)
    except Exception as exc:
        logger.error("[%s] Discord 送信エラー: %s", name, exc)
        return

    # 送信成功後に履歴を記録する
    for task in new_tasks:
        mark_notified(name, task.page_id, today_str)
    logger.info("[%s] 履歴保存完了", name)


def main() -> None:
    """エントリポイント。全ワークスペースの通知処理を実行する。"""
    # ステップ 1: config 読み込み
    config = _load_config(_CONFIG_PATH)
    logger.info("設定読み込み完了: %d ワークスペース", len(config))

    # ステップ 2: DB 初期化
    initialize_db()

    today_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    # ステップ 3〜8: 各ワークスペースを並列処理
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(_process_workspace, workspace_config, today_str)
            for workspace_config in config
        ]
        concurrent.futures.wait(futures)

    logger.info("全処理完了")


if __name__ == "__main__":
    main()
