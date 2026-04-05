"""Discord Webhook 通知モジュール。

concept.md §8 の通知フォーマットでメッセージを生成し、Discord へ送信する。
"""

from __future__ import annotations

import requests
from datetime import datetime, timezone
from typing import Optional

from notion_client import Task


def _format_message(tasks: list[Task], mention_id: Optional[str] = None) -> str:
    """タスクリストを Discord 通知用のメッセージ文字列に変換する。

    Args:
        tasks: 通知対象の Task リスト。
        mention_id: メンション対象の Discord ユーザー ID。

    Returns:
        Discord 送信用のメッセージ文字列。
    """
    now = datetime.now(tz=timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    header = "**期限に関する通知があります**\n"
    if mention_id:
        header = f"<@{mention_id}> " + header

    lines: list[str] = [header]
    for task in tasks:
        due_str = (
            task.due_date.strftime("%Y-%m-%d") if task.due_date else "未設定"
        )
        assignee_str = task.assignee if task.assignee else "未設定"

        if task.due_date:
            days_diff = (task.due_date - today_start).days
            if days_diff < 0:
                overdue_days = abs(days_diff)
                title_prefix = f"【{overdue_days}日超過: ステータスを更新して下さい】"
            elif days_diff == 0:
                title_prefix = "【本日締切】"
            else:
                title_prefix = f"【残り{days_diff}日】"
        else:
            title_prefix = ""

        lines.append(
            f"- **{title_prefix} {task.title}**\n"
            f"  締切: {due_str} | 担当: {assignee_str}\n"
            f"  {task.url}"
        )
    return "\n".join(lines)


def send_notifications(
    tasks: list[Task],
    webhook_url: str,
    workspace_name: str,
    mention_id: Optional[str] = None,
) -> None:
    """タスクリストを Discord Webhook へ送信する。

    タスクが空の場合は何もしない。
    Discord のメッセージ文字数制限（2000 文字）を超える場合は
    複数リクエストに分割して送信する。

    Args:
        tasks: 通知対象の Task リスト。
        webhook_url: 送信先の Discord Webhook URL。
        workspace_name: ワークスペース名（ログ表示用）。
        mention_id: メンション対象の Discord ユーザー ID。

    Raises:
        requests.HTTPError: Discord API がエラーレスポンスを返した場合。
    """
    if not tasks:
        return

    message = _format_message(tasks, mention_id)
    _send_chunked(message, webhook_url, workspace_name)


def _send_chunked(
    message: str,
    webhook_url: str,
    workspace_name: str,
    chunk_size: int = 1900,
) -> None:
    """メッセージを Discord の文字数制限に合わせて分割送信する。

    Args:
        message: 送信するメッセージ全文。
        webhook_url: 送信先の Discord Webhook URL。
        workspace_name: ワークスペース名（ログ表示用）。
        chunk_size: 1 リクエストあたりの最大文字数。デフォルトは 1900。
    """
    chunks = [message[i:i + chunk_size] for i in range(0, len(message), chunk_size)]
    for i, chunk in enumerate(chunks, start=1):
        payload = {"content": chunk}
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        print(
            f"[{workspace_name}] Discord 通知送信完了 "
            f"({i}/{len(chunks)})"
        )
