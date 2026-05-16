import pandas as pd
import sqlite3
import pymysql
import os
from pathlib import Path

# ================= 配置区 (已根据你的 config.py 自动匹配) =================
MYSQL_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',              # 对应你的 DB_USER
    'password': '1023',          # 对应你的 DB_PWD
    'database': 'chanlun_db',    # 对应你的 DB_DATABASE
    'charset': 'utf8mb4'
}

# 数据源路径
CSV_ROOT = os.path.expanduser("~/.chanlun_pro/klines.KILLED")
SQLITE_DB = os.path.expanduser("~/.chanlun_pro/db/chanlun_klines.sqlite")
# ========================================================================

def create_table(conn):
    """创建 MySQL 表结构"""
    cursor = conn.cursor()
    sql = """
    CREATE TABLE IF NOT EXISTS klines (
        id INT AUTO_INCREMENT PRIMARY KEY,
        market VARCHAR(10) NOT NULL,
        code VARCHAR(20) NOT NULL,
        frequency VARCHAR(10) NOT NULL,
        time DATETIME NOT NULL,
        open DECIMAL(20, 4),
        high DECIMAL(20, 4),
        low DECIMAL(20, 4),
        close DECIMAL(20, 4),
        volume DECIMAL(20, 4),
        amount DECIMAL(20, 4) DEFAULT 0,
        UNIQUE KEY unique_kline (market, code, frequency, time)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    cursor.execute(sql)
    conn.commit()
    print("✅ MySQL 表结构检查/创建完成。")

def import_csv_to_mysql(conn):
    """导入 CSV 文件夹"""
    if not os.path.exists(CSV_ROOT):
        print(f"⚠️ 未找到 CSV 备份目录 ({CSV_ROOT})，跳过 CSV 导入。")
        return

    cursor = conn.cursor()
    total_count = 0
    
    print(f"📂 开始扫描 CSV 目录: {CSV_ROOT}")
    
    # 遍历市场
    for market_dir in Path(CSV_ROOT).iterdir():
        if not market_dir.is_dir(): continue
        market = market_dir.name
        
        # 遍历代码
        for code_dir in market_dir.iterdir():
            if not code_dir.is_dir(): continue
            code = code_dir.name
            
            # 遍历频率文件
            for csv_file in code_dir.glob("*.csv"):
                freq = csv_file.stem 
                
                try:
                    df = pd.read_csv(csv_file)
                    if df.empty: continue
                    
                    # 标准化列名
                    df.columns = [c.lower().strip() for c in df.columns]
                    
                    if 'time' not in df.columns and 'date' in df.columns:
                        df.rename(columns={'date': 'time'}, inplace=True)
                    
                    df['time'] = pd.to_datetime(df['time'])
                    df['market'] = market
                    df['code'] = code
                    df['frequency'] = freq
                    
                    cols = ['market', 'code', 'frequency', 'time', 'open', 'high', 'low', 'close', 'volume']
                    if 'amount' in df.columns:
                        cols.append('amount')
                    
                    records = df[cols].where(pd.notnull(df[cols]), None).values.tolist()
                    
                    if not records: continue

                    insert_sql = f"""
                        INSERT INTO klines ({', '.join(cols)}) 
                        VALUES ({', '.join(['%s'] * len(cols))})
                        ON DUPLICATE KEY UPDATE 
                        open=VALUES(open), high=VALUES(high), low=VALUES(low), 
                        close=VALUES(close), volume=VALUES(volume)
                    """
                    
                    cursor.executemany(insert_sql, records)
                    conn.commit()
                    
                    count = len(records)
                    total_count += count
                    print(f"   ✅ [{market}.{code}.{freq}] 导入 {count} 条")
                    
                except Exception as e:
                    print(f"   ❌ 失败 [{csv_file.name}]: {e}")
                    conn.rollback()

    print(f"\n🎉 CSV 导入完成！共写入 {total_count} 条记录。")

def import_sqlite_to_mysql(conn):
    """补充导入 SQLite 中的数据"""
    if not os.path.exists(SQLITE_DB):
        print(f"⚠️ 未找到 SQLite 文件 ({SQLITE_DB})，跳过补充导入。")
        return

    print(f"🔋 正在从 SQLite 补充数据: {SQLITE_DB}")
    try:
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        df = pd.read_sql_query("SELECT * FROM klines", sqlite_conn)
        sqlite_conn.close()
        
        if df.empty:
            print("   SQLite 中没有数据。")
            return

        cursor = conn.cursor()
        df['time'] = pd.to_datetime(df['time'])
        
        cols = ['market', 'code', 'frequency', 'time', 'open', 'high', 'low', 'close', 'volume']
        available_cols = [c for c in cols if c in df.columns]
        if 'amount' in df.columns:
            available_cols.append('amount')
            
        records = df[available_cols].where(pd.notnull(df[available_cols]), None).values.tolist()
        
        insert_sql = f"""
            INSERT INTO klines ({', '.join(available_cols)}) 
            VALUES ({', '.join(['%s'] * len(available_cols))})
            ON DUPLICATE KEY UPDATE 
            open=VALUES(open), high=VALUES(high), low=VALUES(low), 
            close=VALUES(close), volume=VALUES(volume)
        """
        
        cursor.executemany(insert_sql, records)
        conn.commit()
        print(f"   ✅ 从 SQLite 补充导入 {len(records)} 条记录。")
        
    except Exception as e:
        print(f"   ❌ SQLite 导入失败: {e}")

if __name__ == "__main__":
    print("🚀 开始迁移数据到 MySQL (chanlun_db)...")
    
    try:
        # 先确保数据库存在 (如果不存在则尝试创建，需要 root 权限)
        temp_conn = pymysql.connect(
            host=MYSQL_CONFIG['host'], 
            port=MYSQL_CONFIG['port'], 
            user=MYSQL_CONFIG['user'], 
            password=MYSQL_CONFIG['password']
        )
        temp_cursor = temp_conn.cursor()
        temp_cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_CONFIG['database']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        temp_conn.commit()
        temp_conn.close()
        print(f"✅ 数据库 `{MYSQL_CONFIG['database']}` 已确认存在。")

        # 连接目标数据库
        conn = pymysql.connect(**MYSQL_CONFIG)
        print("✅ 成功连接 MySQL。")
        
        create_table(conn)
        import_csv_to_mysql(conn)
        import_sqlite_to_mysql(conn)
        
        conn.close()
        print("\n💡 迁移全部完成！请重启 app.py 测试。")
        
    except Exception as e:
        print(f"\n❌ 发生严重错误: {e}")
        print("💡 提示：请检查 MySQL 服务是否启动，以及 root 密码是否为 '1023'。")
