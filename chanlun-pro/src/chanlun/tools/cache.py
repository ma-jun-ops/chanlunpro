import redis
import json
import time
from chanlun.config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB

class Cache:
    def __init__(self):
        self.redis_client = None
        if REDIS_HOST:
            try:
                self.redis_client = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    password=REDIS_PASSWORD if hasattr(REDIS_PASSWORD, '__len__') and len(REDIS_PASSWORD) > 0 else None,
                    db=REDIS_DB if hasattr(REDIS_DB, '__int__') else 0,
                    decode_responses=True
                )
                self.redis_client.ping()
                print("Redis 连接成功")
            except Exception as e:
                print(f"Redis 连接失败: {e}")
                self.redis_client = None
        self.memory_cache = {}  # 内存缓存，作为 Redis 不可用时的备选

    def set(self, key, value, expire=3600):
        """设置缓存
        :param key: 缓存键
        :param value: 缓存值
        :param expire: 过期时间（秒）
        """
        try:
            # 序列化值
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, default=str)
            else:
                value_str = str(value)
            
            # 尝试使用 Redis
            if self.redis_client:
                self.redis_client.set(key, value_str, ex=expire)
            else:
                # 使用内存缓存
                self.memory_cache[key] = {
                    'value': value_str,
                    'expire': time.time() + expire
                }
            return True
        except Exception as e:
            print(f"设置缓存失败: {e}")
            return False

    def get(self, key):
        """获取缓存
        :param key: 缓存键
        :return: 缓存值
        """
        try:
            # 尝试使用 Redis
            if self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    # 尝试反序列化
                    try:
                        return json.loads(value)
                    except:
                        return value
            else:
                # 使用内存缓存
                if key in self.memory_cache:
                    item = self.memory_cache[key]
                    if time.time() < item['expire']:
                        # 尝试反序列化
                        try:
                            return json.loads(item['value'])
                        except:
                            return item['value']
                    else:
                        # 过期，删除
                        del self.memory_cache[key]
            return None
        except Exception as e:
            print(f"获取缓存失败: {e}")
            return None

    def delete(self, key):
        """删除缓存
        :param key: 缓存键
        """
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            else:
                if key in self.memory_cache:
                    del self.memory_cache[key]
        except Exception as e:
            print(f"删除缓存失败: {e}")

    def clear(self):
        """清空缓存
        """
        try:
            if self.redis_client:
                self.redis_client.flushdb()
            else:
                self.memory_cache.clear()
        except Exception as e:
            print(f"清空缓存失败: {e}")

    def get_keys(self, pattern):
        """获取匹配模式的键
        :param pattern: 键模式，如 "klines:*"
        :return: 键列表
        """
        try:
            if self.redis_client:
                return self.redis_client.keys(pattern)
            else:
                # 内存缓存中查找
                keys = []
                for key in self.memory_cache:
                    if pattern.replace('*', '') in key:
                        keys.append(key)
                return keys
        except Exception as e:
            print(f"获取键失败: {e}")
            return []

    def exists(self, key):
        """检查键是否存在
        :param key: 缓存键
        :return: 是否存在
        """
        try:
            if self.redis_client:
                return self.redis_client.exists(key) > 0
            else:
                return key in self.memory_cache and time.time() < self.memory_cache[key]['expire']
        except Exception as e:
            print(f"检查键失败: {e}")
            return False

    def expire(self, key, seconds):
        """设置键的过期时间
        :param key: 缓存键
        :param seconds: 过期时间（秒）
        :return: 是否成功
        """
        try:
            if self.redis_client:
                return self.redis_client.expire(key, seconds)
            else:
                if key in self.memory_cache:
                    self.memory_cache[key]['expire'] = time.time() + seconds
                    return True
                return False
        except Exception as e:
            print(f"设置过期时间失败: {e}")
            return False

# 创建缓存实例
cache = Cache()
