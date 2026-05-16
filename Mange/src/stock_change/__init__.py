"""
股票涨跌幅计算模块

主要功能：
- 计算关注股票每天的涨跌幅（当前价格与添加当天价格的比值）
- 提供涨跌幅数据查询接口
- 支持定时任务自动计算

模块说明：
- calculator.py: 涨跌幅计算核心逻辑
- scheduler.py: 定时任务调度（每天自动计算）


"""

from stock_change.calculator import calculate_all_changes, get_change_data, create_change_table
from stock_change.scheduler import start_scheduler
