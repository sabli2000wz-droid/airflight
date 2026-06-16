"""
可爱版小飞机动画窗口
- 手绘风卡通小飞机（canvas 画的，不是字符）
- 彩色波浪旗帜横幅 + 粉色虚线绳子
- 星星尾迹粒子
- 飞行时轻微上下飘动（sin 波）
- 窗口淡入淡出
"""

from __future__ import annotations

import math
import random
import tkinter as tk
from tkinter import font as tkfont

# ── 可调参数 ────────────────────────────────────────────────
SPEED           = 5          # 水平速度 px/帧
FRAME_MS        = 14         # 帧间隔（约70fps）
BOB_AMPLITUDE   = 6          # 上下飘动幅度 px
BOB_SPEED       = 0.12       # 飘动角速度（弧度/帧）
WINDOW_H        = 110        # 画布高度
VERT_RATIO      = 0.18       # 飞行垂直位置（占屏高比例）
FONT_FAMILY     = "Microsoft YaHei"
FONT_SIZE       = 17
STAR_COUNT      = 7          # 同时存在的尾迹星星数量
FADE_FRAMES     = 18         # 淡入/淡出帧数

# ── 配色（可随意换）───────────────────────────────────────
PLANE_BODY   = "#7EC8E3"   # 机身浅蓝
PLANE_WING   = "#A8D8EA"   # 机翼
PLANE_CABIN  = "#FFF9C4"   # 舷窗黄
PLANE_DETAIL = "#4A90D9"   # 线条深蓝
ROPE_COLOR   = "#FFB7C5"   # 粉色绳子
BANNER_BG    = "#FFFDE7"   # 横幅米黄
BANNER_LINE1 = "#FF8FAB"   # 横幅顶边粉红
BANNER_LINE2 = "#A0C4FF"   # 横幅底边浅蓝
STAR_COLORS  = ["#FFD700", "#FF8FAB", "#B5EAD7", "#C7CEEA", "#FFDAC1"]


