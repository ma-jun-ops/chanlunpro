"""
数据库配置管理模块

主要功能：
- 集中管理所有MySQL数据库连接配置
- 提供数据库连接URI生成函数
- 支持跨项目数据库访问（PythonProject1和chanlun-pro）

数据库说明：
- chanlun_klines: 用户管理数据库（用户信息、密码等）
- stokedb: 股票关注与涨跌幅数据库
- chanlun_db: chanlun-pro缠论分析数据库

作者：系统
版本：1.0
"""

import os
import pymysql

# ==================== MySQL 连接配置 ====================
# 注意：修改此处配置后，所有使用该模块的数据库连接都会自动更新
DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = 'root'
DB_PASSWORD = '123456'

# ==================== 数据库名称配置 ====================
# PythonProject1 用户管理数据库
USER_DB_NAME = 'chanlun_klines'

# PythonProject1 股票关注与涨跌幅数据库
STOCK_DB_NAME = 'stokedb'

# chanlun-pro 缠论分析数据库
CHANLUN_DB_NAME = 'chanlun_db'
CHANLUN_PRO_PATH = None  # 设为 None 则自动查找同级目录


def get_chanlun_pro_path():
    """
    获取 chanlun-pro 项目路径
    
    说明：
    - 如果 CHANLUN_PRO_PATH 已设置，直接返回
    - 否则自动查找同级目录下的 chanlun-pro 项目
    
    Returns:
        str: chanlun-pro 项目的 web/chanlun_chart 目录路径
    """
    if CHANLUN_PRO_PATH:
        return CHANLUN_PRO_PATH
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(os.path.dirname(current_dir))
    return os.path.join(base_dir, 'chanlun-pro', 'web', 'chanlun_chart')


def get_user_db_uri():
    """
    获取用户管理数据库连接 URI
    
    Returns:
        str: SQLAlchemy 格式的数据库连接URI
        示例: mysql+pymysql://root:123456@localhost:3306/chanlun_klines?charset=utf8mb4
    """
    return f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{USER_DB_NAME}?charset=utf8mb4'


def get_stock_db_uri():
    """
    获取股票数据库连接 URI
    
    Returns:
        str: SQLAlchemy 格式的数据库连接URI
        示例: mysql+pymysql://root:123456@localhost:3306/stokedb?charset=utf8mb4
    """
    return f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{STOCK_DB_NAME}?charset=utf8mb4'


def get_db_connection():
    """
    获取股票数据库的 pymysql 连接
    
    Returns:
        pymysql.Connection: 数据库连接对象（DictCursor模式，返回字典格式结果）
    """
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=STOCK_DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def create_stock_db():
    """
    创建股票数据库（如果不存在）
    
    说明：
    - 使用 utf8mb4 字符集，支持完整的 Unicode 字符
    - 如果数据库已存在，不会报错
    """
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS {STOCK_DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[OK] 数据库 {STOCK_DB_NAME} 创建成功")
    except Exception as e:
        print(f"[ERROR] 创建数据库失败：{e}")
