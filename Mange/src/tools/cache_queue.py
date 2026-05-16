"""
缓存队列模块

主要功能：
- 提供异步批量缓存操作功能
- 支持队列化处理，提高缓存写入性能
- 集成Cache类，实现Redis/内存缓存的异步操作

设计模式：
- 单例模式：get_cache_queue() 返回全局唯一实例
- 生产者-消费者模式：enqueue入队，worker_thread处理

类说明：
- CacheQueue: 缓存队列核心类，负责批量处理
- CacheWithQueue: 带队列的缓存封装类，提供便捷接口


"""

import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


class CacheQueue:
    """
    缓存队列类，用于批量处理缓存操作
    
    优势：
    - 异步处理缓存操作，提高性能
    - 批量处理减少Redis网络请求次数
    - 支持按操作类型分组处理
    """
    
    def __init__(self, batch_size: int = 10, process_interval: float = 0.1):
        """
        初始化缓存队列
        
        Args:
            batch_size: 批量处理的大小，默认10
            process_interval: 处理间隔时间（秒），默认0.1秒
        """
        self.queue = queue.Queue()
        self.batch_size = batch_size
        self.process_interval = process_interval
        self.running = False
        self.worker_thread = None
        self.cache_operations: Dict[str, Callable] = {}
        self.lock = threading.Lock()
    
    def register_operation(self, operation_name: str, operation_func: Callable):
        """
        注册缓存操作函数
        
        Args:
            operation_name: 操作名称（如 "set", "get", "delete"）
            operation_func: 操作函数（如 cache.set）
        """
        with self.lock:
            self.cache_operations[operation_name] = operation_func
    
    def enqueue(self, operation_name: str, *args, **kwargs):
        """
        将缓存操作入队
        
        Args:
            operation_name: 操作名称
            *args: 操作位置参数
            **kwargs: 操作关键字参数
        
        Raises:
            ValueError: 操作未注册时抛出
        """
        if operation_name not in self.cache_operations:
            raise ValueError(f"Operation {operation_name} not registered")
        
        self.queue.put((operation_name, args, kwargs))
    
    def start(self):
        """启动缓存队列处理线程"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.worker_thread.start()
    
    def stop(self):
        """停止缓存队列处理线程"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
    
    def _process_queue(self):
        """
        处理队列中的缓存操作
        
        流程：
            1. 从队列中批量获取操作（最多batch_size个）
            2. 按操作类型分组
            3. 批量执行同类型操作
            4. 等待process_interval后继续
        """
        while self.running:
            batch = []
            
            # 收集批量操作
            while len(batch) < self.batch_size:
                try:
                    # 非阻塞获取队列元素
                    item = self.queue.get(block=False)
                    batch.append(item)
                    self.queue.task_done()
                except queue.Empty:
                    break
            
            # 处理批量操作
            if batch:
                self._process_batch(batch)
            
            # 等待下一次处理
            time.sleep(self.process_interval)
    
    def _process_batch(self, batch: List[Tuple[str, tuple, dict]]):
        """
        处理批量缓存操作
        
        Args:
            batch: 批量操作列表，每个元素为 (操作名, 位置参数, 关键字参数)
        
        处理策略：
            - set_batch: 批量设置缓存
            - delete_batch: 批量删除缓存
            - 其他: 逐个执行操作
        """
        # 按操作类型分组
        operations_by_type: Dict[str, List[Tuple[tuple, dict]]] = {}
        for operation_name, args, kwargs in batch:
            if operation_name not in operations_by_type:
                operations_by_type[operation_name] = []
            operations_by_type[operation_name].append((args, kwargs))
        
        # 处理每种类型的操作
        for operation_name, operations in operations_by_type.items():
            try:
                operation_func = self.cache_operations[operation_name]
                # 对于批量操作，调用对应的处理函数
                if operation_name == "set_batch":
                    # 批量设置缓存
                    items = [(args[0], args[1], kwargs.get('expire', 3600)) for args, kwargs in operations]
                    operation_func(items)
                elif operation_name == "delete_batch":
                    # 批量删除缓存
                    keys = [args[0] for args, kwargs in operations]
                    operation_func(keys)
                else:
                    # 单个操作
                    for args, kwargs in operations:
                        operation_func(*args, **kwargs)
            except Exception as e:
                print(f"Error processing {operation_name}: {e}")