class AirplaneNotification:
    def __init__(self, parent: tk.Tk, text: str):
        self._parent  = parent
        self._text    = text
        self._frame   = 0
        self._alpha   = 0.0
        self._stars: list[dict] = []
        self._build()
        self._spawn_stars()
        self._animate()

    # ── 构建 ─────────────────────────────────────────────

    def _build(self):
        sw = self._parent.winfo_screenwidth()
        sh = self._parent.winfo_screenheight()

        # 量文字宽度
        tmp = tk.Toplevel(self._parent)
        tmp.withdraw()
        bf = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE, weight="bold")
        text_w = bf.measure(self._text)
        tmp.destroy()

        # 各区域宽度
        self._plane_w  = 90    # 飞机区域宽
        self._rope_len = 38
        self._banner_w = text_w + 52
        self._banner_h = FONT_SIZE + 28
        total_w = self._plane_w + self._rope_len + self._banner_w + 30

        self._total_w = total_w
        self._screen_w = sw
        win_y = int(sh * VERT_RATIO)
        self._base_y = win_y

        # 窗口
        win = tk.Toplevel(self._parent)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        try:
            win.attributes("-transparentcolor", "#020202")
            self._bg = "#020202"
        except tk.TclError:
            self._bg = "#f0f0f0"

        win.configure(bg=self._bg)
        win.geometry(f"{total_w}x{WINDOW_H}+{sw}+{win_y}")

        cv = tk.Canvas(win, width=total_w, height=WINDOW_H,
                       bg=self._bg, highlightthickness=0)
        cv.pack()

        self._win = win
        self._cv  = cv
        self._x   = float(sw)

        # 画静态元素（横幅）
        self._draw_banner()
        # 飞机和星星在每帧重绘

    def _draw_banner(self):
        cv = self._cv
        bx = self._plane_w + self._rope_len
        by = (WINDOW_H - self._banner_h) // 2
        bw = self._banner_w
        bh = self._banner_h

        # 旗帜主体（圆角，带阴影感）
        _rrect(cv, bx+3, by+4, bx+bw+3, by+bh+4, 14,
               fill="#e0d0c0", outline="", width=0)   # 阴影
        _rrect(cv, bx, by, bx+bw, by+bh, 14,
               fill=BANNER_BG, outline=BANNER_LINE1, width=2)

        # 顶部彩条
        cv.create_line(bx+14, by+2, bx+bw-14, by+2,
                       fill=BANNER_LINE1, width=3, capstyle="round")
        # 底部彩条
        cv.create_line(bx+14, by+bh-2, bx+bw-14, by+bh-2,
                       fill=BANNER_LINE2, width=3, capstyle="round")

        # 左侧小三角旗耳
        cv.create_polygon(
            bx, by+8,  bx-8, by+bh//2,  bx, by+bh-8,
            fill=BANNER_LINE1, outline=""
        )

        # 文字（带小描边效果）
        tx = bx + bw // 2
        ty = by + bh // 2
        for dx, dy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
            cv.create_text(tx+dx, ty+dy, text=self._text,
                           font=(FONT_FAMILY, FONT_SIZE, "bold"),
                           fill="#ffffff", anchor="center")
        cv.create_text(tx, ty, text=self._text,
                       font=(FONT_FAMILY, FONT_SIZE, "bold"),
                       fill="#d63384", anchor="center")

        # 绳子（粉色虚线）
        ry = WINDOW_H // 2
        cv.create_line(self._plane_w - 2, ry, bx + 2, ry,
                       fill=ROPE_COLOR, width=2, dash=(5, 4))
        # 绳结小圆
        cv.create_oval(bx-4, ry-4, bx+4, ry+4,
                       fill=ROPE_COLOR, outline="")

        self._banner_tag_base = None   # 横幅已画好，不需 tag

    # ── 星星 ─────────────────────────────────────────────

    def _spawn_stars(self):
        for _ in range(STAR_COUNT):
            self._stars.append(self._new_star(offset=random.randint(0, 40)))

    def _new_star(self, offset: int = 0) -> dict:
        ry = WINDOW_H // 2
        return {
            "x": self._plane_w - random.randint(10 + offset, 30 + offset),
            "y": ry + random.randint(-20, 20),
            "size": random.uniform(4, 9),
            "color": random.choice(STAR_COLORS),
            "life": random.randint(8, 20),
            "age": 0,
            "rot": random.uniform(0, math.pi),
        }

    def _draw_stars(self):
        cv = self._cv
        alive = []
        for s in self._stars:
            s["age"] += 1
            if s["age"] > s["life"]:
                alive.append(self._new_star())
                continue
            alpha_ratio = 1 - s["age"] / s["life"]
            sz = s["size"] * alpha_ratio
            if sz < 1:
                alive.append(self._new_star())
                continue
            _star5(cv, s["x"], s["y"], sz, s["color"], s["rot"])
            s["rot"] += 0.1
            alive.append(s)
        self._stars = alive

    # ── 飞机（canvas 手绘）───────────────────────────────

    def _draw_plane(self):
        cv  = self._cv
        cx  = self._plane_w // 2
        cy  = WINDOW_H // 2
        # 机身（椭圆）
        cv.create_oval(cx-38, cy-13, cx+22, cy+13,
                       fill=PLANE_BODY, outline=PLANE_DETAIL, width=1.5)
        # 机头（半圆突出）
        cv.create_arc(cx+4, cy-13, cx+30, cy+13,
                      start=-90, extent=180, style="chord",
                      fill=PLANE_BODY, outline=PLANE_DETAIL, width=1.5)
        # 主翼（上方）
        cv.create_polygon(
            cx-10, cy-13,
            cx+6,  cy-36,
            cx+24, cy-30,
            cx+12, cy-13,
            fill=PLANE_WING, outline=PLANE_DETAIL, width=1.5, smooth=True
        )
        # 尾翼（后上）
        cv.create_polygon(
            cx-38, cy-13,
            cx-34, cy-28,
            cx-22, cy-20,
            cx-22, cy-13,
            fill=PLANE_WING, outline=PLANE_DETAIL, width=1.5, smooth=True
        )
        # 尾翼（后下）
        cv.create_polygon(
            cx-38, cy+13,
            cx-34, cy+24,
            cx-26, cy+18,
            cx-26, cy+13,
            fill=PLANE_WING, outline=PLANE_DETAIL, width=1.5, smooth=True
        )
        # 舷窗
        for wx in [cx+6, cx-4, cx-14]:
            cv.create_oval(wx-6, cy-7, wx+6, cy+7,
                           fill=PLANE_CABIN, outline=PLANE_DETAIL, width=1)
            # 高光
            cv.create_oval(wx-4, cy-5, wx, cy-1,
                           fill="white", outline="")
        # 发动机（下方）
        cv.create_oval(cx-2, cy+10, cx+14, cy+20,
                       fill="#B0C4DE", outline=PLANE_DETAIL, width=1)
        # 脸（可爱版：眼睛 + 嘴）
        cv.create_oval(cx+20, cy-7, cx+27, cy,
                       fill="#333", outline="")   # 眼睛
        cv.create_arc(cx+15, cy-2, cx+28, cy+8,
                      start=200, extent=140, style="arc",
                      outline="#555", width=2)    # 笑嘴

    # ── 动画主循环 ────────────────────────────────────────

    def _animate(self):
        f = self._frame

        # 淡入
        if f < FADE_FRAMES:
            self._alpha = f / FADE_FRAMES
            self._win.attributes("-alpha", min(self._alpha * 0.95, 0.95))

        # 到了左侧边缘：淡出
        remaining = (self._x + self._total_w) / SPEED
        if remaining < FADE_FRAMES:
            a = max(0.0, remaining / FADE_FRAMES * 0.95)
            self._win.attributes("-alpha", a)
            if a <= 0:
                self._win.destroy()
                return

        # 飞出屏幕
        if self._x + self._total_w < -20:
            self._win.destroy()
            return

        # 移动（含上下飘动）
        self._x -= SPEED
        bob = BOB_AMPLITUDE * math.sin(f * BOB_SPEED)
        new_y = self._base_y + int(bob)
        self._win.geometry(f"+{int(self._x)}+{new_y}")

        # 重绘动态部分（飞机 + 星星）
        cv = self._cv
        # 只删飞机和星星的 tag，横幅保留
        cv.delete("dynamic")
        self._draw_stars_tagged()
        self._draw_plane_tagged()

        self._frame += 1
        self._win.after(FRAME_MS, self._animate)

    def _draw_stars_tagged(self):
        cv  = self._cv
        alive = []
        for s in self._stars:
            s["age"] += 1
            if s["age"] > s["life"]:
                alive.append(self._new_star())
                continue
            ratio = 1 - s["age"] / s["life"]
            sz = s["size"] * ratio
            if sz < 1:
                alive.append(self._new_star())
                continue
            _star5_tagged(cv, s["x"], s["y"], sz, s["color"], s["rot"])
            s["rot"] += 0.08
            alive.append(s)
        self._stars = alive

    def _draw_plane_tagged(self):
        cv  = self._cv
        cx  = self._plane_w // 2
        cy  = WINDOW_H // 2

        def ov(x1,y1,x2,y2,**kw):
            return cv.create_oval(x1,y1,x2,y2,tags="dynamic",**kw)
        def po(*pts,**kw):
            return cv.create_polygon(*pts,tags="dynamic",**kw)
        def ar(x1,y1,x2,y2,**kw):
            return cv.create_arc(x1,y1,x2,y2,tags="dynamic",**kw)

        # 机身
        ov(cx-38,cy-13,cx+22,cy+13,fill=PLANE_BODY,outline=PLANE_DETAIL,width=1.5)
        # 机头
        ar(cx+4,cy-13,cx+30,cy+13,start=-90,extent=180,style="chord",
           fill=PLANE_BODY,outline=PLANE_DETAIL,width=1.5)
        # 主翼
        po(cx-10,cy-13,cx+6,cy-36,cx+24,cy-30,cx+12,cy-13,
           fill=PLANE_WING,outline=PLANE_DETAIL,width=1.5,smooth=True)
        # 尾翼上
        po(cx-38,cy-13,cx-34,cy-28,cx-22,cy-20,cx-22,cy-13,
           fill=PLANE_WING,outline=PLANE_DETAIL,width=1.5,smooth=True)
        # 尾翼下
        po(cx-38,cy+13,cx-34,cy+24,cx-26,cy+18,cx-26,cy+13,
           fill=PLANE_WING,outline=PLANE_DETAIL,width=1.5,smooth=True)
        # 舷窗
        for wx in [cx+6, cx-4, cx-14]:
            ov(wx-6,cy-7,wx+6,cy+7,fill=PLANE_CABIN,outline=PLANE_DETAIL,width=1)
            ov(wx-4,cy-5,wx,cy-1,fill="white",outline="")
        # 发动机
        ov(cx-2,cy+10,cx+14,cy+20,fill="#B0C4DE",outline=PLANE_DETAIL,width=1)
        # 眼睛
        ov(cx+20,cy-7,cx+27,cy,fill="#333",outline="",tags="dynamic")
        # 嘴
        ar(cx+15,cy-2,cx+28,cy+8,start=200,extent=140,style="arc",
           outline="#555",width=2)
        # 腮红
        ov(cx+12,cy+2,cx+20,cy+9,fill="#FFB7C5",outline="")


# ── 工具函数 ────────────────────────────────────────────────

def _rrect(cv, x1, y1, x2, y2, r=10, **kw):
    pts = [
        x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
        x2,y2-r, x2,y2, x2-r,y2, x1+r,y2,
        x1,y2, x1,y2-r, x1,y1+r, x1,y1, x1+r,y1,
    ]
    return cv.create_polygon(pts, smooth=True, **kw)


def _star5(cv, cx, cy, r, color, rot=0):
    """画五角星"""
    pts = []
    for i in range(10):
        angle = rot + i * math.pi / 5 - math.pi / 2
        radius = r if i % 2 == 0 else r * 0.4
        pts += [cx + radius*math.cos(angle), cy + radius*math.sin(angle)]
    cv.create_polygon(pts, fill=color, outline="")


def _star5_tagged(cv, cx, cy, r, color, rot=0):
    pts = []
    for i in range(10):
        angle = rot + i * math.pi / 5 - math.pi / 2
        radius = r if i % 2 == 0 else r * 0.4
        pts += [cx + radius*math.cos(angle), cy + radius*math.sin(angle)]
    cv.create_polygon(pts, fill=color, outline="", tags="dynamic")
