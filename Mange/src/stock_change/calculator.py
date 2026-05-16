"""
股票涨跌幅计算核心模块

主要功能：
- 计算关注股票的涨跌幅（当前价格 vs 添加当天价格）
- 存储涨跌幅数据到数据库
- 提供涨跌幅数据查询接口

计算逻辑：
1. 获取股票关注记录（包含添加日期）
2. 查询添加当天的收盘价
3. 获取当前最新价格
4. 计算涨跌幅 = (当前价 - 添加日收盘价) / 添加日收盘价 * 100%

数据源：
- 腾讯财经API: 获取实时价格
- 东方财富API: 获取历史收盘价
- 新浪财经API: 备用数据源

数据库表：
- stock_changes: 涨跌幅数据表
  - stock_code: 股票代码
  - stock_name: 股票名称
  - follow_date: 关注日期
  - follow_price: 关注时价格
  - current_price: 当前价格
  - change_rate: 涨跌幅百分比
  - update_time: 更新时间


"""

import os
import sys
import time
import requests
import pymysql
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, func
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from sqlalchemy.pool import QueuePool
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from db.database import get_stock_db_uri, get_chanlun_pro_path, get_db_connection
from services.stock_api import get_stock_data, get_stock_data_batch
from services.stock_name import get_stock_name_by_code


def _build_session():
    s = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=['GET']
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=5, pool_maxsize=10)
    s.mount('http://', adapter)
    s.mount('https://', adapter)
    return s


def _safe_request(method, url, **kwargs):
    kwargs.setdefault('timeout', 8)
    try:
        session = _build_session()
        resp = session.request(method, url, **kwargs)
        return resp
    except Exception:
        return None

# ==================== 数据库配置 ====================
stock_db_uri = get_stock_db_uri()
stock_engine = create_engine(stock_db_uri, poolclass=QueuePool, pool_recycle=3600, pool_pre_ping=True, pool_size=10, max_overflow=20, pool_timeout=10)
StockSession = sessionmaker(bind=stock_engine)
stock_db = scoped_session(StockSession)

# ==================== 涨跌幅数据模型 ====================
Base = declarative_base()

class StockChange(Base):
    """
    股票涨跌幅数据模型
    
    表名: stock_changes
    用途: 存储每只关注股票的涨跌幅数据
    """
    __tablename__ = 'stock_changes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)
    stock_name = Column(String(100), nullable=False)
    follow_date = Column(String(20), nullable=False)
    follow_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    change_rate = Column(Float, nullable=False)
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

# chanlunpro项目路径
chanlun_path = get_chanlun_pro_path()
if os.path.exists(chanlun_path) and chanlun_path not in sys.path:
    sys.path.insert(0, chanlun_path)

try:
    from chanlun.db import DB
    from chanlun import config
    CHANLUN_AVAILABLE = True
except ImportError:
    CHANLUN_AVAILABLE = False


# ==================== 数据库表操作 ====================
def create_change_table():
    """
    创建涨跌幅数据表
    
    表结构:
    - stock_code: 股票代码
    - stock_name: 股票名称
    - follow_price: 关注当天收盘价
    - follow_date: 关注日期
    - latest_price: 最新价格
    - latest_date: 最新价格日期
    - change_rate: 涨跌幅百分比
    - update_time: 更新时间戳
    
    唯一约束: (stock_code, follow_date)
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_change (
                id INT AUTO_INCREMENT PRIMARY KEY,
                stock_code VARCHAR(20) NOT NULL,
                stock_name VARCHAR(100) NOT NULL,
                follow_price DECIMAL(10, 3) NOT NULL COMMENT '关注当天收盘价',
                follow_date DATE NOT NULL COMMENT '关注日期',
                latest_price DECIMAL(10, 3) NOT NULL COMMENT '最新价格',
                latest_date DATE NOT NULL COMMENT '最新价格日期',
                change_rate DECIMAL(10, 2) NOT NULL COMMENT '涨跌幅百分比',
                update_time INT NOT NULL COMMENT '更新时间戳',
                UNIQUE KEY uk_code_date (stock_code, follow_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        conn.commit()
        print("[OK] stock_change 表创建成功")

        cursor.execute("ALTER TABLE stock_change CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        print("[OK] stock_change 表排序规则已统一为 utf8mb4_unicode_ci")
    except Exception as e:
        print(f"[ERROR] 创建/修复stock_change表失败: {e}")
    finally:
        conn.close()


def get_follow_stocks():
    """
    获取所有关注的股票列表
    
    Returns:
        list: 关注股票列表，包含 stock_code, stock_name, follow_time 字段
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_code, stock_name, follow_time FROM stock_follows")
        return cursor.fetchall()
    finally:
        conn.close()


