# ✈️ Outlook 日历小飞机提醒

在 Outlook 日历事项开始前 **15 分钟**，一架小飞机从屏幕右侧飞出，
后面拖着写有事项标题的白色横幅，划过屏幕后自动消失。

```
         ✈ ─ ─ ─ ┌──────────────────────┐
                  │  10:00  每周例会      │
                  └──────────────────────┘
```

---

## 快速开始（Windows + 本地 Outlook）

```bash
# 1. 安装依赖（只需 pywin32）
pip install pywin32

# 2. 启动（确保 Outlook 已打开）
python main.py
```

程序会一直在后台运行，每分钟检查一次日历。

---

## 跨平台 / 无本地 Outlook（Microsoft Graph API）

```bash
# 1. 安装依赖
pip install msal

# 2. 配置 Azure AD 凭证
cp config.json.example config.json
# 按 config.json 中的注释填写 client_id 和 tenant_id

# 3. 首次运行会弹出设备码认证，之后 token 自动缓存
python main.py
```

---

## 文件结构

```
airplane_reminder/
├── main.py            # 入口：监控日历 + 调度动画
├── calendar_reader.py # 日历读取（win32com / Graph API 双后端）
├── airplane_window.py # 小飞机动画窗口（tkinter）
├── requirements.txt
└── config.json.example
```

---

## 自定义参数

编辑 `main.py` 顶部：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `REMIND_MINUTES_BEFORE` | 15 | 提前几分钟提醒 |
| `CHECK_INTERVAL_SECONDS` | 60 | 检查日历的间隔（秒） |

编辑 `airplane_window.py` 顶部：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SPEED_PX_PER_FRAME` | 6 | 飞行速度（像素/帧） |
| `VERTICAL_POSITION` | 0.20 | 飞机飞行的垂直位置（0=顶部，1=底部） |
| `FONT_SIZE` | 18 | 横幅文字大小 |
| `PLANE_FONT_SIZE` | 36 | 飞机符号大小 |

---

## 开机自启（可选）

在 Windows 启动文件夹创建快捷方式：
- `Win+R` → `shell:startup`
- 把 `pythonw main.py` 的快捷方式放进去（`pythonw` 不会弹黑框）
