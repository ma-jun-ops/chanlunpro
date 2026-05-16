"""
股票名称/代码转换服务模块

主要功能：
- 通过股票代码获取股票名称（支持A股、港股、美股、期货、基金）
- 通过股票名称获取股票代码
- 集成多个数据源（腾讯、东方财富、雪球、新浪）提高查询成功率

数据源说明：
- 腾讯财经API: 获取股票基本信息
- 东方财富API: 获取股票详细信息
- 雪球API: 获取港股/美股信息
- 新浪财经API: 搜索股票名称对应代码

本地映射表：
- STOCK_NAME_MAP: 常用股票名称与代码的映射关系（约60只热门股票）


"""

import re
import json
import requests

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== 本地股票名称映射表 ====================
# 说明：常用股票名称与代码的映射，优先从本地查找，提高响应速度
STOCK_NAME_MAP = {
    '上证指数': 'SH.000001', '深证成指': 'SZ.399001', '创业板指': 'SZ.399006',
    '平安银行': 'SZ.000001', '招商银行': 'SH.600036', '贵州茅台': 'SH.600519',
    '中国平安': 'SH.601318', '腾讯控股': 'hk.00700', '阿里巴巴': 'hk.09988',
    '苹果': 'us.AAPL', '微软': 'us.MSFT', '特斯拉': 'us.TSLA',
    '万科A': 'SZ.000002', '浦发银行': 'SH.600000', '中信证券': 'SH.600030',
    '伊利股份': 'SH.600887', '恒瑞医药': 'SH.600276', '中国建筑': 'SH.601668',
    '中国中免': 'SH.601888', '长江电力': 'SH.600900', '海康威视': 'SZ.002415',
    '美的集团': 'SZ.000333', '格力电器': 'SZ.000651', '五粮液': 'SZ.000858',
    '泸州老窖': 'SZ.000568', '洋河股份': 'SZ.002304', '山西汾酒': 'SH.600809',
    '宁德时代': 'SZ.300750', '比亚迪': 'SZ.002594', '隆基绿能': 'SH.601012',
    '阳光电源': 'SZ.300274', '通威股份': 'SH.600438', '立讯精密': 'SZ.002475',
    '歌尔股份': 'SZ.002241', '工业富联': 'SH.601138', '中兴通讯': 'SZ.000063',
    '中国电信': 'SH.601728', '中国移动': 'SH.600941', '中国联通': 'SH.600050',
    '江天化学': 'SZ.300927', '好想你': 'SZ.002582', '药明康德': 'SH.603259',
    '长春高新': 'SZ.000661', '万华化学': 'SH.600309', '中国神华': 'SH.601088',
    '中国石油': 'SH.601857', '中国石化': 'SH.600028', '中国铝业': 'SH.601600',
    '中国中铁': 'SH.601390', '中国铁建': 'SH.601186', '中国交建': 'SH.601800',
    '中国中冶': 'SH.601618', '中国电建': 'SH.601669', '中国能建': 'SH.601868',
    '中国核电': 'SH.601985', '中国广核': 'SZ.003816', '中国人寿': 'SH.601628',
    '中国太保': 'SH.601601', '新华保险': 'SH.601336', '中信银行': 'SH.601998',
    '建设银行': 'SH.601939', '工商银行': 'SH.601398', '农业银行': 'SH.601288',
    '中国银行': 'SH.601988', '交通银行': 'SH.601328', '邮储银行': 'SH.601658',
    '民生银行': 'SH.600016', '兴业银行': 'SH.601166', '海通证券': 'SH.600837',
    '国泰君安': 'SH.601211', '华泰证券': 'SH.601688', '广发证券': 'SZ.000776',
    '东方证券': 'SH.600958', '招商证券': 'SH.600999', '申万宏源': 'SZ.000166',
    '银河证券': 'SH.601881', '中信建投': 'SH.601066',
}

# 通用请求头
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


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
    kwargs.setdefault('headers', UA)
    try:
        session = _build_session()
        resp = session.request(method, url, **kwargs)
        return resp
    except Exception:
        return None


# ==================== 辅助函数 ====================
def _exchange_prefix(exchange, code):
    """生成腾讯API格式的代码前缀"""
    mapping = {'SH': 'sh', 'SZ': 'sz', 'hk': 'hk', 'us': 'us'}
    return f"{mapping.get(exchange, 'sh')}{code}"