class CacheWithQueue:
    """
    带队列的缓存类，集成缓存队列功能
    
    优势：
    - 支持同步和异步操作
    - 写操作默认异步，提高响应速度
    - 读操作默认同步，保证数据一致性
    """
    
    def __init__(self, cache, batch_size: int = 10, process_interval: float = 0.1):
        """
        初始化带队列的缓存
        
        Args:
            cache: 缓存实例（Cache对象）
            batch_size: 批量处理的大小，默认10
            process_interval: 处理间隔时间（秒），默认0.1秒
        """
        self.cache = cache
        self.queue = CacheQueue(batch_size, process_interval)
        
        # 注册缓存操作
        self.queue.register_operation("set", self.cache.set)
        self.queue.register_operation("get", self.cache.get)
        self.queue.register_operation("delete", self.cache.delete)
        self.queue.register_operation("clear", self.cache.clear)
        
        # 注册批量操作
        self.queue.register_operation("set_batch", self._batch_set)
        self.queue.register_operation("delete_batch", self._batch_delete)
        
        # 启动队列
        self.queue.start()
    
    def set(self, key: str, value: Any, expire: int = 3600, async_: bool = True):
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            expire: 过期时间（秒），默认3600秒
            async_: 是否异步处理，默认True（异步）
        """
        if async_:
            self.queue.enqueue("set", key, value, expire=expire)
        else:
            self.cache.set(key, value, expire)
    
    def get(self, key: str, async_: bool = False) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            key: 缓存键
            async_: 是否异步处理（获取操作通常同步处理）
        
        Returns:
            缓存值，不存在返回None
        """
        # 获取操作通常需要同步返回结果
        return self.cache.get(key)
    
    def delete(self, key: str, async_: bool = True):
        """
        删除缓存
        
        Args:
            key: 缓存键
            async_: 是否异步处理，默认True（异步）
        """
        if async_:
            self.queue.enqueue("delete", key)
        else:
            self.cache.delete(key)
    
    def clear(self, async_: bool = True):
        """
        清空缓存
        
        Args:
            async_: 是否异步处理，默认True（异步）
        """
        if async_:
            self.queue.enqueue("clear")
        else:
            self.cache.clear()
    
    def set_batch(self, items: List[Tuple[str, Any, int]], async_: bool = True):
        """
        批量设置缓存
        
        Args:
            items: 缓存项列表，每个项为 (key, value, expire)
            async_: 是否异步处理，默认True（异步）
        """
        if async_:
            for key, value, expire in items:
                self.queue.enqueue("set", key, value, expire=expire)
        else:
            self._batch_set(items)
    
    def delete_batch(self, keys: List[str], async_: bool = True):
        """
        批量删除缓存
        
        Args:
            keys: 缓存键列表
            async_: 是否异步处理，默认True（异步）
        """
        if async_:
            for key in keys:
                self.queue.enqueue("delete", key)
        else:
            self._batch_delete(keys)
    
    def _batch_set(self, items: List[Tuple[str, Any, int]]):
        """
        批量设置缓存的内部方法
        
        Args:
            items: 缓存项列表，每个项为 (key, value, expire)
        """
        for key, value, expire in items:
            self.cache.set(key, value, expire)
    
    def _batch_delete(self, keys: List[str]):
        """
        批量删除缓存的内部方法
        
        Args:
            keys: 缓存键列表
        """
        for key in keys:
            self.cache.delete(key)
    
    def stop(self):
        """停止缓存队列"""
        self.queue.stop()


# 全局缓存队列实例
_cache_queue_instance = None


def get_cache_queue(cache=None, batch_size: int = 10, process_interval: float = 0.1) -> CacheWithQueue:
    """
    获取缓存队列实例（单例模式）
    
    Args:
        cache: 缓存实例（Cache对象）
        batch_size: 批量处理的大小，默认10
        process_interval: 处理间隔时间（秒），默认0.1秒
    
    Returns:
        CacheWithQueue: 缓存队列实例
    
    说明：
        - 首次调用时创建实例
        - 后续调用返回同一实例（单例模式）
        - 必须传入cache参数才能创建实例
    """
    global _cache_queue_instance
    if _cache_queue_instance is None and cache:
        _cache_queue_instance = CacheWithQueue(cache, batch_size, process_interval)
    return _cache_queue_instance
