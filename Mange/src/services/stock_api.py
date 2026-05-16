"""
股票数据API服务模块

主要功能：
- 从腾讯财经API获取股票实时行情数据
- 支持单只股票和批量获取
- 集成Redis/内存缓存机制，减少API请求频率

API说明：
- 腾讯财经API: http://qt.gtimg.cn/q=sh600519,sz000001
- 返回格式: gbk编码，~分隔的字段数据

缓存策略：
- 使用Redis作为主缓存，内存缓存作为备选
- 缓存有效期: 300秒（5分钟）
- 支持异步批量写入缓存


"""

import requests
import time
import os
import sys
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from tools.cache import cache
from tools.cache_queue import get_cache_queue

# 缓存配置
CACHE_TTL = 300  # 缓存有效期（秒）
cache_queue = get_cache_queue(cache)


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


# ==================== 代码格式转换函数 ====================
def code_to_tencent(code):
    """
    将缠论格式代码转为腾讯API格式
    
    Args:
        code: 缠论格式代码，如 "SH.600519", "SZ.000001", "hk.00700"
    
    Returns:
        str: 腾讯API格式代码，如 "sh600519", "sz000001", "hk00700"
    
    示例:
        >>> code_to_tencent("SH.600519")
        "sh600519"
    """
    parts = code.split('.')
    if len(parts) == 2:
        ex, c = parts
        mapping = {'SH': 'sh', 'SZ': 'sz', 'hk': 'hk', 'us': 'us'}
        return f"{mapping.get(ex, 'sh')}{c}"
    return f"sz{code}"


def code_to_eastmoney(code):
    """
    将缠论格式代码转为东方财富API格式
    
    Args:
        code: 缠论格式代码，如 "SH.600519"
    
    Returns:
        str: 东方财富API格式代码，如 "1.600519"
    
    市场代码映射:
        SH -> 1 (上海)
        SZ -> 0 (深圳)
        hk -> 116 (港股)
        us -> 106 (美股)
    """
    parts = code.split('.')
    if len(parts) == 2:
        ex, c = parts
        mapping = {'SH': '1', 'SZ': '0', 'hk': '116', 'us': '106'}
        return f"{mapping.get(ex, '1')}.{c}"
    return f"1.{code}"


# ==================== 数据解析函数 ====================
def parse_tencent_line(line):
    """
    解析腾讯API单行数据
    
    Args:
        line: 腾讯API返回的原始数据行（~分隔）
    
    Returns:
        dict: 解析后的股票数据字典，包含以下字段:
            - last: 最新价
            - buy1: 买一价
            - sell1: 卖一价
            - low: 今日最低价
            - high: 今日最高价
            - open: 今日开盘价
            - volume: 成交量
            - rate: 涨跌幅百分比
    
    腾讯API字段说明（部分）:
        data[1]: 股票名称
        data[3]: 最新价
        data[4]: 昨收价
        data[5]: 今开价
        data[6]: 成交量
        data[9]: 买一价
        data[19]: 卖一价
        data[33]: 最高价
        data[34]: 最低价
    """
    if '~' not in line:
        return None
    data = line.split('~')
    if len(data) < 35:
        return None
    try:
        price = float(data[3] or 0)
        last_close = float(data[4] or 0)
        open_price = float(data[5] or 0)
        high = float(data[33] or 0)
        low = float(data[34] or 0)
        volume = float(data[6] or 0)
        bid1 = float(data[9] or 0)
        ask1 = float(data[19] or 0)
        rate = round((price - last_close) / last_close * 100, 2) if last_close > 0 else 0.0
        return {
            'last': price,
            'buy1': bid1,
            'sell1': ask1,
            'low': low,
            'high': high,
            'open': open_price,
            'volume': volume,
            'rate': rate
        }
    except (ValueError, IndexError):
        return None


# ==================== 数据获取函数 ====================
def get_stock_data(stock_code):
    """
    获取单只股票实时数据
    
    Args:
        stock_code: 缠论格式股票代码，如 "SH.600519"
    
    Returns:
        dict: 股票数据字典（同parse_tencent_line返回值）
        None: 获取失败时返回
    
    流程:
        1. 先检查缓存
        2. 缓存未命中则请求腾讯API
        3. 解析数据并存入缓存
    """
    try:
        cached_data = cache_queue.get(f"stock:tick:{stock_code}")
        if cached_data:
            return cached_data

        tencent_code = code_to_tencent(stock_code)
        url = f"http://qt.gtimg.cn/q={tencent_code}"
        resp = _safe_request('GET', url)
        if resp is None:
            return None
        resp.encoding = 'gbk'

        if resp.status_code == 200 and '~' in resp.text:
            result = parse_tencent_line(resp.text)
            if result:
                cache_queue.set(f"stock:tick:{stock_code}", result, expire=300, async_=True)
                return result
    except Exception as e:
        print(f"获取股票数据失败：{e}")
    return None


def get_stock_data_batch(stock_codes):
    """
    批量获取股票实时数据
    
    Args:
        stock_codes: 股票代码列表，如 ["SH.600519", "SZ.000001"]
    
    Returns:
        dict: {股票代码: 股票数据} 字典
    
    优化策略:
        - 先检查缓存，只请求未缓存的股票
        - 分批请求，每批最多50只股票
        - 异步写入缓存，提高响应速度
    """
    if not stock_codes:
        return {}

    results = {}
    to_fetch = []

    # 第一步：检查缓存
    for code in stock_codes:
        cached = cache_queue.get(f"stock:tick:{code}")
        if cached:
            results[code] = cached
        else:
            to_fetch.append(code)

    if not to_fetch:
        return results

    # 第二步：批量请求API
    batch_size = 50
    for i in range(0, len(to_fetch), batch_size):
        batch = to_fetch[i:i + batch_size]
        tencent_codes = [code_to_tencent(sc) for sc in batch]
        if not tencent_codes:
            continue

        url = f"http://qt.gtimg.cn/q={','.join(tencent_codes)}"
        try:
            resp = _safe_request('GET', url)
            if resp is None:
                continue
            resp.encoding = 'gbk'

            if resp.status_code == 200:
                lines = resp.text.split(';')
                for line in lines:
                    parsed = parse_tencent_line(line)
                    if parsed:
                        # 通过代码匹配原始 stock_code
                        for sc in batch:
                            if code_to_tencent(sc).lower() in line.lower():
                                results[sc] = parsed
                                cache_queue.set(f"stock:tick:{sc}", parsed, expire=300, async_=True)
                                break
        except Exception as e:
            print(f"批量获取股票数据失败：{e}")

    return results
