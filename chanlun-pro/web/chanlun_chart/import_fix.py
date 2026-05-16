import os, csv, mysql.connector
from pathlib import Path

# ⚠️【重要】确认密码
PWD = "1023" 
SRC = Path("/home/shengge/.chanlun_pro/klines.KILLED")

try:
    conn = mysql.connector.connect(host="localhost", user="root", password=PWD, database="chanlun_db")
    cur = conn.cursor()
    print("✅ 数据库连接成功")
except Exception as e:
    print(f"❌ 数据库连接失败: {e}")
    exit()

total = 0
print(f"🔍 开始扫描目录: {SRC}")

for f in SRC.rglob("*.csv"):
    try:
        parts = f.parts
        idx = parts.index("klines.KILLED")
        mkt = parts[idx+1].lower()
        if mkt == "cn": mkt = "a"
        
        name = f.name.split(".")[0]
        segs = name.split("_")
        code = segs[1] if len(segs)>1 and segs[0].isalpha() else segs[0]
        freq = "1m" if "_m." in f.name else ("week" if "_w." in f.name else "day")
        
        with open(f, "r", errors="ignore") as fp:
            reader = csv.reader(fp)
            rows = list(reader)
        
        if not rows: 
            continue
        
        # --- 关键逻辑：解析表头 ---
        header = [h.lower().strip() for h in rows[0]]
        
        # 寻找各列的索引
        try:
            idx_time = header.index('date') if 'date' in header else header.index('datetime')
            idx_open = header.index('open')
            idx_high = header.index('high')
            idx_low = header.index('low')
            idx_close = header.index('close')
            # 尝试找 volume，如果没有，用 trade 代替，再没有用 amount
            if 'volume' in header:
                idx_vol = header.index('volume')
            elif 'trade' in header:
                idx_vol = header.index('trade') # 用成交笔数暂代
            elif 'amount' in header:
                idx_vol = header.index('amount') # 用成交额暂代
            else:
                idx_vol = -1 # 找不到
                
        except ValueError as e:
            print(f"⚠️ {f.name}: 表头格式未知，跳过。({e})")
            continue

        batch = []
        # 从第 1 行开始遍历数据
        for r in rows[1:]:
            if len(r) > max(idx_time, idx_close):
                # 提取数据并去除空格
                t_val = r[idx_time].strip()
                o_val = r[idx_open].strip()
                h_val = r[idx_high].strip()
                l_val = r[idx_low].strip()
                c_val = r[idx_close].strip()
                v_val = r[idx_vol].strip() if idx_vol != -1 else "0"
                
                # 简单清洗时间格式 (确保符合 MySQL)
                # 原数据是 2004-06-16 15:00:00，通常可以直接用
                if len(t_val) == 16: # 如果是 2004-06-16 15:00
                    t_val += ":00"
                
                batch.append((mkt, code, freq, t_val, o_val, h_val, l_val, c_val, v_val))
        
        if batch:
            sql = """INSERT INTO klines (market, code, frequency, time, open, high, low, close, volume) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) 
                     ON DUPLICATE KEY UPDATE close=VALUES(close), high=VALUES(high), low=VALUES(low), volume=VALUES(volume)"""
            
            cur.executemany(sql, batch)
            conn.commit()
            total += len(batch)
            print(f"📥 {f.name}: +{len(batch)} 条 (时间示例:{batch[0][3]}, 代码:{code})")
            
    except Exception as e:
        print(f"⚠️ 处理文件 {f.name} 时出错: {e}")

print("\n" + "="*30)
print(f"🎉 全部完成! 总共导入行数: {total}")
print("="*30)

cur.close()
conn.close()
