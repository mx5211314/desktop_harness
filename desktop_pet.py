# -*- coding: utf-8 -*-
"""
蓝色小鲸鱼薪资桌宠 · Whale Salary Pet（办公室治愈/隐匿版）
==========================================================

一只常驻 Windows 桌面的圆润治愈系蓝色小鲸鱼，陪你上班、帮你记录薪资。
专为「不想被老板发现」设计：

  形象与互动
  ----------
  - 圆润蓝鲸鱼：白肚皮、大眼睛、粉紫腮红、头顶喷水、摆尾（PIL 预渲染多帧贴图）
  - 动作：呼吸、眨眼、摆尾、喷水、开心、下班犯困（随机触发，有陪伴感）
  - 单击：鼓励语 / 今日薪资；双击：薪资面板；右键：菜单（面板/设置/隐藏/退出）
  - 上班「今天也要努力搬砖呀！」下班「辛苦啦…」周日「今天休息，工资也照常计算哦！」
  - 透明背景、无边框、置顶、可拖动；老板键 Ctrl+Q 全局一键隐身（无托盘无任务栏）
  - 迷你形态为低调蓝点（隐匿），数据文件伪装为 widget.cfg

  薪资规则（严格按用户口径实现，勿改）
  ----------------------------------
  - 月薪固定税前 7000 元；每周日不上班，但周日计入薪资分摊（单休也摊全月）
  - 时薪 = 7000 ÷ 当月自然日天数 ÷ 11（薪资基准 11h/天，自动识别 28/29/30/31 天与闰年）
    （10 月 31 天 → ¥20.53/h；30 天 → ¥21.21/h）
  - 实际在岗三段 08:30-11:00 / 13:00-16:30 / 17:30-19:30 合计 8 小时，
    仅用于「工时展示」；薪资计算基准仍为 11h/天，两者分开处理
  - 计时窗口 8:30-19:30 全程连续（午休晚饭也在公司，照算钱），8:30 自动开工
  - 双口径统计严格分开不重复相加：
    A 固定月薪累计 = 月薪 ÷ 当月自然日 × 已过天数（周日照常累计）
    B 工时折算 = 时薪 × 实际计时分钟（面板标注"参考，不重复计入"）
  - 月历标记周日休息日；薪资进度条按自然日推进；跨天/跨月/重启不丢数据

运行：双击 start_pet.pyw，或命令行 pythonw desktop_pet.py
打包：pyinstaller --onefile --noconsole --name WhaleSalaryPet desktop_pet.py
依赖：仅 Python 标准库（tkinter）；贴图由 render_whale.py（Pillow）离线生成
"""
from __future__ import annotations

import calendar
import ctypes
import json
import math
import os
import random
import socket
import sys
import threading
import time
from datetime import date, datetime, timedelta

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

MAGENTA = "#FF00FF"  # 透明色：窗口内该色区域变透明
if getattr(sys, "frozen", False):
    # PyInstaller onefile：贴图在临时解包目录，数据必须存 exe 旁边（否则重启即丢）
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))          # 数据目录
    BUNDLE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)                      # 只读资源目录
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR
DATA_FILE = os.path.join(BASE_DIR, "widget.cfg")  # 伪装成普通配置文件
FONT = "Microsoft YaHei"
SINGLE_INSTANCE_PORT = 47821  # 单实例互斥端口

# 精致灰蓝系配色（低调不炸眼）
C_BODY = "#C9D2DC"
C_EDGE = "#9AA7B4"
C_BELLY = "#EEF2F6"
C_INNER = "#E5C9C9"
C_DARK = "#3E4653"
C_TEXT = "#444441"
C_MUTED = "#6E7278"
C_CARD = "#F1EFE8"
C_BLUE = "#185FA5"
C_GOLD = "#BA7517"
C_BLUSH = "#F2C4C4"

# 面板 / 对话框 UI 配色（浅色扁平风）
UI_BG = "#FFFFFF"
UI_CARD = "#F4F6F9"
UI_BORDER = "#E3E8EF"
UI_ACCENT = "#4C8BF5"
UI_ACCENT_D = "#3A72CF"
UI_TEXT = "#2B3440"
UI_MUTED = "#8A94A6"
UI_ORANGE = "#F0A13A"

# 修饰键虚拟键码
VK_CTRL, VK_ALT, VK_SHIFT = 0x11, 0x12, 0x10
HOTKEYS = {
    "Ctrl+Q": ([VK_CTRL], 0x51),
    "Ctrl+Alt+H": ([VK_CTRL, VK_ALT], 0x48),
    "Ctrl+Alt+Q": ([VK_CTRL, VK_ALT], 0x51),
    "Ctrl+Alt+P": ([VK_CTRL, VK_ALT], 0x50),
}

POKE_QUOTES = [
    "今天也要努力搬砖呀！",
    "喷一口水，元气满满！",
    "钱包在悄悄变鼓哦。",
    "小鱼干…不对，工资在涨！",
    "你已经很努力啦，歇会儿~",
    "攒钱小鲸鱼陪你一起冲！",
]

WORK_QUOTES = [
    "今天也要努力搬砖呀！",
    "工位小鲸鱼已就位~",
    "每分钟都在进账哦！",
]
OFF_QUOTES = [
    "辛苦啦，今天也离攒钱自由更近一步！",
    "下班啦~小鲸鱼帮你看着钱包。",
    "今天辛苦了，奖励自己一条小鱼干！",
]
SUNDAY_QUOTE = "今天休息，工资也照常计算哦！"


def _fmt(v: float) -> str:
    return "¥{:,.2f}".format(v)


def _fmt_int(v: float) -> str:
    return "¥{:,.0f}".format(v)


def _h(hours: float) -> str:
    """小时数格式化：1 位小数，整数不带 .0（4.6057→4.6，16.0→16）。"""
    return "{:g}".format(round(hours, 1))


def _setup_fonts(root) -> None:
    """统一全局字体，消除"同一窗口字体对不上"的问题。

    原因：ttk 控件（如 Combobox）、下拉列表、菜单、系统弹窗不理会单控件的
    font 参数，会回退到 Tk 命名字体 / 主题默认字体（英文环境下是 Segoe UI），
    和显式指定雅黑的控件混排时字形、字号都不一致。
    这里把所有命名字体、ttk 样式、Combobox 下拉列表全部统一成微软雅黑。
    """
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
                 "TkTooltipFont", "TkCaptionFont", "TkSmallCaptionFont",
                 "TkIconFont"):
        try:
            tkfont.nametofont(name).configure(family=FONT, size=11)
        except tk.TclError:
            pass
    try:
        style = ttk.Style(root)
        style.configure(".", font=(FONT, 11))
        style.configure("TCombobox", font=(FONT, 11))
        style.configure("TCheckbutton", font=(FONT, 11))
        style.configure("TEntry", font=(FONT, 11))
    except tk.TclError:
        pass
    root.option_add("*TCombobox*Listbox.font", (FONT, 11))
    root.option_add("*Font", (FONT, 11))


def _fit_text_font(text: str, max_px: int, start: int = 9, floor: int = 6):
    """返回一个宽度不超过 max_px 的字体（逐级缩小字号）。"""
    size = start
    f = tkfont.Font(family=FONT, size=size)
    while size > floor and f.measure(text) > max_px:
        size -= 1
        f = tkfont.Font(family=FONT, size=size)
    return f


