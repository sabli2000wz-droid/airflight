"""
Outlook Calendar 小飞机提醒
在日历事项开始前15分钟，屏幕上飞过一架小飞机，后面拖着写有事项标题的白色横幅
"""

import sys
import threading
import time
from datetime import datetime, timedelta

import tkinter as tk

from calendar_reader import OutlookCalendarReader
from airplane_window import AirplaneNotification


CHECK_INTERVAL_SECONDS = 60   # 每分钟检查一次日历
REMIND_MINUTES_BEFORE = 15    # 提前15分钟提醒


def monitor_calendar(reader: OutlookCalendarReader):
    """后台线程：持续监控即将到来的日历事项"""
    notified: set[str] = set()  # 记录已提醒的事项，避免重复

    while True:
        now = datetime.now()
        window_start = now + timedelta(minutes=REMIND_MINUTES_BEFORE - 1)
        window_end   = now + timedelta(minutes=REMIND_MINUTES_BEFORE + 1)

        try:
            events = reader.get_events_in_range(window_start, window_end)
        except Exception as e:
            print(f"[日历读取错误] {e}")
            time.sleep(CHECK_INTERVAL_SECONDS)
            continue

        for event in events:
            key = f"{event['id']}_{event['start'].isoformat()}"
            if key not in notified:
                notified.add(key)
                title = event["title"]
                start_str = event["start"].strftime("%H:%M")
                banner_text = f"📅 {start_str}  {title}"
                print(f"[提醒] {banner_text}")
                # 在主线程中创建动画窗口
                show_airplane(banner_text)

        # 清理两小时前的记录，防止 set 无限增长
        cutoff = now - timedelta(hours=2)
        notified = {
            k for k in notified
            if not _key_is_old(k, cutoff)
        }

        time.sleep(CHECK_INTERVAL_SECONDS)


def _key_is_old(key: str, cutoff: datetime) -> bool:
    # key 格式：id_ISO时间，无法反解时保留
    try:
        iso = key.rsplit("_", 1)[-1]
        return datetime.fromisoformat(iso) < cutoff
    except Exception:
        return False


_root: tk.Tk | None = None
_pending_banners: list[str] = []


def show_airplane(text: str):
    """线程安全地触发飞机动画"""
    if _root:
        _root.after(0, _launch_animation, text)
    else:
        _pending_banners.append(text)


def _launch_animation(text: str):
    AirplaneNotification(_root, text)


def main():
    global _root

    # ── 初始化日历读取器 ──────────────────────────────────
    reader = OutlookCalendarReader()
    connected, msg = reader.connect()
    if not connected:
        print(f"[错误] 无法连接 Outlook 日历：{msg}")
        print("请确认已安装 pywin32 并且 Outlook 正在运行，或已配置 Microsoft Graph API。")
        sys.exit(1)
    print(f"[连接成功] {msg}")

    # ── 后台监控线程 ────────────────────────────────────
    t = threading.Thread(target=monitor_calendar, args=(reader,), daemon=True)
    t.start()

    # ── 主 tkinter 隐藏窗口（用于调度 after() 回调）────
    _root = tk.Tk()
    _root.withdraw()          # 隐藏主窗口
    _root.title("CalendarPlane")

    # 处理启动前积压的提醒
    for banner in _pending_banners:
        _launch_animation(banner)
    _pending_banners.clear()

    print("[运行中] 正在监控 Outlook 日历，按 Ctrl+C 退出…")
    _root.mainloop()


if __name__ == "__main__":
    main()
