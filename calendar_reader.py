"""
日历读取器：优先尝试 win32com（本地 Outlook），
回退到 Microsoft Graph API（需要 config.json 中的凭证）
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

# ── 类型别名 ─────────────────────────────────────────────
CalendarEvent = dict[str, Any]   # {"id", "title", "start", "end"}


class OutlookCalendarReader:
    """
    抽象日历读取器。
    连接优先级：
      1. win32com  —— 本地 Outlook（Windows 最简单）
      2. Graph API —— 需要 Azure AD 应用注册（跨平台）
    """

    def __init__(self):
        self._backend: _Backend | None = None

    def connect(self) -> tuple[bool, str]:
        # 先试 win32com
        backend = _Win32Backend()
        ok, msg = backend.connect()
        if ok:
            self._backend = backend
            return True, msg

        # 再试 Graph API
        cfg_path = Path(__file__).parent / "config.json"
        if cfg_path.exists():
            backend2 = _GraphBackend(cfg_path)
            ok2, msg2 = backend2.connect()
            if ok2:
                self._backend = backend2
                return True, msg2
            return False, f"win32com: {msg} | Graph: {msg2}"

        return False, (
            f"win32com 不可用（{msg}），且未找到 config.json（Graph API 凭证）。"
            " 请参阅 README 完成配置。"
        )

    def get_events_in_range(
        self, start: datetime, end: datetime
    ) -> list[CalendarEvent]:
        if self._backend is None:
            raise RuntimeError("未连接日历，请先调用 connect()")
        return self._backend.get_events_in_range(start, end)


# ════════════════════════════════════════════════════════
#  后端抽象基类
# ════════════════════════════════════════════════════════

class _Backend:
    def connect(self) -> tuple[bool, str]: ...
    def get_events_in_range(self, start: datetime, end: datetime) -> list[CalendarEvent]: ...


# ════════════════════════════════════════════════════════
#  后端 1：win32com（本地 Outlook / Windows）
# ════════════════════════════════════════════════════════

class _Win32Backend(_Backend):
    def __init__(self):
        self._outlook = None
        self._calendar = None

    def connect(self) -> tuple[bool, str]:
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
            ns = outlook.GetNamespace("MAPI")
            # 6 = olFolderCalendar
            self._calendar = ns.GetDefaultFolder(9)
            self._outlook = outlook
            return True, "已通过 win32com 连接本地 Outlook 日历"
        except ImportError:
            return False, "pywin32 未安装（pip install pywin32）"
        except Exception as e:
            return False, str(e)

    def get_events_in_range(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        items = self._calendar.Items
        items.Sort("[Start]")
        items.IncludeRecurrences = True

        # Outlook Restrict 过滤器需要用这个时间格式
        f_start = start.strftime("%Y-%m-%d %H:%M")
        f_end   = end.strftime("%Y-%m-%d %H:%M")
        restriction = (
            f"[Start] >= '{f_start}' AND [Start] <= '{f_end}'"
        )
        filtered = items.Restrict(restriction)

        results: list[CalendarEvent] = []
        for item in filtered:
            try:
                results.append({
                    "id":    str(item.EntryID),
                    "title": item.Subject or "(无标题)",
                    "start": item.Start.replace(tzinfo=None),   # win32 COM datetime → python
                    "end":   item.End.replace(tzinfo=None),
                })
            except Exception:
                pass
        return results


# ════════════════════════════════════════════════════════
#  后端 2：Microsoft Graph API（跨平台）
# ════════════════════════════════════════════════════════

class _GraphBackend(_Backend):
    """
    需要 config.json：
    {
        "client_id":     "...",
        "client_secret": "...",   // 可选，委托流用设备码
        "tenant_id":     "..."
    }
    首次运行会弹出浏览器/设备码认证，token 缓存到 .token_cache
    """

    def __init__(self, cfg_path: Path):
        self._cfg_path = cfg_path
        self._app = None
        self._token: dict | None = None

    def connect(self) -> tuple[bool, str]:
        try:
            import msal
        except ImportError:
            return False, "msal 未安装（pip install msal）"

        try:
            cfg = json.loads(self._cfg_path.read_text())
            authority = f"https://login.microsoftonline.com/{cfg['tenant_id']}"
            cache_path = self._cfg_path.parent / ".token_cache"

            cache = msal.SerializableTokenCache()
            if cache_path.exists():
                cache.deserialize(cache_path.read_text())

            self._app = msal.PublicClientApplication(
                cfg["client_id"],
                authority=authority,
                token_cache=cache,
            )

            scopes = ["Calendars.Read"]
            accounts = self._app.get_accounts()
            result = None
            if accounts:
                result = self._app.acquire_token_silent(scopes, account=accounts[0])

            if not result:
                flow = self._app.initiate_device_flow(scopes=scopes)
                print(f"\n[Graph 认证] {flow['message']}\n")
                result = self._app.acquire_token_by_device_flow(flow)

            if "access_token" not in result:
                return False, result.get("error_description", "Graph 认证失败")

            self._token = result
            cache_path.write_text(cache.serialize())
            return True, "已通过 Microsoft Graph API 连接 Outlook 日历"

        except Exception as e:
            return False, str(e)

    def get_events_in_range(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        import urllib.request, urllib.parse

        iso = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S")
        params = urllib.parse.urlencode({
            "startDateTime": iso(start),
            "endDateTime":   iso(end),
            "$select":       "id,subject,start,end",
            "$top":          "50",
        })
        url = f"https://graph.microsoft.com/v1.0/me/calendarView?{params}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self._token['access_token']}"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        results: list[CalendarEvent] = []
        for item in data.get("value", []):
            try:
                dt_str = item["start"]["dateTime"][:19]
                results.append({
                    "id":    item["id"],
                    "title": item.get("subject") or "(无标题)",
                    "start": datetime.fromisoformat(dt_str),
                    "end":   datetime.fromisoformat(item["end"]["dateTime"][:19]),
                })
            except Exception:
                pass
        return results