def _eastmoney_prefix(exchange, code):
    """生成东方财富API格式的代码前缀"""
    mapping = {'SH': '1', 'SZ': '0', 'hk': '116', 'us': '106'}
    return f"{mapping.get(exchange, '1')}.{code}"


def _parse_exchange_code(product_code):
    """
    解析缠论格式代码
    
    Args:
        product_code: 缠论格式代码，如 "SH.600519"
    
    Returns:
        tuple: (交易所代码, 数字代码)，如 ("SH", "600519")
    """
    parts = product_code.split('.')
    if len(parts) == 2:
        return parts[0], parts[1]
    return 'SZ', product_code


# ==================== 数据源API调用函数 ====================
def _call_tencent(exchange, code):
    """从腾讯财经API获取股票名称"""
    url = f"http://qt.gtimg.cn/q={_exchange_prefix(exchange, code)}"
    resp = _safe_request('GET', url)
    if resp is None:
        return None
    resp.encoding = 'gbk'
    if resp.status_code == 200 and '~' in resp.text:
        data = resp.text.split('~')
        if len(data) > 1 and data[1] and data[1] != code and data[1].strip():
            return data[1]
    return None


def _call_eastmoney(exchange, code):
    """从东方财富API获取股票名称"""
    url = f"http://push2.eastmoney.com/api/qt/stock/get?secid={_eastmoney_prefix(exchange, code)}&fields=f14"
    resp = _safe_request('GET', url)
    if resp is None:
        return None
    resp.encoding = 'utf-8'
    if resp.status_code == 200:
        data = resp.json()
        if data and data.get('data'):
            name = data['data'].get('f14')
            if name and name != code and name.strip():
                return name
    return None


def _call_xueqiu(code):
    """从雪球API获取股票名称（主要用于港股/美股）"""
    url = f"https://xueqiu.com/stock/search.json?q={code}"
    resp = _safe_request('GET', url)
    if resp is None:
        return None
    resp.encoding = 'utf-8'
    if resp.status_code == 200:
        data = resp.json()
        if data and data.get('stocks'):
            for stock in data['stocks']:
                sc = stock.get('code') or stock.get('symbol')
                if sc and (sc == code or sc.endswith(code)):
                    name = stock.get('name')
                    if name and name != code and name.strip():
                        return name
    return None


def _call_eastmoney_fund(code):
    """从东方财富基金页面获取基金名称"""
    url = f"http://fund.eastmoney.com/{code}.html"
    resp = _safe_request('GET', url)
    if resp is None:
        return None
    resp.encoding = 'utf-8'
    if resp.status_code == 200:
        m = re.search(r'<title>(.*?)_基金净值_天天基金网</title>', resp.text)
        if m and m.group(1) and m.group(1) != code and m.group(1).strip():
            return m.group(1)
    return None


# ==================== 主要功能函数 ====================
def get_stock_name_by_code(product_code):
    """
    通过股票代码获取股票名称

    Args:
        product_code: 缠论格式代码，如 "SH.600519", "hk.00700", "us.AAPL"

    Returns:
        str: 股票名称，如 "贵州茅台"；如果所有API均失败，返回 code 本身作为降级名称
        None: 仅在代码格式完全无法解析时返回

    查询策略（按优先级）:
        1. 港股/美股: 雪球 -> 东方财富 -> 腾讯
        2. 期货: 东方财富 -> 腾讯
        3. 基金: 东方财富基金 -> 东方财富 -> 腾讯
        4. A股: 东方财富 -> 腾讯
    """
    try:
        exchange, code = _parse_exchange_code(product_code)

        if exchange in ['hk', 'us']:
            apis = [
                (lambda: _call_xueqiu(code), '雪球'),
                (lambda: _call_eastmoney(exchange, code), '东方财富'),
                (lambda: _call_tencent(exchange, code), '腾讯'),
            ]
        elif exchange == 'FUT':
            apis = [
                (lambda: _call_eastmoney(exchange, code), '东方财富'),
                (lambda: _call_tencent(exchange, code), '腾讯'),
            ]
        elif code.isdigit() and len(code) == 6:
            apis = [
                (lambda: _call_eastmoney_fund(code), '东方财富基金'),
                (lambda: _call_eastmoney(exchange, code), '东方财富'),
                (lambda: _call_tencent(exchange, code), '腾讯'),
            ]
        else:
            apis = [
                (lambda: _call_eastmoney(exchange, code), '东方财富'),
                (lambda: _call_tencent(exchange, code), '腾讯'),
            ]

        for api, _source_name in apis:
            try:
                result = api()
                if result:
                    return result
            except Exception:
                continue

        if exchange == 'FUT':
            return code
        print(f"[WARN] 所有API均无法解析 {product_code} 的名称，使用代码作为名称")
        return code
    except Exception as e:
        print(f"[ERROR] 获取产品名称失败：{e}")
        _, code = _parse_exchange_code(product_code)
        return code


