"""
涨跌幅定时任务调度模块

主要功能：
- 每天定时执行涨跌幅计算任务
- 默认执行时间：每天下午16:05（A股收盘后）
- 使用独立线程运行，不阻塞主程序

调度策略：
- 计算目标时间：当天16:05，如果已过则设为次日16:05
- 等待到目标时间后执行计算
- 计算完成后等待60秒，避免重复执行


"""

import threading
import time
from datetime import datetime
from stock_change.calculator import calculate_all_changes


def run_daily_scheduler():
    """
    每天定时计算涨跌幅
    
    执行时间：每天下午16:05（A股收盘后）
    运行方式：独立后台线程（daemon=True）
    
    流程：
        1. 计算下次执行时间（当天或次日16:05）
        2. 等待到目标时间
        3. 执行涨跌幅计算
        4. 等待60秒后循环
    """
    print("[INFO] 涨跌幅定时任务已启动")
    
    while True:
        now = datetime.now()
        target_time = now.replace(hour=16, minute=5, second=0, microsecond=0)
        
        if now >= target_time:
            target_time = target_time.replace(day=target_time.day + 1)
        
        wait_seconds = (target_time - now).total_seconds()
        print(f"[INFO] 下次计算时间: {target_time.strftime('%Y-%m-%d %H:%M:%S')}, 等待 {wait_seconds:.0f} 秒")
        
        time.sleep(wait_seconds)
        
        print(f"\n{'=' * 50}")
        print(f"[INFO] 开始执行每日涨跌幅计算: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 50}")
        
        try:
            calculate_all_changes()
        except Exception as e:
            print(f"[ERROR] 定时计算失败: {e}")
        
        time.sleep(60)


def start_scheduler():
    """
    启动定时任务线程
    
    Returns:
        threading.Thread: 定时任务线程对象
    
    说明：
        - 线程设置为daemon=True，主程序退出时自动终止
        - 线程启动后立即返回，不阻塞主程序
    """
    scheduler_thread = threading.Thread(target=run_daily_scheduler, daemon=True)
    scheduler_thread.start()
    print("[OK] 涨跌幅定时任务线程已启动")
    return scheduler_thread
