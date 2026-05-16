import redis
import json

# 连接Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# 查看所有股票相关的键
stock_keys = redis_client.keys('stock:*')

print(f"Redis缓存中的股票数据数量: {len(stock_keys)}")
print("\n缓存的股票数据:")

for key in stock_keys:
    try:
        data = redis_client.get(key)
        if data:
            stock_data = json.loads(data)
            stock_code = key.replace('stock:', '')
            print(f"股票代码: {stock_code}")
            print(f"  名称: {stock_data.get('name', 'N/A')}")
            print(f"  价格: {stock_data.get('price', 'N/A')}")
            print(f"  涨跌: {stock_data.get('change', 'N/A')}")
            print(f"  涨跌幅: {stock_data.get('change_percent', 'N/A')}%")
            print()
    except Exception as e:
        print(f"读取{key}失败: {e}")

if not stock_keys:
    print("Redis缓存中没有股票数据")
