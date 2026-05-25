"""
涨跌幅定时任务调度模块

主要功能：
- 交易时段每 5 分钟执行一次涨跌幅计算
- 每天 15:05 追加执行一次收盘后补算
- 周末和非交易时间不执行计算
- 使用独立线程运行，不阻塞主程序

调度策略：
- 上午交易时段：09:30 - 11:30
- 下午交易时段：13:00 - 15:00
- 交易时段命中 5 分钟整点时执行一次
- 15:05 再执行一次收盘后补算
- 通过运行标记避免同一分钟重复执行
"""

import threading
import time
from datetime import datetime, time as dt_time
from stock_change.calculator import calculate_all_changes


MORNING_START = dt_time(9, 30)
MORNING_END = dt_time(11, 30)
AFTERNOON_START = dt_time(13, 0)
AFTERNOON_END = dt_time(15, 0)
CLOSE_RUN_TIME = dt_time(15, 5)
CHECK_INTERVAL_SECONDS = 30


def is_trading_day(now):
    """仅工作日执行，周六周日跳过"""
    return now.weekday() < 5


def in_trading_session(current_time):
    """判断是否处于 A 股交易时段"""
    in_morning = MORNING_START <= current_time <= MORNING_END
    in_afternoon = AFTERNOON_START <= current_time <= AFTERNOON_END
    return in_morning or in_afternoon


def should_run_intraday(now):
    """交易时段内每 5 分钟执行一次"""
    return (
        in_trading_session(now.time())
        and now.minute % 5 == 0
    )


def should_run_close_job(now):
    """15:05 执行一次收盘后补算"""
    return now.time().hour == CLOSE_RUN_TIME.hour and now.time().minute == CLOSE_RUN_TIME.minute


def run_scheduler():
    """
    自动计算涨跌幅

    执行策略：
        1. 仅在工作日运行
        2. 交易时段每 5 分钟执行一次
        3. 15:05 再执行一次收盘后补算
        4. 周末和非交易时间只做低频检查，不执行计算

    运行方式：独立后台线程（daemon=True）
    """
    print("[INFO] 涨跌幅自动调度已启动")
    print("[INFO] 交易时段每 5 分钟自动计算，15:05 执行一次收盘后补算")

    last_run_key = None

    while True:
        now = datetime.now()
        run_type = None

        if is_trading_day(now):
            if should_run_intraday(now):
                run_type = "intraday"
            elif should_run_close_job(now):
                run_type = "close"

        if run_type is not None:
            run_key = f"{now.strftime('%Y-%m-%d %H:%M')}-{run_type}"
            if run_key != last_run_key:
                print(f"\n{'=' * 50}")
                print(f"[INFO] 开始执行涨跌幅自动计算 ({run_type}): {now.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'=' * 50}")
                try:
                    calculate_all_changes()
                    last_run_key = run_key
                except Exception as e:
                    print(f"[ERROR] 定时计算失败: {e}")

        time.sleep(CHECK_INTERVAL_SECONDS)


def start_scheduler():
    """
    启动定时任务线程
    
    Returns:
        threading.Thread: 定时任务线程对象
    
    说明：
        - 线程设置为daemon=True，主程序退出时自动终止
        - 线程启动后立即返回，不阻塞主程序
    """
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("[OK] 涨跌幅定时任务线程已启动")
    return scheduler_thread
