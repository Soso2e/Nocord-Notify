"""Notion API クライアント / データ取得・正規化モジュール。

ワークスペース設定を受け取り、Notion データベースをクエリして
正規化された Task リストを返す。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import requests


_NOTION_API_VERSION = "2022-06-28"
_QUERY_URL_TEMPLATE = "https://api.notion.com/v1/databases/{database_id}/query"


# concept.md §6 のデータモデル
class Task:
    """正規化されたタスクデータ。

    Attributes:
        workspace: ワークスペース名。
        page_id: Notion のページ ID。
        title: タスク名。
        due_date: 期限（UTC aware datetime）。None の場合は期限未設定。
        status: ステータス文字列。
        url: Notion ページの URL。
        assignee: 担当者名。担当者未設定の場合は None。
    """

    def __init__(
        self,
        workspace: str,
        page_id: str,
        title: str,
        due_date: Optional[datetime],
        status: str,
        url: str,
        additional_label: str = "",
        additional_value: str = "",
    ) -> None:
        self.workspace = workspace
        self.page_id = page_id
        self.title = title
        self.due_date = due_date
        self.status = status
        self.url = url
        self.additional_label = additional_label
        self.additional_value = additional_value

    def __repr__(self) -> str:
        return (
            f"Task(workspace={self.workspace!r}, title={self.title!r}, "
            f"due_date={self.due_date!r}, status={self.status!r})"
        )


def _extract_title(properties: dict) -> str:
    """ページプロパティからタスク名を抽出する。

    Args:
        properties: Notion ページのプロパティ辞書。

    Returns:
        タスク名文字列。取得できない場合は空文字列。
    """
    for prop in properties.values():
        if prop.get("type") == "title":
            rich_texts = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts)
    return ""


def _extract_date(properties: dict, date_property: str) -> Optional[datetime]:
    """指定プロパティから期限日時を抽出する。

    Args:
        properties: Notion ページのプロパティ辞書。
        date_property: 期限が格納されているプロパティ名。

    Returns:
        UTC aware datetime。プロパティが存在しない / 値が None の場合は None。
    """
    prop = properties.get(date_property)
    if not prop:
        return None
    date_obj = prop.get("date")
    if not date_obj:
        return None
    raw = date_obj.get("end") or date_obj.get("start")
    if not raw:
        return None
    # date-only の場合（"2026-04-10"）はその日の midnight UTC として扱う
    try:
        if "T" in raw:
            return datetime.fromisoformat(raw).astimezone(timezone.utc)
        else:
            return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _extract_status(properties: dict, status_property: str) -> str:
    """指定プロパティからステータス文字列を抽出する。

    Args:
        properties: Notion ページのプロパティ辞書。
        status_property: ステータスが格納されているプロパティ名。

    Returns:
        ステータス文字列。取得できない場合は空文字列。
    """
    prop = properties.get(status_property)
    if not prop:
        return ""
    prop_type = prop.get("type")
    if prop_type == "status":
        status_obj = prop.get("status") or {}
        return status_obj.get("name", "")
    if prop_type == "select":
        select_obj = prop.get("select") or {}
        return select_obj.get("name", "")
    if prop_type == "rich_text":
        rich_texts = prop.get("rich_text", [])
        return "".join(rt.get("plain_text", "") for rt in rich_texts)
    if prop_type == "checkbox":
        return str(prop.get("checkbox", False))
    return ""


_RELATION_CACHE = {}

def _extract_additional(properties: dict, prop_name: str, token: str = "") -> str:
    """指定プロパティの値を文字列として抽出する（汎用）。"""
    prop = properties.get(prop_name)
    if not prop:
        return ""
    prop_type = prop.get("type", "")
    if prop_type == "select":
        val = prop.get("select")
        return val.get("name", "") if val else ""
    if prop_type == "multi_select":
        return ", ".join(item.get("name", "") for item in prop.get("multi_select", []))
    if prop_type == "rich_text":
        return "".join(rt.get("plain_text", "") for rt in prop.get("rich_text", []))
    if prop_type == "status":
        val = prop.get("status")
        return val.get("name", "") if val else ""
    if prop_type == "title":
        rich_texts = prop.get("title", [])
        return "".join(rt.get("plain_text", "") for rt in rich_texts)
    if prop_type == "relation" and token:
        val = prop.get("relation", [])
        names = []
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
        }
        for item in val:
            page_id = item.get("id")
            if not page_id:
                continue
            if page_id in _RELATION_CACHE:
                names.append(_RELATION_CACHE[page_id])
                continue
            try:
                url = f"https://api.notion.com/v1/pages/{page_id}"
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    p_props = resp.json().get("properties", {})
                    for k, v in p_props.items():
                        if v.get("type") == "title":
                            rta = v.get("title", [])
                            title_str = "".join(rt.get("plain_text", "") for rt in rta)
                            _RELATION_CACHE[page_id] = title_str
                            names.append(title_str)
                            break
            except Exception:
                pass
        return ", ".join(names)
    if prop_type == "formula":
        val = prop.get("formula", {})
        f_type = val.get("type", "")
        return str(val.get(f_type, "")) if f_type else ""

    # デフォルト
    val = prop.get(prop_type)
    return str(val) if val is not None else ""



def fetch_tasks(workspace_config: dict) -> list[Task]:
    """ワークスペース設定に基づき Notion からタスクを取得・正規化する。

    Args:
        workspace_config: config.json の1エントリ辞書。
            必須キー: name, notion_token, database_id,
                      date_property, status_property, done_values

    Returns:
        正規化された Task のリスト。

    Raises:
        requests.HTTPError: Notion API がエラーレスポンスを返した場合。
    """
    workspace_name: str = workspace_config["name"]
    token: str = workspace_config["notion_token"]
    database_id: str = workspace_config["database_id"]
    date_property: str = workspace_config["date_property"]
    status_property: str = workspace_config["status_property"]
    additional_property: Optional[str] = workspace_config.get("additional_property")

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NOTION_API_VERSION,
        "Content-Type": "application/json",
    }
    url = _QUERY_URL_TEMPLATE.format(database_id=database_id)

    tasks: list[Task] = []
    has_more = True
    start_cursor: Optional[str] = None

    while has_more:
        payload: dict = {}
        if start_cursor:
            payload["start_cursor"] = start_cursor

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        for page in data.get("results", []):
            properties = page.get("properties", {})
            task = Task(
                workspace=workspace_name,
                page_id=page["id"],
                title=_extract_title(properties),
                due_date=_extract_date(properties, date_property),
                status=_extract_status(properties, status_property),
                url=page.get("url", ""),
                additional_label=additional_property or "",
                additional_value=_extract_additional(properties, additional_property, token) if additional_property else "",
            )
            tasks.append(task)

        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return tasks