def get_stock_close_price(stock_code, date_str):
    """
    获取指定日期的收盘价（带降级策略）

    Args:
        stock_code: 缠论格式代码，如 "SH.600519"
        date_str: 目标日期字符串，格式 "YYYY-MM-DD"

    Returns:
        float: 收盘价，获取失败返回 None

    降级策略:
        - 先精确查询目标日期的收盘价
        - 如果当天无数据（未收盘/停牌/节假日），向前回溯最多10个自然日
        - 取最近一个有效日期的收盘价
    """
    parts = stock_code.split('.')
    if len(parts) == 2:
        exchange, code = parts
    else:
        return None

    if exchange == 'SH':
        tencent_code = f"sh{code}"
    elif exchange == 'SZ':
        tencent_code = f"sz{code}"
    else:
        return None

    target_date = datetime.strptime(date_str, '%Y-%m-%d')
    lookback_start = (target_date - timedelta(days=10)).strftime('%Y-%m-%d')

    try:
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tencent_code},day,{lookback_start},{date_str},20,qfq"
        resp = _safe_request('GET', url)
        if resp is None:
            return None
        data = resp.json()

        if data.get('code') == 0 and data.get('data'):
            stock_data = data['data'].get(tencent_code, {})
            klines = stock_data.get('qfqday', []) or stock_data.get('day', [])
            if klines:
                valid_klines = [k for k in klines if len(k) >= 3 and float(k[2]) > 0]
                valid_klines.sort(key=lambda k: k[0], reverse=True)
                for kline in valid_klines:
                    if kline[0] <= date_str:
                        close_price = float(kline[2])
                        print(f"  [OK] 获取 {stock_code} {kline[0]} 收盘价: {close_price} (目标日期: {date_str})")
                        return close_price
    except Exception as e:
        print(f"  [WARN] 获取 {stock_code} 收盘价异常: {e}")

    return None


def get_current_price(stock_code):
    """
    获取当前最新价格
    
    Args:
        stock_code: 缠论格式代码，如 "SH.600519"
    
    Returns:
        tuple: (最新价格, 最新价格日期)，获取失败返回 (None, None)
    
    数据源:
    - 腾讯财经API: http://qt.gtimg.cn/q=sh600519
    """
    try:
        parts = stock_code.split('.')
        if len(parts) == 2:
            exchange, code = parts
        else:
            return None, None

        if exchange == 'SH':
            tencent_code = f"sh{code}"
        elif exchange == 'SZ':
            tencent_code = f"sz{code}"
        else:
            return None, None

        url = f"http://qt.gtimg.cn/q={tencent_code}"
        resp = _safe_request('GET', url)
        if resp is None:
            return None, None
        resp.encoding = 'gbk'
        content = resp.text

        if '~' in content:
            fields = content.split('~')
            price = float(fields[3]) if len(fields) > 3 else 0
            raw_date = fields[30] if len(fields) > 30 else ''
            # 转换日期格式为 YYYY-MM-DD
            date_str = ''
            if raw_date:
                try:
                    # 腾讯返回格式如: 2026/05/15 15:00:00
                    date_str = raw_date.split(' ')[0].replace('/', '-')
                except:
                    date_str = raw_date
            return price, date_str
    except Exception as e:
        print(f"  [WARN] 获取 {stock_code} 当前价格失败: {e}")
    return None, None