class PetData:
    """数据层：收入记录与持久化，不依赖 GUI，可独立测试。"""

    def __init__(self, path: str = DATA_FILE):
        self.path = path
        self.first_run = not os.path.exists(path)
        self.data = {
            "monthly_salary": 7000.0,
            "start_date": "2026-10-15",  # 入职/计薪起始日（月中入职从这天起算）
            # 日薪分母口径：calendar=当月总天数(30/31，单休也摊全月) / workdays=当月工作日(排除休息日)
            "salary_basis": "calendar",
            # 计时时段：每天 8:30-19:30 全程 11 小时（午休晚饭也在公司，照算）
            "work_segments": [["08:30", "19:30"]],
            "rest_weekdays": [6],  # 0=周一 … 6=周日；周日休息
            "auto_schedule": True,
            "work_minutes_per_day": 660,
            "mini_mode": True,
            "show_mini_amount": True,
            "show_plaque": False,
            "animate": False,
            "pet_size": "m",        # s/m/l 三档
            "auto_hide": False,     # 闲置 5 分钟自动收起小点
            "hotkey": "Ctrl+Q",
            "window_pos": None,
            "records": {},
        }
        self._load()

    def _load(self):
        if self.first_run:
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except (OSError, ValueError):
            pass
        self._migrate()

    def _migrate(self):
        """配置升级迁移。

        v2（2026-10-19 最终口径，一次性强制迁移，用 model_v2_11h 标记防重跑）：
          - 日薪 = 月薪 ÷ 当月总天数（单休、周日也摊进分母）
          - 计时时段 = 每天 8:30-19:30 全程 11 小时（660 分钟）

        旧版字段（daily_salary + 连续 work_start/work_end）在此一并清理。
        """
        d = self.data
        if not d.get("model_v2_11h"):
            if "daily_salary" in d:
                try:
                    ms = float(d.get("daily_salary", 0)) * 30.0
                except (TypeError, ValueError):
                    ms = 7000.0
                # 月薪按整数元取整：旧日薪 233.33×30=6999.9 → 7000
                d["monthly_salary"] = round(ms)
            d["salary_basis"] = "calendar"
            d["work_segments"] = [["08:30", "19:30"]]
            d["work_minutes_per_day"] = 660
            d["model_v2_11h"] = True
        if "work_segments" not in d:
            d["work_segments"] = [["08:30", "19:30"]]
        if "rest_weekdays" not in d:
            d["rest_weekdays"] = [6]
        if "salary_basis" not in d:
            d["salary_basis"] = "calendar"
        if "start_date" not in d:
            d["start_date"] = "2026-10-15"
        for old in ("daily_salary", "work_start", "work_end"):
            d.pop(old, None)
        self.save()

    def save(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass

    @staticmethod
    def today_str() -> str:
        return date.today().isoformat()

    @staticmethod
    def month_str() -> str:
        return date.today().strftime("%Y-%m")

    def day_record(self, day: str | None = None, create: bool = True):
        d = day or self.today_str()
        recs = self.data.setdefault("records", {}).setdefault(d[:7], {})
        rec = recs.get(d)
        if rec is None and create:
            rec = {"timed_minutes": 0.0, "manual": []}
            recs[d] = rec
        return rec

    @staticmethod
    def _parse_hm(s, default: int) -> int:
        try:
            h, m = str(s).split(":")
            return int(h) * 60 + int(m)
        except (ValueError, AttributeError):
            return default

    def schedule_segments(self) -> list:
        """工作时段列表 [(start_min, end_min), ...]。"""
        segs = []
        for seg in self.data.get("work_segments", []):
            if not isinstance(seg, (list, tuple)) or len(seg) < 2:
                continue
            s = self._parse_hm(seg[0], 8 * 60 + 30)
            e = self._parse_hm(seg[1], 19 * 60 + 30)
            if e > s:
                segs.append((s, e))
        return segs

    def schedule_minutes(self) -> float:
        """自动排班每日总工时（分钟）= 各段时长之和，默认 480。"""
        return float(sum(e - s for s, e in self.schedule_segments()))

    def schedule_summary(self) -> str:
        return " / ".join("{:02d}:{:02d}-{:02d}:{:02d}".format(s // 60, s % 60, e // 60, e % 60)
                          for s, e in self.schedule_segments())

    def in_work_window(self, now: float | None = None) -> bool:
        """当前是否在自动排班的工作时段内。手动模式（auto_schedule=False）恒为 True。

        休息日（默认周日）整日不工作；其余时段需落在某一段之内。
        """
        if not self.data.get("auto_schedule", True):
            return True
        t = datetime.now() if now is None else datetime.fromtimestamp(now)
        if t.weekday() in self.data.get("rest_weekdays", [6]):
            return False
        minutes = t.hour * 60 + t.minute + t.second / 60.0
        for s, e in self.schedule_segments():
            if s <= minutes < e:
                return True
        return False

    def cap(self) -> float:
        if self.data.get("auto_schedule", True):
            return self.schedule_minutes()
        try:
            v = float(self.data.get("work_minutes_per_day", 480))
        except (TypeError, ValueError):
            v = 480.0
        return v if v > 0 else 480.0

    @staticmethod
    def _workday_count(year: int, month: int, rest_weekdays: list) -> int:
        """当月非休息日（工作日）天数。"""
        ndays = calendar.monthrange(year, month)[1]
        count = 0
        for day in range(1, ndays + 1):
            if datetime(year, month, day).weekday() not in rest_weekdays:
                count += 1
        return count

    def _daily_divisor(self, today: date) -> int:
        """算日薪时的分母：按「当月工作日」或「当月总天数」。"""
        if self.data.get("salary_basis", "workdays") == "calendar":
            return calendar.monthrange(today.year, today.month)[1]
        return self._workday_count(today.year, today.month,
                                   self.data.get("rest_weekdays", [6]))

    def daily_salary(self, today: date | None = None) -> float:
        today = today or date.today()
        div = self._daily_divisor(today)
        if div <= 0:
            return 0.0
        try:
            monthly = float(self.data.get("monthly_salary", 0.0))
        except (TypeError, ValueError):
            monthly = 0.0
        return monthly / div

    def projected_month_total(self, today: date | None = None) -> float:
        """满勤预估：本月底能累计到多少（按入职日起算的在职天数）。

        calendar 口径：在职自然日 × 日薪（含周日带薪）
        workdays 口径：在职工作日 × 日薪
        月中入职时本月自然拿不满月薪，整月（如 11 月起）满勤 = 月薪。
        """
        today = today or date.today()
        daily = self.daily_salary(today)
        s = self._start_day_of_month(today)
        if self.data.get("salary_basis", "workdays") == "calendar":
            return round(daily * (calendar.monthrange(today.year, today.month)[1] - s + 1), 2)
        rest = set(self.data.get("rest_weekdays", [6]))
        wd = sum(1 for day in range(s, calendar.monthrange(today.year, today.month)[1] + 1)
                 if datetime(today.year, today.month, day).weekday() not in rest)
        return round(daily * wd, 2)

    def _start_day_of_month(self, today: date) -> int:
        """本月计薪起始日：入职日在本月则从入职日起算，否则从 1 号。"""
        sd = self._parse_date(self.data.get("start_date"))
        if sd and sd.year == today.year and sd.month == today.month:
            return max(1, min(sd.day, calendar.monthrange(today.year, today.month)[1]))
        return 1

    @staticmethod
    def _parse_date(v):
        try:
            return datetime.strptime(str(v), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    def month_billed_days(self, today: date | None = None) -> int:
        """本月已计薪自然日天数：已过天数中 ≥ 计薪起始日 的部分（含今天）。"""
        today = today or date.today()
        s = self._start_day_of_month(today)
        return max(0, today.day - s + 1)

    def rest_pay_days(self, today: date | None = None) -> int:
        """本月已过、且没有计时收入的休息日天数（应带薪，从入职日起算）。"""
        today = today or date.today()
        if self.data.get("salary_basis", "workdays") != "calendar":
            return 0
        rest = set(self.data.get("rest_weekdays", [6]))
        if not rest:
            return 0
        s = self._start_day_of_month(today)
        records = self.month_days()
        count = 0
        for day in range(s, today.day + 1):
            t = datetime(today.year, today.month, day)
            if t.weekday() not in rest:
                continue
            rec = records.get(t.strftime("%Y-%m-%d"))
            if not rec or rec.get("timed_minutes", 0.0) <= 0:
                count += 1
        return count

    def month_rest_pay(self, today: date | None = None) -> float:
        """休息日带薪：单休也摊全月 → 休息日不上班也按日薪计入。"""
        return round(self.rest_pay_days(today) * self.daily_salary(today), 2)

    def per_minute(self) -> float:
        monthly = 0.0
        try:
            monthly = float(self.data.get("monthly_salary", 0.0))
        except (TypeError, ValueError):
            monthly = 0.0
        cap = self.cap()
        if cap <= 0:
            return 0.0
        today = date.today()
        div = self._daily_divisor(today)
        if div <= 0:
            return 0.0
        daily = monthly / div
        return daily / cap

    def add_manual(self, amount: float, note: str = "") -> float:
        rec = self.day_record()
        rec.setdefault("manual", []).append(
            {"ts": time.time(), "amount": round(float(amount), 2), "note": note}
        )
        self.save()
        return self.day_income()

    def set_timed_minutes(self, minutes: float) -> float:
        minutes = max(0.0, min(float(minutes), self.cap()))
        self.day_record()["timed_minutes"] = round(minutes, 4)
        return minutes

    def timed_income(self, day: str | None = None) -> float:
        rec = self.day_record(day, create=False)
        return (rec.get("timed_minutes", 0.0) if rec else 0.0) * self.per_minute()

    def manual_income(self, day: str | None = None) -> float:
        rec = self.day_record(day, create=False)
        if not rec:
            return 0.0
        return sum(i.get("amount", 0.0) for i in rec.get("manual", []))

    def day_income(self, day: str | None = None) -> float:
        return round(self.timed_income(day) + self.manual_income(day), 2)

    # ---- 双口径统计（严格区分，不重复相加）----
    # 口径A 固定月薪累计：按当月自然日时间进度平均分摊，周日也照常累计
    # 口径B 工时折算：时薪 × 实际计时分钟（只算真正在计时的时间）

    def month_days_in_month(self, today: date | None = None) -> int:
        """当月自然日总数（自动识别 28/29/30/31，含闰年）。"""
        today = today or date.today()
        return calendar.monthrange(today.year, today.month)[1]

    def month_days_passed(self, today: date | None = None) -> int:
        """本月已过自然日天数（含今天）。"""
        today = today or date.today()
        return today.day

    def month_days_left(self, today: date | None = None) -> int:
        """本月剩余自然日天数。"""
        today = today or date.today()
        return self.month_days_in_month(today) - today.day

    def month_salary_progress(self, today: date | None = None) -> float:
        """口径A：固定月薪按自然日进度累计（周日也照常计入，从入职日起算）。"""
        today = today or date.today()
        try:
            monthly = float(self.data.get("monthly_salary", 0.0))
        except (TypeError, ValueError):
            monthly = 0.0
        return monthly / self.month_days_in_month(today) * self.month_billed_days(today)

    def month_manual_income(self) -> float:
        total = 0.0
        for rec in self.month_days().values():
            total += sum(i.get("amount", 0.0) for i in rec.get("manual", []))
        return total

    def month_work_income(self, today: date | None = None) -> float:
        """口径B：本月工时折算收入 = 累计计时分钟 × 时薪（不含周日/不计时时段）。"""
        return self.month_total_minutes() * self.per_minute()

    def month_income(self) -> float:
        """本月总收入 = 固定月薪进度累计 + 手动外快（工时折算单独展示，不重复相加）。"""
        return round(self.month_salary_progress() + self.month_manual_income(), 2)

    def actual_hours(self, minutes: float) -> float:
        """实际在岗工时（小时）：三段合计 8h/11h 基准折算。

        计时按 11h/天基准（8:30-19:30 全程），实际在岗为三段共 8h，
        两者同比例换算：在岗小时 = 计时分钟 × 8/11 ÷ 60。
        """
        return float(minutes) * 8.0 / 11.0 / 60.0

    def day_actual_hours(self) -> float:
        rec = self.day_record(create=False)
        return self.actual_hours(rec.get("timed_minutes", 0.0) if rec else 0.0)

    def month_actual_hours(self) -> float:
        return self.actual_hours(self.month_total_minutes())

    def month_days(self) -> dict:
        return self.data.get("records", {}).get(self.month_str(), {})

    def hourly_rate(self, today: date | None = None) -> float:
        """时薪 = 日薪 ÷ 每日计时小时数（面板/设置统一用这一个口径）。"""
        cap = self.cap()
        if cap <= 0:
            return 0.0
        return self.daily_salary(today) / cap * 60.0

    def month_worked_days(self) -> int:
        """本月有计时或手动收入记录的天数（已工作天数）。"""
        count = 0
        for rec in self.month_days().values():
            if rec.get("timed_minutes", 0.0) > 0 or rec.get("manual"):
                count += 1
        return count

    def month_total_minutes(self) -> float:
        """本月累计计时分钟数。"""
        return float(sum(rec.get("timed_minutes", 0.0)
                         for rec in self.month_days().values()))


class DesktopPetApp:
    MINI, MINI_SIZE = 32, 32

    def __init__(self):
        self.data = PetData()
        self._lock_socket = self._ensure_single_instance()
        if self._lock_socket is None:
            return

        self.root = tk.Tk()
        self.root.title("桌面小组件")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=MAGENTA)
        self.root.attributes("-transparentcolor", MAGENTA)

        _setup_fonts(self.root)
        self._size_factor = {"s": 0.85, "m": 1.0, "l": 1.2}.get(
            self.data.data.get("pet_size", "m"), 1.0)
        self.W = int(190 * self._size_factor)
        self.H = int(175 * self._size_factor)
        self._sprites = self._scale_sprites(self._load_sprites(), self._size_factor)

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        pos = self.data.data.get("window_pos") or [sw - 70, sh - 150]
        self.root.geometry("{}x{}+{}+{}".format(self.MINI_SIZE, self.MINI_SIZE, int(pos[0]), int(pos[1])))

        self.canvas = tk.Canvas(
            self.root, width=self.MINI_SIZE, height=self.MINI_SIZE, bg=MAGENTA, highlightthickness=0
        )
        self.canvas.pack()

        # 运行状态
        self.mini = bool(self.data.data.get("mini_mode", True))
        if self.data.first_run:
            self.mini = False  # 首次启动用完整形态做引导
        self.hidden = False
        self.hover = False
        self.working = False
        self.session_start = 0.0
        self.base_minutes = 0.0
        self.frame = 0
        self.blink_next = time.time() + random.uniform(2.0, 5.0)
        self.blink_until = 0.0
        self.hop_until = 0.0
        # 随机动作状态机：spout 喷水 / tail 摆尾 / happy 开心
        self._action = None          # "spout" | "tail" | "happy"
        self._action_until = 0.0
        self._next_spout = time.time() + random.uniform(8, 20)
        self._next_tail = time.time() + random.uniform(4, 10)
        self.bubble_text = None
        self.bubble_until = 0.0
        self.panel = None
        self._tip = None
        self._drag = None
        self._moved = False
        self._today = self.data.today_str()
        self._last_activity = time.time()
        self._stop = threading.Event()
        self._hotkey_combo = HOTKEYS.get(self.data.data.get("hotkey"), HOTKEYS["Ctrl+Q"])
        self._last_in_win = None
        self._manual_pause = False

        self._var_top = tk.BooleanVar(value=True)
        self._bind_events()
        self._build_menu()

        if self.data.first_run:
            self.show_bubble("我是你的小鲸鱼~\n老板键 Ctrl+Q 一键隐身\n双击看收入 · 单击聊聊天 · 右键有菜单", 6.0)
        else:
            if self.data.data.get("auto_schedule") and self.data.in_work_window():
                status = "自动排班计时中"
            elif self.data.data.get("auto_schedule"):
                segs = self.data.schedule_segments()
                first = segs[0][0] // 60 if segs else 8
                status = "休息中，明早 {} 点自动开工".format(first)
            else:
                status = "右键可开始计时"
            self.show_bubble("今日 {}\n{}\n（老板键 {} 隐身）".format(
                _fmt(self.data.day_income()), status, self.data.data.get("hotkey")), 3.5)

        self._resize()
        threading.Thread(target=self._watch_hotkey, daemon=True).start()
        self._tick()

    @staticmethod
    def _load_sprites() -> dict:
        """加载预渲染小鲸鱼帧（render_whale.py 生成）；缺失时返回空走矢量回退。"""
        sprites = {}
        names = ["idle0", "idle1", "blink", "happy", "sleepy", "off",
                 "tail0", "tail1", "tail2",
                 "spout0", "spout1", "spout2", "spout3"]
        for n in names:
            try:
                sprites[n] = tk.PhotoImage(
                    file=os.path.join(BUNDLE_DIR, "whale_{}.png".format(n)))
            except tk.TclError:
                return {}
        return sprites

    @staticmethod
    def _scale_sprites(sprites: dict, factor: float) -> dict:
        """按大小档缩放全部帧（zoom+subsample 组合近似任意倍率）。"""
        if abs(factor - 1.0) < 0.02:
            return sprites
        z = 6
        sub = max(2, int(round(z / factor)))
        out = {}
        for k, ph in sprites.items():
            try:
                out[k] = ph.zoom(z, z).subsample(sub, sub)
            except tk.TclError:
                out[k] = ph
        return out

    # ---------- 单实例 ----------
    def _ensure_single_instance(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
            s.listen(1)
            return s
        except OSError:
            messagebox.showinfo("赚账宠", "桌宠已经在运行啦。\n按 {} 可以隐藏 / 唤回。".format(
                self.data.data.get("hotkey", "Ctrl+Q")))
            return None

    # ---------- 事件 ----------
    def _bind_events(self):
        c = self.canvas
        c.bind("<ButtonPress-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Double-Button-1>", lambda e: self.open_panel())
        c.bind("<Button-3>", self._on_right_click)
        c.bind("<Enter>", lambda e: self._set_hover(True))
        c.bind("<Leave>", lambda e: self._set_hover(False))

    def _set_hover(self, on: bool):
        self.hover = on
        self._last_activity = time.time()
        try:
            self.root.attributes("-alpha", 1.0 if on else 0.78)
        except tk.TclError:
            pass

    def _on_press(self, e):
        self._last_activity = time.time()
        self._drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())
        self._moved = False

    def _on_drag(self, e):
        if not self._drag:
            return
        self._moved = True  # 只要有拖动事件就算拖动，杜绝"拖动松手误触发展开/冒泡"
        dx, dy = self._drag
        nx, ny = e.x_root - dx, e.y_root - dy
        self.root.geometry("+{}+{}".format(nx, ny))

    def _on_release(self, e):
        self._last_activity = time.time()
        if self._drag and not self._moved:
            if self.mini:
                self._set_mini(False)
            else:
                self._poke()
        self._drag = None

    def _poke(self):
        self.hop_until = time.time() + 0.4
        self._action, self._action_until = "happy", time.time() + 0.6
        t = datetime.now()
        if t.weekday() == 6:
            quote = SUNDAY_QUOTE
        elif self.working or self.data.in_work_window():
            quote = random.choice(WORK_QUOTES)
        else:
            quote = random.choice(OFF_QUOTES)
        self.show_bubble(quote + "\n今日已赚 " + _fmt(self.data.day_income()), 3.0)

    def _on_right_click(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def _build_menu(self):
        m = tk.Menu(self.root, tearoff=0, font=(FONT, 11))
        m.add_command(label="展开 / 收起小点", command=lambda: self._set_mini(not self.mini))
        m.add_command(label="暂停计时" if self.working else "开始今天的工作",
                      command=self._pause_work if self.working else self._start_work)
        m.add_command(label="记一笔…", command=self.open_add_money)
        m.add_command(label="收入面板", command=self.open_panel)
        m.add_command(label="设置…", command=self.open_settings)
        m.add_separator()
        m.add_command(label="立即隐身（老板键）", command=self._toggle_hidden)
        m.add_separator()
        m.add_command(label="退出", command=self.quit)
        self.menu = m

    # ---------- 形态切换 ----------
    def _resize(self):
        if self.mini:
            self.canvas.config(width=self.MINI_SIZE, height=self.MINI_SIZE)
            self.root.geometry("{}x{}".format(self.MINI_SIZE, self.MINI_SIZE))
        else:
            self.canvas.config(width=self.W, height=self.H)
            self.root.geometry("{}x{}".format(self.W, self.H))

    def _set_mini(self, mini: bool):
        if mini == self.mini:
            return
        # 保持窗口中心不变
        cx = self.root.winfo_x() + (self.MINI_SIZE if self.mini else self.W) / 2
        cy = self.root.winfo_y() + (self.MINI_SIZE if self.mini else self.H) / 2
        self.mini = mini
        self.data.data["mini_mode"] = mini
        self._resize()
        w = self.MINI_SIZE if mini else self.W
        h = self.MINI_SIZE if mini else self.H
        self.root.geometry("+{}+{}".format(int(cx - w / 2), int(cy - h / 2)))
        self.data.save()

    # ---------- 隐身 ----------
    def _toggle_hidden(self):
        if self.hidden:
            # 静默唤回，不弹任何提示（避免暴露）
            self.root.deiconify()
            self.root.lift()
            self.hidden = False
            self._last_activity = time.time()
        else:
            self.root.withdraw()
            self.hidden = True
            self.bubble_text = None
            self.bubble_until = 0.0
            if self._tip is not None:
                self._tip.hide()

    def _watch_hotkey(self):
        user32 = ctypes.windll.user32
        mods, vk = self._hotkey_combo

        def pressed() -> bool:
            try:
                return (all(user32.GetAsyncKeyState(m) & 0x8000 for m in mods)
                        and user32.GetAsyncKeyState(vk) & 0x8000)
            except OSError:
                return False

        while not self._stop.is_set():
            if pressed():
                self.root.after(0, self._toggle_hidden)
                while not self._stop.is_set() and pressed():
                    time.sleep(0.05)
            time.sleep(0.05)

    # ---------- 计时 ----------
    def _start_work(self, announce: bool = True):
        self._manual_pause = False
        rec = self.data.day_record(create=False)
        existing = float(rec.get("timed_minutes", 0.0)) if rec else 0.0
        if existing >= self.data.cap():
            if announce:
                self.show_bubble("今天的工时已经满了，好好休息", 3.0)
            self.working = False
            return
        self.base_minutes = existing  # 恢复当天已有计时，重启/暂停不丢
        self.session_start = time.time()
        self.working = True
        if announce:
            self.show_bubble("开始计时\n每分钟 " + _fmt(self.data.per_minute()), 3.0)

    def _pause_work(self):
        if not self.working:
            return
        minutes = min(self.data.cap(), self.base_minutes + (time.time() - self.session_start) / 60.0)
        self.data.set_timed_minutes(minutes)
        self.base_minutes = minutes
        self.working = False
        self._manual_pause = True
        self.data.save()
        self.show_bubble("已暂停\n今日 " + _fmt(self.data.day_income()), 2.5)

    def _auto_schedule_update(self):
        """自动排班：到点自动开工 / 收工。手动暂停后当日内不再自动重启。"""
        if not self.data.data.get("auto_schedule", True):
            return
        in_win = self.data.in_work_window()
        if in_win != self._last_in_win:
            self._last_in_win = in_win
            self._manual_pause = False
        if in_win and not self.working and not self._manual_pause:
            if self.base_minutes < self.data.cap():
                self._start_work(announce=False)
                self.show_bubble("到点自动开工\n每分钟 " + _fmt(self.data.per_minute()), 4.0)
        elif not in_win and self.working:
            self._pause_work()
            self.show_bubble("到点自动收工\n今日 " + _fmt(self.data.day_income()), 4.0)

    def _accrue(self, now: float):
        if not self.working:
            return
        minutes = self.base_minutes + (now - self.session_start) / 60.0
        if minutes >= self.data.cap():
            minutes = self.data.cap()
            self.working = False
            self.show_bubble("今天的目标工时已完成\n今日 " + _fmt(self.data.day_income()), 4.0)
        self.data.set_timed_minutes(minutes)
        if self.frame % 300 == 0:
            self.data.save()

    def _check_new_day(self):
        today = self.data.today_str()
        if today != self._today:
            self.data.save()
            self._today = today
            self.base_minutes = 0.0
            self._manual_pause = False
            if self.working:
                self.session_start = time.time()
            self.show_bubble("新的一天，从赚米开始", 3.0)

    # ---------- 主循环 ----------
    def _tick(self):
        self.frame += 1
        now = time.time()
        self._check_new_day()
        self._auto_schedule_update()
        self._accrue(now)
        if now >= self.blink_next:
            self.blink_until = now + 0.14
            self.blink_next = now + random.uniform(2.5, 5.5)
        self._update_actions(now)
        self._auto_hide_check(now)
        self._draw(now)
        self.root.after(100, self._tick)

    def _auto_hide_check(self, now: float):
        """闲置 5 分钟自动收起小点（可在设置关闭）。"""
        if not self.data.data.get("auto_hide") or self.mini or self.hidden:
            return
        if now - self._last_activity > 300:
            self._set_mini(True)
            self.show_bubble("闲置太久，小鲸鱼先收起来啦\n右键可再展开", 3.0)
            self._last_activity = now

    def _update_actions(self, now: float):
        """随机动作调度：喷水 / 摆尾，制造陪伴感。"""
        if self._action and now >= self._action_until:
            self._action = None
        if self.hidden or self.mini:
            return
        if self._action:
            return
        if now >= self._next_spout:
            self._action, self._action_until = "spout", now + 0.8
            self._next_spout = now + random.uniform(10, 25)
        elif now >= self._next_tail:
            self._action, self._action_until = "tail", now + 0.6
            self._next_tail = now + random.uniform(6, 14)

    # ---------- 绘制 ----------
    def _mood(self) -> str:
        """表情状态：work 开心 / off 疲惫（收工后）/ idle 平静。"""
        if self.working:
            return "work"
        if self.data.data.get("auto_schedule") and not self.data.in_work_window():
            return "off"
        return "idle"

    def _draw(self, now: float):
        c = self.canvas
        c.delete("all")
        if self.bubble_text and now < self.bubble_until and not self.mini:
            self._draw_bubble(c)
        dy = 0.0
        if self.mini:
            if self.working:
                dy = -abs(math.sin(now * 5.0)) * 2  # 迷你形态也有轻微活跃感
        elif self.data.data.get("animate"):
            dy = -abs(math.sin(now * 5.0)) * 3 if self.working else math.sin(now * 1.8) * 1.5
        if now < self.hop_until:
            dy += -math.sin((self.hop_until - now) / 0.4 * math.pi) * 6
        if self.mini:
            self._draw_mini(c, dy)
        else:
            self._draw_whale(c, dy, now)
            if self.data.data.get("show_plaque"):
                self._draw_plaque(c)

    # ---------- 小鲸鱼绘制 ----------
    def _whale_key(self, now: float) -> str:
        """根据动作状态机 + 心情 + 眨眼选当前帧。"""
        if self._action == "spout":
            f = int((self._action_until - now) / 0.2)  # 0.8s -> 0..3
            return "spout{}".format(max(0, min(3, 3 - f)))
        if self._action == "tail":
            f = int((now * 10) % 3)
            return "tail{}".format(f)
        if self._action == "happy" or (self.working and self.hover):
            return "happy"
        mood = self._mood()
        if mood == "work":
            return "tail{}".format(int(self.frame // 8) % 3)  # 工作持续摆尾
        if mood == "off":
            return "off"
        if now < self.blink_until:
            return "blink"
        return "idle{}".format(int(self.frame // 12) % 2)

    def _draw_whale(self, c, dy: float, now: float):
        if not self._sprites:
            self._draw_whale_legacy(c, dy)
            return
        key = self._whale_key(now)
        ph = self._sprites.get(key) or self._sprites.get("idle0")
        c.create_image(0, self.H - ph.height() + dy, image=ph, anchor="nw")
        # 困倦 Zzz（下班休息且非动画帧时偶发）
        if self._mood() == "off" and int(now * 2) % 2 == 0:
            fx, fy = self.W - 24 * self._size_factor, self.H - 120 * self._size_factor
            c.create_text(fx, fy, text="Z z", font=(FONT, 10),
                          fill="#8FA6BE", anchor="center")

    def _draw_bubble(self, c):
        lines = self.bubble_text.split("\n")
        w, lh = 150, 18
        h = 10 + len(lines) * lh
        c.create_oval(10, 2, 10 + w, 2 + h, fill="#FFFFFF", outline="#D3D1C7", width=1)
        c.create_polygon([(76, h), (88, h), (82, h + 7)], fill="#FFFFFF", outline="")
        for i, line in enumerate(lines):
            c.create_text(10 + w / 2, 12 + i * lh, text=line, font=(FONT, 11),
                          fill=C_TEXT, anchor="center")

    def _draw_mini(self, c, dy: float = 0.0):
        hover = self.hover
        fill = "#9CCBEE" if hover else "#8FBEE4"   # 迷你小鲸鱼蓝点
        pad = -1 if hover else 0  # 悬停时微微放大
        # 小尾鳍
        c.create_oval(24, 16 + pad + dy, 31 - pad, 25 + pad + dy,
                      fill="#7FB0DC", outline="#5E92C2", width=1)
        # 圆点本体
        c.create_oval(2 + pad, 7 + pad + dy, 28 - pad, 33 - pad + dy,
                      fill=fill, outline="#5E92C2", width=1)
        # 当日完成度进度环（贴在圆点边缘，从正上方顺时针走）
        rec = self.data.day_record(create=False)
        timed = rec.get("timed_minutes", 0.0) if rec else 0.0
        p = max(0.0, min(1.0, timed / self.data.cap()))
        if p > 0:
            c.create_arc(3, 8, 27, 32, start=90, extent=-360 * p,
                         outline=UI_ACCENT, width=2, style="arc")
        # 高光 + 小眼睛
        c.create_oval(6, 12 + dy, 11, 17 + dy, fill="#DFF0FC", outline="")
        c.create_oval(10, 15 + dy, 12, 17 + dy, fill="#2E4A66", outline="")
        c.create_oval(17, 15 + dy, 19, 17 + dy, fill="#2E4A66", outline="")
        if self.data.data.get("show_mini_amount", True):
            txt = _fmt_int(self.data.day_income())
            # 金额超出小圆点宽度时自动缩小字号，避免文字顶破圆边
            f = _fit_text_font(txt, max_px=22, start=9, floor=6)
            c.create_text(15, 24 + dy, text=txt, font=f, fill="#2E4A66", anchor="center")

    def _draw_whale_legacy(self, c, dy: float):
        """贴图缺失时的矢量简笔鲸鱼回退。"""
        W, H = self.W, self.H
        s = self._size_factor
        bx0, by0 = int(W * 0.08), int(H * 0.32)
        bx1, by1 = int(W * 0.82), int(H * 0.97)
        c.create_oval(bx0, by0 + dy, bx1, by1 + dy,
                      fill="#84BAE9", outline="#3E6FA0", width=2)
        c.create_oval(int(W * 0.22), int(H * 0.60) + dy,
                      int(W * 0.66), int(H * 0.92) + dy,
                      fill="#F6FBFF", outline="")
        # 尾鳍
        c.create_oval(bx1 - 6, int(H * 0.42) + dy, bx1 + 26 * s, int(H * 0.72) + dy,
                      fill="#68A4DA", outline="#3E6FA0", width=2)
        # 眼睛 + 高光
        for ex in (int(W * 0.30), int(W * 0.54)):
            c.create_oval(ex, int(H * 0.44) + dy, ex + 12 * s, int(H * 0.44) + 12 * s + dy,
                          fill=C_DARK, outline="")
            c.create_oval(ex + 2, int(H * 0.44) + 2 + dy, ex + 6, int(H * 0.44) + 6 + dy,
                          fill="#FFFFFF", outline="")
        # 腮红 / 嘴 / 喷水孔
        c.create_oval(int(W * 0.18), int(H * 0.55) + dy, int(W * 0.30), int(H * 0.62) + dy,
                      fill="#F4C5D8", outline="")
        c.create_oval(int(W * 0.62), int(H * 0.55) + dy, int(W * 0.74), int(H * 0.62) + dy,
                      fill="#F4C5D8", outline="")
        c.create_arc(int(W * 0.44), int(H * 0.52) + dy, int(W * 0.56), int(H * 0.62) + dy,
                     start=25, extent=130, style="arc", fill=C_DARK, width=2)
        c.create_oval(int(W * 0.46), int(H * 0.20) + dy, int(W * 0.54), int(H * 0.28) + dy,
                      fill="#68A4DA", outline="#3E6FA0", width=1)

    def _draw_plaque(self, c):
        c.create_rectangle(24, 160, 146, 199, fill="#FFFFFF", outline="#D3D1C7", width=1)
        c.create_text(85, 172, text="今日 " + _fmt(self.data.day_income()),
                      font=(FONT, 11), fill=C_TEXT, anchor="center")
        rec = self.data.day_record(create=False)
        timed = rec.get("timed_minutes", 0.0) if rec else 0.0
        p = max(0.0, min(1.0, timed / self.data.cap()))
        c.create_rectangle(34, 181, 136, 186, fill="#F1EFE8", outline="")
        if p > 0:
            c.create_rectangle(34, 181, 34 + 102 * p, 186, fill=C_BLUE, outline="")
        c.create_text(85, 193, text="本月 " + _fmt(self.data.month_income()),
                      font=(FONT, 10), fill=C_MUTED, anchor="center")

    def show_bubble(self, text: str, seconds: float = 3.0):
        self.bubble_text = text
        self.bubble_until = time.time() + seconds
        if self.mini and not self.hidden:
            # mini 模式下画布太小，改用独立气泡小窗
            if self._tip is None:
                self._tip = _BubbleTip(self)
            x = self.root.winfo_x() + self.MINI_SIZE / 2
            y = max(0, self.root.winfo_y() - 58)
            self._tip.show(text, seconds, x, y)
        elif self._tip is not None:
            self._tip.hide()

    # ---------- 面板 ----------
    def open_panel(self):
        if self.panel is not None:
            try:
                if self.panel.winfo_exists():
                    self.panel.lift()
                    self.panel.focus_force()
                    return
            except tk.TclError:
                pass
        p = tk.Toplevel(self.root)
        self.panel = p
        p.title("小组件")
        p.attributes("-topmost", True)
        p.resizable(False, False)
        p.configure(bg=UI_BG)
        p.protocol("WM_DELETE_WINDOW", self._close_panel)

        tk.Label(p, text="赚账本", font=(FONT, 16), bg=UI_BG, fg=UI_TEXT).pack(
            anchor="w", padx=20, pady=(16, 0))
        self._lbl_month_head = tk.Label(p, text="", font=(FONT, 11), bg=UI_BG, fg=UI_MUTED)
        self._lbl_month_head.pack(anchor="w", padx=20, pady=(0, 0))
        self._lbl_month_head2 = tk.Label(p, text="", font=(FONT, 11), bg=UI_BG, fg=UI_MUTED)
        self._lbl_month_head2.pack(anchor="w", padx=20, pady=(0, 12))

        cards = tk.Frame(p, bg=UI_BG)
        cards.pack(fill="x", padx=16)
        self._lbl_today = self._card(cards, "今日收入", UI_ACCENT, 0)
        self._lbl_month = self._card(cards, "本月总收入", UI_ORANGE, 1)
        self._lbl_rate = self._card(cards, "当前时薪", "#7C6FC8", 2)
        for i in range(3):
            cards.columnconfigure(i, weight=1)

        # —— 月薪进度（口径A：按自然日进度累计，周日也照常计入）——
        prog = tk.Frame(p, bg=UI_CARD, highlightthickness=1,
                        highlightbackground=UI_BORDER, bd=0)
        prog.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(prog, text="月薪进度 · 按当月自然日累计（周日也计入）", font=(FONT, 10),
                 bg=UI_CARD, fg=UI_MUTED).pack(anchor="w", padx=12, pady=(8, 0))
        self._prog = tk.Canvas(prog, width=338, height=30, bg=UI_CARD,
                               highlightthickness=0)
        self._prog.pack(fill="x", padx=10, pady=(2, 0))
        self._lbl_prog2 = tk.Label(prog, text="", font=(FONT, 10), bg=UI_CARD, fg=UI_MUTED)
        self._lbl_prog2.pack(anchor="w", padx=12, pady=(2, 0))
        self._lbl_prog3 = tk.Label(prog, text="", font=(FONT, 10), bg=UI_CARD, fg=UI_MUTED)
        self._lbl_prog3.pack(anchor="w", padx=12, pady=(0, 8))

        # —— 工时统计（口径B：三段实际在岗，每日 8 小时）——
        work = tk.Frame(p, bg=UI_CARD, highlightthickness=1,
                        highlightbackground=UI_BORDER, bd=0)
        work.pack(fill="x", padx=16, pady=(8, 0))
        tk.Label(work, text="工时统计 · 实际在岗（每日 8 小时）", font=(FONT, 10),
                 bg=UI_CARD, fg=UI_MUTED).pack(anchor="w", padx=12, pady=(8, 0))
        self._lbl_work1 = tk.Label(work, text="", font=(FONT, 11), bg=UI_CARD, fg=UI_TEXT,
                                   anchor="w", justify="left")
        self._lbl_work1.pack(anchor="w", padx=12, pady=(2, 0))
        self._lbl_work2 = tk.Label(work, text="", font=(FONT, 10), bg=UI_CARD, fg=UI_MUTED,
                                   anchor="w", justify="left")
        self._lbl_work2.pack(anchor="w", padx=12, pady=(0, 8))

        # —— 当月日历（周日标休，薪资照常按自然日累计）——
        cal = tk.Frame(p, bg=UI_CARD, highlightthickness=1,
                       highlightbackground=UI_BORDER, bd=0)
        cal.pack(fill="x", padx=16, pady=(8, 0))
        tk.Label(cal, text="当月日历 · 周日休息（薪资照常按自然日累计）", font=(FONT, 10),
                 bg=UI_CARD, fg=UI_MUTED).pack(anchor="w", padx=12, pady=(8, 0))
        self._cal = tk.Canvas(cal, width=338, height=190, bg=UI_CARD, highlightthickness=0)
        self._cal.pack(fill="x", padx=8, pady=(0, 8))

        self._chart = tk.Canvas(p, width=338, height=112, bg=UI_BG,
                                highlightthickness=1, highlightbackground=UI_BORDER, bd=0)
        self._chart.pack(fill="x", padx=16, pady=12)

        tk.Label(p, text="本月每日明细", font=(FONT, 10), bg=UI_BG, fg=UI_MUTED).pack(
            anchor="w", padx=20, pady=(0, 4))
        frame = tk.Frame(p, bg=UI_BG, highlightthickness=1, highlightbackground=UI_BORDER, bd=0)
        self._list = tk.Listbox(frame, font=(FONT, 11), height=7, bd=0, highlightthickness=0,
                                bg=UI_BG, fg=UI_TEXT, selectbackground=UI_ACCENT,
                                selectforeground="#FFFFFF", activestyle="none")
        sb = tk.Scrollbar(frame, command=self._list.yview)
        self._list.configure(yscrollcommand=sb.set)
        self._list.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        sb.pack(side="right", fill="y")
        frame.pack(fill="both", expand=True, padx=16)

        btns = tk.Frame(p, bg=UI_BG)
        _FlatButton(btns, "记一笔", self.open_add_money, primary=True).pack(side="left")
        _FlatButton(btns, "设置", self.open_settings).pack(side="left", padx=8)
        _FlatButton(btns, "关闭", self._close_panel).pack(side="right")
        btns.pack(fill="x", padx=16, pady=12)

        self._status = tk.Label(p, text="", font=(FONT, 11), bg=UI_BG, fg=UI_MUTED)
        self._status.pack(pady=(0, 14))

        self._refresh_panel()
        p.update_idletasks()
        h = max(540, p.winfo_reqheight() + 6)  # 按内容自适应高度，避免底部按钮被裁
        x = self.root.winfo_x() + 40
        y = max(0, self.root.winfo_y() - h - 40)
        x = max(0, min(x, self.root.winfo_screenwidth() - 400))
        p.geometry("380x{}+{}+{}".format(h, x, y))

    def _card(self, parent, title: str, color: str, col: int):
        f = tk.Frame(parent, bg=UI_CARD, highlightthickness=1,
                     highlightbackground=UI_BORDER, bd=0)
        tk.Label(f, text=title, font=(FONT, 10), bg=UI_CARD, fg=UI_MUTED).pack(
            anchor="w", padx=8, pady=(10, 0))
        lb = tk.Label(f, text="", font=(FONT, 15), bg=UI_CARD, fg=color)
        lb.pack(anchor="w", padx=8, pady=(2, 10))
        pad = (0, 8) if col < 2 else (0, 0)
        f.grid(row=0, column=col, sticky="ew", padx=pad)
        return lb

    def _close_panel(self):
        if self.panel is not None:
            self.panel.destroy()
            self.panel = None

    def _refresh_panel(self):
        if self.panel is None or not self.panel.winfo_exists():
            return
        today = date.today()
        d = self.data
        # 顶部三卡（各口径独立，不重复相加）
        self._lbl_today.config(text=_fmt(d.day_income()))
        self._lbl_month.config(text=_fmt(d.month_income()))
        self._lbl_rate.config(text="¥{:.2f}/h".format(d.hourly_rate(today)))
        self._lbl_month_head.config(text="{} 年 {} 月 · 共 {} 天 · 自 {} 起计薪".format(
            today.year, today.month, d.month_days_in_month(today),
            str(d.data.get("start_date", ""))[5:]))
        self._lbl_month_head2.config(text="已过 {} 天 · 剩余 {} 天 · 在职 {} 天".format(
            d.month_days_passed(today), d.month_days_left(today),
            d.month_billed_days(today)))
        # 月薪进度（口径A）
        monthly = float(d.data.get("monthly_salary", 0) or 0)
        prog_amt = d.month_salary_progress(today)
        pct = min(1.0, prog_amt / monthly) if monthly > 0 else 0.0
        self._draw_progress(pct, prog_amt, monthly)
        self._lbl_prog2.config(text="在职 {} 天 × 日薪 {}（含周日带薪 {} 天）".format(
            d.month_billed_days(today), _fmt(d.daily_salary(today)),
            d.rest_pay_days(today)))
        self._lbl_prog3.config(text="工时折算 {} 为参考口径，不重复计入".format(
            _fmt(d.month_work_income())))
        # 工时统计（口径B：三段实际在岗 8h 折算展示）
        self._lbl_work1.config(text="今日在岗 {} / 8 小时　·　本月累计在岗 {}".format(
            _h(d.day_actual_hours()), _h(d.month_actual_hours())))
        self._lbl_work2.config(text="三段 {}（实际 8h/天）· 计时基准 {:g}h/天 · 周日带薪 {} 天".format(
            " + ".join("{:g}h".format((e - s) / 60.0) for s, e in d.schedule_segments()),
            d.cap() / 60.0, d.rest_pay_days(today)))
        self._draw_calendar()
        if not self.data.data.get("auto_schedule"):
            status = "手动计时模式"
        elif self.working:
            status = "计时中 · 自动排班 {}".format(self.data.schedule_summary())
        elif self.data.in_work_window():
            status = "排班时段内 · 已手动暂停"
        else:
            segs = self.data.schedule_segments()
            first = "{:02d}:{:02d}".format(segs[0][0] // 60, segs[0][0] % 60) if segs else "08:30"
            status = "休息中 · 次日 {} 自动开工".format(first)
        self._status.config(text="{} · 老板键 {} 隐身".format(
            status, self.data.data.get("hotkey")))
        self._draw_chart()
        self._list.delete(0, "end")
        rows = []
        for day, rec in sorted(self.data.month_days().items()):
            timed = rec.get("timed_minutes", 0.0) * self.data.per_minute()
            manual = sum(i.get("amount", 0.0) for i in rec.get("manual", []))
            line = "{}   计时 {}".format(day[5:], _fmt(timed))
            if manual:
                line += "   手动 +{}".format(_fmt(manual))
            rows.append(line)
        for r in rows or ["（本月暂无记录，右键开始计时吧）"]:
            self._list.insert("end", r)

    def _draw_progress(self, pct: float, got: float, monthly: float):
        c = self._prog
        c.delete("all")
        W, Hh = 338, 30
        x0, x1, y0, y1 = 4, W - 4, 5, 23
        r = (y1 - y0) / 2
        c.create_oval(x0, y0, x0 + 2 * r, y1, fill="#E8EEF6", outline="")
        c.create_oval(x1 - 2 * r, y0, x1, y1, fill="#E8EEF6", outline="")
        c.create_rectangle(x0 + r, y0, x1 - r, y1, fill="#E8EEF6", outline="")
        fw = max(2 * r, (x1 - x0) * pct)
        if pct > 0:
            c.create_oval(x0, y0, x0 + 2 * r, y1, fill=UI_ACCENT, outline="")
            c.create_oval(x0 + fw - 2 * r, y0, x0 + fw, y1, fill=UI_ACCENT, outline="")
            c.create_rectangle(x0 + r, y0, x0 + fw - r, y1, fill=UI_ACCENT, outline="")
        c.create_text(W / 2, (y0 + y1) / 2,
                      text="{:.1f}%　{} / {}".format(pct * 100, _fmt(got), _fmt_int(monthly)),
                      font=(FONT, 10), fill="#FFFFFF" if pct > 0.28 else UI_TEXT,
                      anchor="center")

    def _draw_calendar(self):
        c = self._cal
        c.delete("all")
        today = date.today()
        d = self.data
        ndays = d.month_days_in_month(today)
        cw, ch, gap = 46, 27, 2
        x0, y0 = 4, 2
        heads = ["日", "一", "二", "三", "四", "五", "六"]
        for i, htxt in enumerate(heads):
            color = "#D97A7A" if i == 0 else UI_MUTED
            c.create_text(x0 + i * (cw + gap) + cw / 2, y0 + 10, text=htxt,
                          font=(FONT, 10), fill=color, anchor="center")
        first_wd = datetime(today.year, today.month, 1).weekday()  # 0=周一
        start_col = (first_wd + 1) % 7                              # 周日在第 0 列
        rows = (start_col + ndays + 6) // 7
        c.config(height=max(190, y0 + 24 + rows * (ch + gap) + 6))
        for day in range(1, ndays + 1):
            col = (start_col + day - 1) % 7
            row = (start_col + day - 1) // 7
            cx = x0 + col * (cw + gap) + cw / 2
            cy2 = y0 + 24 + row * (ch + gap) + ch / 2
            is_sunday = col == 0
            is_today = day == today.day
            passed = day <= today.day
            if is_today:
                c.create_oval(cx - 12, cy2 - 11, cx + 12, cy2 + 11,
                              fill=UI_ACCENT, outline="")
                c.create_text(cx, cy2, text=str(day), font=(FONT, 11),
                              fill="#FFFFFF", anchor="center")
            else:
                color = "#C9D2DC" if not passed else ("#D97A7A" if is_sunday else UI_TEXT)
                c.create_text(cx, cy2, text=str(day), font=(FONT, 11),
                              fill=color, anchor="center")
            if is_sunday and not is_today:
                c.create_text(cx, cy2 + 10, text="休", font=(FONT, 8),
                              fill="#D97A7A", anchor="center")

    def _draw_chart(self):
        c = self._chart
        c.delete("all")
        W, H, pad = 338, 112, 12
        days = self.data.month_days()
        maxv = max([self.data.day_income(d) for d in days] + [1.0])
        bar_w = (W - pad * 2) / 31.0
        today = self.data.today_str()
        base = H - 22
        # 横向浅网格
        for gy in (base - 22, base - 44, base - 66):
            c.create_line(pad, gy, W - pad, gy, fill="#EEF1F5", width=1)
        # Y 轴峰值标注
        c.create_text(pad + 2, 22, text=_fmt_int(maxv), font=(FONT, 9),
                      fill=UI_MUTED, anchor="nw")
        for n in range(1, 32):
            key = "{}-{:02d}".format(self.data.month_str(), n)
            v = self.data.day_income(key)
            if v <= 0:
                continue
            h = max(3.0, (v / maxv) * (base - 22))
            x0 = pad + (n - 1) * bar_w + 1
            bw = max(3.0, bar_w - 3)
            is_today = key == today
            color = UI_ORANGE if is_today else "#7FB0F0"
            c.create_rectangle(x0, base - h, x0 + bw, base, fill=color,
                               outline="#D98A1F" if is_today else "", width=1 if is_today else 0)
            if is_today:  # 今天的柱子加圆头 + "今日"标签
                c.create_oval(x0, base - h - 3, x0 + bw, base - h + 1, fill=UI_ORANGE, outline="")
                yy = max(16, base - h - 11)  # 高柱时贴顶显示，避免被上边缘裁掉
                c.create_text(x0 + bw / 2, yy, text="今日", font=(FONT, 9),
                              fill=UI_ORANGE, anchor="s")
        c.create_line(pad, base, W - pad, base, fill="#D7DCE3", width=1)
        for d in (1, 10, 20, 31):
            x = pad + (d - 1) * bar_w + bar_w / 2
            c.create_text(x, base + 9, text=str(d), font=(FONT, 11), fill=UI_MUTED, anchor="center")

    # ---------- 对话框 ----------
    def open_add_money(self):
        dlg = _AddMoneyDialog(self)
        if dlg.result:
            amount, note = dlg.result
            self.data.add_manual(amount, note)
            self.show_bubble("记一笔 {}\n今日 {}".format(_fmt(amount), _fmt(self.data.day_income())), 3.0)
            self._refresh_panel()

    def open_settings(self):
        old_size = self.data.data.get("pet_size", "m")
        dlg = _SettingsDialog(self)
        if dlg.saved:
            self._hotkey_combo = HOTKEYS.get(self.data.data.get("hotkey"), HOTKEYS["Ctrl+Q"])
            self._resize()
            self._refresh_panel()
            if self.data.data.get("pet_size", "m") != old_size:
                self.show_bubble("大小已保存\n重启桌宠后生效", 3.0)
            else:
                self.show_bubble("每分钟 {}\n设置已保存".format(_fmt(self.data.per_minute())), 2.5)

    # ---------- 退出 ----------
    def quit(self):
        if self.working:
            self._pause_work()
        self._stop.set()
        if self._tip is not None:
            self._tip.destroy()
        self.data.data["window_pos"] = [self.root.winfo_x(), self.root.winfo_y()]
        self.data.save()
        self.root.destroy()


class _BubbleTip(tk.Toplevel):
    """独立气泡小窗：mini 形态太小，用它在小点上方显示提示。"""

    def __init__(self, app: "DesktopPetApp"):
        super().__init__(app.root)
        self.app = app
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#FFFFFF")
        self.withdraw()
        self.label = tk.Label(self, text="", font=(FONT, 11), bg="#FFFFFF",
                              fg=C_TEXT, justify="center", padx=12, pady=7)
        self.label.pack()
        self._timer = None

    def show(self, text: str, seconds: float, x: int, y: int):
        self.label.config(text=text)
        self.update_idletasks()
        w = max(60, self.winfo_reqwidth())
        sw = self.winfo_screenwidth()
        x = max(4, min(int(x - w / 2), int(sw - w - 4)))
        self.geometry("+{}+{}".format(x, int(y)))
        self.deiconify()
        self.lift()
        if self._timer:
            self.after_cancel(self._timer)
        self._timer = self.after(int(seconds * 1000), self.hide)

    def hide(self):
        try:
            self.withdraw()
        except tk.TclError:
            pass


class _FlatButton(tk.Label):
    """扁平按钮（用 Label 模拟，绕开 Windows 原生按钮不改色的限制）。"""

    def __init__(self, parent, text, command, primary=False, **kw):
        self._bg = UI_ACCENT if primary else UI_CARD
        self._bg_hover = UI_ACCENT_D if primary else "#E8ECF2"
        self._bg_press = "#2E5FB0" if primary else "#DCE2EA"
        fg = "#FFFFFF" if primary else UI_TEXT
        super().__init__(parent, text=text, font=(FONT, 11), bg=self._bg, fg=fg,
                         padx=14, pady=6, cursor="hand2", **kw)
        self._cmd = command
        self.bind("<Button-1>", lambda e: (self.config(bg=self._bg_press), command()))
        self.bind("<Enter>", lambda e: self.config(bg=self._bg_hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))


def _mk_entry(parent, width):
    """美化版输入框：扁平 + 细边框 + 聚焦高亮。"""
    return tk.Entry(parent, width=width, font=(FONT, 11), relief="flat",
                    highlightthickness=1, highlightbackground=UI_BORDER,
                    highlightcolor=UI_ACCENT, bg="#FFFFFF", fg=UI_TEXT,
                    insertbackground=UI_TEXT)


class _AddMoneyDialog(tk.Toplevel):
    def __init__(self, app: "DesktopPetApp"):
        super().__init__(app.root)
        self.app = app
        self.result = None
        self.title("记一笔")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.configure(bg=UI_BG)
        self.transient(app.root)

        f = tk.Frame(self, bg=UI_BG, padx=20, pady=16)
        f.pack(fill="both", expand=True)
        tk.Label(f, text="金额（元）", font=(FONT, 11), bg=UI_BG, fg=UI_MUTED).grid(
            row=0, column=0, columnspan=2, sticky="w")
        self._amount = _mk_entry(f, 22)
        self._amount.grid(row=1, column=0, columnspan=2, pady=(4, 12), ipady=4)
        tk.Label(f, text="备注（可选）", font=(FONT, 11), bg=UI_BG, fg=UI_MUTED).grid(
            row=2, column=0, columnspan=2, sticky="w")
        self._note = _mk_entry(f, 22)
        self._note.grid(row=3, column=0, columnspan=2, pady=(4, 16), ipady=4)
        btns = tk.Frame(f, bg=UI_BG)
        btns.grid(row=4, column=0, columnspan=2, sticky="e")
        _FlatButton(btns, "取消", self.destroy).pack(side="left", padx=(0, 8))
        _FlatButton(btns, "确定", self._ok, primary=True).pack(side="left")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self._amount.focus_force()
        self.grab_set()
        self.wait_window(self)

    def _ok(self):
        raw = self._amount.get().strip()
        try:
            v = float(raw)
        except ValueError:
            messagebox.showwarning("赚账宠", "请输入正确的金额数字", parent=self)
            return
        if v <= 0:
            messagebox.showwarning("赚账宠", "金额要大于 0", parent=self)
            return
        self.result = (round(v, 2), self._note.get().strip())
        self.destroy()


class _SettingsDialog(tk.Toplevel):
    REST_OPTIONS = [
        ("仅周日休息", [6]),
        ("周六、周日都休息", [5, 6]),
        ("不休息（全周上班）", []),
    ]
    BASIS_OPTIONS = [
        ("按当月总天数平均(周日带薪)", "calendar"),
        ("按当月工作日(周日不计钱)", "workdays"),
    ]

    def __init__(self, app: "DesktopPetApp"):
        super().__init__(app.root)
        self.app = app
        self.saved = False
        self.title("设置")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.configure(bg=UI_BG)
        self.transient(app.root)

        d = app.data.data
        f = tk.Frame(self, bg=UI_BG, padx=20, pady=16)
        f.pack(fill="both", expand=True)

        # —— 计费 ——
        tk.Label(f, text="月薪（元）　日薪按下一项口径分摊到每小时", font=(FONT, 11),
                 bg=UI_BG, fg=UI_MUTED).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self._salary = _mk_entry(f, 12)
        self._salary.insert(0, str(d.get("monthly_salary", 7000)))
        self._salary.grid(row=0, column=1, sticky="e", pady=(0, 4), ipady=3)

        tk.Label(f, text="入职/计薪起始日（YYYY-MM-DD）", font=(FONT, 11),
                 bg=UI_BG, fg=UI_MUTED).grid(row=1, column=0, sticky="w", pady=4)
        self._start = _mk_entry(f, 12)
        self._start.insert(0, str(d.get("start_date", "2026-10-15")))
        self._start.grid(row=1, column=1, sticky="e", pady=4, ipady=3)

        tk.Label(f, text="日薪按哪种天数算", font=(FONT, 11), bg=UI_BG, fg=UI_MUTED).grid(
            row=2, column=0, sticky="w", pady=4)
        cur_basis = d.get("salary_basis", "calendar")
        basis_idx = 0
        for i, (label, val) in enumerate(self.BASIS_OPTIONS):
            if val == cur_basis:
                basis_idx = i
                break
        self._basis = ttk.Combobox(f, width=18, state="readonly",
                                   values=[lbl for lbl, _ in self.BASIS_OPTIONS], font=(FONT, 11))
        self._basis.current(basis_idx)
        self._basis.grid(row=2, column=1, sticky="e", pady=4, ipady=3)

        tk.Label(f, text="休息日", font=(FONT, 11), bg=UI_BG, fg=UI_MUTED).grid(
            row=2, column=0, sticky="w", pady=4)
        cur_rest = d.get("rest_weekdays", [6])
        rest_idx = 0
        for i, (label, val) in enumerate(self.REST_OPTIONS):
            if val == cur_rest or (not val and not cur_rest):
                rest_idx = i
                break
        self._rest = ttk.Combobox(f, width=14, state="readonly",
                                  values=[lbl for lbl, _ in self.REST_OPTIONS], font=(FONT, 11))
        self._rest.current(rest_idx)
        self._rest.grid(row=2, column=1, sticky="e", pady=4, ipady=3)

        # —— 计时时段（HH:MM）——
        tk.Label(f, text="计时时段（HH:MM，每天按各段总时长算钱）", font=(FONT, 11),
                 bg=UI_BG, fg=UI_MUTED).grid(row=4, column=0, columnspan=2,
                                            sticky="w", pady=(10, 4))
        self._seg_s, self._seg_e = [], []
        segs = d.get("work_segments", [["08:30", "19:30"]])
        for i in range(3):
            seg = segs[i] if i < len(segs) else ["", ""]
            tk.Label(f, text="时段 {}".format(i + 1), font=(FONT, 11), bg=UI_BG, fg=UI_TEXT).grid(
                row=5 + i, column=0, sticky="w", pady=2)
            s = _mk_entry(f, 7)
            s.insert(0, str(seg[0]))
            s.grid(row=5 + i, column=1, sticky="e", pady=2, ipady=3)
            tk.Label(f, text="—", font=(FONT, 11), bg=UI_BG, fg=UI_MUTED).grid(
                row=5 + i, column=1, sticky="e", padx=(0, 64))
            e = _mk_entry(f, 7)
            e.insert(0, str(seg[1]))
            e.grid(row=5 + i, column=1, sticky="e", pady=2, ipady=3)
            self._seg_s.append(s)
            self._seg_e.append(e)

        # —— 当前费率预览（统一口径：日薪/时薪/满勤，全部走 PetData 方法）——
        today = date.today()
        dd = self.app.data
        div = dd._daily_divisor(today)
        daily = dd.daily_salary(today)
        hourly = dd.hourly_rate(today)
        proj = dd.projected_month_total(today)
        if cur_basis == "workdays":
            div_text = "月薪÷{}个工作日".format(div)
            full_text = "满勤约 ¥{:.0f}".format(proj)
        else:
            div_text = "月薪÷{}天".format(div)
            full_text = "满勤约 ¥{:.0f}(含周日带薪)".format(proj)
        tk.Label(f, text="当前：日薪 ¥{:.2f}（{}）· 时薪 ¥{:.2f}/小时 · {}".format(
            daily, div_text, hourly, full_text), font=(FONT, 10),
            bg=UI_BG, fg=UI_ACCENT).grid(row=8, column=0, columnspan=2, sticky="w", pady=(4, 8))

        # —— 显示 / 行为 ——
        self._v_mini = tk.BooleanVar(value=bool(d.get("mini_mode", True)))
        self._v_amt = tk.BooleanVar(value=bool(d.get("show_mini_amount", True)))
        self._v_plaque = tk.BooleanVar(value=bool(d.get("show_plaque", False)))
        self._v_anim = tk.BooleanVar(value=bool(d.get("animate", False)))
        self._v_auto = tk.BooleanVar(value=bool(d.get("auto_schedule", True)))
        self._v_hide = tk.BooleanVar(value=bool(d.get("auto_hide", False)))
        cb_row = 9
        for i, (text, var) in enumerate([
            ("默认迷你小点模式", self._v_mini),
            ("小点内显示当日收入", self._v_amt),
            ("显示胸前收入牌", self._v_plaque),
            ("动画效果（呼吸/摆尾）", self._v_anim),
            ("自动排班（到点自动开工/收工）", self._v_auto),
            ("闲置 5 分钟自动收起小点", self._v_hide),
        ]):
            tk.Checkbutton(f, text=text, font=(FONT, 11), bg=UI_BG, fg=UI_TEXT,
                           activebackground=UI_BG, activeforeground=UI_TEXT,
                           selectcolor="#FFFFFF", variable=var).grid(
                row=cb_row + i, column=0, columnspan=2, sticky="w", pady=2)

        tk.Label(f, text="桌宠大小", font=(FONT, 11), bg=UI_BG, fg=UI_MUTED).grid(
            row=cb_row + 6, column=0, sticky="w", pady=(8, 4))
        SIZE_OPTIONS = [("小", "s"), ("中（默认）", "m"), ("大", "l")]
        self._size = ttk.Combobox(f, width=11, state="readonly",
                                  values=[lbl for lbl, _ in SIZE_OPTIONS], font=(FONT, 11))
        cur_size = d.get("pet_size", "m")
        self._size.current([v for _, v in SIZE_OPTIONS].index(cur_size)
                           if cur_size in [v for _, v in SIZE_OPTIONS] else 1)
        self._size.grid(row=cb_row + 6, column=1, sticky="e", pady=(8, 4), ipady=3)

        tk.Label(f, text="老板键（隐藏 / 唤回）", font=(FONT, 11), bg=UI_BG, fg=UI_MUTED).grid(
            row=cb_row + 7, column=0, sticky="w", pady=(8, 4))
        self._hotkey = ttk.Combobox(f, width=11, state="readonly",
                                    values=list(HOTKEYS.keys()), font=(FONT, 11))
        self._hotkey.set(d.get("hotkey", "Ctrl+Q"))
        self._hotkey.grid(row=cb_row + 7, column=1, sticky="e", pady=(8, 4), ipady=3)

        btns = tk.Frame(f, bg=UI_BG)
        btns.grid(row=cb_row + 8, column=0, columnspan=2, sticky="e", pady=(16, 0))
        _FlatButton(btns, "取消", self.destroy).pack(side="left", padx=(0, 8))
        _FlatButton(btns, "保存", self._save, primary=True).pack(side="left")

        tk.Label(self, text="数据保存在同目录 widget.cfg", font=(FONT, 11),
                 bg=UI_BG, fg=UI_MUTED).pack(pady=(0, 12))
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.wait_window(self)

    @staticmethod
    def _parse_hm(s):
        parts = s.strip().split(":")
        if len(parts) != 2:
            raise ValueError
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError
        return h * 60 + m

    def _save(self):
        try:
            salary = float(self._salary.get().strip())
        except ValueError:
            messagebox.showwarning("赚账宠", "月薪必须是数字", parent=self)
            return
        if salary <= 0:
            messagebox.showwarning("赚账宠", "月薪必须大于 0", parent=self)
            return

        start_v = self._start.get().strip()
        if PetData._parse_date(start_v) is None:
            messagebox.showwarning("赚账宠", "入职日期格式应为 YYYY-MM-DD\n例如 2026-10-15", parent=self)
            return

        rest = self.REST_OPTIONS[self._rest.current()][1]

        segs = []
        for s_e, e_e in zip(self._seg_s, self._seg_e):
            sv, ev = s_e.get().strip(), e_e.get().strip()
            if not sv and not ev:
                continue
            if not sv or not ev:
                messagebox.showwarning("赚账宠", "时段需要同时填写开始和结束时间", parent=self)
                return
            try:
                s, e = self._parse_hm(sv), self._parse_hm(ev)
            except ValueError:
                messagebox.showwarning("赚账宠", "时间格式应为 HH:MM，例如 08:30", parent=self)
                return
            if s >= e:
                messagebox.showwarning("赚账宠", "每个时段的结束时间要晚于开始时间", parent=self)
                return
            segs.append(["{:02d}:{:02d}".format(s // 60, s % 60),
                         "{:02d}:{:02d}".format(e // 60, e % 60)])
        if not segs:
            messagebox.showwarning("赚账宠", "请至少填写一个工作时段", parent=self)
            return

        d = self.app.data.data
        d["monthly_salary"] = round(salary, 2)
        d["start_date"] = start_v
        d["salary_basis"] = self.BASIS_OPTIONS[self._basis.current()][1]
        d["rest_weekdays"] = rest
        d["work_segments"] = segs
        d["work_minutes_per_day"] = int(sum(
            self._parse_hm(e) - self._parse_hm(s) for s, e in segs))
        d["mini_mode"] = self._v_mini.get()
        d["show_mini_amount"] = self._v_amt.get()
        d["show_plaque"] = self._v_plaque.get()
        d["animate"] = self._v_anim.get()
        d["auto_schedule"] = self._v_auto.get()
        d["auto_hide"] = self._v_hide.get()
        d["pet_size"] = SIZE_OPTIONS[self._size.current()][1]
        d["hotkey"] = self._hotkey.get()
        self.app.data.save()
        self.saved = True
        self.destroy()


def main():
    app = DesktopPetApp()
    if app._lock_socket is None:
        return
    app.root.mainloop()


if __name__ == "__main__":
    main()
