import os
import sys
import time
import threading
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools.cache import cache
from services.stock_api import get_stock_data_batch
from db.database import get_db_connection

_CHANLUN_PRO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'chanlun-pro', 'web', 'chanlun_chart'
)
if _CHANLUN_PRO_PATH not in sys.path:
    sys.path.insert(0, _CHANLUN_PRO_PATH)

try:
    from chanlun.exchange.exchange_tdx import ExchangeTDX
except Exception:
    ExchangeTDX = None

KLINE_FREQUENCIES = ['d', 'w', 'm', 'y', '60m', '30m', '15m', '5m', '1m']
KLINE_CACHE_TTL = 1800

INDEX_STOCKS = [
    ('SH.000001', '上证指数'),
    ('SZ.399001', '深证成指'),
    ('SZ.399006', '创业板指'),
    ('SH.000688', '科创50'),
]


def _get_followed_stock_codes():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT stock_code FROM stock_follows")
        rows = cursor.fetchall()
        return [r['stock_code'] for r in rows]
    finally:
        conn.close()


def prefetch_stock_data():
    codes = _get_followed_stock_codes()
    for idx_code, _ in INDEX_STOCKS:
        if idx_code not in codes:
            codes.append(idx_code)
    if not codes:
        return
    get_stock_data_batch(codes)


def prefetch_klines_for_chanlun():
    if ExchangeTDX is None:
        print("[PREFETCH] ExchangeTDX 不可用，跳过K线预抓取")
        return

    codes = _get_followed_stock_codes()
    for idx_code, _ in INDEX_STOCKS:
        if idx_code not in codes:
            codes.append(idx_code)
    if not codes:
        return

    try:
        from chanlun.cl_utils import (
            query_cl_chart_config,
            web_batch_get_cl_datas,
            cl_data_to_tv_chart,
        )
    except Exception:
        print("[PREFETCH] 缠论计算模块不可用，跳过")
        return

    ex = None
    for code in codes:
        for freq in KLINE_FREQUENCIES:
            result_key = f"tv_cl_result:a:{code}:{freq}"
            try:
                if ex is None:
                    ex = ExchangeTDX()
                klines = ex.klines(code, freq)
                if klines is None or len(klines) == 0:
                    continue

                if klines["date"].dt.tz is not None:
                    klines["date"] = klines["date"].dt.tz_localize(None)

                last_date = str(klines.iloc[-1]["date"])
                existing = cache.get(result_key)
                if existing and isinstance(existing, dict) and existing.get("_last_date") == last_date:
                    continue

                cl_config = query_cl_chart_config("a", code)
                cd = web_batch_get_cl_datas("a", code, {freq: klines}, cl_config)[0]
                chart_data = cl_data_to_tv_chart(cd, cl_config)
                chart_data["_last_date"] = last_date
                cache.set(result_key, chart_data, expire=KLINE_CACHE_TTL)
            except Exception:
                pass


def background_update_cache():
    while True:
        try:
            prefetch_stock_data()
        except Exception as e:
            print(f"[PREFETCH] 后台更新实时行情失败: {e}")
            traceback.print_exc()
        try:
            prefetch_klines_for_chanlun()
        except Exception as e:
            print(f"[PREFETCH] 后台更新K线失败: {e}")
            traceback.print_exc()
        time.sleep(120)


def start_prefetch():
    print("[INFO] 后台预抓取已启动（每2分钟刷新：实时行情 + K线拉取 + 缠论计算 → Redis）")
    t = threading.Thread(target=background_update_cache, daemon=True)
    t.start()
    return t
