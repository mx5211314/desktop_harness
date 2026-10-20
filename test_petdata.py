# -*- coding: utf-8 -*-
"""PetData 数据层单元测试（不启动 GUI）。

薪资规则（用户指定，勿改）：
  - 月薪固定税前 7000；周日不上班但计入薪资分摊（按当月自然日平均）
  - 时薪 = 7000 ÷ 当月自然日天数 ÷ 11（30 天≈21.21，31 天≈20.53）
  - 薪资基准 11h/天；实际在岗三段合计 8h，仅用于展示（8/11 折算）
  - 双口径：月薪进度累计（周日照常）与工时折算严格分开，不重复相加

运行：python test_petdata.py
"""
import json
import os
import sys
import tempfile
import calendar
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from desktop_pet import HOTKEYS, PetData  # noqa: E402


def ts(y=2026, m=10, d=17, h=0, mi=0, s=0):
    return datetime(y, m, d, h, mi, s).timestamp()


def main():
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "widget.cfg")

    # ---- 快捷键结构 ----
    assert HOTKEYS["Ctrl+Q"] == ([0x11], 0x51), "Ctrl+Q 应为 Ctrl + Q"

    # ---- 默认配置 ----
    d = PetData(path)
    assert d.first_run
    assert d.data["auto_schedule"] is True, "8:30 自动开始算钱"
    assert d.data["monthly_salary"] == 7000.0, "月薪固定税前 7000"
    assert d.data["salary_basis"] == "calendar", "按当月自然日平均分摊"
    assert d.data["work_segments"] == [["08:30", "19:30"]], "计时窗口 8:30-19:30"
    assert d.data["rest_weekdays"] == [6], "周日休息"

    # ---- ★ 每日计时窗口 = 11 小时（薪资基准）----
    assert d.schedule_minutes() == 660.0
    assert d.cap() == 660.0
    assert d.schedule_segments() == [(510, 1170)]
    assert sum(e - s for s, e in d.schedule_segments()) == 660

    # ---- ★ 时薪公式：7000 ÷ 当月自然日 ÷ 11 ----
    assert abs(d.daily_salary(date(2026, 10, 15)) - 7000.0 / 31) < 1e-9
    assert abs(d.hourly_rate(date(2026, 10, 15)) - 7000.0 / 31 / 11) < 1e-9, \
        "31 天月份时薪 ≈ 20.53"
    assert abs(d.hourly_rate(date(2026, 10, 15)) - 20.5288) < 0.001
    assert abs(d.hourly_rate(date(2025, 11, 15)) - 7000.0 / 30 / 11) < 1e-9, \
        "30 天月份时薪 ≈ 21.21"
    assert abs(d.hourly_rate(date(2025, 11, 15)) - 21.2121) < 0.001
    # 闰年 2 月 29 天 / 平年 2 月 28 天 自动识别
    assert abs(d.daily_salary(date(2028, 2, 15)) - 7000.0 / 29) < 1e-9, "闰年 2028-02=29 天"
    assert abs(d.daily_salary(date(2027, 2, 15)) - 7000.0 / 28) < 1e-9, "平年 2027-02=28 天"
    # 运行日动态校验（口径自洽）
    today = date.today()
    ndays = d.month_days_in_month(today)
    assert d.month_days_passed(today) == today.day
    assert d.month_days_left(today) == ndays - today.day
    assert abs(d.hourly_rate(today) * 11.0 - d.daily_salary(today)) < 1e-9

    # ---- 实际在岗工时（三段 8h，8/11 折算，仅展示）----
    assert abs(d.actual_hours(660.0) - 8.0) < 1e-9, "满勤 11h 基准 → 实际在岗 8h"
    assert abs(d.actual_hours(330.0) - 4.0) < 1e-9, "半程 5.5h → 在岗 4h"
    assert abs(d.actual_hours(0.0)) == 0.0

    # ---- ★ 双口径严格分开，不重复相加（月中入职从 start_date 起算）----
    d20 = date(2026, 10, 20)
    prog = d.month_salary_progress(d20)
    # start_date 默认 2026-10-15：在职自然日 15..20 = 6 天
    assert d.month_billed_days(d20) == 6, "在职计薪 6 天（10-15 起算）"
    assert abs(prog - 7000.0 / 31 * 6) < 1e-9, "口径A：自然日进度从入职日起算"
    # 满勤预估（月中入职拿不满月薪，整月起恢复）
    assert abs(d.projected_month_total(d20) - 7000.0 / 31 * 17) < 0.01, \
        "10-15~31 共 17 个自然日"
    # 11 月整月不受 start_date 影响（start 在上月 → 从 1 号起算）
    assert d.month_billed_days(date(2026, 11, 5)) == 5
    assert abs(d.month_salary_progress(date(2026, 11, 5)) - 7000.0 / 30 * 5) < 1e-9
    # 周日带薪从入职日起算：10 月已过周日中 ≥15 号的只有 10/18
    assert d.rest_pay_days(d20) == 1, "10/18 一个带薪周日（4、11 在入职前）"
    d2 = PetData(path)
    d2.add_manual(50, "外快")
    d2.set_timed_minutes(120)
    assert abs(d2.month_work_income() - 120 * d2.per_minute()) < 1e-9
    assert abs(d2.month_income() - (d2.month_salary_progress() + 50.0)) < 0.01, \
        "月收入 = 月薪进度 + 手动外快（不含工时折算，避免重复）"
    assert abs(d2.day_income() - (50 + 120 * d2.per_minute())) < 0.01, "今日收入=工时口径"

    # ---- 计时窗口（8:30-19:30 全程，午休晚饭照算钱）----
    d.data["rest_weekdays"] = []
    assert d.in_work_window(ts(h=8, mi=30)) is True, "8:30 整点自动开工"
    assert d.in_work_window(ts(h=8, mi=29, s=59)) is False
    assert d.in_work_window(ts(h=12, mi=0)) is True, "午休在公司照算钱"
    assert d.in_work_window(ts(h=16, mi=45)) is True, "晚饭时间照算钱"
    assert d.in_work_window(ts(h=19, mi=29, s=59)) is True
    assert d.in_work_window(ts(h=19, mi=30)) is False, "19:30 收工"
    assert d.in_work_window(ts(h=23, mi=0)) is False

    # ---- 周日：不计时 ----
    d.data["rest_weekdays"] = [6]
    assert date(2026, 10, 4).weekday() == 6
    assert d.in_work_window(ts(y=2026, m=10, d=4, h=10)) is False, "周日不计时"
    assert d.in_work_window(ts(y=2026, m=10, d=5, h=10)) is True

    # ---- 手动模式 ----
    d.data["auto_schedule"] = False
    assert d.cap() == 660.0
    assert d.in_work_window(ts(h=3, mi=0)) is True
    d.data["auto_schedule"] = True

    # ---- 口径切换：按工作日（周日不计钱；月中入职在职工作日=15）----
    d.data["salary_basis"] = "workdays"
    wd = PetData._workday_count(2026, 10, [6])
    assert wd == 27
    assert abs(d.projected_month_total(d20) - 7000.0 / 27 * 15) < 0.01, \
        "10-15~31 工作日 15 天"
    assert d.rest_pay_days(d20) == 0
    d.data["salary_basis"] = "calendar"
    assert abs(d.projected_month_total(d20) - 7000.0 / 31 * 17) < 0.01, "在职自然日 17 天"

    # ---- 多段自定义（回归：各段求和）----
    d.data["work_segments"] = [["08:30", "11:00"], ["13:00", "16:30"], ["17:30", "19:30"]]
    assert d.schedule_minutes() == 480.0, "三段 2.5h+3.5h+2h = 8 小时"
    d.data["work_segments"] = [["08:30", "19:30"]]

    # ---- 封顶 / 本月统计 / 持久化 ----
    d2.set_timed_minutes(9999)
    assert d2.day_record()["timed_minutes"] == 660.0, "工时封顶 = 11h 基准"
    assert abs(d2.day_actual_hours() - 8.0) < 1e-9, "今日在岗封顶 8h"
    d2.save()
    d3 = PetData(path)
    assert not d3.first_run
    assert abs(d3.month_income() - d2.month_income()) < 0.01, "重启不丢数据"
    assert d3.month_worked_days() == 1
    assert abs(d3.month_total_minutes() - 660.0) < 1e-6
    assert abs(d3.month_actual_hours() - 8.0) < 1e-9

    # ---- 月份切换：day_record 按月分桶 ----
    d3.day_record("2026-09-30").setdefault("manual", []).append(
        {"ts": 0, "amount": 9.9, "note": "上月"})
    assert "2026-09" in d3.data["records"]
    assert d3.month_days().get("2026-09-30") is None, "上月记录不进本月统计"
    d3.save()

    # ---- 旧配置 v2 强制迁移（一次性，标记防重跑）----
    old = {
        "daily_salary": 200.0,
        "auto_start": True,
        "hotkey": "Ctrl+Alt+H",
        "salary_basis": "workdays",
        "work_minutes_per_day": 480,
        "work_segments": [["08:30", "11:00"], ["13:00", "16:30"], ["17:30", "19:30"]],
        "records": {"2026-09": {"2026-09-01": {"timed_minutes": 60, "manual": []}}},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(old, f)
    d4 = PetData(path)
    assert d4.data["model_v2_11h"] is True
    assert d4.data["salary_basis"] == "calendar"
    assert d4.data["work_segments"] == [["08:30", "19:30"]]
    assert d4.data["work_minutes_per_day"] == 660
    assert d4.data["monthly_salary"] == 6000, "旧日薪200×30 反推月薪"
    assert d4.data["hotkey"] == "Ctrl+Alt+H"
    assert d4.cap() == 660.0
    d4.data["salary_basis"] = "workdays"
    d4.save()
    d4b = PetData(path)
    assert d4b.data["salary_basis"] == "workdays", "v2 后用户修改不被覆盖"

    # ---- 坏配置不崩溃（回退默认口径）----
    with open(path, "w", encoding="utf-8") as f:
        f.write("{ not valid json")
    d5 = PetData(path)
    assert isinstance(d5.month_income(), float)

    # ---- 鲸鱼贴图完整性（动画帧齐全）----
    need = ["idle0", "idle1", "blink", "happy", "sleepy", "off",
            "tail0", "tail1", "tail2", "spout0", "spout1", "spout2", "spout3"]
    missing = [n for n in need
               if not os.path.exists(os.path.join(os.path.dirname(
                   os.path.abspath(__file__)), "whale_{}.png".format(n)))]
    assert not missing, "缺鲸鱼帧: {}".format(missing)

    print("all tests passed")


if __name__ == "__main__":
    main()
