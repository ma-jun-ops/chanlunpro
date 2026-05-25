"""
PythonProject1 - 用户管理与股票关注系统

主要功能：
- 用户注册、登录、管理（增删改查）
- 股票关注功能（添加、删除、查看实时行情）
- 仓位设置管理
- 股票涨跌幅计算与展示

项目结构：
- app.py: 应用入口，负责初始化Flask应用、注册蓝图、启动定时任务
- db/: 数据库配置管理
- models/: 数据模型定义
- routes/: 路由处理（按功能模块拆分）
- services/: 业务服务（股票API、名称转换等）
- stock_change/: 涨跌幅计算模块
- tools/: 工具类（缓存等）
- templates/: HTML模板

"""

from flask import Flask
import os
import sys
import webbrowser

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 导入数据库配置
from db.database import get_user_db_uri, create_stock_db, get_db_connection
# 导入数据模型
from models import db
# 导入路由蓝图
from routes import auth_bp, user_bp, follow_bp, position_bp, change_bp, stock_engine, StockFollow
# 导入涨跌幅计算模块
from stock_change.calculator import create_change_table, create_star_marks_table
from stock_change.scheduler import start_scheduler

# 创建Flask应用实例
app = Flask(__name__)
app.config['SECRET_KEY'] = 'chanlun_secure_login_2024'
app.config['SQLALCHEMY_DATABASE_URI'] = get_user_db_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化数据库
db.init_app(app)

# 注册所有路由蓝图
app.register_blueprint(auth_bp)      # 认证相关路由（登录、登出）
app.register_blueprint(user_bp)      # 用户管理路由
app.register_blueprint(follow_bp)    # 股票关注路由
app.register_blueprint(position_bp)  # 仓位设置路由
app.register_blueprint(change_bp)    # 涨跌幅展示路由


# 注册模板过滤器：将时间戳转换为可读日期格式
@app.template_filter('timestamp_to_datetime')
def timestamp_to_datetime(timestamp):
    """将Unix时间戳转换为 YYYY-MM-DD HH:MM:SS 格式"""
    import datetime
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def open_browser():
    """延迟1.5秒后自动打开浏览器"""
    import threading
    threading.Timer(1.5, lambda: webbrowser.open('http://127.0.0.1:5000')).start()


# 应用启动入口
if __name__ == '__main__':
    # 第一步：初始化用户管理数据库
    try:
        with app.app_context():
            db.create_all()
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            if 'user_plain_passwords' in tables:
                print("[OK] 明文密码表 user_plain_passwords 创建成功")
            else:
                print("[ERROR] 明文密码表创建失败，请手动执行SQL创建")
            print("[OK] 数据库表初始化完成")
    except Exception as e:
        print(f"[WARNING] 数据库连接失败：{e}")

    # 第二步：初始化股票数据库
    try:
        create_stock_db()
        StockFollow.__table__.create(stock_engine, checkfirst=True)
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("ALTER TABLE stock_follows ADD COLUMN sector VARCHAR(200) DEFAULT ''")
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()
        create_change_table()
        create_star_marks_table()
    except Exception as e:
        print(f"[WARNING] 股票数据库初始化失败：{e}")

    # 第三步：启动涨跌幅定时任务
    try:
        start_scheduler()
    except Exception as e:
        print(f"[WARNING] 涨跌幅定时任务启动失败：{e}")

    # 打印启动信息
    print("=" * 50)
    print("[INFO] 应用启动成功！")
    print("=" * 50)
    print("[INFO] 登录页面：http://127.0.0.1:5000/login")
    print("[INFO] 用户名：qwer")
    print("=" * 50)

    # 自动打开浏览器（除非命令行参数包含nobrowser）
    if "nobrowser" not in sys.argv:
        webbrowser.open("http://127.0.0.1:5000/login")
    app.run(debug=False, host='0.0.0.0', port=5000)