# ==================== 名称转代码辅助函数 ====================
def _to_full_code(code_str):
    """
    将纯数字代码转为缠论格式
    
    Args:
        code_str: 纯数字代码，如 "600519"
    
    Returns:
        str: 缠论格式代码，如 "SH.600519"
    
    规则:
        - 6开头: 上海证券交易所 (SH)
        - 其他: 深圳证券交易所 (SZ)
    """
    if code_str.startswith('6'):
        return f"SH.{code_str}"
    return f"SZ.{code_str}"


def _search_sina(stock_name):
    """从新浪搜索API获取股票代码"""
    url = f"http://suggest3.sinajs.cn/suggest/?name={stock_name}&type=11"
    resp = _safe_request('GET', url)
    if resp is None:
        return None
    resp.encoding = 'gbk'
    if resp.status_code == 200 and '=' in resp.text:
        data = resp.text.split('=')[1].strip('"').split(',')
        for i in range(0, len(data) - 1, 2):
            c, n = data[i], data[i + 1]
            if stock_name in n or n in stock_name:
                return _to_full_code(c)
    return None


def _search_sina_backup(stock_name):
    """从新浪备用API获取股票代码"""
    url = f"http://hq.sinajs.cn/list=s_{stock_name}"
    resp = _safe_request('GET', url)
    if resp is None:
        return None
    resp.encoding = 'gbk'
    if resp.status_code == 200 and '~' in resp.text:
        data = resp.text.split('~')
        if len(data) > 2:
            return _to_full_code(data[2])
    return None


def _search_eastmoney(stock_name):
    """从东方财富搜索API获取股票代码"""
    url = f"http://nufm.dfcfw.com/EM_Finance2014NumericApplication/JS.aspx?type=CT&cmd=C.{stock_name}&sty=FCOIATC&token=7bc05d0d4c3c22ef9fca8c2a912d779c"
    resp = _safe_request('GET', url)
    if resp is None:
        return None
    resp.encoding = 'utf-8'
    if resp.status_code == 200 and '(' in resp.text:
        data_str = resp.text.split('(')[1].split(')')[0]
        data = json.loads(data_str)
        for item in data:
            if len(item) > 2 and (stock_name in item[2] or item[2] in stock_name):
                return _to_full_code(item[1])
    return None


def _search_sina_html(stock_name):
    """从新浪网页搜索获取股票代码"""
    url = f"http://finance.sina.com.cn/realstock/company/search.php?q={stock_name}"
    resp = _safe_request('GET', url)
    if resp is None:
        return None
    resp.encoding = 'gbk'
    if resp.status_code == 200:
        for code, name in re.findall(r'<a href=\"/realstock/company/(\w+)/\"[^>]*>(.*?)</a>', resp.text):
            if stock_name in name or name in stock_name:
                if code.startswith('sh'):
                    return f"SH.{code[2:]}"
                elif code.startswith('sz'):
                    return f"SZ.{code[2:]}"
                return f"SH.{code}" if code.startswith('6') else f"SZ.{code}"
    return None


def get_stock_code_by_name(stock_name):
    """
    通过股票名称获取股票代码
    
    Args:
        stock_name: 股票名称，如 "贵州茅台", "腾讯控股"
    
    Returns:
        str: 缠论格式代码，如 "SH.600519"
        None: 未找到时返回
    
    查询策略（按优先级）:
        1. 本地映射表匹配（最快）
        2. 新浪搜索API
        3. 新浪备用API
        4. 东方财富搜索API
        5. 新浪网页搜索
    """
    try:
        # 第一步：从本地映射表查找
        for name, code in STOCK_NAME_MAP.items():
            if stock_name in name or name in stock_name:
                return code

        # 第二步：从多个数据源搜索
        for api in [_search_sina, _search_sina_backup, _search_eastmoney, _search_sina_html]:
            result = api(stock_name)
            if result:
                return result

        return None
    except Exception as e:
        print(f"[ERROR] 获取股票代码失败：{e}")
        # 异常时回退到本地映射表
        for name, code in STOCK_NAME_MAP.items():
            if stock_name in name or name in stock_name:
                return code
        return None
