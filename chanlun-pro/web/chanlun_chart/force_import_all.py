import os
import csv
import mysql.connector
from pathlib import Path

# ================= 配置区域 =================
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',  # ⚠️【重要】请确保这里是你真实的 MySQL 密码
    'database': 'chanlun_db'
}
# 数据源目录
SOURCE_DIR = Path('/home/shengge/.chanlun_pro/klines.KILLED')
# ===========================================

def infer_market_and_code(filepath):
    """根据路径推断 market 和 code"""
    parts = filepath.parts
    # 预期结构: .../klines.KILLED/{market}/{code}_d.csv
    try:
        # 找到 klines.KILLED 的索引
        idx = parts.index('klines.KILLED')
        market_folder = parts[idx + 1] # 例如 'hk', 'a', 'us'
        filename = parts[-1]           # 例如 'KH_00700_d.csv'
        
        # 标准化市场名称 (根据文件夹名)
        market_map = {'a': 'a', 'hk': 'hk', 'us': 'us', 'cn': 'a'}
        market = market_map.get(market_folder.lower(), market_folder.lower())
        
        # 提取代码 (去掉 _d.csv, _m.csv 等后缀，去掉前缀 KH_, US_ 等)
        # 假设文件名格式: {Prefix}_{Code}_{freq}.csv 或 {Code}_{freq}.csv
        name_part = filename.split('.')[0] # KH_00700_d
        segments = name_part.split('_')
        
        # 简单逻辑：如果第一段是字母且长度<=3，可能是前缀，取第二段作为代码
        # 否则直接取第一段
        if len(segments) >= 2 and segments[0].isalpha() and len(segments[0]) <= 3:
            code = segments[1]
        else:
            code = segments[0]
            
        return market, code
    except Exception as e:
        return None, None

def main():
    print(f"🔍 开始扫描: {SOURCE_DIR}")
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("⚠️ 请检查脚本中的 DB_CONFIG 密码是否正确！")
        return

    total_rows = 0
    file_count = 0
    
    # 遍历所有 .csv 文件
    for csv_file in SOURCE_DIR.rglob('*.csv'):
        market, code = infer_market_and_code(csv_file)
        if not market or not code:
            print(f"⚠️ 跳过无法解析的文件: {csv_file.name}")
            continue
            
        # 判断频率 (简单根据文件名包含 d/m/w)
        freq = 'day'
        fname_lower = csv_file.name.lower()
        if '_m.' in fname_lower or 'min' in fname_lower:
            freq = '1m'
        elif '_w.' in fname_lower:
            freq = 'week'
            
        print(f"📥 正在导入: {csv_file.name} -> Market: {market}, Code: {code}, Freq: {freq}")
        
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
            if not rows:
                continue
                
            # 检查表头 (假设第一行包含非数字字符则是表头)
            start_idx = 0
            if rows[0] and any(not cell.replace('.','').replace('-','').isdigit() for cell in rows[0] if cell):
                start_idx = 1
                
            data_to_insert = []
            for row in rows[start_idx:]:
                if len(row) >= 7: # 确保列数足够
                    # 假设 CSV 列顺序: time, open, high, low, close, volume, turnover
                    # 清洗数据
                    t, o, h, l, c, v, *rest = row[:7]
                    # 简单验证时间格式 (略)，直接插入
                    data_to_insert.append((market, code, freq, t.strip(), o.strip(), h.strip(), l.strip(), c.strip(), v.strip()))
            
            if data_to_insert:
                sql = """
                    INSERT INTO klines (market, code, frequency, time, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE close=VALUES(close)
                """
                cursor.executemany(sql, data_to_insert)
                conn.commit()
                count = len(data_to_insert)
                total_rows += count
                print(f"   ✅ 成功插入 {count} 条记录")
                file_count += 1
        except Exception as e:
            print(f"   ❌ 处理文件 {csv_file.name} 时出错: {e}")

    print("\n" + "="*30)
    print(f"🎉 迁移完成！")
    print(f"📂 处理文件数: {file_count}")
    print(f"📊 总插入行数: {total_rows}")
    print("="*30)
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
