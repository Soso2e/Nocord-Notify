"""タスクフィルタリングモジュール。

concept.md §7 のフィルタ条件を適用し、通知対象タスクを絞り込む。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

from notion_client import Task


_DEFAULT_NOTIFY_WITHIN_DAYS = 7


def filter_tasks(
    tasks: Sequence[Task],
    done_values: list[str],
    notify_within_days: int = _DEFAULT_NOTIFY_WITHIN_DAYS,
) -> list[Task]:
    """通知対象タスクをフィルタリングする。

    以下の全条件を満たすタスクを返す:
        - 期限が設定されている
        - 期限 >= 今日（過去の未完了タスクを除外）
        - 期限 <= 今日 + notify_within_days
        - ステータスが done_values に含まれない

    Args:
        tasks: フィルタ対象の Task リスト。
        done_values: 完了扱いとするステータス値のリスト。
        notify_within_days: 通知する期限の範囲（今日から何日後まで）。
            デフォルトは 7 日。

    Returns:
        通知対象の Task リスト。
    """
    now = datetime.now(tz=timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = today_start + timedelta(days=notify_within_days)

    result: list[Task] = []
    for task in tasks:
        if task.due_date is None:
            continue
        if task.status in done_values:
            continue
        if task.due_date > window_end:
            continue
        result.append(task)

    return result
