from chanlun import config
from chanlun.base import Market
from chanlun.exchange.exchange import Exchange

# 全局保存交易所对象，避免创建多个交易所对象
g_exchange_obj = {}


def get_exchange(market: Market) -> Exchange:
    """
    获取市场的交易所对象，根据config配置中设置的进行获取
    """
    global g_exchange_obj
    if market.value in g_exchange_obj.keys():
        return g_exchange_obj[market.value]

    if market == Market.A:
        # 沪深 A股 交易所
        if config.EXCHANGE_A == "tdx":
            from chanlun.exchange.exchange_tdx import ExchangeTDX

            g_exchange_obj[market.value] = ExchangeTDX()
        elif config.EXCHANGE_A == "futu":
            from chanlun.exchange.exchange_futu import ExchangeFutu

            g_exchange_obj[market.value] = ExchangeFutu()
        elif config.EXCHANGE_A == "baostock":
            from chanlun.exchange.exchange_baostock import ExchangeBaostock

            g_exchange_obj[market.value] = ExchangeBaostock()
        elif config.EXCHANGE_A == "db":
            from chanlun.exchange.exchange_db import ExchangeDB

            g_exchange_obj[market.value] = ExchangeDB(Market.A.value)
        elif config.EXCHANGE_A == "qmt":
            from chanlun.exchange.exchange_qmt import ExchangeQMT

            g_exchange_obj[market.value] = ExchangeQMT()
        else:
            raise Exception(f"不支持的沪深交易所 {config.EXCHANGE_A}")

    elif market == Market.HK:
        # 港股 交易所
        if config.EXCHANGE_HK == "tdx_hk":
            try:
                # 先导入ExchangeTDXHK类
                from chanlun.exchange.exchange_tdx_hk import ExchangeTDXHK
                # 尝试创建实例
                # 由于ExchangeTDXHK使用了singleton装饰器，我们需要先清除可能存在的缓存
                # 直接创建一个临时实例，捕获异常
                temp_instance = ExchangeTDXHK()
                g_exchange_obj[market.value] = temp_instance
            except Exception as e:
                print(f"通达信 香港行情接口初始化失败，香港行情不可用: {e}")
                # 回退到数据库接口
                from chanlun.exchange.exchange_db import ExchangeDB
                g_exchange_obj[market.value] = ExchangeDB(Market.HK.value)
        elif config.EXCHANGE_HK == "futu":
            try:
                from chanlun.exchange.exchange_futu import ExchangeFutu

                g_exchange_obj[market.value] = ExchangeFutu()
            except Exception as e:
                print(f"富途 香港行情接口初始化失败，香港行情不可用: {e}")
                # 回退到数据库接口
                from chanlun.exchange.exchange_db import ExchangeDB
                g_exchange_obj[market.value] = ExchangeDB(Market.HK.value)
        elif config.EXCHANGE_HK == "db":
            from chanlun.exchange.exchange_db import ExchangeDB

            g_exchange_obj[market.value] = ExchangeDB(Market.HK.value)
        else:
            raise Exception(f"不支持的香港交易所 {config.EXCHANGE_HK}")

    elif market == Market.FUTURES:
        # 期货 交易所
        if config.EXCHANGE_FUTURES == "tq":
            try:
                from chanlun.exchange.exchange_tq import ExchangeTq

                g_exchange_obj[market.value] = ExchangeTq()
            except Exception as e:
                print(f"天勤 期货行情接口初始化失败，期货行情不可用: {e}")
                # 回退到数据库接口
                from chanlun.exchange.exchange_db import ExchangeDB
                g_exchange_obj[market.value] = ExchangeDB(Market.FUTURES.value)
        elif config.EXCHANGE_FUTURES == "tdx_futures":
            try:
                from chanlun.exchange.exchange_tdx_futures import ExchangeTDXFutures

                g_exchange_obj[market.value] = ExchangeTDXFutures()
            except Exception as e:
                print(f"通达信 期货行情接口初始化失败，期货行情不可用: {e}")
                # 回退到数据库接口
                from chanlun.exchange.exchange_db import ExchangeDB
                g_exchange_obj[market.value] = ExchangeDB(Market.FUTURES.value)
        elif config.EXCHANGE_FUTURES == "db":
            from chanlun.exchange.exchange_db import ExchangeDB

            g_exchange_obj[market.value] = ExchangeDB(Market.FUTURES.value)
        else:
            raise Exception(f"不支持的期货交易所 {config.EXCHANGE_FUTURES}")
    elif market == Market.NY_FUTURES:
        # 美股期货 交易所
        if config.EXCHANGE_NY_FUTURES == "tdx_ny_futures":
            try:
                from chanlun.exchange.exchange_tdx_ny_futures import ExchangeTDXNYFutures

                g_exchange_obj[market.value] = ExchangeTDXNYFutures()
            except Exception as e:
                print(f"通达信 纽约期货行情接口初始化失败，纽约期货行情不可用: {e}")
                # 回退到数据库接口
                from chanlun.exchange.exchange_db import ExchangeDB
                g_exchange_obj[market.value] = ExchangeDB(Market.NY_FUTURES.value)
        elif config.EXCHANGE_NY_FUTURES == "db":
            from chanlun.exchange.exchange_db import ExchangeDB

            g_exchange_obj[market.value] = ExchangeDB(Market.NY_FUTURES.value)
    elif market == Market.FX:
        # 外汇市场行情
        if config.EXCHANGE_FX == "tdx_fx":
            try:
                from chanlun.exchange.exchange_tdx_fx import ExchangeTDXFX

                g_exchange_obj[market.value] = ExchangeTDXFX()
            except Exception as e:
                print(f"通达信 外汇行情接口初始化失败，外汇行情不可用: {e}")
                # 回退到数据库接口
                from chanlun.exchange.exchange_db import ExchangeDB
                g_exchange_obj[market.value] = ExchangeDB(Market.FX.value)
        elif config.EXCHANGE_FX == "db":
            from chanlun.exchange.exchange_db import ExchangeDB

            g_exchange_obj[market.value] = ExchangeDB(Market.FX.value)
        else:
            raise Exception(f"不支持的外汇交易所 {config.EXCHANGE_FX}")

    elif market == Market.CURRENCY:
        # 数字货币 交易所
        if config.EXCHANGE_CURRENCY == "binance":
            try:
                from chanlun.exchange.exchange_binance import ExchangeBinance

                g_exchange_obj[market.value] = ExchangeBinance()
            except Exception as e:
                print(f"Binance 合约行情接口初始化失败，合约行情不可用: {e}")
                # 回退到数据库接口
                from chanlun.exchange.exchange_db import ExchangeDB
                g_exchange_obj[market.value] = ExchangeDB(Market.CURRENCY.value)
        elif config.EXCHANGE_CURRENCY == "db":
            from chanlun.exchange.exchange_db import ExchangeDB

            g_exchange_obj[market.value] = ExchangeDB(Market.CURRENCY.value)
        else:
            raise Exception(f"不支持的数字货币交易所 {config.EXCHANGE_CURRENCY}")
    elif market == Market.CURRENCY_SPOT:
        # 数字货币 交易所
        if config.EXCHANGE_CURRENCY_SPOT == "binance_spot":
            try:
                from chanlun.exchange.exchange_binance_spot import ExchangeBinanceSpot

                g_exchange_obj[market.value] = ExchangeBinanceSpot()
            except Exception as e:
                print(f"Binance 现货行情接口初始化失败，现货行情不可用: {e}")
                # 回退到数据库接口
                from chanlun.exchange.exchange_db import ExchangeDB
                g_exchange_obj[market.value] = ExchangeDB(Market.CURRENCY_SPOT.value)
        elif config.EXCHANGE_CURRENCY_SPOT == "db":
            from chanlun.exchange.exchange_db import ExchangeDB

            g_exchange_obj[market.value] = ExchangeDB(Market.CURRENCY_SPOT.value)
        else:
            raise Exception(f"不支持的数字货币交易所 {config.EXCHANGE_CURRENCY_SPOT}")
    elif market == Market.US:
        # 美股 交易所
        if config.EXCHANGE_US == "alpaca":
            try:
                from chanlun.exchange.exchange_alpaca import ExchangeAlpaca

                g_exchange_obj[market.value] = ExchangeAlpaca()
            except Exception as e:
                print(f"Alpaca 美股行情接口初始化失败，美股行情不可用: {e}")
                # 回退到数据库接口
                from chanlun.exchange.exchange_db import ExchangeDB
                g_exchange_obj[market.value] = ExchangeDB(Market.US.value)
        elif config.EXCHANGE_US == "polygon":
            try:
                from chanlun.exchange.exchange_polygon import ExchangePolygon

                g_exchange_obj[market.value] = ExchangePolygon()
            except Exception as e:
                print(f"Polygon 美股行情接口初始化失败，美股行情不可用: {e}")
                # 回退到数据库接口
                from chanlun.exchange.exchange_db import ExchangeDB
                g_exchange_obj[market.value] = ExchangeDB(Market.US.value)
        elif config.EXCHANGE_US == "ib":
            try:
                from chanlun.exchange.exchange_ib import ExchangeIB

                g_exchange_obj[market.value] = ExchangeIB()
            except Exception as e:
                print(f"IB 美股行情接口初始化失败，美股行情不可用: {e}")
                # 回退到数据库接口
                from chanlun.exchange.exchange_db import ExchangeDB
                g_exchange_obj[market.value] = ExchangeDB(Market.US.value)
        elif config.EXCHANGE_US == "tdx_us":
            try:
                from chanlun.exchange.exchange_tdx_us import ExchangeTDXUS

                g_exchange_obj[market.value] = ExchangeTDXUS()
            except Exception as e:
                print(f"通达信 美股行情接口初始化失败，美股行情不可用: {e}")
                # 回退到数据库接口
                from chanlun.exchange.exchange_db import ExchangeDB
                g_exchange_obj[market.value] = ExchangeDB(Market.US.value)
        elif config.EXCHANGE_US == "db":
            from chanlun.exchange.exchange_db import ExchangeDB

            g_exchange_obj[market.value] = ExchangeDB(Market.US.value)
        else:
            raise Exception(f"不支持的美股交易所 {config.EXCHANGE_US}")

    return g_exchange_obj[market.value]