def calculate_all_changes():
    """
    计算所有关注股票的涨跌幅
    
    流程:
        1. 获取所有关注股票列表
        2. 对每只股票:
           a. 获取关注日期的收盘价
           b. 获取当前最新价格
           c. 计算涨跌幅 = (当前价 - 关注价) / 关注价 * 100%
           d. 保存到数据库（使用INSERT ... ON DUPLICATE KEY UPDATE）
    
    说明:
        - 如果无法获取关注日收盘价，跳过该股票
        - 如果无法获取当前价格，跳过该股票
        - 每次请求间隔0.3秒，避免API限流
    """
    print("=" * 50)
    print(f"[INFO] 开始计算涨跌幅，时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    stocks = get_follow_stocks()
    if not stocks:
        print("[INFO] 没有关注的股票")
        return

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM stock_change
            WHERE stock_code COLLATE utf8mb4_unicode_ci NOT IN (SELECT stock_code FROM stock_follows)
        """)
        orphan_count = cursor.rowcount
        if orphan_count > 0:
            print(f"[INFO] 清理 {orphan_count} 条已取消关注的涨跌幅记录")
            conn.commit()

        success_count = 0
        fail_count = 0

        for stock in stocks:
            code = stock['stock_code']
            name = stock['stock_name']
            follow_ts = stock['follow_time']
            follow_date = datetime.fromtimestamp(follow_ts).strftime('%Y-%m-%d')

            print(f"\n处理: {code} ({name}), 关注日期: {follow_date}")

            follow_price = get_stock_close_price(code, follow_date)
            if follow_price is None or follow_price == 0:
                print(f"  [SKIP] 无法获取关注日收盘价，跳过")
                fail_count += 1
                continue

            current_price, current_date = get_current_price(code)
            if current_price is None or current_price == 0:
                print(f"  [SKIP] 无法获取当前价格，跳过")
                fail_count += 1
                continue

            change_rate = round((current_price - follow_price) / follow_price * 100, 2)
            update_time = int(time.time())

            print(f"  关注价: {follow_price}, 当前价: {current_price}, 涨跌幅: {change_rate}%")

            try:
                cursor.execute("""
                    INSERT INTO stock_change 
                    (stock_code, stock_name, follow_price, follow_date, latest_price, latest_date, change_rate, update_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        stock_name = VALUES(stock_name),
                        follow_price = VALUES(follow_price),
                        latest_price = VALUES(latest_price),
                        latest_date = VALUES(latest_date),
                        change_rate = VALUES(change_rate),
                        update_time = VALUES(update_time)
                """, (code, name, follow_price, follow_date, current_price, current_date, change_rate, update_time))
                success_count += 1
            except Exception as e:
                print(f"  [ERROR] 保存失败: {e}")
                fail_count += 1

            time.sleep(0.3)

        conn.commit()
        print(f"\n{'=' * 50}")
        print(f"[OK] 计算完成: 成功 {success_count}, 失败 {fail_count}")
        print(f"{'=' * 50}")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] 计算过程出错: {e}")
    finally:
        conn.close()


def get_change_data():
    """
    获取所有涨跌幅数据（仅返回仍在关注列表中的股票）

    Returns:
        list: 涨跌幅数据列表，按涨跌幅降序排列

    返回字段:
        - stock_code: 股票代码
        - stock_name: 股票名称
        - follow_price: 关注时价格
        - follow_date: 关注日期
        - latest_price: 最新价格
        - latest_date: 最新价格日期
        - change_rate: 涨跌幅百分比
        - update_time: 更新时间

    说明:
        - 通过 INNER JOIN stock_follows 确保只返回当前关注的股票
        - 日期格式统一为 YYYY-MM-DD
        - 按涨跌幅降序排列（涨幅高的在前）
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sc.stock_code, sc.stock_name, sc.follow_price, sc.follow_date,
                   sc.latest_price, sc.latest_date, sc.change_rate, sc.update_time
            FROM stock_change sc
            INNER JOIN stock_follows sf ON sc.stock_code COLLATE utf8mb4_unicode_ci = sf.stock_code
            ORDER BY sc.change_rate DESC
        """)
        rows = cursor.fetchall()
        # 格式化日期为 YYYY-MM-DD
        for row in rows:
            if row.get('follow_date'):
                d = row['follow_date']
                if hasattr(d, 'strftime'):
                    row['follow_date'] = d.strftime('%Y-%m-%d')
                else:
                    row['follow_date'] = str(d)[:10]
            if row.get('latest_date'):
                d = row['latest_date']
                if hasattr(d, 'strftime'):
                    row['latest_date'] = d.strftime('%Y-%m-%d')
                else:
                    row['latest_date'] = str(d)[:10]
        return rows
    finally:
        conn.close()


if __name__ == '__main__':
    create_change_table()
    calculate_all_changes()
