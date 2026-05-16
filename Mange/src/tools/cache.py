"""
缓存管理模块

主要功能：
- 提供统一的缓存接口（Redis + 内存缓存双模式）
- 支持键值对存储、删除、清空、查询等操作
- Redis不可用时自动降级为内存缓存

缓存策略：
- 优先使用Redis缓存（高性能、持久化）
- Redis连接失败时自动使用内存缓存（dict实现）
- 支持JSON序列化/反序列化（dict和list类型）
- 支持设置过期时间


"""

import redis
import json
import time


class Cache:
    """
    缓存类，支持Redis和内存缓存双模式
    
    属性：
        redis_client: Redis客户端实例
        memory_cache: 内存缓存字典（备选方案）
    """
    
    def __init__(self):
        """
        初始化缓存实例
        
        流程：
            1. 尝试连接Redis（127.0.0.1:6379）
            2. 连接成功则使用Redis
            3. 连接失败则使用内存缓存
        """
        self.redis_client = None
        try:
            self.redis_client = redis.Redis(
                host='127.0.0.1',
                port=6379,
                db=0,
                decode_responses=True
            )
            self.redis_client.ping()
            print("Redis 连接成功")
        except Exception as e:
            print(f"Redis 连接失败: {e}")
            self.redis_client = None
        self.memory_cache = {}  # 内存缓存，作为 Redis 不可用时的备选

    def set(self, key, value, expire=3600):
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值（支持字符串、字典、列表）
            expire: 过期时间（秒），默认3600秒（1小时）
        
        Returns:
            bool: 设置是否成功
        
        说明：
            - dict和list类型会自动JSON序列化
            - Redis不可用时使用内存缓存
        """
        try:
            # 序列化值
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value)
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
        """
        获取缓存
        
        Args:
            key: 缓存键
        
        Returns:
            缓存值（自动反序列化为原始类型），不存在或过期返回None
        
        说明：
            - 自动尝试JSON反序列化
            - 内存缓存会检查过期时间
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
        """
        删除缓存
        
        Args:
            key: 缓存键
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
        """
        清空缓存
        
        说明：
            - Redis模式：清空当前数据库（flushdb）
            - 内存模式：清空字典
        """
        try:
            if self.redis_client:
                self.redis_client.flushdb()
            else:
                self.memory_cache.clear()
        except Exception as e:
            print(f"清空缓存失败: {e}")

    def get_keys(self, pattern):
        """
        获取匹配模式的键
        
        Args:
            pattern: 键模式，如 "klines:*"
        
        Returns:
            list: 匹配的键列表
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
        """
        检查键是否存在
        
        Args:
            key: 缓存键
        
        Returns:
            bool: 是否存在且未过期
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
        """
        设置键的过期时间
        
        Args:
            key: 缓存键
            seconds: 过期时间（秒）
        
        Returns:
            bool: 是否成功
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
